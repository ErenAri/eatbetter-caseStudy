from __future__ import annotations

from collections import Counter
from dataclasses import replace
from typing import Any

from app.ai.schemas import CanonicalizationCandidate, CanonicalizationOutput
from app.application.services.meal_canonicalization_service import MealCanonicalizationService


CONTROL_CONDITIONS = ("CONTROL_A", "CONTROL_B", "CONTROL_C")
ARRAY_CONDITIONS = ("ARRAY_REVERSED", "ARRAY_ROTATE_LEFT")
RERANK_CONDITIONS = ("RERANK_REVERSED", "RERANK_ROTATE_LEFT")
ALL_CONDITIONS = CONTROL_CONDITIONS + ARRAY_CONDITIONS + RERANK_CONDITIONS
ABSTAIN_IDENTITY = "__ABSTAIN__"


def permuted_candidates(candidates: list[Any], condition: str) -> list[Any]:
    """Return one candidate presentation variant.

    ARRAY_* changes JSON array order while preserving the existing rank labels.
    RERANK_* changes the ordering and reassigns ranks 1..N, matching the signal a
    different retrieval ranker would expose to the selector.
    """
    if condition in CONTROL_CONDITIONS:
        return list(candidates)
    if condition == "ARRAY_REVERSED":
        return list(reversed(candidates))
    if condition == "ARRAY_ROTATE_LEFT":
        return _rotate_left(candidates)
    if condition == "RERANK_REVERSED":
        return _renumber(list(reversed(candidates)))
    if condition == "RERANK_ROTATE_LEFT":
        return _renumber(_rotate_left(candidates))
    raise ValueError(f"unknown selector permutation condition: {condition}")


def candidate_input(candidate: Any) -> CanonicalizationCandidate:
    data = candidate.data if isinstance(candidate.data, dict) else {}

    def optional_text(key: str) -> str | None:
        value = data.get(key)
        return str(value) if value is not None else None

    return CanonicalizationCandidate(
        rank=candidate.rank,
        name=candidate.name,
        data_type=optional_text("data_type"),
        brand_owner=optional_text("brand_owner"),
        household_serving_full_text=optional_text("household_serving_full_text"),
    )


def selected_identity(output: CanonicalizationOutput, candidates: list[Any]) -> str:
    if output.selected_candidate_rank is None:
        return ABSTAIN_IDENTITY
    selected = next(
        (candidate for candidate in candidates if candidate.rank == output.selected_candidate_rank),
        None,
    )
    return selected.source_food_id if selected is not None else "__INVALID_RANK__"


def post_gate_identity(item: Any, output: CanonicalizationOutput, candidates: list[Any]) -> str:
    if output.selected_candidate_rank is None:
        return ABSTAIN_IDENTITY
    if not MealCanonicalizationService._selection_passes_deterministic_gate(
        item, candidates, output
    ):
        return ABSTAIN_IDENTITY
    return selected_identity(output, candidates)


def summarize_item_runs(runs: list[dict], acceptable_ids: set[str]) -> dict:
    by_condition = {run["condition"]: run for run in runs}
    return {
        "raw": _summarize_identity_field(
            by_condition, "raw_selected_food_id", acceptable_ids
        ),
        "post_gate": _summarize_identity_field(
            by_condition, "post_gate_selected_food_id", acceptable_ids
        ),
    }


def aggregate_item_summaries(items: list[dict]) -> dict:
    return {
        "eligible_item_count": len(items),
        "raw": _aggregate_mode(items, "raw"),
        "post_gate": _aggregate_mode(items, "post_gate"),
        "gate_effects": _gate_effects(items),
    }


def _summarize_identity_field(
    by_condition: dict[str, dict], field: str, acceptable_ids: set[str]
) -> dict:
    control_ids = [by_condition[name][field] for name in CONTROL_CONDITIONS]
    control_mode = _mode(control_ids)
    array_ids = [by_condition[name][field] for name in ARRAY_CONDITIONS]
    rerank_ids = [by_condition[name][field] for name in RERANK_CONDITIONS]
    return {
        "control_selected_food_ids": control_ids,
        "control_mode_food_id": control_mode,
        "control_stable": len(set(control_ids)) == 1,
        "array_selected_food_ids": array_ids,
        "array_position_sensitive": any(value != control_mode for value in array_ids),
        "rerank_selected_food_ids": rerank_ids,
        "rank_label_sensitive": any(value != control_mode for value in rerank_ids),
        "control_mode_correct": control_mode in acceptable_ids,
        "condition_correctness": {
            name: by_condition[name][field] in acceptable_ids for name in ALL_CONDITIONS
        },
    }


def _aggregate_mode(items: list[dict], mode: str) -> dict:
    summaries = [item["summary"][mode] for item in items]
    denominator = len(summaries)
    stable = [summary for summary in summaries if summary["control_stable"]]
    condition_accuracy = {}
    for condition in ALL_CONDITIONS:
        hits = sum(summary["condition_correctness"][condition] for summary in summaries)
        condition_accuracy[condition] = _ratio(hits, denominator)

    return {
        "control_repeat_instability": _ratio(
            sum(not summary["control_stable"] for summary in summaries), denominator
        ),
        "array_position_sensitivity": _ratio(
            sum(summary["array_position_sensitive"] for summary in summaries), denominator
        ),
        "rank_label_sensitivity": _ratio(
            sum(summary["rank_label_sensitive"] for summary in summaries), denominator
        ),
        "control_mode_accuracy": _ratio(
            sum(summary["control_mode_correct"] for summary in summaries), denominator
        ),
        "control_stable_item_count": len(stable),
        "array_position_sensitivity_control_stable": _ratio(
            sum(summary["array_position_sensitive"] for summary in stable), len(stable)
        ),
        "rank_label_sensitivity_control_stable": _ratio(
            sum(summary["rank_label_sensitive"] for summary in stable), len(stable)
        ),
        "condition_accuracy": condition_accuracy,
    }


def _gate_effects(items: list[dict]) -> dict:
    total_runs = 0
    changed = 0
    blocked_wrong = 0
    blocked_correct = 0
    for item in items:
        acceptable_ids = set(item.get("acceptable_food_ids", []))
        for run in item["runs"]:
            total_runs += 1
            raw = run["raw_selected_food_id"]
            post = run["post_gate_selected_food_id"]
            if raw != post:
                changed += 1
            if post == ABSTAIN_IDENTITY and raw != ABSTAIN_IDENTITY:
                if raw in acceptable_ids:
                    blocked_correct += 1
                else:
                    blocked_wrong += 1
    return {
        "selection_changed_by_gate": _ratio(changed, total_runs),
        "wrong_selection_blocked": _ratio(blocked_wrong, total_runs),
        "correct_selection_blocked": _ratio(blocked_correct, total_runs),
    }


def _rotate_left(values: list[Any]) -> list[Any]:
    if len(values) < 2:
        return list(values)
    return [*values[1:], values[0]]


def _renumber(values: list[Any]) -> list[Any]:
    return [replace(candidate, rank=index) for index, candidate in enumerate(values, start=1)]


def _mode(values: list[str]) -> str:
    counts = Counter(values)
    first_index = {value: values.index(value) for value in counts}
    return min(counts, key=lambda value: (-counts[value], first_index[value]))


def _ratio(numerator: int, denominator: int) -> dict:
    return {
        "value": numerator / denominator if denominator else None,
        "numerator": numerator,
        "denominator": denominator,
        "unit": "ratio",
    }
