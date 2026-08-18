from decimal import Decimal
from uuid import uuid4

import pytest

from app.domain.entities import MealItem, NutritionPer100g, PortionEstimate
from app.domain.policies import RiskLevel, UncertaintyPolicy, UncertaintyReason


def item(
    minimum: Decimal | None,
    maximum: Decimal | None,
    *,
    calories: Decimal | None = Decimal("100"),
    canonical: bool = True,
    certainty: str = "HIGH",
) -> MealItem:
    value = MealItem(
        uuid4(), 0, "food",
        canonical_food_id="food-1" if canonical else None,
        portion_estimate=PortionEstimate(minimum, maximum),
        observation_certainty=certainty,
    )
    if calories is not None:
        value.nutrition_snapshot = NutritionPer100g(calories, 0, 0, 0)
    return value


def test_missing_and_exact_portions_have_explicit_behavior():
    policy = UncertaintyPolicy()
    assert policy.assess_portion(item(None, None)).reasons == (UncertaintyReason.PORTION_UNKNOWN,)
    exact = policy.assess_portion(item(Decimal("80"), Decimal("80")))
    assert exact.reasons == ()
    assert exact.midpoint_g == Decimal("80")
    assert exact.absolute_calorie_uncertainty == 0


def test_zero_calorie_range_does_not_divide_by_zero():
    result = UncertaintyPolicy().assess_portion(item(Decimal("0"), Decimal("100"), calories=Decimal("0")))
    assert result.relative_calorie_uncertainty == 0
    assert result.reasons == ()


def test_invalid_range_is_rejected_at_the_domain_boundary():
    with pytest.raises(ValueError, match="maximum cannot be below"):
        PortionEstimate(Decimal("101"), Decimal("100"))


def test_missing_snapshot_low_certainty_hidden_and_abstain_are_categorical():
    policy = UncertaintyPolicy()
    missing = item(Decimal("90"), Decimal("110"), calories=None)
    assert policy.assess_item(missing).reasons == (UncertaintyReason.MISSING_NUTRITION_SNAPSHOT,)
    low = policy.assess_item(item(Decimal("90"), Decimal("110"), certainty="LOW"))
    assert low.level == RiskLevel.HIGH
    assert UncertaintyReason.LOW_OBSERVATION_CERTAINTY in low.reasons
    hidden = policy.assess_item(
        item(Decimal("90"), Decimal("110")), hidden_impacts=("MATERIAL", "UNKNOWN")
    )
    assert UncertaintyReason.MATERIAL_HIDDEN_INGREDIENT in hidden.reasons
    assert UncertaintyReason.UNKNOWN_HIDDEN_INGREDIENT in hidden.reasons
    abstain = policy.assess_item(item(Decimal("90"), Decimal("110"), canonical=False))
    assert abstain.reasons[0] == UncertaintyReason.CANONICAL_UNRESOLVED


def test_removed_item_never_auto_accepts_or_blocks():
    value = item(None, None, canonical=False, certainty="LOW")
    value.is_removed = True
    assessment = UncertaintyPolicy().assess_item(value, hidden_impacts=("MATERIAL",))
    assert assessment.level == RiskLevel.LOW
    assert assessment.reasons == ()
    assert assessment.auto_accept_eligible is False


def test_same_gram_range_is_decided_by_nutrition_impact():
    policy = UncertaintyPolicy(max_relative_calorie_uncertainty=Decimal("2"))
    oil = policy.assess_portion(item(Decimal("5"), Decimal("25"), calories=Decimal("884")))
    low_calorie = policy.assess_portion(item(Decimal("5"), Decimal("25"), calories=Decimal("35")))
    assert UncertaintyReason.ABSOLUTE_CALORIE_UNCERTAINTY in oil.reasons
    assert UncertaintyReason.ABSOLUTE_CALORIE_UNCERTAINTY not in low_calorie.reasons
