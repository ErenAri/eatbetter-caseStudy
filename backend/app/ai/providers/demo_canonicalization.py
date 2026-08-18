from uuid import UUID

from app.ai.schemas import (
    CanonicalizationDecision,
    CanonicalizationOutput,
    CanonicalizationReason,
    CanonicalizationRequest,
    MatchQuality,
)
from app.domain.entities import CanonicalizationAnalysisResult


class DemoCanonicalizationProvider:
    """Deterministic TEST/DEMO selector; it makes no claim about model accuracy."""

    provider_name = "TEST_DATA"
    model = "deterministic-rank-selector"
    prompt_version = "canonicalization_v1"
    reasoning_effort = "low"

    def __init__(self) -> None:
        self.call_count = 0

    async def select_candidate(
        self,
        *,
        request: CanonicalizationRequest,
        request_id: UUID | None = None,
    ) -> CanonicalizationAnalysisResult:
        self.call_count += 1
        ambiguous = "ambiguous" in request.observed_name.lower()
        output = (
            CanonicalizationOutput(
                decision=CanonicalizationDecision.ABSTAIN,
                selected_candidate_rank=None,
                match_quality=MatchQuality.AMBIGUOUS,
                reason_codes=[CanonicalizationReason.AMBIGUOUS_BETWEEN_CANDIDATES],
            )
            if ambiguous
            else CanonicalizationOutput(
                decision=CanonicalizationDecision.SELECT,
                selected_candidate_rank=request.candidates[0].rank,
                match_quality=MatchQuality.STRONG,
                reason_codes=[CanonicalizationReason.FOOD_IDENTITY_MATCH],
            )
        )
        return CanonicalizationAnalysisResult(
            output=output,
            provider=self.provider_name,
            model=self.model,
            prompt_version=self.prompt_version,
            reasoning_effort=self.reasoning_effort,
        )


class UnconfiguredCanonicalizationProvider:
    provider_name = "OPENAI"
    model = "unconfigured"
    prompt_version = "canonicalization_v1"
    reasoning_effort = "low"

    async def select_candidate(self, **_: object) -> CanonicalizationAnalysisResult:
        from app.ai.canonicalization_errors import CanonicalizationConfigurationError

        raise CanonicalizationConfigurationError(
            "OpenAI canonicalization is selected but OPENAI_API_KEY is not configured."
        )
