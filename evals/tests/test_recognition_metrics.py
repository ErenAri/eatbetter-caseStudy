import pytest

from evals.recognition_metrics import (
    ExpectedFood,
    preparation_accuracy,
    recognition_metrics,
)


def test_alias_matching_reports_misses_and_hallucinations() -> None:
    expected = [
        ExpectedFood("chicken", ("grilled chicken breast", "chicken breast")),
        ExpectedFood("white rice", ("cooked rice",)),
        ExpectedFood("broccoli"),
    ]

    metrics = recognition_metrics(expected, ["chicken breast", "cooked rice", "sauce"])

    assert metrics.food_precision == pytest.approx(2 / 3)
    assert metrics.food_recall == pytest.approx(2 / 3)
    assert metrics.food_f1 == pytest.approx(2 / 3)
    assert metrics.hallucinated_food_count == 1
    assert metrics.missed_food_count == 1


def test_hidden_warnings_are_not_part_of_predicted_food_input() -> None:
    metrics = recognition_metrics([ExpectedFood("rice")], ["rice"])
    assert metrics.hallucinated_food_count == 0


def test_preparation_accuracy_skips_unknown_ground_truth() -> None:
    assert preparation_accuracy(["grilled", None], ["grilled", "fried"]) == 1
    with pytest.raises(ValueError):
        preparation_accuracy([None], ["fried"])
