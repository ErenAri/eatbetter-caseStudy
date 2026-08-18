from __future__ import annotations

import re
from time import perf_counter
from uuid import UUID

from app.ai.errors import VisionImageUnavailableError, VisionUnsupportedImageError
from app.application.errors import (
    InvalidMealStateError,
    MealNotFoundError,
    RetryableProviderError,
    ValidationError,
)
from app.domain.entities import AIRun, Meal, MealImage, MealItem, PortionEstimate
from app.domain.enums import MealStatus
from app.domain.ports import MealRepository, StorageProvider, VisionProvider
from app.observability.logging import log_event


class MealRecognitionService:
    def __init__(
        self,
        repository: MealRepository,
        storage: StorageProvider,
        vision_provider: VisionProvider,
    ) -> None:
        self.repository = repository
        self.storage = storage
        self.vision_provider = vision_provider

    async def analyze(
        self, *, meal_id: UUID, user_id: UUID, request_id: UUID | None
    ) -> Meal:
        meal = await self.repository.get_owned(meal_id, user_id)
        if meal is None:
            raise MealNotFoundError("Meal was not found.")
        if meal.status in {MealStatus.ANALYZING, MealStatus.NEEDS_REVIEW}:
            return meal
        if meal.status == MealStatus.CONFIRMED:
            raise InvalidMealStateError("Confirmed meals cannot be re-analyzed.")
        if meal.status == MealStatus.FAILED_PERMANENT:
            raise InvalidMealStateError("This meal has a permanent analysis failure.")
        if meal.image_path is None:
            raise ValidationError("Attach a meal image before starting analysis.")

        meal.transition_to(MealStatus.ANALYZING)
        meal.failure_code = None
        meal.failure_message = None
        run = AIRun(
            meal_id=meal.id,
            stage="MEAL_RECOGNITION",
            provider=self.vision_provider.provider_name,
            model=self.vision_provider.model,
            prompt_version=self.vision_provider.prompt_version,
            request_id=request_id,
            image_detail=self.vision_provider.image_detail,
            reasoning_effort=self.vision_provider.reasoning_effort,
        )
        meal.ai_runs.append(run)
        await self.repository.save(meal)
        started = perf_counter()
        log_event(
            "meal_recognition_started",
            meal_id=meal.id,
            request_id=request_id,
            provider=run.provider,
            model=run.model,
            prompt_version=run.prompt_version,
            image_detail=run.image_detail,
            reasoning_effort=run.reasoning_effort,
            user_context_present=meal.user_context is not None,
        )

        try:
            stored = await self.storage.get_private(meal.image_path)
            if stored is None:
                raise VisionImageUnavailableError("The private meal image is unavailable.")
            content, mime_type = stored
            try:
                image = MealImage(content=content, mime_type=mime_type)
            except ValueError:
                raise VisionUnsupportedImageError(
                    "The stored image is not supported for recognition."
                ) from None
            result = await self.vision_provider.analyze_meal(
                image=image,
                user_context=meal.user_context,
                request_id=request_id,
            )
            meal.items = self._items_from_observation(meal.id, result.observation.items)
            run.provider = result.provider
            run.model = result.model
            run.prompt_version = result.prompt_version
            run.image_detail = result.image_detail
            run.reasoning_effort = result.reasoning_effort
            latency_ms = round((perf_counter() - started) * 1000)
            run.succeed(
                latency_ms=latency_ms,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                structured_output=result.observation.model_dump(mode="json"),
                retry_count=result.retry_count,
            )
            meal.transition_to(MealStatus.NEEDS_REVIEW)
            await self.repository.save(meal)
            log_event(
                "meal_recognition_completed",
                meal_id=meal.id,
                request_id=request_id,
                provider=run.provider,
                model=run.model,
                prompt_version=run.prompt_version,
                image_detail=run.image_detail,
                reasoning_effort=run.reasoning_effort,
                latency_ms=latency_ms,
                observed_item_count=len(meal.items),
                possible_hidden_ingredient_count=len(
                    result.observation.possible_hidden_ingredients
                ),
                image_usable=result.observation.image_quality.usable,
                retry_count=result.retry_count,
            )
            return meal
        except Exception as error:
            latency_ms = round((perf_counter() - started) * 1000)
            code = getattr(error, "code", "VISION_INVALID_RESPONSE")
            details = getattr(error, "details", None)
            retry_count = details.get("retry_count", 0) if isinstance(details, dict) else 0
            run.fail(latency_ms=latency_ms, error_code=code, retry_count=retry_count)
            meal.failure_code = code
            meal.failure_message = "Meal recognition could not be completed."
            meal.transition_to(
                MealStatus.FAILED_RETRYABLE
                if isinstance(error, RetryableProviderError)
                else MealStatus.FAILED_PERMANENT
            )
            await self.repository.save(meal)
            log_event(
                "meal_recognition_failed",
                meal_id=meal.id,
                request_id=request_id,
                provider=run.provider,
                model=run.model,
                prompt_version=run.prompt_version,
                image_detail=run.image_detail,
                reasoning_effort=run.reasoning_effort,
                latency_ms=latency_ms,
                error_code=code,
                retry_count=retry_count,
            )
            raise

    @staticmethod
    def _items_from_observation(meal_id: UUID, observations: list) -> list[MealItem]:
        items: list[MealItem] = []
        seen: set[str] = set()
        for observation in observations:
            normalized = re.sub(r"\s+", " ", observation.observed_name.strip().lower())
            if normalized in seen:
                continue
            seen.add(normalized)
            portion = observation.portion_estimate
            items.append(
                MealItem(
                    meal_id=meal_id,
                    position=len(items),
                    observed_name=observation.observed_name,
                    normalized_name=normalized,
                    preparation_method=observation.preparation_method,
                    observation_certainty=str(observation.observation_certainty),
                    portion_estimate=PortionEstimate(
                        min_g=portion.min_g if portion else None,
                        max_g=portion.max_g if portion else None,
                    ),
                )
            )
        return items
