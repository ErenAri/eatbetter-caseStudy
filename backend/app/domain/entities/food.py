from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from .nutrition import NutritionPer100g


@dataclass(frozen=True, slots=True)
class CanonicalFood:
    source: str
    source_food_id: str
    name: str
    nutrition_per_100g: NutritionPer100g
    data: dict[str, Any] | None = None
    retrieved_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True, slots=True)
class CanonicalFoodCandidate:
    meal_item_id: UUID
    rank: int
    source: str
    source_food_id: str
    name: str
    data: dict[str, Any] | None = None
    nutrition_per_100g: NutritionPer100g | None = None
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if self.rank < 1:
            raise ValueError("candidate rank must be at least 1")
