from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


Numeric = Decimal | int | float | str


def decimal_value(value: Numeric) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


@dataclass(frozen=True, slots=True)
class NutritionTotals:
    calories_kcal: Decimal = Decimal("0")
    protein_g: Decimal = Decimal("0")
    carbs_g: Decimal = Decimal("0")
    fat_g: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        for field_name in ("calories_kcal", "protein_g", "carbs_g", "fat_g"):
            value = decimal_value(getattr(self, field_name))
            if value < 0:
                raise ValueError(f"{field_name} cannot be negative")
            object.__setattr__(self, field_name, value)

    def __add__(self, other: "NutritionTotals") -> "NutritionTotals":
        return NutritionTotals(
            self.calories_kcal + other.calories_kcal,
            self.protein_g + other.protein_g,
            self.carbs_g + other.carbs_g,
            self.fat_g + other.fat_g,
        )


@dataclass(frozen=True, slots=True)
class NutritionPer100g:
    calories_kcal: Decimal
    protein_g: Decimal
    carbs_g: Decimal
    fat_g: Decimal

    def __post_init__(self) -> None:
        for field_name in ("calories_kcal", "protein_g", "carbs_g", "fat_g"):
            value = decimal_value(getattr(self, field_name))
            if value < 0:
                raise ValueError(f"{field_name} cannot be negative")
            object.__setattr__(self, field_name, value)


def calculate_nutrition_for_grams(
    nutrition_per_100g: NutritionPer100g, grams: Numeric
) -> NutritionTotals:
    portion = decimal_value(grams)
    if portion < 0:
        raise ValueError("grams cannot be negative")
    factor = portion / Decimal("100")
    return NutritionTotals(
        nutrition_per_100g.calories_kcal * factor,
        nutrition_per_100g.protein_g * factor,
        nutrition_per_100g.carbs_g * factor,
        nutrition_per_100g.fat_g * factor,
    )
