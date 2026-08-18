from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from app.domain.entities import NutritionPer100g


PROTEIN_ID = 1003
FAT_ID = 1004
CARBOHYDRATE_ID = 1005
ENERGY_PRECEDENCE = (2048, 2047, 1008)
KJ_PER_KCAL = Decimal("4.184")


@dataclass(frozen=True, slots=True)
class ParsedUSDANutrition:
    nutrition: NutritionPer100g | None
    energy_nutrient_id: int | None
    missing_nutrients: tuple[str, ...]


def _entry_values(entry: dict[str, Any]) -> tuple[int | None, Decimal | None, str | None]:
    nutrient = entry.get("nutrient") if isinstance(entry.get("nutrient"), dict) else {}
    nutrient_id = entry.get("nutrientId", nutrient.get("id"))
    amount = entry.get("value") if "value" in entry else entry.get("amount")
    unit = entry.get("unitName", nutrient.get("unitName"))
    try:
        parsed_id = int(nutrient_id) if nutrient_id is not None else None
        parsed_amount = Decimal(str(amount)) if amount is not None else None
    except (TypeError, ValueError, InvalidOperation):
        return None, None, None
    return parsed_id, parsed_amount, str(unit).upper() if unit is not None else None


def _grams(amount: Decimal, unit: str | None) -> Decimal | None:
    if amount < 0:
        return None
    if unit == "G":
        return amount
    if unit == "MG":
        return amount / Decimal("1000")
    if unit in {"UG", "µG", "MCG"}:
        return amount / Decimal("1000000")
    return None


def _kilocalories(amount: Decimal, unit: str | None) -> Decimal | None:
    if amount < 0:
        return None
    if unit in {"KCAL", "KCAL/100G"}:
        return amount
    if unit in {"KJ", "KJ/100G"}:
        return amount / KJ_PER_KCAL
    return None


def parse_usda_nutrition(nutrients: list[dict[str, Any]]) -> ParsedUSDANutrition:
    values: dict[int, list[tuple[Decimal, str | None]]] = {}
    for entry in nutrients:
        nutrient_id, amount, unit = _entry_values(entry)
        if nutrient_id is not None and amount is not None:
            values.setdefault(nutrient_id, []).append((amount, unit))

    macros: dict[str, Decimal] = {}
    for name, nutrient_id in (
        ("protein", PROTEIN_ID),
        ("fat", FAT_ID),
        ("carbohydrate", CARBOHYDRATE_ID),
    ):
        compatible = [
            converted
            for amount, unit in values.get(nutrient_id, [])
            if (converted := _grams(amount, unit)) is not None
        ]
        if compatible:
            macros[name] = compatible[0]

    energy: Decimal | None = None
    selected_energy_id: int | None = None
    for nutrient_id in ENERGY_PRECEDENCE:
        compatible = [
            converted
            for amount, unit in values.get(nutrient_id, [])
            if (converted := _kilocalories(amount, unit)) is not None
        ]
        if compatible:
            energy = compatible[0]
            selected_energy_id = nutrient_id
            break

    missing = tuple(
        name
        for name, present in (
            ("energy", energy is not None),
            ("protein", "protein" in macros),
            ("carbohydrate", "carbohydrate" in macros),
            ("fat", "fat" in macros),
        )
        if not present
    )
    if missing:
        return ParsedUSDANutrition(None, selected_energy_id, missing)
    return ParsedUSDANutrition(
        NutritionPer100g(
            calories_kcal=energy,
            protein_g=macros["protein"],
            carbs_g=macros["carbohydrate"],
            fat_g=macros["fat"],
        ),
        selected_energy_id,
        (),
    )
