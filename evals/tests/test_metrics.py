import pytest

from evals.metrics import (
    food_set_metrics,
    high_confidence_wrong_rate,
    mean_absolute_error,
    retrieval_recall_at_k,
)


def test_food_set_metrics_penalizes_hallucination_and_miss():
    result = food_set_metrics({"rice", "chicken"}, {"rice", "sauce"})
    assert result.precision == 0.5
    assert result.recall == 0.5
    assert result.f1 == 0.5


def test_numeric_metrics():
    assert mean_absolute_error([100, 200], [110, 180]) == 15
    assert high_confidence_wrong_rate([True, False, False], [0.9, 0.95, 0.2]) == 0.5


def test_retrieval_recall_at_k_preserves_rank_cutoff():
    ranked = ["one", "two", "three", "four", "five"]
    assert retrieval_recall_at_k("three", ranked, 1) == 0
    assert retrieval_recall_at_k("three", ranked, 3) == 1
    with pytest.raises(ValueError):
        retrieval_recall_at_k("three", ranked, 0)
