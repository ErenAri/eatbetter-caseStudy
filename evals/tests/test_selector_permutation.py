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


def runs_from(post_gate: dict[str, str], raw: dict[str, str] | None = None) -> list[dict]:
    raw = raw or post_gate
    return [
        {
            "condition": condition,
            "raw_selected_food_id": raw[condition],
            "post_gate_selected_food_id": post_gate[condition],
        }
        for condition in ALL_CONDITIONS
    ]


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
    summary = summarize_item_runs(runs_from(selected), {"1"})

    for mode in ("raw", "post_gate"):
        current = summary[mode]
        assert current["control_stable"] is True
        assert current["control_mode_food_id"] == "1"
        assert current["array_position_sensitive"] is True
        assert current["rank_label_sensitive"] is True
        assert current["control_mode_correct"] is True
        assert current["condition_correctness"]["ARRAY_ROTATE_LEFT"] is False


def test_aggregate_conditions_sensitivity_on_control_stable_items() -> None:
    stable_selected = {condition: "1" for condition in ALL_CONDITIONS}
    stable_selected["RERANK_REVERSED"] = "2"
    unstable_selected = {
        "CONTROL_A": "1",
        "CONTROL_B": "2",
        "CONTROL_C": "1",
        "ARRAY_REVERSED": "2",
        "ARRAY_ROTATE_LEFT": "1",
        "RERANK_REVERSED": "1",
        "RERANK_ROTATE_LEFT": "1",
    }
    items = []
    for selected in (stable_selected, unstable_selected):
        runs = runs_from(selected)
        items.append(
            {
                "acceptable_food_ids": ["1"],
                "runs": runs,
                "summary": summarize_item_runs(runs, {"1"}),
            }
        )

    metrics = aggregate_item_summaries(items)
    gated = metrics["post_gate"]

    assert metrics["eligible_item_count"] == 2
    assert gated["control_repeat_instability"]["value"] == 0.5
    assert gated["control_stable_item_count"] == 1
    assert gated["array_position_sensitivity_control_stable"]["value"] == 0.0
    assert gated["rank_label_sensitivity_control_stable"]["value"] == 1.0


def test_gate_effects_distinguish_blocked_wrong_and_blocked_correct_selection() -> None:
    post = {condition: "1" for condition in ALL_CONDITIONS}
    raw = dict(post)
    raw["ARRAY_REVERSED"] = "2"
    post["ARRAY_REVERSED"] = ABSTAIN_IDENTITY
    raw["RERANK_REVERSED"] = "1"
    post["RERANK_REVERSED"] = ABSTAIN_IDENTITY
    runs = runs_from(post, raw)
    item = {
        "acceptable_food_ids": ["1"],
        "runs": runs,
        "summary": summarize_item_runs(runs, {"1"}),
    }

    effects = aggregate_item_summaries([item])["gate_effects"]

    assert effects["selection_changed_by_gate"]["numerator"] == 2
    assert effects["wrong_selection_blocked"]["numerator"] == 1
    assert effects["correct_selection_blocked"]["numerator"] == 1


def test_abstain_identity_is_explicit_in_summary() -> None:
    selected = {condition: ABSTAIN_IDENTITY for condition in ALL_CONDITIONS}
    summary = summarize_item_runs(runs_from(selected), {"1"})
    assert summary["post_gate"]["control_stable"] is True
    assert summary["post_gate"]["control_mode_food_id"] == ABSTAIN_IDENTITY
    assert summary["post_gate"]["control_mode_correct"] is False
