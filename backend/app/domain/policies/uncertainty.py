from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from app.domain.entities.meal import MealItem
from app.domain.entities.nutrition import NutritionTotals, calculate_nutrition_for_grams


class RiskLevel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class UncertaintyReason(StrEnum):
    CANONICAL_UNRESOLVED = "CANONICAL_UNRESOLVED"
    CANONICAL_AMBIGUOUS = "CANONICAL_AMBIGUOUS"
    PORTION_UNKNOWN = "PORTION_UNKNOWN"
    ABSOLUTE_CALORIE_UNCERTAINTY = "ABSOLUTE_CALORIE_UNCERTAINTY"
    RELATIVE_CALORIE_UNCERTAINTY = "RELATIVE_CALORIE_UNCERTAINTY"
    LOW_OBSERVATION_CERTAINTY = "LOW_OBSERVATION_CERTAINTY"
    MATERIAL_HIDDEN_INGREDIENT = "MATERIAL_HIDDEN_INGREDIENT"
    UNKNOWN_HIDDEN_INGREDIENT = "UNKNOWN_HIDDEN_INGREDIENT"
    INVALID_PORTION_RANGE = "INVALID_PORTION_RANGE"
    MISSING_NUTRITION_SNAPSHOT = "MISSING_NUTRITION_SNAPSHOT"


@dataclass(frozen=True, slots=True)
class PortionAssessment:
    minimum: NutritionTotals | None
    maximum: NutritionTotals | None
    absolute_calorie_uncertainty: Decimal | None
    relative_calorie_uncertainty: Decimal | None
    midpoint_g: Decimal | None
    reasons: tuple[UncertaintyReason, ...]

    @property
    def requires_clarification(self) -> bool:
        return bool(self.reasons)


@dataclass(frozen=True, slots=True)
class ItemRiskAssessment:
    level: RiskLevel
    reasons: tuple[UncertaintyReason, ...]
    auto_accept_eligible: bool
    portion: PortionAssessment | None

    @property
    def requires_clarification(self) -> bool:
        return self.level == RiskLevel.HIGH


@dataclass(frozen=True, slots=True)
class UncertaintyPolicy:
    max_absolute_calorie_uncertainty: Decimal = Decimal("100")
    max_relative_calorie_uncertainty: Decimal = Decimal("0.20")

    def assess_portion(self, item: MealItem) -> PortionAssessment:
        estimate = item.portion_estimate
        if estimate.min_g is None or estimate.max_g is None:
            return PortionAssessment(None, None, None, None, None, (UncertaintyReason.PORTION_UNKNOWN,))
        if estimate.min_g < 0 or estimate.max_g < estimate.min_g:
            return PortionAssessment(None, None, None, None, None, (UncertaintyReason.INVALID_PORTION_RANGE,))
        midpoint = (estimate.min_g + estimate.max_g) / Decimal("2")
        if item.nutrition_snapshot is None:
            return PortionAssessment(None, None, None, None, midpoint, (UncertaintyReason.MISSING_NUTRITION_SNAPSHOT,))
        minimum = calculate_nutrition_for_grams(item.nutrition_snapshot, estimate.min_g)
        maximum = calculate_nutrition_for_grams(item.nutrition_snapshot, estimate.max_g)
        absolute = maximum.calories_kcal - minimum.calories_kcal
        calorie_midpoint = (minimum.calories_kcal + maximum.calories_kcal) / Decimal("2")
        relative = Decimal("0") if calorie_midpoint == 0 and absolute == 0 else (
            None if calorie_midpoint == 0 else absolute / calorie_midpoint
        )
        reasons: list[UncertaintyReason] = []
        # Boundary is inclusive: exactly 100 kcal or 20% is safe; only greater blocks.
        if absolute > self.max_absolute_calorie_uncertainty:
            reasons.append(UncertaintyReason.ABSOLUTE_CALORIE_UNCERTAINTY)
        if relative is None or relative > self.max_relative_calorie_uncertainty:
            reasons.append(UncertaintyReason.RELATIVE_CALORIE_UNCERTAINTY)
        return PortionAssessment(minimum, maximum, absolute, relative, midpoint, tuple(reasons))

    def assess_item(self, item: MealItem, *, hidden_impacts: tuple[str, ...] = ()) -> ItemRiskAssessment:
        if item.is_removed:
            return ItemRiskAssessment(RiskLevel.LOW, (), False, None)
        reasons: list[UncertaintyReason] = []
        portion: PortionAssessment | None = None
        if item.canonical_food_id is None:
            reasons.append(UncertaintyReason.CANONICAL_AMBIGUOUS if item.candidates else UncertaintyReason.CANONICAL_UNRESOLVED)
        elif item.nutrition_snapshot is None:
            reasons.append(UncertaintyReason.MISSING_NUTRITION_SNAPSHOT)
        if item.observation_certainty == "LOW":
            reasons.append(UncertaintyReason.LOW_OBSERVATION_CERTAINTY)
        for impact in hidden_impacts:
            if impact == "MATERIAL":
                reasons.append(UncertaintyReason.MATERIAL_HIDDEN_INGREDIENT)
            elif impact == "UNKNOWN":
                reasons.append(UncertaintyReason.UNKNOWN_HIDDEN_INGREDIENT)
        if item.confirmed_portion_g is None and item.canonical_food_id and item.nutrition_snapshot:
            portion = self.assess_portion(item)
            reasons.extend(portion.reasons)
        unique = tuple(dict.fromkeys(reasons))
        level = RiskLevel.HIGH if unique else (RiskLevel.MEDIUM if item.observation_certainty == "MEDIUM" else RiskLevel.LOW)
        auto = level != RiskLevel.HIGH and item.confirmed_portion_g is None and portion is not None
        return ItemRiskAssessment(level, unique, auto, portion)
