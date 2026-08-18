from datetime import datetime, timezone
from uuid import UUID

import pytest

from app.ai.errors import VisionTimeoutError
from app.ai.schemas import MealObservation
from app.application.services import MealRecognitionService
from app.domain.entities import Meal, VisionAnalysisResult
from app.domain.enums import MealStatus
from app.infrastructure.storage import InMemoryPrivateStorage
from app.repositories import InMemoryMealRepository


class FakeVisionProvider:
    provider_name = "FAKE_TEST_DATA"
    model = "fake-vision-model"
    prompt_version = "meal_recognition_v1"
    image_detail = "high"
    reasoning_effort = "low"

    def __init__(self, observation: MealObservation | None = None, error=None) -> None:
        self.observation = observation or MealObservation.model_validate(
            {
                "image_quality": {"usable": True, "issues": []},
                "items": [
                    {
                        "observed_name": "Rice",
                        "preparation_method": "cooked",
                        "portion_estimate": None,
                        "observation_certainty": "MEDIUM",
                        "alternatives": [],
                        "uncertainties": ["portion size"],
                        "visible_evidence": ["white cooked grains"],
                    },
                    {
                        "observed_name": "rice",
                        "preparation_method": "cooked",
                        "portion_estimate": {"min_g": 100, "max_g": 180},
                        "observation_certainty": "LOW",
                        "alternatives": [],
                        "uncertainties": [],
                        "visible_evidence": ["same visible portion"],
                    },
                ],
                "possible_hidden_ingredients": [],
                "meal_level_uncertainties": [],
            }
        )
        self.error = error
        self.call_count = 0
        self.request_ids = []

    async def analyze_meal(self, *, image, user_context, request_id=None):
        self.call_count += 1
        self.request_ids.append(request_id)
        if self.error:
            raise self.error
        return VisionAnalysisResult(
            observation=self.observation,
            provider=self.provider_name,
            model=self.model,
            prompt_version=self.prompt_version,
            image_detail=self.image_detail,
            reasoning_effort=self.reasoning_effort,
            input_tokens=20,
            output_tokens=10,
        )


async def setup(provider):
    repository = InMemoryMealRepository()
    storage = InMemoryPrivateStorage()
    user_id = UUID(int=1)
    meal = Meal(
        user_id=user_id,
        meal_request_id=UUID(int=2),
        logged_at=datetime.now(timezone.utc),
        user_context="Cooked at home",
    )
    meal.image_path = await storage.put_private(b"\xff\xd8\xffimage", "image/jpeg")
    await repository.create(meal)
    return MealRecognitionService(repository, storage, provider), repository, meal, user_id


@pytest.mark.asyncio
async def test_analysis_creates_only_observed_fields_and_records_ai_run() -> None:
    provider = FakeVisionProvider()
    service, _repository, meal, user_id = await setup(provider)
    request_id = UUID(int=3)

    result = await service.analyze(meal_id=meal.id, user_id=user_id, request_id=request_id)

    assert result.status == MealStatus.NEEDS_REVIEW
    assert len(result.items) == 1  # lightweight exact duplicate protection
    item = result.items[0]
    assert item.observed_name == "Rice"
    assert item.portion_estimate.min_g is None
    assert item.canonical_food_id is None
    assert item.candidates == []
    assert item.nutrition_snapshot is None
    assert item.final_nutrition is None
    assert provider.call_count == 1
    assert provider.request_ids == [request_id]
    run = result.ai_runs[0]
    assert run.stage == "MEAL_RECOGNITION"
    assert run.status == "SUCCEEDED"
    assert run.provider == "FAKE_TEST_DATA"
    assert run.model == "fake-vision-model"
    assert run.prompt_version == "meal_recognition_v1"
    assert run.request_id == request_id
    assert run.input_tokens == 20
    assert run.output_tokens == 10
    assert run.estimated_cost_usd is None
    assert run.structured_output["items"][1]["observed_name"] == "rice"


@pytest.mark.asyncio
async def test_duplicate_analysis_does_not_call_provider_or_replace_predictions() -> None:
    provider = FakeVisionProvider()
    service, _repository, meal, user_id = await setup(provider)

    first = await service.analyze(meal_id=meal.id, user_id=user_id, request_id=UUID(int=4))
    second = await service.analyze(meal_id=meal.id, user_id=user_id, request_id=UUID(int=5))

    assert second is first
    assert provider.call_count == 1
    assert len(second.ai_runs) == 1


@pytest.mark.asyncio
async def test_retryable_failure_records_run_and_allows_new_attempt() -> None:
    provider = FakeVisionProvider(
        error=VisionTimeoutError("Vision request timed out.", details={"retry_count": 2})
    )
    service, repository, meal, user_id = await setup(provider)

    with pytest.raises(VisionTimeoutError):
        await service.analyze(meal_id=meal.id, user_id=user_id, request_id=UUID(int=6))

    failed = await repository.get_owned(meal.id, user_id)
    assert failed.status == MealStatus.FAILED_RETRYABLE
    assert failed.failure_code == "VISION_TIMEOUT"
    assert failed.ai_runs[0].status == "FAILED"
    assert failed.ai_runs[0].retry_count == 2

    provider.error = None
    completed = await service.analyze(
        meal_id=meal.id, user_id=user_id, request_id=UUID(int=7)
    )
    assert completed.status == MealStatus.NEEDS_REVIEW
    assert len(completed.ai_runs) == 2
