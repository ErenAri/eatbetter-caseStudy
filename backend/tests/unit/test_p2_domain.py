from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.ai.schemas import CanonicalizationOutput, MealObservation
from app.domain.entities import (
    CanonicalFoodCandidate,
    Meal,
    MealItem,
    NutritionPer100g,
    PortionEstimate,
)
from app.domain.enums import MealStatus


def test_decimal_totals_are_deterministic_without_float_accumulation():
    meal = Meal(uuid4(), uuid4(), datetime.now(timezone.utc))
    for position, grams in enumerate((Decimal("33.3"), Decimal("66.7"))):
        item = MealItem(
            meal_id=meal.id,
            position=position,
            observed_name="food",
            confirmed_portion_g=grams,
            nutrition_snapshot=NutritionPer100g("123.4", "5.6", "7.8", "9.1"),
            canonical_food_id=f"food-{position}",
        )
        item.recalculate()
        meal.items.append(item)
    totals = meal.totals()
    assert totals.calories_kcal == Decimal("123.4000")
    assert totals.protein_g == Decimal("5.600")


def test_portion_confidence_and_candidate_constraints():
    with pytest.raises(ValueError, match="below minimum"):
        PortionEstimate(100, 99)
    with pytest.raises(ValueError, match="between 0 and 1"):
        MealItem(uuid4(), 0, "rice", canonical_confidence=Decimal("1.01"))
    with pytest.raises(ValueError, match="at least 1"):
        CanonicalFoodCandidate(uuid4(), 0, "USDA", "id", "Rice")


def test_nutrition_consensus_spread_rejects_negative_and_coerces_strings():
    item = MealItem(uuid4(), 0, "cabbage salad", nutrition_consensus_spread="1.4")
    assert item.nutrition_consensus_spread == Decimal("1.4")
    with pytest.raises(ValueError, match="cannot be negative"):
        MealItem(uuid4(), 0, "rice", nutrition_consensus_spread=Decimal("-0.1"))


def test_canonicalization_rank_must_reference_supplied_candidate():
    output = CanonicalizationOutput(
        decision="SELECT",
        selected_candidate_rank=3,
        match_quality="STRONG",
        reason_codes=["FOOD_IDENTITY_MATCH"],
    )
    with pytest.raises(ValueError, match="not present"):
        output.validate_against_supplied_ranks({1, 2})


def test_meal_observation_has_no_authoritative_nutrition_or_food_id_fields():
    schema = MealObservation.model_json_schema()
    serialized = str(schema)
    assert "calories" not in serialized
    assert "food_id" not in serialized


def test_confirm_transition_only_occurs_from_review():
    meal = Meal(uuid4(), uuid4(), datetime.now(timezone.utc))
    with pytest.raises(ValueError):
        meal.transition_to(MealStatus.CONFIRMED)
    meal.transition_to(MealStatus.ANALYZING)
    meal.transition_to(MealStatus.NEEDS_REVIEW)
    meal.transition_to(MealStatus.CONFIRMED)
