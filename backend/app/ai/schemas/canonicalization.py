from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CanonicalizationDecision(StrEnum):
    SELECT = "SELECT"
    ABSTAIN = "ABSTAIN"


class MatchQuality(StrEnum):
    EXACT = "EXACT"
    STRONG = "STRONG"
    AMBIGUOUS = "AMBIGUOUS"
    NO_MATCH = "NO_MATCH"


class CanonicalizationReason(StrEnum):
    EXACT_DESCRIPTION_MATCH = "EXACT_DESCRIPTION_MATCH"
    FOOD_IDENTITY_MATCH = "FOOD_IDENTITY_MATCH"
    PREPARATION_MATCH = "PREPARATION_MATCH"
    GENERIC_VARIANT_MATCH = "GENERIC_VARIANT_MATCH"
    AMBIGUOUS_BETWEEN_CANDIDATES = "AMBIGUOUS_BETWEEN_CANDIDATES"
    INSUFFICIENT_OBSERVATION = "INSUFFICIENT_OBSERVATION"
    PREPARATION_CONFLICT = "PREPARATION_CONFLICT"
    BRANDED_MISMATCH = "BRANDED_MISMATCH"
    COMPOSITE_FOOD_MISMATCH = "COMPOSITE_FOOD_MISMATCH"
    NO_SUITABLE_CANDIDATE = "NO_SUITABLE_CANDIDATE"


class StrictCanonicalizationModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class CanonicalizationCandidate(StrictCanonicalizationModel):
    rank: int = Field(ge=1, le=20)
    name: str = Field(min_length=1, max_length=300)
    data_type: str | None = Field(default=None, max_length=100)
    brand_owner: str | None = Field(default=None, max_length=200)
    household_serving_full_text: str | None = Field(default=None, max_length=200)


class CanonicalizationRequest(StrictCanonicalizationModel):
    meal_item_id: UUID
    observed_name: str = Field(min_length=1, max_length=200)
    preparation_method: str | None = Field(default=None, max_length=100)
    user_context: str | None = Field(default=None, max_length=1000)
    candidates: list[CanonicalizationCandidate] = Field(min_length=1, max_length=5)


class CanonicalizationOutput(StrictCanonicalizationModel):
    decision: CanonicalizationDecision
    selected_candidate_rank: int | None = Field(default=None, ge=1, le=20)
    match_quality: MatchQuality
    reason_codes: list[CanonicalizationReason] = Field(default_factory=list, max_length=5)

    @model_validator(mode="after")
    def validate_decision(self) -> "CanonicalizationOutput":
        if self.decision == CanonicalizationDecision.SELECT:
            if self.selected_candidate_rank is None:
                raise ValueError("SELECT requires selected_candidate_rank")
            if self.match_quality not in {MatchQuality.EXACT, MatchQuality.STRONG}:
                raise ValueError("SELECT requires EXACT or STRONG match quality")
        else:
            if self.selected_candidate_rank is not None:
                raise ValueError("ABSTAIN forbids selected_candidate_rank")
            if self.match_quality not in {MatchQuality.AMBIGUOUS, MatchQuality.NO_MATCH}:
                raise ValueError("ABSTAIN requires AMBIGUOUS or NO_MATCH match quality")
        return self

    def validate_against_supplied_ranks(self, supplied_ranks: set[int]) -> None:
        if (
            self.selected_candidate_rank is not None
            and self.selected_candidate_rank not in supplied_ranks
        ):
            raise ValueError("selected_candidate_rank was not present in supplied candidates")
