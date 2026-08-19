from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.application.services import MealReviewService
from app.domain.entities import (
    CanonicalFoodCandidate,
    Meal,
    MealItem,
    NutritionPer100g,
    PortionEstimate,
)
from app.domain.enums import PortionResolutionSource
from app.domain.policies import UncertaintyPolicy
from app.repositories import InMemoryMealRepository


class ForbiddenGrounding:
    def __init__(self) -> None:
        self.call_count = 0

    async def ground_selected_candidate(self, *args, **kwargs):
        self.call_count += 1
        raise AssertionError("REMOVE_ITEM must not ground a canonical candidate")


class UnusedDependency:
    pass


def _meal() -> Meal:
    return Meal(uuid4(), uuid4(), datetime.now(timezone.utc))


def _candidate(item: MealItem) -> CanonicalFoodCandidate:
    return CanonicalFoodCandidate(
        meal_item_id=item.id,
        rank=1,
        source="USDA_FDC",
        source_food_id="2709977",
        name="Pepper, sweet, red, cooked",
        data={"data_type": "Survey (FNDDS)"},
    )


def _grounded_item(meal: Meal, *, position: int) -> MealItem:
    item = MealItem(
        meal_id=meal.id,
        position=position,
        observed_name="rice",
        canonical_food_id="rice-1",
        canonical_food_name="Rice, cooked",
        canonical_source="TEST",
        portion_estimate=PortionEstimate(Decimal("90"), Decimal("110")),
        observation_certainty="HIGH",
    )
    item.nutrition_snapshot = NutritionPer100g(100, 2, 20, 1)
    return item


def test_candidate_clarification_offers_search_and_remove_recovery() -> None:
    meal = _meal()
    item = MealItem(meal.id, 0, "red bell pepper", observation_certainty="LOW")
    item.candidates = [_candidate(item)]
    meal.items.append(item)
    service = object.__new__(MealReviewService)

    service._ensure_identity(meal, item)

    clarification = meal.clarifications[-1]
    assert clarification.type == "CANONICAL_SELECTION"
    actions = {
        option["value"].get("action")
        for option in clarification.options
        if "action" in option["value"]
    }
    assert actions == {"MANUAL_SEARCH", "REMOVE_ITEM"}
    assert clarification.options[-1] == {
        "id": "remove-item",
        "label": "This food is not in my meal",
        "value": {"action": "REMOVE_ITEM"},
    }


@pytest.mark.asyncio
async def test_canonical_remove_resolves_without_grounding_and_reassesses_remaining_meal() -> None:
    repository = InMemoryMealRepository()
    meal = _meal()
    removable = MealItem(meal.id, 0, "red bell pepper", observation_certainty="LOW")
    removable.candidates = [_candidate(removable)]
    remaining = _grounded_item(meal, position=1)
    meal.items.extend([removable, remaining])
    await repository.create(meal)

    grounding = ForbiddenGrounding()
    service = MealReviewService(
        repository,
        grounding,
        UnusedDependency(),
        UncertaintyPolicy(),
    )
    await service.assess_meal(meal)
    clarification = next(
        value
        for value in meal.clarifications
        if value.type == "CANONICAL_SELECTION" and value.meal_item_id == removable.id
    )

    await service.answer(
        meal,
        clarification.id,
        option_id="remove-item",
        custom_grams=None,
    )

    assert grounding.call_count == 0
    assert removable.is_removed is True
    assert clarification.resolution_satisfied is True
    assert remaining.confirmed_portion_g == Decimal("100")
    assert remaining.portion_resolution_source == PortionResolutionSource.AUTO_ESTIMATE
    assert remaining.final_nutrition is not None
    assert any(
        correction.meal_item_id == removable.id
        and correction.field_name == "removed_item"
        and correction.corrected_value is True
        for correction in meal.corrections
    )
