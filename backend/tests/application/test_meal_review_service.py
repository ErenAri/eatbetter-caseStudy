from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.application.services import MealReviewService
from app.application.services import FoodGroundingService
from app.domain.entities import AIRun, Meal, MealItem, NutritionPer100g, PortionEstimate
from app.domain.enums import PortionResolutionSource
from app.domain.policies import UncertaintyPolicy
from app.repositories import InMemoryMealRepository
from app.nutrition.providers import DemoNutritionProvider


class UnusedDependency:
    pass


class ForbiddenCanonicalization:
    call_count = 0

    async def canonicalize_item(self, *args, **kwargs):
        self.call_count += 1
        raise AssertionError("P5 must not rerun for an explicit human candidate choice")


def meal_with(*items: MealItem) -> Meal:
    meal = Meal(uuid4(), uuid4(), datetime.now(timezone.utc))
    for item in items:
        item.meal_id = meal.id
        meal.items.append(item)
    return meal


def grounded_item(minimum: str, maximum: str, *, certainty: str = "HIGH") -> MealItem:
    item = MealItem(
        meal_id=uuid4(),
        position=0,
        observed_name="rice",
        canonical_food_id="rice-1",
        canonical_food_name="Rice, cooked",
        canonical_source="TEST",
        portion_estimate=PortionEstimate(Decimal(minimum), Decimal(maximum)),
        observation_certainty=certainty,
    )
    item.nutrition_snapshot = NutritionPer100g(100, 2, 20, 1)
    return item


@pytest.mark.asyncio
async def test_safe_range_auto_resolves_to_midpoint_without_ai():
    repository = InMemoryMealRepository()
    item = grounded_item("90", "110")
    meal = meal_with(item)
    await repository.create(meal)
    service = MealReviewService(repository, UnusedDependency(), UnusedDependency(), UncertaintyPolicy())

    assessed = await service.assess_meal(meal)

    assert assessed.items[0].confirmed_portion_g == Decimal("100")
    assert assessed.items[0].portion_resolution_source == PortionResolutionSource.AUTO_ESTIMATE
    assert assessed.items[0].final_nutrition is not None
    assert assessed.clarifications == []


@pytest.mark.asyncio
async def test_identity_precedes_portion_and_generation_is_idempotent():
    repository = InMemoryMealRepository()
    unresolved = MealItem(uuid4(), 0, "mystery food", observation_certainty="LOW")
    risky_portion = grounded_item("50", "150")
    risky_portion.position = 1
    meal = meal_with(unresolved, risky_portion)
    await repository.create(meal)
    service = MealReviewService(repository, UnusedDependency(), UnusedDependency(), UncertaintyPolicy())

    await service.assess_meal(meal)
    await service.assess_meal(meal)

    assert len(meal.clarifications) == 1
    clarification = meal.clarifications[0]
    assert clarification.type == "FOOD_IDENTITY"
    assert {option["value"]["action"] for option in clarification.options} == {
        "MANUAL_SEARCH", "REMOVE_ITEM"
    }
    assert risky_portion.final_nutrition is None


@pytest.mark.asyncio
async def test_medium_observation_alone_does_not_interrupt():
    repository = InMemoryMealRepository()
    item = grounded_item("95", "105", certainty="MEDIUM")
    meal = meal_with(item)
    await repository.create(meal)
    service = MealReviewService(repository, UnusedDependency(), UnusedDependency(), UncertaintyPolicy())

    await service.assess_meal(meal)

    assert item.confirmed_portion_g == Decimal("100")
    assert meal.clarifications == []


@pytest.mark.asyncio
async def test_hidden_ingredients_are_material_only_and_deduplicated_before_portion():
    repository = InMemoryMealRepository()
    item = grounded_item("50", "150")
    meal = meal_with(item)
    run = AIRun(meal.id, "MEAL_RECOGNITION", "TEST", "TEST", "v1")
    run.succeed(
        latency_ms=1, input_tokens=None, output_tokens=None, retry_count=0,
        structured_output={"possible_hidden_ingredients": [
            {"name": " Cooking Oil ", "reason": "possibly used", "potential_impact": "MATERIAL"},
            {"name": "cooking   oil", "reason": "duplicate", "potential_impact": "MATERIAL"},
            {"name": "parsley", "reason": "garnish", "potential_impact": "LOW"},
        ]},
    )
    meal.ai_runs.append(run)
    await repository.create(meal)
    service = MealReviewService(repository, UnusedDependency(), UnusedDependency(), UncertaintyPolicy())

    await service.assess_meal(meal)
    await service.assess_meal(meal)

    assert [value.type for value in meal.clarifications] == ["HIDDEN_INGREDIENT"]
    assert item.final_nutrition is None


@pytest.mark.asyncio
async def test_human_candidate_answer_grounds_directly_without_rerunning_p4_or_p5():
    repository = InMemoryMealRepository()
    unresolved = MealItem(uuid4(), 0, "white rice", portion_estimate=PortionEstimate(90, 110), observation_certainty="HIGH")
    meal = meal_with(unresolved)
    await repository.create(meal)
    grounding = FoodGroundingService(DemoNutritionProvider())
    await grounding.retrieve_candidates(unresolved)
    forbidden = ForbiddenCanonicalization()
    service = MealReviewService(repository, grounding, forbidden, UncertaintyPolicy())
    await service.assess_meal(meal)
    clarification = meal.clarifications[0]

    await service.answer(meal, clarification.id, option_id="candidate-1", custom_grams=None)

    assert forbidden.call_count == 0
    assert unresolved.canonical_food_id is not None
    assert unresolved.nutrition_snapshot is not None
