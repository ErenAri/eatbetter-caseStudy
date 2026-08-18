from dataclasses import dataclass

from app.ai.schemas import CanonicalizationOutput


@dataclass(frozen=True, slots=True)
class CanonicalizationAnalysisResult:
    output: CanonicalizationOutput
    provider: str
    model: str
    prompt_version: str
    reasoning_effort: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    retry_count: int = 0
