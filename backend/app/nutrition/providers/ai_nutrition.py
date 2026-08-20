"""Model-sampled nutrition with agreement as the confidence signal.

No external food database is consulted. Because there is no provenance to point
at, the provider samples the model several times for the same food and treats
disagreement between samples as uncertainty. Results are cached per normalized
food name, so a food logged twice within the same process yields identical
nutrition. The cache has no in-flight coordination: two concurrent first-lookups
of the same food may each sample independently and diverge before either result
is cached.
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable
from decimal import Decimal
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

PROMPT_VERSION = "ai_nutrition_v2"
PROMPT_PATH = Path(__file__).parents[2] / "ai" / "prompts" / f"{PROMPT_VERSION}.md"

# Spread measures response *stability*, not *knowledge*: a fabricated food can
# get identical (wrong) answers every time. Self-reported familiarity is the
# only knowledge signal available, so it dampens confidence multiplicatively.
_FAMILIARITY_CONFIDENCE_MULTIPLIER: dict[str, Decimal] = {
    "high": Decimal("1.0"),
    "medium": Decimal("0.6"),
    "low": Decimal("0.3"),
}
_FAMILIARITY_ORDER: dict[str, int] = {"low": 0, "medium": 1, "high": 2}


def _lowest_familiarity(values: list[str]) -> str:
    return min(values, key=lambda value: _FAMILIARITY_ORDER[value])


class AINutritionProvider:
    """Values are model estimates, not database records."""

    source = "AI_ESTIMATE"
    # This provider reasons over free text rather than doing lexical search
    # against an external index, so lexical-search query rewriting (USDA
    # search-index aliases, preparation-term reordering) must not be applied
    # to what it receives as input or displays as a name.
    uses_lexical_search = False

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
        self._cache: dict[str, tuple[NutritionPer100g | None, dict[str, Any], str]] = {}

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

    async def _sample_once(self, food_name: str) -> AINutritionOutput:
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
        return parsed

    async def _resolve(
        self, normalized: str, display_name: str
    ) -> tuple[NutritionPer100g | None, dict[str, Any], str]:
        key = self._cache_key(normalized)
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        samples = [await self._sample_once(normalized) for _ in range(self._sample_count)]
        recognized_samples = [sample for sample in samples if sample.recognized]
        total = len(samples)
        # Strictly more than half must agree the food is real, otherwise a
        # single confident hallucination could tip an otherwise-unknown food
        # into "recognized".
        is_recognized = len(recognized_samples) * 2 > total

        if not is_recognized:
            data: dict[str, Any] = {
                "recognized": False,
                "sample_count": self._sample_count,
                "recognized_count": len(recognized_samples),
                "model": self.model,
                "prompt_version": self.prompt_version,
                "estimated": True,
                "provenance_note": "AI ESTIMATE — NOT A DATABASE RECORD",
            }
            log_event(
                "ai_nutrition_unrecognized",
                food=normalized,
                sample_count=self._sample_count,
                recognized_count=len(recognized_samples),
            )
            self._cache[key] = (None, data, display_name)
            return None, data, display_name

        usable = [
            sample
            for sample in recognized_samples
            if sample.calories_kcal is not None
            and sample.protein_g is not None
            and sample.carbs_g is not None
            and sample.fat_g is not None
        ]
        if not usable:
            raise AINutritionInvalidResponseError(
                "AI nutrition provider marked the food recognized but returned"
                " no usable nutrient values."
            )
        nutrition_samples = [
            NutritionPer100g(
                sample.calories_kcal, sample.protein_g, sample.carbs_g, sample.fat_g
            )
            for sample in usable
        ]
        nutrition = median_nutrition(nutrition_samples)
        spread = relative_spread(nutrition_samples)
        familiarity = _lowest_familiarity([sample.familiarity for sample in usable])
        confidence = confidence_from_spread(spread) * _FAMILIARITY_CONFIDENCE_MULTIPLIER[familiarity]
        confidence = min(Decimal("1"), max(Decimal("0"), confidence))
        data = {
            "confidence": str(confidence),
            "spread": str(spread),
            "sample_count": self._sample_count,
            "model": self.model,
            "prompt_version": self.prompt_version,
            "estimated": True,
            "provenance_note": "AI ESTIMATE — NOT A DATABASE RECORD",
            "recognized": True,
            "familiarity": familiarity.upper(),
        }
        log_event(
            "ai_nutrition_resolved",
            food=normalized,
            sample_count=self._sample_count,
            spread=str(spread),
            confidence=str(confidence),
            familiarity=familiarity,
        )
        self._cache[key] = (nutrition, data, display_name)
        return nutrition, data, display_name

    async def search_foods(
        self, query: str, *, meal_item_id: UUID, limit: int = 5
    ) -> list[CanonicalFoodCandidate]:
        normalized = normalize_food_query(query)
        if not normalized:
            return []
        nutrition, data, display_name = await self._resolve(normalized, query.strip())
        if nutrition is None:
            return []
        return [
            CanonicalFoodCandidate(
                meal_item_id=meal_item_id,
                rank=1,
                source=self.source,
                source_food_id=normalized,
                # The candidate name is user-facing (it becomes
                # canonical_food_name), so it stays in the caller's own words
                # rather than the lowercased/reordered identifier below.
                name=display_name,
                data=dict(data),
                nutrition_per_100g=nutrition,
            )
        ]

    async def get_food(self, source_food_id: str) -> CanonicalFood | None:
        normalized = normalize_food_query(source_food_id)
        cached = self._cache.get(self._cache_key(normalized))
        if cached is None:
            return None
        nutrition, data, display_name = cached
        if nutrition is None:
            return None
        return CanonicalFood(
            source=self.source,
            # The source_food_id is the normalized food name itself: search_foods
            # mints it from the same normalization, so a food resolved via search
            # and then looked up via get_food must agree on this identifier.
            source_food_id=normalized,
            # The readable name is cached alongside the nutrition/data at
            # search time, so get_food (an identifier-keyed cache read here,
            # not an independent lookup) returns the exact same display name.
            name=display_name,
            nutrition_per_100g=nutrition,
            data=dict(data),
        )


class UnconfiguredAINutritionProvider:
    """Boot-safe local adapter that fails explicitly instead of impersonating USDA."""

    async def search_foods(self, query: str, *, meal_item_id: UUID, limit: int = 5):
        raise AINutritionConfigurationError(
            "AI nutrition is selected but OPENAI_API_KEY is not configured."
        )

    async def get_food(self, source_food_id: str):
        raise AINutritionConfigurationError(
            "AI nutrition is selected but OPENAI_API_KEY is not configured."
        )
