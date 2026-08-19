from __future__ import annotations

from uuid import UUID

from app.domain.entities import CanonicalFoodCandidate
from evals.selector_permutation import (
    ABSTAIN_IDENTITY,
    ALL_CONDITIONS,
    aggregate_item_summaries,
    permuted_candidates,
    summarize_item_runs,
)


def candidate(rank: int, food_id: str) -> CanonicalFoodCandidate:
    return CanonicalFoodCandidate(
        meal_item_id=UUID(int=1),
        rank=rank,
        source="USDA_FDC",
        source_food_id=food_id,
        name=f"Food {food_id}",
    )


def test_array_permutation_changes_position_but_preserves_rank_labels() -> None:
    values = [candidate(1, "1"), candidate(2, "2"), candidate(3, "3")]
    reversed_values = permuted_candidates(values, "ARRAY_REVERSED")

    assert [value.source_food_id for value in reversed_values] == ["3", "2", "1"]
    assert [value.rank for value in reversed_values] == [3, 2, 1]


def test_rerank_permutation_reassigns_rank_labels() -> None:
    values = [candidate(1, "1"), candidate(2, "2"), candidate(3, "3")]
    reversed_values = permuted_candidates(values, "RERANK_REVERSED")

    assert [value.source_food_id for value in reversed_values] == ["3", "2", "1"]
    assert [value.rank for value in reversed_values] == [1, 2, 3]


def test_summary_separates_control_noise_array_bias_and_rank_bias() -> None:
    selected = {
        "CONTROL_A": "1",
        "CONTROL_B": "1",
        "CONTROL_C": "1",
        "ARRAY_REVERSED": "1",
        "ARRAY_ROTATE_LEFT": "2",
        "RERANK_REVERSED": "3",
        "RERANK_ROTATE_LEFT": "1",
    }
    runs = [
        {"condition": condition, "post_gate_selected_food_id": selected[condition]}
        for condition in ALL_CONDITIONS
    ]

    summary = summarize_item_runs(runs, {"1"})

    assert summary["control_stable"] is True
    assert summary["control_mode_food_id"] == "1"
    assert summary["array_position_sensitive"] is True
    assert summary["rank_label_sensitive"] is True
    assert summary["control_mode_correct"] is True
    assert summary["condition_correctness"]["ARRAY_ROTATE_LEFT"] is False


def test_aggregate_reports_instability_and_sensitivity_denominators() -> None:
    first = {
        "summary": {
            "control_stable": True,
            "array_position_sensitive": False,
            "rank_label_sensitive": True,
            "control_mode_correct": True,
            "condition_correctness": {condition: True for condition in ALL_CONDITIONS},
        }
    }
    second_correctness = {condition: False for condition in ALL_CONDITIONS}
    second_correctness["CONTROL_A"] = True
    second = {
        "summary": {
            "control_stable": False,
            "array_position_sensitive": True,
            "rank_label_sensitive": False,
            "control_mode_correct": False,
            "condition_correctness": second_correctness,
        }
    }

    metrics = aggregate_item_summaries([first, second])

    assert metrics["eligible_item_count"] == 2
    assert metrics["control_repeat_instability"]["value"] == 0.5
    assert metrics["array_position_sensitivity"]["value"] == 0.5
    assert metrics["rank_label_sensitivity"]["value"] == 0.5
    assert metrics["control_mode_accuracy"]["value"] == 0.5
    assert metrics["condition_accuracy"]["CONTROL_A"]["value"] == 1.0


def test_abstain_identity_is_explicit_in_summary() -> None:
    runs = [
        {"condition": condition, "post_gate_selected_food_id": ABSTAIN_IDENTITY}
        for condition in ALL_CONDITIONS
    ]
    summary = summarize_item_runs(runs, {"1"})
    assert summary["control_stable"] is True
    assert summary["control_mode_food_id"] == ABSTAIN_IDENTITY
    assert summary["control_mode_correct"] is False
