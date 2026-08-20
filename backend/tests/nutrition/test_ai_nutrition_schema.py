from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.nutrition.schemas.ai_nutrition import AINutritionOutput


def test_valid_payload_parses_into_decimals() -> None:
    parsed = AINutritionOutput.model_validate(
        {
            "basis": "per_100g",
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
            {"basis": "per_100g", "calories_kcal": -1, "protein_g": 0, "carbs_g": 0, "fat_g": 0}
        )


def test_calories_above_pure_fat_are_rejected() -> None:
    with pytest.raises(ValidationError):
        AINutritionOutput.model_validate(
            {"basis": "per_100g", "calories_kcal": 2500, "protein_g": 0, "carbs_g": 0, "fat_g": 0}
        )


def test_a_basis_other_than_per_100g_is_rejected() -> None:
    with pytest.raises(ValidationError):
        AINutritionOutput.model_validate(
            {"basis": "per_serving", "calories_kcal": 100, "protein_g": 1, "carbs_g": 1, "fat_g": 1}
        )
