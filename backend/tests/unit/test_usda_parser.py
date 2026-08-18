import json
from decimal import Decimal
from pathlib import Path

from app.nutrition.usda_parser import parse_usda_nutrition


FIXTURES = Path(__file__).parents[1] / "fixtures" / "usda"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_parser_is_order_independent_and_preserves_explicit_zero() -> None:
    nutrients = load_fixture("detail_standard.json")["foodNutrients"]
    parsed = parse_usda_nutrition(list(reversed(nutrients)))

    assert parsed.missing_nutrients == ()
    assert parsed.energy_nutrient_id == 1008
    assert parsed.nutrition is not None
    assert parsed.nutrition.calories_kcal == Decimal("165")
    assert parsed.nutrition.protein_g == Decimal("31")
    assert parsed.nutrition.carbs_g == Decimal("0")
    assert parsed.nutrition.fat_g == Decimal("3.6")


def test_foundation_energy_precedence_is_2048_then_2047_then_1008() -> None:
    parsed = parse_usda_nutrition(
        load_fixture("detail_foundation.json")["foodNutrients"]
    )

    assert parsed.energy_nutrient_id == 2048
    assert parsed.nutrition is not None
    assert parsed.nutrition.calories_kcal == Decimal("120")


def test_kilojoules_and_macro_units_are_converted() -> None:
    parsed = parse_usda_nutrition(
        [
            {"nutrientId": 1008, "unitName": "KJ", "value": 418.4},
            {"nutrientId": 1003, "unitName": "MG", "value": 1000},
            {"nutrientId": 1004, "unitName": "UG", "value": 1000000},
            {"nutrientId": 1005, "unitName": "G", "value": 2},
        ]
    )

    assert parsed.nutrition is not None
    assert parsed.nutrition.calories_kcal == Decimal("100")
    assert parsed.nutrition.protein_g == Decimal("1")
    assert parsed.nutrition.fat_g == Decimal("1")


def test_missing_nutrient_is_not_treated_as_zero() -> None:
    parsed = parse_usda_nutrition(
        load_fixture("incomplete_nutrition.json")["foodNutrients"]
    )

    assert parsed.nutrition is None
    assert parsed.missing_nutrients == ("protein",)


def test_incompatible_units_are_reported_as_missing() -> None:
    parsed = parse_usda_nutrition(
        [
            {"nutrientId": 1008, "unitName": "G", "value": 100},
            {"nutrientId": 1003, "unitName": "KCAL", "value": 1},
            {"nutrientId": 1004, "unitName": "G", "value": 1},
            {"nutrientId": 1005, "unitName": "G", "value": 1},
        ]
    )

    assert parsed.nutrition is None
    assert parsed.missing_nutrients == ("energy", "protein")


def test_explicit_zero_fat_is_valid_but_negative_values_are_not() -> None:
    zero = parse_usda_nutrition(
        [
            {"nutrientId": 1008, "unitName": "KCAL", "value": 20},
            {"nutrientId": 1003, "unitName": "G", "value": 1},
            {"nutrientId": 1004, "unitName": "G", "value": 0},
            {"nutrientId": 1005, "unitName": "G", "value": 3},
        ]
    )
    negative = parse_usda_nutrition(
        [
            {"nutrientId": 1008, "unitName": "KCAL", "value": 20},
            {"nutrientId": 1003, "unitName": "G", "value": 1},
            {"nutrientId": 1004, "unitName": "G", "value": -1},
            {"nutrientId": 1005, "unitName": "G", "value": 3},
        ]
    )

    assert zero.nutrition is not None
    assert zero.nutrition.fat_g == Decimal("0")
    assert negative.nutrition is None
    assert negative.missing_nutrients == ("fat",)
