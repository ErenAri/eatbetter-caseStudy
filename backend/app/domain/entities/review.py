from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from app.domain.enums import ClarificationStatus


@dataclass(slots=True)
class Correction:
    meal_id: UUID
    field_name: str
    predicted_value: Any
    corrected_value: Any
    meal_item_id: UUID | None = None
    correction_source: str = "USER"
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(slots=True)
class Clarification:
    meal_id: UUID
    type: str
    question: str
    reason_codes: tuple[str, ...]
    meal_item_id: UUID | None = None
    options: tuple[dict[str, Any], ...] = ()
    status: ClarificationStatus = ClarificationStatus.PENDING
    answer: dict[str, Any] | None = None
    blocking: bool = True
    stable_key: str | None = None
    resolution_satisfied: bool = False
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    answered_at: datetime | None = None

    def answer_with(self, answer: dict[str, Any], *, resolution_satisfied: bool) -> None:
        if self.status != ClarificationStatus.PENDING:
            raise ValueError("clarification is not pending")
        self.answer = answer
        self.resolution_satisfied = resolution_satisfied
        self.status = ClarificationStatus.ANSWERED
        self.answered_at = datetime.now(timezone.utc)
