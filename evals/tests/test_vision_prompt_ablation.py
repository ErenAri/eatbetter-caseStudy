import pytest

from evals.run_vision_prompt_ablation import (
    BASELINE_NAME,
    CANDIDATE_NAME,
    balanced_variant_order,
    paired_deltas,
    summarize_repeats,
)


def metric(value, numerator=1, denominator=1):
    return {
        "value": value,
        "numerator": numerator,
        "denominator": denominator,
        "unit": "ratio",
        "exclusion": None,
    }


def count_metric(value):
    return {
        "value": float(value),
        "numerator": value,
        "denominator": 10,
        "unit": "count",
        "exclusion": None,
    }


def repeat(*, f1, precision, recall, missed, hallucinated, categories=None):
    categories = categories or {}
    return {
        "strict_metrics": {
            "food_f1": metric(f1),
            "food_precision": metric(precision),
            "food_recall": metric(recall),
            "missed_food_count": count_metric(missed),
            "hallucinated_food_count": count_metric(hallucinated),
        },
        "diagnostic_metrics": {
            "category_event_counts": dict(categories),
            "category_strict_error_units": {
                key: value * 2 for key, value in categories.items()
            },
        },
        "cases": [],
    }


def test_balanced_order_alternates_by_repeat_and_case() -> None:
    assert balanced_variant_order(0, 0) == (BASELINE_NAME, CANDIDATE_NAME)
    assert balanced_variant_order(0, 1) == (CANDIDATE_NAME, BASELINE_NAME)
    assert balanced_variant_order(1, 0) == (CANDIDATE_NAME, BASELINE_NAME)
    assert balanced_variant_order(1, 1) == (BASELINE_NAME, CANDIDATE_NAME)


def test_repeat_summary_keeps_sampling_visible_and_averages_metrics() -> None:
    values = [
        repeat(
            f1=0.50,
            precision=0.40,
            recall=0.67,
            missed=3,
            hallucinated=5,
            categories={"UNDER_SEGMENTATION": 1},
        ),
        repeat(
            f1=0.70,
            precision=0.70,
            recall=0.70,
            missed=2,
            hallucinated=2,
            categories={"UNEXPLAINED_PREDICTION": 2},
        ),
    ]

    summary = summarize_repeats(values)

    assert summary["food_f1"]["values"] == [0.50, 0.70]
    assert summary["food_f1"]["mean"] == pytest.approx(0.60)
    assert summary["missed_food_count"]["mean"] == 2.5
    assert summary["hallucinated_food_count"]["mean"] == 3.5
    assert summary["diagnostic_event_means"]["UNDER_SEGMENTATION"] == 0.5
    assert summary["diagnostic_event_means"]["UNEXPLAINED_PREDICTION"] == 1


def test_paired_deltas_are_candidate_minus_baseline_per_repeat() -> None:
    baseline = [
        repeat(f1=0.50, precision=0.50, recall=0.50, missed=5, hallucinated=5),
        repeat(f1=0.60, precision=0.60, recall=0.60, missed=4, hallucinated=4),
    ]
    candidate = [
        repeat(f1=0.70, precision=0.65, recall=0.75, missed=3, hallucinated=4),
        repeat(f1=0.55, precision=0.58, recall=0.52, missed=5, hallucinated=3),
    ]

    result = paired_deltas(baseline, candidate)

    assert result[0]["food_f1_delta"] == pytest.approx(0.20)
    assert result[0]["missed_food_count_delta"] == -2
    assert result[0]["hallucinated_food_count_delta"] == -1
    assert result[1]["food_f1_delta"] == pytest.approx(-0.05)
    assert result[1]["missed_food_count_delta"] == 1
    assert result[1]["hallucinated_food_count_delta"] == -1


def test_summary_rejects_empty_repeat_set() -> None:
    with pytest.raises(ValueError, match="at least one"):
        summarize_repeats([])


def test_paired_deltas_reject_unpaired_repeat_counts() -> None:
    one = [repeat(f1=0.5, precision=0.5, recall=0.5, missed=1, hallucinated=1)]
    with pytest.raises(ValueError, match="equal lengths"):
        paired_deltas(one, [])
