from evals.clarification_recovery import (
    RecoveryClassification,
    classify_clarification,
    trace_recovery,
)
from evals.dataset import DatasetManifest
from evals.tests.test_p8_dataset import manifest, valid_case


def _candidate_option(rank: int, food_id: str) -> dict:
    return {
        "id": f"candidate-{rank}",
        "label": food_id,
        "value": {"candidate_rank": rank},
        "grader_food_id": food_id,
    }


def _manual() -> dict:
    return {
        "id": "manual-search",
        "label": "Search for another food",
        "value": {"action": "MANUAL_SEARCH"},
    }


def _remove() -> dict:
    return {
        "id": "remove-item",
        "label": "This food is not in my meal",
        "value": {"action": "REMOVE_ITEM"},
    }


def _case(**changes):
    return DatasetManifest.model_validate(manifest([valid_case(**changes)])).cases[0]


def test_observed_name_association_gap_is_detected_when_correct_fdc_is_offered() -> None:
    case = _case()
    clarification = {
        "type": "CANONICAL_SELECTION",
        "observed_name": "ripe yellow fruit",
        "resolvable": False,
        "options": [_candidate_option(1, "173944"), _manual()],
    }

    result = classify_clarification(case, clarification)

    assert result["classification"] == str(
        RecoveryClassification.OBSERVED_NAME_ASSOCIATION_GAP_CORRECT_FDC_OFFERED
    )
    assert result["candidate_truth_item_ids"] == ["banana"]


def test_retrieval_option_miss_is_separate_from_name_association() -> None:
    case = _case()
    clarification = {
        "type": "CANONICAL_SELECTION",
        "observed_name": "fresh banana",
        "resolvable": False,
        "options": [_candidate_option(1, "999"), _manual()],
    }

    result = classify_clarification(case, clarification)

    assert result["classification"] == str(RecoveryClassification.RETRIEVAL_OPTION_MISS)
    assert result["manual_search_available"] is True


def test_candidate_clarification_without_truth_association_exposes_missing_remove_recovery() -> None:
    case = _case()
    clarification = {
        "type": "CANONICAL_SELECTION",
        "observed_name": "red bell pepper",
        "resolvable": False,
        "options": [_candidate_option(1, "999"), _manual()],
    }

    result = classify_clarification(case, clarification)

    assert result["classification"] == str(
        RecoveryClassification.NO_TRUTH_ASSOCIATION_REMOVE_MISSING
    )
    assert result["remove_item_available"] is False


def test_remove_recovery_is_reported_without_counting_as_strictly_resolvable() -> None:
    case = _case()
    clarification = {
        "type": "CANONICAL_SELECTION",
        "observed_name": "red bell pepper",
        "resolvable": False,
        "options": [_candidate_option(1, "999"), _manual(), _remove()],
    }

    result = classify_clarification(case, clarification)

    assert result["classification"] == str(
        RecoveryClassification.NO_TRUTH_ASSOCIATION_REMOVE_AVAILABLE
    )
    assert result["resolvable"] is False


def test_unmappable_truth_is_not_called_retrieval_miss() -> None:
    raw = valid_case()
    raw["items"][0]["canonical_ground_truth_status"] = "UNMAPPABLE"
    raw["items"][0]["expected_fdc_id"] = None
    raw["items"][0]["expected_fdc_name"] = None
    case = DatasetManifest.model_validate(manifest([raw])).cases[0]
    clarification = {
        "type": "CANONICAL_SELECTION",
        "observed_name": "fresh banana",
        "resolvable": False,
        "options": [_candidate_option(1, "999"), _manual()],
    }

    result = classify_clarification(case, clarification)

    assert result["classification"] == str(
        RecoveryClassification.UNMAPPABLE_TRUTH_REQUIRES_MANUAL_RECOVERY
    )


def test_trace_only_includes_explicitly_unresolved_identity_or_canonical_questions() -> None:
    case = _case(case_id="meal")
    records = [
        {
            "case_id": "meal",
            "status": "completed",
            "configurations": {
                "HYBRID_AUTO": {
                    "clarifications": [
                        {
                            "type": "CANONICAL_SELECTION",
                            "observed_name": "fresh banana",
                            "resolvable": False,
                            "options": [_candidate_option(1, "999"), _manual()],
                        },
                        {
                            "type": "PORTION",
                            "observed_name": "fresh banana",
                            "resolvable": False,
                            "options": [],
                        },
                        {
                            "type": "CANONICAL_SELECTION",
                            "observed_name": "fresh banana",
                            "resolvable": True,
                            "options": [_candidate_option(1, "173944")],
                        },
                    ]
                }
            },
        }
    ]

    result = trace_recovery([case], records, configuration="HYBRID_AUTO")

    assert result["unresolved_identity_or_canonical_question_count"] == 1
    assert result["classification_counts"] == {"RETRIEVAL_OPTION_MISS": 1}
