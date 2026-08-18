from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

import pytest

from app.ai.canonicalization_errors import CanonicalizationTimeoutError
from app.ai.schemas import CanonicalizationOutput, MealObservation
from app.application.services import (
    FoodGroundingService,
    MealCanonicalizationService,
    MealContractService,
    MealRecognitionService,
)
from app.domain.entities import (
    CanonicalFood,
    CanonicalFoodCandidate,
    Meal,
    MealItem,
    NutritionPer100g,
    VisionAnalysisResult,
)
from app.domain.enums import MealStatus
from app.infrastructure.storage import InMemoryPrivateStorage
from app.nutrition.normalization import build_grounding_query
from app.repositories import InMemoryMealRepository


class FakeNutritionProvider:
    source = "FAKE_USDA"

    def __init__(self, *, empty: bool = False) -> None:
        self.empty = empty
        self.queries = []
        self.detail_calls = []

    async def search_foods(self, query, *, meal_item_id, limit=5):
        self.queries.append(query)
        if self.empty:
            return []
        return [
            CanonicalFoodCandidate(
                meal_item_id=meal_item_id,
                rank=1,
                source=self.source,
                source_food_id="food-1",
                name="Rice, white, cooked",
                data={
                    "data_type": "Foundation",
                    "brand_owner": None,
                    "household_serving_full_text": "1 cup",
                    "rogue": "must not pass",
                    "calories": 999,
                },
                nutrition_per_100g=NutritionPer100g(1, 1, 1, 1),
            ),
            CanonicalFoodCandidate(
                meal_item_id=meal_item_id,
                rank=2,
                source=self.source,
                source_food_id="food-2",
                name="Rice noodles, cooked",
                data={"data_type": "Survey (FNDDS)"},
            ),
        ][:limit]

    async def get_food(self, source_food_id):
        self.detail_calls.append(source_food_id)
        nutrition = (
            NutritionPer100g(130, 2.7, 28.2, 0.3)
            if source_food_id == "food-1"
            else NutritionPer100g(109, 0.9, 24.9, 0.2)
        )
        return CanonicalFood(
            source=self.source,
            source_food_id=source_food_id,
            name="Rice detail" if source_food_id == "food-1" else "Rice noodles detail",
            nutrition_per_100g=nutrition,
        )


class FakeSelector:
    provider_name = "FAKE_SELECTOR"
    model = "fake-selector-model"
    prompt_version = "canonicalization_v1"
    reasoning_effort = "low"

    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.call_count = 0
        self.requests = []

    async def select_candidate(self, *, request, request_id=None):
        from app.domain.entities import CanonicalizationAnalysisResult

        self.call_count += 1
        self.requests.append(request)
        outcome = self.outcomes[min(self.call_count - 1, len(self.outcomes) - 1)]
        if isinstance(outcome, Exception):
            raise outcome
        return CanonicalizationAnalysisResult(
            output=outcome,
            provider=self.provider_name,
            model=self.model,
            prompt_version=self.prompt_version,
            reasoning_effort=self.reasoning_effort,
            input_tokens=10,
            output_tokens=4,
        )


def select(rank=1):
    return CanonicalizationOutput(
        decision="SELECT",
        selected_candidate_rank=rank,
        match_quality="STRONG",
        reason_codes=["FOOD_IDENTITY_MATCH", "PREPARATION_MATCH"],
    )


def abstain():
    return CanonicalizationOutput(
        decision="ABSTAIN",
        selected_candidate_rank=None,
        match_quality="AMBIGUOUS",
        reason_codes=["AMBIGUOUS_BETWEEN_CANDIDATES"],
    )


async def setup_item(selector, *, empty=False):
    repository = InMemoryMealRepository()
    nutrition = FakeNutritionProvider(empty=empty)
    grounding = FoodGroundingService(nutrition)
    service = MealCanonicalizationService(repository, grounding, selector)
    meal = Meal(UUID(int=1), UUID(int=2), datetime.now(timezone.utc))
    meal.transition_to(MealStatus.ANALYZING)
    meal.transition_to(MealStatus.NEEDS_REVIEW)
    item = MealItem(
        meal_id=meal.id,
        position=0,
        observed_name="white rice",
        preparation_method="cooked",
    )
    meal.items.append(item)
    await repository.create(meal)
    return service, repository, nutrition, meal, item


def test_preparation_aware_query_is_deterministic_without_duplicates() -> None:
    assert build_grounding_query("chicken breast", "grilled") == "chicken breast grilled"
    assert build_grounding_query("grilled chicken breast", "grilled") == "chicken breast grilled"
    assert build_grounding_query("white rice", "cooked with garlic") == "white rice cooked"
    assert build_grounding_query("chicken breast", "with skin") == "chicken breast with skin"


@pytest.mark.asyncio
async def test_select_retrieves_candidates_and_detail_grounds_snapshot() -> None:
    selector = FakeSelector([select()])
    service, _repository, nutrition, meal, item = await setup_item(selector)
    original = (item.observed_name, item.preparation_method, item.portion_estimate)

    await service.canonicalize_meal(meal, request_id=UUID(int=3))
    await service.canonicalize_meal(meal, request_id=UUID(int=4))

    assert nutrition.queries == ["white rice cooked"]
    assert nutrition.detail_calls == ["food-1"]
    assert selector.call_count == 1
    assert len(item.candidates) == 2
    assert item.canonical_food_id == "food-1"
    assert item.nutrition_snapshot == NutritionPer100g(130, 2.7, 28.2, 0.3)
    assert item.canonical_confidence is None
    assert item.confirmed_portion_g is None
    assert item.final_nutrition is None
    assert (item.observed_name, item.preparation_method, item.portion_estimate) == original
    assert set(selector.requests[0].candidates[0].model_dump()) == {
        "rank",
        "name",
        "data_type",
        "brand_owner",
        "household_serving_full_text",
    }
    run = meal.ai_runs[0]
    assert run.stage == "CANONICALIZATION"
    assert run.status == "SUCCEEDED"
    assert run.structured_output["meal_item_id"] == str(item.id)
    assert run.structured_output["selected_candidate_rank"] == 1


@pytest.mark.asyncio
async def test_abstain_preserves_candidates_and_is_idempotent() -> None:
    selector = FakeSelector([abstain()])
    service, _repository, nutrition, meal, item = await setup_item(selector)

    await service.canonicalize_meal(meal, request_id=None)
    await service.canonicalize_meal(meal, request_id=None)

    assert selector.call_count == 1
    assert len(item.candidates) == 2
    assert item.canonical_food_id is None
    assert item.nutrition_snapshot is None
    assert nutrition.detail_calls == []
    assert meal.ai_runs[0].structured_output["decision"] == "ABSTAIN"


@pytest.mark.asyncio
async def test_zero_candidates_skips_selector_and_records_deterministic_abstain() -> None:
    selector = FakeSelector([select()])
    service, _repository, _nutrition, meal, item = await setup_item(selector, empty=True)

    await service.canonicalize_meal(meal, request_id=None)
    await service.canonicalize_meal(meal, request_id=None)

    assert selector.call_count == 0
    assert item.candidates == []
    assert item.canonical_food_id is None
    assert meal.ai_runs[0].provider == "DETERMINISTIC"
    assert meal.ai_runs[0].structured_output["reason_codes"] == ["NO_SUITABLE_CANDIDATE"]


@pytest.mark.asyncio
async def test_application_rejects_invalid_rank_from_any_provider_implementation() -> None:
    selector = FakeSelector([select(3)])
    service, _repository, _nutrition, meal, item = await setup_item(selector)

    await service.canonicalize_meal(meal, request_id=None)

    assert item.canonical_food_id is None
    assert item.nutrition_snapshot is None
    assert meal.ai_runs[0].status == "FAILED"
    assert meal.ai_runs[0].error_code == "CANONICALIZATION_INVALID_SELECTION"


class FakeVision:
    provider_name = "FAKE_VISION"
    model = "fake-vision"
    prompt_version = "meal_recognition_v1"
    image_detail = "high"
    reasoning_effort = "low"

    def __init__(self):
        self.call_count = 0

    async def analyze_meal(self, **_kwargs):
        self.call_count += 1
        observation = MealObservation.model_validate(
            {
                "image_quality": {"usable": True, "issues": []},
                "items": [
                    {
                        "observed_name": "white rice",
                        "preparation_method": "cooked",
                        "portion_estimate": {"min_g": 120, "max_g": 200},
                        "observation_certainty": "HIGH",
                        "alternatives": [],
                        "uncertainties": ["portion"],
                        "visible_evidence": ["white cooked grains"],
                    }
                ],
                "possible_hidden_ingredients": [],
                "meal_level_uncertainties": [],
            }
        )
        return VisionAnalysisResult(
            observation=observation,
            provider=self.provider_name,
            model=self.model,
            prompt_version=self.prompt_version,
            image_detail=self.image_detail,
            reasoning_effort=self.reasoning_effort,
        )


@pytest.mark.asyncio
async def test_partial_selector_failure_preserves_recognition_and_retry_skips_vision() -> None:
    repository = InMemoryMealRepository()
    storage = InMemoryPrivateStorage()
    nutrition = FakeNutritionProvider()
    grounding = FoodGroundingService(nutrition)
    vision = FakeVision()
    selector = FakeSelector(
        [CanonicalizationTimeoutError("timeout", details={"retry_count": 2}), select()]
    )
    recognition = MealRecognitionService(repository, storage, vision)
    canonicalization = MealCanonicalizationService(repository, grounding, selector)
    contract = MealContractService(
        repository,
        storage,
        grounding,
        recognition,
        canonicalization,
        max_upload_bytes=1024,
        allowed_mime_types=("image/jpeg",),
    )
    meal = Meal(UUID(int=11), UUID(int=12), datetime.now(timezone.utc))
    meal.image_path = await storage.put_private(b"\xff\xd8\xffimage", "image/jpeg")
    await repository.create(meal)

    first = await contract.start_analysis(meal.id, meal.user_id, UUID(int=13))
    recognition_output = first.ai_runs[0].structured_output.copy()
    assert first.status == MealStatus.NEEDS_REVIEW
    assert len(first.items) == 1
    assert len(first.items[0].candidates) == 2
    assert first.items[0].canonical_food_id is None
    assert first.ai_runs[0].status == "SUCCEEDED"
    assert first.ai_runs[1].status == "FAILED"

    second = await contract.start_analysis(meal.id, meal.user_id, UUID(int=14))
    assert vision.call_count == 1
    assert selector.call_count == 2
    assert second.items[0].canonical_food_id == "food-1"
    assert len(second.ai_runs) == 3
    assert second.ai_runs[0].structured_output == recognition_output


@pytest.mark.asyncio
async def test_user_added_item_is_canonicalized_and_manual_override_wins() -> None:
    selector = FakeSelector([select()])
    service, repository, nutrition, meal, item = await setup_item(selector)
    grounding = service.grounding
    await service.canonicalize_meal(meal, request_id=None)

    class NoopRecognition:
        pass

    contract = MealContractService(
        repository,
        InMemoryPrivateStorage(),
        grounding,
        NoopRecognition(),
        service,
        max_upload_bytes=1024,
        allowed_mime_types=("image/jpeg",),
    )
    corrected = await contract.update_item(
        meal_id=meal.id,
        item_id=item.id,
        user_id=meal.user_id,
        changes={"candidate_rank": 2},
    )
    await service.canonicalize_meal(corrected, request_id=None)

    assert item.canonical_candidate_rank == 2
    assert item.canonical_food_id == "food-2"
    assert selector.call_count == 1
    assert corrected.corrections[-1].field_name == "canonical_food"
    assert corrected.corrections[-1].predicted_value["candidate_rank"] == 1
    assert corrected.corrections[-1].corrected_value["candidate_rank"] == 2

    added = await contract.add_missing_item(
        meal_id=meal.id,
        user_id=meal.user_id,
        query="white rice",
        portion_g=Decimal("100"),
        request_id=UUID(int=15),
    )
    assert added.items[-1].canonical_food_id == "food-1"
