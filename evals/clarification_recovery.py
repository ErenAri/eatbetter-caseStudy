from __future__ import annotations

from collections import Counter
from enum import StrEnum

from .dataset import CanonicalGroundTruthStatus, EvaluationCase
from .recognition_metrics import normalize_food_name


class RecoveryClassification(StrEnum):
    STRICTLY_RESOLVABLE = "STRICTLY_RESOLVABLE"
    OBSERVED_NAME_ASSOCIATION_GAP_CORRECT_FDC_OFFERED = (
        "OBSERVED_NAME_ASSOCIATION_GAP_CORRECT_FDC_OFFERED"
    )
    CORRECT_FDC_OPTION_PRESENT_BUT_ORACLE_UNRESOLVED = (
        "CORRECT_FDC_OPTION_PRESENT_BUT_ORACLE_UNRESOLVED"
    )
    RETRIEVAL_OPTION_MISS = "RETRIEVAL_OPTION_MISS"
    UNMAPPABLE_TRUTH_REQUIRES_MANUAL_RECOVERY = (
        "UNMAPPABLE_TRUTH_REQUIRES_MANUAL_RECOVERY"
    )
    UNVERIFIED_TRUTH_REQUIRES_MANUAL_RECOVERY = (
        "UNVERIFIED_TRUTH_REQUIRES_MANUAL_RECOVERY"
    )
    NO_CANDIDATES_MANUAL_SEARCH = "NO_CANDIDATES_MANUAL_SEARCH"
    NO_TRUTH_ASSOCIATION_REMOVE_AVAILABLE = "NO_TRUTH_ASSOCIATION_REMOVE_AVAILABLE"
    NO_TRUTH_ASSOCIATION_REMOVE_MISSING = "NO_TRUTH_ASSOCIATION_REMOVE_MISSING"
    AMBIGUOUS_OBSERVED_TRUTH_ASSOCIATION = "AMBIGUOUS_OBSERVED_TRUTH_ASSOCIATION"
    AMBIGUOUS_CANDIDATE_TRUTH_ASSOCIATION = "AMBIGUOUS_CANDIDATE_TRUTH_ASSOCIATION"


def _observed_truth_matches(case: EvaluationCase, observed_name: str | None):
    normalized = normalize_food_name(observed_name or "")
    if not normalized:
        return []
    return [
        item
        for item in case.items
        if normalized
        in {
            normalize_food_name(name)
            for name in (item.label, *item.acceptable_aliases)
        }
    ]


def _option_food_ids(clarification: dict) -> set[str]:
    return {
        str(option["grader_food_id"])
        for option in clarification.get("options", [])
        if option.get("grader_food_id") is not None
    }


def _action_available(clarification: dict, action: str) -> bool:
    return any(
        option.get("value", {}).get("action") == action
        for option in clarification.get("options", [])
    )


def _candidate_truth_matches(case: EvaluationCase, option_ids: set[str]):
    return [
        item
        for item in case.items
        if item.canonical_ground_truth_status == CanonicalGroundTruthStatus.VERIFIED
        and item.acceptable_canonical_ids & option_ids
    ]


def classify_clarification(case: EvaluationCase, clarification: dict) -> dict:
    kind = str(clarification.get("type") or "")
    if kind not in {"CANONICAL_SELECTION", "FOOD_IDENTITY"}:
        raise ValueError(f"unsupported clarification type for recovery trace: {kind}")

    observed_name = clarification.get("observed_name")
    observed_matches = _observed_truth_matches(case, observed_name)
    option_ids = _option_food_ids(clarification)
    candidate_matches = _candidate_truth_matches(case, option_ids)
    manual_search = _action_available(clarification, "MANUAL_SEARCH")
    remove_item = _action_available(clarification, "REMOVE_ITEM")

    if clarification.get("resolvable") is True:
        classification = RecoveryClassification.STRICTLY_RESOLVABLE
    elif kind == "FOOD_IDENTITY":
        if len(observed_matches) > 1:
            classification = RecoveryClassification.AMBIGUOUS_OBSERVED_TRUTH_ASSOCIATION
        elif observed_matches:
            classification = RecoveryClassification.NO_CANDIDATES_MANUAL_SEARCH
        elif remove_item:
            classification = RecoveryClassification.NO_TRUTH_ASSOCIATION_REMOVE_AVAILABLE
        else:
            classification = RecoveryClassification.NO_TRUTH_ASSOCIATION_REMOVE_MISSING
    elif len(observed_matches) > 1:
        classification = RecoveryClassification.AMBIGUOUS_OBSERVED_TRUTH_ASSOCIATION
    elif len(observed_matches) == 1:
        truth = observed_matches[0]
        if truth.canonical_ground_truth_status == CanonicalGroundTruthStatus.VERIFIED:
            if truth.acceptable_canonical_ids & option_ids:
                classification = (
                    RecoveryClassification.CORRECT_FDC_OPTION_PRESENT_BUT_ORACLE_UNRESOLVED
                )
            else:
                classification = RecoveryClassification.RETRIEVAL_OPTION_MISS
        elif truth.canonical_ground_truth_status == CanonicalGroundTruthStatus.UNMAPPABLE:
            classification = RecoveryClassification.UNMAPPABLE_TRUTH_REQUIRES_MANUAL_RECOVERY
        else:
            classification = RecoveryClassification.UNVERIFIED_TRUTH_REQUIRES_MANUAL_RECOVERY
    elif len(candidate_matches) == 1:
        classification = (
            RecoveryClassification.OBSERVED_NAME_ASSOCIATION_GAP_CORRECT_FDC_OFFERED
        )
    elif len(candidate_matches) > 1:
        classification = RecoveryClassification.AMBIGUOUS_CANDIDATE_TRUTH_ASSOCIATION
    elif remove_item:
        classification = RecoveryClassification.NO_TRUTH_ASSOCIATION_REMOVE_AVAILABLE
    else:
        classification = RecoveryClassification.NO_TRUTH_ASSOCIATION_REMOVE_MISSING

    return {
        "classification": str(classification),
        "type": kind,
        "observed_name": observed_name,
        "resolvable": clarification.get("resolvable"),
        "manual_search_available": manual_search,
        "remove_item_available": remove_item,
        "option_food_ids": sorted(option_ids),
        "observed_truth_item_ids": [item.item_id for item in observed_matches],
        "candidate_truth_item_ids": [item.item_id for item in candidate_matches],
    }


def trace_recovery(cases: list[EvaluationCase], records: list[dict], *, configuration: str) -> dict:
    by_case = {record.get("case_id"): record for record in records if record.get("status") == "completed"}
    traces = []
    for case in cases:
        record = by_case.get(case.case_id)
        if record is None:
            continue
        configurations = record.get("configurations", {})
        if configuration not in configurations:
            raise ValueError(f"case {case.case_id} lacks configuration {configuration}")
        for clarification in configurations[configuration].get("clarifications", []):
            if clarification.get("type") not in {"CANONICAL_SELECTION", "FOOD_IDENTITY"}:
                continue
            if clarification.get("resolvable") is not False:
                continue
            trace = classify_clarification(case, clarification)
            trace["case_id"] = case.case_id
            traces.append(trace)

    counts = Counter(trace["classification"] for trace in traces)
    return {
        "unresolved_identity_or_canonical_question_count": len(traces),
        "classification_counts": dict(sorted(counts.items())),
        "traces": traces,
        "notes": [
            "This trace diagnoses unresolved generated identity/canonical questions only.",
            "A correct FDC option can reveal evaluator association undercount without changing primary recognition metrics.",
            "Manual-search availability is a recovery path but does not convert strict clarification_resolvability into a hit.",
            "No semantic aliases or post-hoc acceptable FDC IDs are introduced.",
        ],
    }
