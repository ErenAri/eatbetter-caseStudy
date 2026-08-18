from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from app.domain.enums import (
    ALLOWED_MEAL_TRANSITIONS,
    ClarificationStatus,
    MealStatus,
    PortionResolutionSource,
)

from .ai_run import AIRun
from .food import CanonicalFoodCandidate
from .nutrition import NutritionPer100g, NutritionTotals, calculate_nutrition_for_grams, decimal_value
from .review import Clarification, Correction


class InvalidMealTransition(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class PortionEstimate:
    min_g: Decimal | None = None
    max_g: Decimal | None = None

    def __post_init__(self) -> None:
        minimum = decimal_value(self.min_g) if self.min_g is not None else None
        maximum = decimal_value(self.max_g) if self.max_g is not None else None
        if minimum is not None and minimum < 0:
            raise ValueError("portion minimum cannot be negative")
        if maximum is not None and maximum < 0:
            raise ValueError("portion maximum cannot be negative")
        if minimum is not None and maximum is not None and maximum < minimum:
            raise ValueError("portion maximum cannot be below minimum")
        object.__setattr__(self, "min_g", minimum)
        object.__setattr__(self, "max_g", maximum)


@dataclass(slots=True)
class MealItem:
    meal_id: UUID
    position: int
    observed_name: str
    id: UUID = field(default_factory=uuid4)
    normalized_name: str | None = None
    preparation_method: str | None = None
    canonical_food_id: str | None = None
    canonical_food_name: str | None = None
    canonical_source: str | None = None
    canonical_candidate_rank: int | None = None
    portion_estimate: PortionEstimate = field(default_factory=PortionEstimate)
    confirmed_portion_g: Decimal | None = None
    portion_resolution_source: PortionResolutionSource | None = None
    observation_certainty: str | None = None
    canonical_confidence: Decimal | None = None
    requires_clarification: bool = False
    clarification_resolved: bool = False
    nutrition_snapshot: NutritionPer100g | None = None
    nutrition_retrieved_at: datetime | None = None
    final_nutrition: NutritionTotals | None = None
    candidates: list[CanonicalFoodCandidate] = field(default_factory=list)
    is_removed: bool = False
    is_user_added: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if self.position < 0:
            raise ValueError("item position cannot be negative")
        if self.confirmed_portion_g is not None:
            self.confirmed_portion_g = decimal_value(self.confirmed_portion_g)
        if self.canonical_confidence is not None:
            self.canonical_confidence = decimal_value(self.canonical_confidence)
            if not Decimal("0") <= self.canonical_confidence <= Decimal("1"):
                raise ValueError("canonical confidence must be between 0 and 1")

    def select_candidate(self, rank: int) -> CanonicalFoodCandidate:
        candidate = next((value for value in self.candidates if value.rank == rank), None)
        if candidate is None:
            raise ValueError("candidate rank was not supplied for this item")
        self.canonical_candidate_rank = rank
        self.canonical_food_id = candidate.source_food_id
        self.canonical_food_name = candidate.name
        self.canonical_source = candidate.source
        self.updated_at = datetime.now(timezone.utc)
        return candidate

    def recalculate(self) -> None:
        if self.is_removed:
            self.final_nutrition = None
        elif self.confirmed_portion_g is not None and self.nutrition_snapshot is not None:
            self.final_nutrition = calculate_nutrition_for_grams(
                self.nutrition_snapshot, self.confirmed_portion_g
            )
        else:
            self.final_nutrition = None
        self.updated_at = datetime.now(timezone.utc)


@dataclass(slots=True)
class Meal:
    user_id: UUID
    meal_request_id: UUID
    logged_at: datetime
    user_context: str | None = None
    id: UUID = field(default_factory=uuid4)
    status: MealStatus = MealStatus.UPLOADED
    image_path: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    confirmed_at: datetime | None = None
    failure_code: str | None = None
    failure_message: str | None = None
    items: list[MealItem] = field(default_factory=list)
    clarifications: list[Clarification] = field(default_factory=list)
    corrections: list[Correction] = field(default_factory=list)
    ai_runs: list[AIRun] = field(default_factory=list)

    def transition_to(self, next_status: MealStatus) -> None:
        if next_status not in ALLOWED_MEAL_TRANSITIONS[self.status]:
            raise InvalidMealTransition(f"cannot transition {self.status} to {next_status}")
        self.status = next_status
        self.updated_at = datetime.now(timezone.utc)
        if next_status == MealStatus.CONFIRMED:
            self.confirmed_at = self.updated_at

    def totals(self) -> NutritionTotals:
        total = NutritionTotals()
        for item in self.items:
            if not item.is_removed and item.final_nutrition is not None:
                total = total + item.final_nutrition
        return total

    def has_unresolved_clarifications(self) -> bool:
        active_ids = {item.id for item in self.items if not item.is_removed}
        clarification_blocks = any(
            value.blocking
            and not value.resolution_satisfied
            and (value.meal_item_id is None or value.meal_item_id in active_ids)
            for value in self.clarifications
        )
        return clarification_blocks or any(
            item.requires_clarification and not item.clarification_resolved and not item.is_removed
            for item in self.items
        )
