"""Combine repeated model samples into one answer plus a disagreement measure.

Repeated sampling is the only confidence signal available when nutrition is not
retrieved from an authoritative database: agreement across independent samples
stands in for provenance.
"""

from __future__ import annotations

from decimal import Decimal

from app.domain.entities import NutritionPer100g

_FIELDS = ("calories_kcal", "protein_g", "carbs_g", "fat_g")


def _median(values: list[Decimal]) -> Decimal:
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return ordered[midpoint]
    return (ordered[midpoint - 1] + ordered[midpoint]) / Decimal("2")


def median_nutrition(samples: list[NutritionPer100g]) -> NutritionPer100g:
    if not samples:
        raise ValueError("at least one nutrition sample is required")
    return NutritionPer100g(
        *(_median([getattr(sample, field) for sample in samples]) for field in _FIELDS)
    )


def relative_spread(samples: list[NutritionPer100g]) -> Decimal:
    if not samples:
        raise ValueError("at least one nutrition sample is required")
    calories = [sample.calories_kcal for sample in samples]
    midpoint = _median(calories)
    if midpoint == 0:
        return Decimal("0")
    return (max(calories) - min(calories)) / midpoint


def confidence_from_spread(spread: Decimal) -> Decimal:
    return min(Decimal("1"), max(Decimal("0"), Decimal("1") - spread))
