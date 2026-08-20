"""Model-sampled nutrition with agreement as the confidence signal.

No external food database is consulted. Because there is no provenance to point
at, the provider samples the model several times for the same food and treats
disagreement between samples as uncertainty. Results are cached per normalized
food name so a food logged twice yields identical nutrition.
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any
from uuid import UUID

import openai
from openai import AsyncOpenAI
from pydantic import ValidationError

from app.ai.providers.bounded_retry import run_with_bounded_retry
from app.domain.entities import CanonicalFood, CanonicalFoodCandidate, NutritionPer100g
from app.observability.logging import log_event

from ..ai_errors import (
    AINutritionConfigurationError,
    AINutritionInvalidResponseError,
    AINutritionRateLimitedError,
    AINutritionTimeoutError,
    AINutritionUnavailableError,
)
from ..consensus import confidence_from_spread, median_nutrition, relative_spread
from ..normalization import normalize_food_query
from ..schemas.ai_nutrition import AINutritionOutput

PROMPT_VERSION = "ai_nutrition_v1"
PROMPT_PATH = Path(__file__).parents[2] / "ai" / "prompts" / f"{PROMPT_VERSION}.md"


class AINutritionProvider:
    """Values are model estimates, not database records."""

    source = "AI_ESTIMATE"

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "gpt-5.6-terra",
        sample_count: int = 3,
        reasoning_effort: str = "low",
        timeout_seconds: float = 25,
        max_attempts: int = 3,
        client: Any | None = None,
        prompt: str | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        jitter: Callable[[float, float], float] = random.uniform,
    ) -> None:
        if not api_key:
            raise AINutritionConfigurationError(
                "OPENAI_API_KEY is required for AI nutrition."
            )
        self.model = model
        self.prompt_version = PROMPT_VERSION
        self._sample_count = min(max(sample_count, 1), 5)
        self._reasoning_effort = reasoning_effort
        self._max_attempts = min(max(max_attempts, 1), 5)
        self._sleep = sleep
        self._jitter = jitter
        self._prompt = prompt if prompt is not None else PROMPT_PATH.read_text(encoding="utf-8")
        self._owns_client = client is None
        self._client = client or AsyncOpenAI(
            api_key=api_key,
            timeout=timeout_seconds,
            max_retries=0,
        )
        self._cache: dict[str, tuple[NutritionPer100g, dict[str, Any]]] = {}

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.close()

    def _cache_key(self, normalized: str) -> str:
        return f"{normalized}|{self.model}|{self.prompt_version}"

    @staticmethod
    def _map_error(error: Exception, retry_count: int) -> Exception:
        details = {"retry_count": retry_count}
        if isinstance(error, (openai.APITimeoutError, TimeoutError, asyncio.TimeoutError)):
            return AINutritionTimeoutError("AI nutrition request timed out.", details=details)
        if isinstance(error, openai.RateLimitError) or getattr(error, "status_code", None) == 429:
            return AINutritionRateLimitedError(
                "AI nutrition provider is rate limited.", details=details
            )
        if isinstance(error, (openai.APIConnectionError, openai.InternalServerError)) or (
            isinstance(getattr(error, "status_code", None), int)
            and getattr(error, "status_code") >= 500
        ):
            return AINutritionUnavailableError(
                "AI nutrition provider is unavailable.", details=details
            )
        return AINutritionInvalidResponseError(
            "AI nutrition provider request failed.", details=details
        )

    async def _sample_once(self, food_name: str) -> NutritionPer100g:
        async def call_api():
            return await self._client.responses.parse(
                model=self.model,
                instructions=self._prompt,
                input=[
                    {
                        "role": "user",
                        "content": [{"type": "input_text", "text": food_name}],
                    }
                ],
                reasoning={"effort": self._reasoning_effort},
                text_format=AINutritionOutput,
                store=False,
            )

        response, _ = await run_with_bounded_retry(
            call_api,
            map_error=self._map_error,
            max_attempts=self._max_attempts,
            sleep=self._sleep,
            jitter=self._jitter,
        )
        parsed = getattr(response, "output_parsed", None)
        if parsed is None:
            raise AINutritionInvalidResponseError(
                "AI nutrition provider returned no parsed estimate."
            )
        if not isinstance(parsed, AINutritionOutput):
            try:
                parsed = AINutritionOutput.model_validate(parsed)
            except ValidationError:
                raise AINutritionInvalidResponseError(
                    "AI nutrition provider returned an invalid estimate."
                ) from None
        return NutritionPer100g(
            parsed.calories_kcal, parsed.protein_g, parsed.carbs_g, parsed.fat_g
        )

    async def _resolve(self, normalized: str) -> tuple[NutritionPer100g, dict[str, Any]]:
        key = self._cache_key(normalized)
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        samples = [await self._sample_once(normalized) for _ in range(self._sample_count)]
        nutrition = median_nutrition(samples)
        spread = relative_spread(samples)
        confidence = confidence_from_spread(spread)
        data: dict[str, Any] = {
            "confidence": str(confidence),
            "spread": str(spread),
            "sample_count": self._sample_count,
            "model": self.model,
            "prompt_version": self.prompt_version,
            "estimated": True,
        }
        log_event(
            "ai_nutrition_resolved",
            food=normalized,
            sample_count=self._sample_count,
            spread=str(spread),
            confidence=str(confidence),
        )
        self._cache[key] = (nutrition, data)
        return nutrition, data

    async def search_foods(
        self, query: str, *, meal_item_id: UUID, limit: int = 5
    ) -> list[CanonicalFoodCandidate]:
        normalized = normalize_food_query(query)
        if not normalized:
            return []
        nutrition, data = await self._resolve(normalized)
        return [
            CanonicalFoodCandidate(
                meal_item_id=meal_item_id,
                rank=1,
                source=self.source,
                source_food_id=normalized,
                name=normalized,
                data=dict(data),
                nutrition_per_100g=nutrition,
            )
        ]

    async def get_food(self, source_food_id: str) -> CanonicalFood | None:
        normalized = normalize_food_query(source_food_id)
        cached = self._cache.get(self._cache_key(normalized))
        if cached is None:
            return None
        nutrition, data = cached
        return CanonicalFood(
            source=self.source,
            # The source_food_id is the normalized food name itself: search_foods
            # mints it from the same normalization, so a food resolved via search
            # and then looked up via get_food must agree on this identifier.
            source_food_id=normalized,
            name=normalized,
            nutrition_per_100g=nutrition,
            data=dict(data),
        )
