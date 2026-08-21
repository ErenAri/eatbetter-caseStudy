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

    def display_name(self) -> str:
        """Return a user-facing label while keeping provenance distinct from match confidence."""
        data = self.data if isinstance(self.data, dict) else {}
        details: list[str] = []
        brand = data.get("brand_owner")
        data_type = data.get("data_type")
        # Distinct from data_type: data_type is a real database field forwarded
        # to the canonicalization selector, while provenance_note is a
        # human-facing label (e.g. the AI-estimate disclaimer) that must never
        # reach the selector. See AINutritionProvider.
        provenance_note = data.get("provenance_note")
        serving = data.get("household_serving_full_text")
        if brand:
            details.append(str(brand))
        elif data_type:
            friendly_types = {
                "foundation": "FoodData Central · Foundation",
                "survey (fndds)": "FoodData Central · FNDDS",
                "sr legacy": "FoodData Central · SR Legacy",
                "branded": "FoodData Central · Branded",
            }
            details.append(friendly_types.get(str(data_type).lower(), str(data_type)))
        elif provenance_note:
            details.append(str(provenance_note))
        if serving:
            details.append(str(serving))
        return self.name if not details else f"{self.name} · {' · '.join(details)}"
