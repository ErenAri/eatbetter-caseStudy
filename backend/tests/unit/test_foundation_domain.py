from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.domain.entities import (
    Meal,
    MealItem,
    NutritionPer100g,
    PortionEstimate,
    calculate_nutrition_for_grams,
)
from app.domain.enums import MealStatus
from app.domain.policies import UncertaintyPolicy, UncertaintyReason


def test_authoritative_nutrition_half_portion_and_negative_validation():
    nutrition = NutritionPer100g(200, 20, 10, 8)
    result = calculate_nutrition_for_grams(nutrition, 50)
    assert result.calories_kcal == Decimal("100")
    assert result.protein_g == Decimal("10")
    with pytest.raises(ValueError, match="cannot be negative"):
        NutritionPer100g(-1, 0, 0, 0)


def test_authoritative_state_machine_allows_review_reanalysis():
    meal = Meal(uuid4(), uuid4(), datetime.now(timezone.utc))
    meal.transition_to(MealStatus.ANALYZING)
    meal.transition_to(MealStatus.NEEDS_REVIEW)
    meal.transition_to(MealStatus.ANALYZING)
    assert meal.status == MealStatus.ANALYZING


def test_uncertainty_policy_returns_structured_reasons_at_boundaries():
    policy = UncertaintyPolicy(
        max_absolute_calorie_uncertainty=Decimal("100"),
        max_relative_calorie_uncertainty=Decimal("3"),
    )
    def item(spread: int) -> MealItem:
        value = MealItem(
            meal_id=uuid4(), position=0, observed_name="food",
            canonical_food_id="1", portion_estimate=PortionEstimate(0, spread),
        )
        value.nutrition_snapshot = NutritionPer100g(100, 0, 0, 0)
        return value

    assert policy.assess_portion(item(99)).requires_clarification is False
    assert policy.assess_portion(item(100)).requires_clarification is False
    assert policy.assess_portion(item(101)).reasons == (
        UncertaintyReason.ABSOLUTE_CALORIE_UNCERTAINTY,
    )


@pytest.mark.parametrize("spread, blocks", [(190, False), (200, False), (210, True)])
def test_relative_uncertainty_19_20_21_percent(spread: int, blocks: bool):
    policy = UncertaintyPolicy(
        max_absolute_calorie_uncertainty=Decimal("1000"),
        max_relative_calorie_uncertainty=Decimal("0.20"),
    )
    value = MealItem(
        meal_id=uuid4(), position=0, observed_name="food", canonical_food_id="1",
        portion_estimate=PortionEstimate(Decimal("1000") - Decimal(spread) / 2, Decimal("1000") + Decimal(spread) / 2),
    )
    value.nutrition_snapshot = NutritionPer100g(100, 0, 0, 0)
    result = policy.assess_portion(value)
    assert (UncertaintyReason.RELATIVE_CALORIE_UNCERTAINTY in result.reasons) is blocks
