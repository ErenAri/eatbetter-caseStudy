from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4


@dataclass(slots=True)
class AIRun:
    meal_id: UUID
    stage: str
    provider: str
    model: str
    prompt_version: str
    status: str = "STARTED"
    id: UUID = field(default_factory=uuid4)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    latency_ms: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated_cost_usd: Decimal | None = None
    request_id: UUID | None = None
    error_code: str | None = None
    structured_output: dict[str, Any] | None = None
    image_detail: str | None = None
    reasoning_effort: str | None = None
    retry_count: int = 0

    def succeed(
        self,
        *,
        latency_ms: int,
        input_tokens: int | None,
        output_tokens: int | None,
        structured_output: dict[str, Any],
        retry_count: int,
    ) -> None:
        self.status = "SUCCEEDED"
        self.completed_at = datetime.now(timezone.utc)
        self.latency_ms = max(latency_ms, 0)
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.structured_output = structured_output
        self.retry_count = retry_count

    def fail(self, *, latency_ms: int, error_code: str, retry_count: int) -> None:
        self.status = "FAILED"
        self.completed_at = datetime.now(timezone.utc)
        self.latency_ms = max(latency_ms, 0)
        self.error_code = error_code
        self.retry_count = retry_count
