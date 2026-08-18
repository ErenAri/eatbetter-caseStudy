import pytest

from evals.uncertainty_metrics import (
    ThresholdCase,
    event_rate,
    interval_coverage,
    simulate_thresholds,
    unsafe_auto_accept_rate,
)


def test_interval_coverage_and_unsafe_rate():
    assert interval_coverage([10, 25], [5, 20], [10, 24]) == 0.5
    assert unsafe_auto_accept_rate([True, False, True], [False, True, True]) == 0.5
    assert event_rate(2, 4) == 0.5


def test_threshold_simulation_uses_inclusive_boundaries():
    cases = [
        ThresholdCase(100, 0.20, False),
        ThresholdCase(101, 0.19, True),
        ThresholdCase(99, 0.21, True),
    ]
    result = simulate_thresholds(cases, [(100, 0.20)])[0]
    assert result.auto_accept_rate == pytest.approx(1 / 3)
    assert result.clarification_rate == pytest.approx(2 / 3)
    assert result.unsafe_auto_accept_rate == 0


def test_unlabeled_inputs_are_rejected_instead_of_fabricated():
    with pytest.raises(ValueError):
        simulate_thresholds([], [(100, 0.20)])
