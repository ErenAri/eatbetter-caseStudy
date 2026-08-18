from __future__ import annotations

from dataclasses import dataclass

from app.ai.schemas import MealObservation


SUPPORTED_MEAL_IMAGE_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})


@dataclass(frozen=True, slots=True)
class MealImage:
    content: bytes
    mime_type: str

    def __post_init__(self) -> None:
        if self.mime_type not in SUPPORTED_MEAL_IMAGE_TYPES or not self.content:
            raise ValueError("unsupported or empty meal image")
        valid_signature = (
            self.mime_type == "image/jpeg" and self.content.startswith(b"\xff\xd8\xff")
        ) or (
            self.mime_type == "image/png"
            and self.content.startswith(b"\x89PNG\r\n\x1a\n")
        ) or (
            self.mime_type == "image/webp"
            and len(self.content) >= 12
            and self.content[:4] == b"RIFF"
            and self.content[8:12] == b"WEBP"
        )
        if not valid_signature:
            raise ValueError("meal image signature does not match its MIME type")


@dataclass(frozen=True, slots=True)
class VisionAnalysisResult:
    observation: MealObservation
    provider: str
    model: str
    prompt_version: str
    image_detail: str
    reasoning_effort: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    retry_count: int = 0
