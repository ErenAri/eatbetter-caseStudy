from decimal import Decimal

import pytest

from app.domain.entities import NutritionPer100g
from app.nutrition.consensus import (
    confidence_from_spread,
    median_nutrition,
    relative_spread,
)


def _sample(calories: str) -> NutritionPer100g:
    return NutritionPer100g(Decimal(calories), Decimal("10"), Decimal("20"), Decimal("5"))


def test_median_of_three_samples_takes_the_middle_value_per_field() -> None:
    samples = [
        NutritionPer100g(Decimal("100"), Decimal("1"), Decimal("30"), Decimal("9")),
        NutritionPer100g(Decimal("200"), Decimal("3"), Decimal("10"), Decimal("7")),
        NutritionPer100g(Decimal("300"), Decimal("2"), Decimal("20"), Decimal("8")),
    ]

    result = median_nutrition(samples)

    assert result.calories_kcal == Decimal("200")
    assert result.protein_g == Decimal("2")
    assert result.carbs_g == Decimal("20")
    assert result.fat_g == Decimal("8")


def test_median_of_even_count_averages_the_two_middle_values() -> None:
    samples = [_sample("100"), _sample("200")]

    assert median_nutrition(samples).calories_kcal == Decimal("150")


def test_single_sample_has_no_spread() -> None:
    assert relative_spread([_sample("250")]) == Decimal("0")


def test_relative_spread_is_range_over_median() -> None:
    samples = [_sample("90"), _sample("100"), _sample("120")]

    assert relative_spread(samples) == Decimal("0.3")


def test_empty_sample_list_is_rejected() -> None:
    with pytest.raises(ValueError):
        median_nutrition([])
    with pytest.raises(ValueError):
        relative_spread([])


def test_zero_median_calories_reports_no_spread_instead_of_dividing_by_zero() -> None:
    assert relative_spread([_sample("0"), _sample("0")]) == Decimal("0")


def test_confidence_is_the_inverse_of_spread_clamped_to_unit_range() -> None:
    assert confidence_from_spread(Decimal("0")) == Decimal("1")
    assert confidence_from_spread(Decimal("0.25")) == Decimal("0.75")
    assert confidence_from_spread(Decimal("2.5")) == Decimal("0")
