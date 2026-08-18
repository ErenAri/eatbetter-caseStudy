from uuid import UUID

import pytest
from pydantic import ValidationError

from app.ai.schemas import (
    CanonicalizationCandidate,
    CanonicalizationOutput,
    CanonicalizationRequest,
)


def test_valid_select_and_abstain() -> None:
    selected = CanonicalizationOutput(
        decision="SELECT",
        selected_candidate_rank=2,
        match_quality="EXACT",
        reason_codes=["EXACT_DESCRIPTION_MATCH", "PREPARATION_MATCH"],
    )
    abstained = CanonicalizationOutput(
        decision="ABSTAIN",
        selected_candidate_rank=None,
        match_quality="AMBIGUOUS",
        reason_codes=["AMBIGUOUS_BETWEEN_CANDIDATES"],
    )
    assert selected.selected_candidate_rank == 2
    assert abstained.selected_candidate_rank is None


@pytest.mark.parametrize(
    "payload",
    [
        {"decision": "SELECT", "selected_candidate_rank": None, "match_quality": "STRONG"},
        {"decision": "SELECT", "selected_candidate_rank": 1, "match_quality": "AMBIGUOUS"},
        {"decision": "ABSTAIN", "selected_candidate_rank": 1, "match_quality": "NO_MATCH"},
        {"decision": "ABSTAIN", "selected_candidate_rank": None, "match_quality": "EXACT"},
    ],
)
def test_decision_invariants_reject_inconsistent_output(payload: dict) -> None:
    with pytest.raises(ValidationError):
        CanonicalizationOutput.model_validate({**payload, "reason_codes": []})


@pytest.mark.parametrize("field", ["fdc_id", "canonical_name", "calories", "protein", "fat", "carbs"])
def test_selector_output_forbids_ids_names_and_nutrition(field: str) -> None:
    with pytest.raises(ValidationError):
        CanonicalizationOutput.model_validate(
            {
                "decision": "SELECT",
                "selected_candidate_rank": 1,
                "match_quality": "STRONG",
                "reason_codes": ["FOOD_IDENTITY_MATCH"],
                field: 500,
            }
        )


def test_request_candidate_contains_only_allowlisted_identity_metadata() -> None:
    request = CanonicalizationRequest(
        meal_item_id=UUID(int=1),
        observed_name="rice",
        preparation_method="cooked",
        user_context=None,
        candidates=[
            CanonicalizationCandidate(
                rank=1,
                name="Rice, cooked",
                data_type="Foundation",
                brand_owner=None,
                household_serving_full_text="1 cup",
            )
        ],
    )
    keys = set(request.candidates[0].model_dump())
    assert keys == {
        "rank",
        "name",
        "data_type",
        "brand_owner",
        "household_serving_full_text",
    }


def test_server_rank_validation_never_falls_back() -> None:
    output = CanonicalizationOutput(
        decision="SELECT",
        selected_candidate_rank=4,
        match_quality="STRONG",
        reason_codes=["FOOD_IDENTITY_MATCH"],
    )
    with pytest.raises(ValueError):
        output.validate_against_supplied_ranks({1, 2, 3})
