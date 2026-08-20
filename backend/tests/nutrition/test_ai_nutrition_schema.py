from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.nutrition.schemas.ai_nutrition import AINutritionOutput


def test_valid_payload_parses_into_decimals() -> None:
    parsed = AINutritionOutput.model_validate(
        {
            "basis": "per_100g",
            "recognized": True,
            "familiarity": "high",
            "calories_kcal": 165,
            "protein_g": 31,
            "carbs_g": 0,
            "fat_g": 3.6,
        }
    )

    assert parsed.calories_kcal == Decimal("165")
    assert parsed.fat_g == Decimal("3.6")


def test_negative_values_are_rejected() -> None:
    with pytest.raises(ValidationError):
        AINutritionOutput.model_validate(
            {
                "basis": "per_100g",
                "recognized": True,
                "familiarity": "high",
                "calories_kcal": -1,
                "protein_g": 0,
                "carbs_g": 0,
                "fat_g": 0,
            }
        )


def test_calories_above_pure_fat_are_rejected() -> None:
    with pytest.raises(ValidationError):
        AINutritionOutput.model_validate(
            {
                "basis": "per_100g",
                "recognized": True,
                "familiarity": "high",
                "calories_kcal": 2500,
                "protein_g": 0,
                "carbs_g": 0,
                "fat_g": 0,
            }
        )


def test_a_basis_other_than_per_100g_is_rejected() -> None:
    with pytest.raises(ValidationError):
        AINutritionOutput.model_validate(
            {
                "basis": "per_serving",
                "recognized": True,
                "familiarity": "high",
                "calories_kcal": 100,
                "protein_g": 1,
                "carbs_g": 1,
                "fat_g": 1,
            }
        )


def test_an_unrecognized_food_may_leave_nutrient_values_null() -> None:
    parsed = AINutritionOutput.model_validate(
        {
            "basis": "per_100g",
            "recognized": False,
            "familiarity": "low",
            "calories_kcal": None,
            "protein_g": None,
            "carbs_g": None,
            "fat_g": None,
        }
    )

    assert parsed.recognized is False
    assert parsed.calories_kcal is None


def test_an_invalid_familiarity_value_is_rejected() -> None:
    with pytest.raises(ValidationError):
        AINutritionOutput.model_validate(
            {
                "basis": "per_100g",
                "recognized": True,
                "familiarity": "extremely-confident",
                "calories_kcal": 100,
                "protein_g": 1,
                "carbs_g": 1,
                "fat_g": 1,
            }
        )
