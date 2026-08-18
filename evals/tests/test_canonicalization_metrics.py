import pytest

from evals.canonicalization_metrics import (
    SelectorCaseResult,
    selector_metrics,
    usda_top_1_accuracy,
)


def test_selector_metrics_expose_accuracy_coverage_and_invalid_ranks() -> None:
    cases = [
        SelectorCaseResult(1, frozenset({1, 2}), "SELECT", 1, "STRONG"),
        SelectorCaseResult(2, frozenset({1, 2}), "SELECT", 1, "STRONG"),
        SelectorCaseResult(1, frozenset({1, 2}), "ABSTAIN", None, "AMBIGUOUS"),
        SelectorCaseResult(1, frozenset({1, 2}), "SELECT", 3, "STRONG"),
    ]
    metrics = selector_metrics(cases)
    assert metrics.selection_accuracy == 0.25
    assert metrics.selective_accuracy == pytest.approx(1 / 3)
    assert metrics.coverage == 0.75
    assert metrics.abstention_rate == 0.25
    assert metrics.wrong_selection_rate == 0.25
    assert metrics.invalid_rank_rate == 0.25
    assert metrics.wrong_strong_selection_rate == 0.25


def test_usda_top_one_baseline_and_unverified_guard() -> None:
    assert usda_top_1_accuracy([1, 2, 1]) == pytest.approx(2 / 3)
    with pytest.raises(ValueError):
        usda_top_1_accuracy([])
    with pytest.raises(ValueError):
        selector_metrics([])
