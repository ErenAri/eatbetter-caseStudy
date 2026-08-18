from dataclasses import dataclass


@dataclass(frozen=True)
class ThresholdCase:
    absolute_calorie_uncertainty: float
    relative_calorie_uncertainty: float
    materially_wrong: bool


@dataclass(frozen=True)
class ThresholdResult:
    absolute_threshold: float
    relative_threshold: float
    auto_accept_rate: float
    clarification_rate: float
    unsafe_auto_accept_rate: float


def interval_coverage(actual: list[float], lower: list[float], upper: list[float]) -> float:
    if not actual or len(actual) != len(lower) or len(actual) != len(upper):
        raise ValueError("interval coverage requires non-empty, equal-length labels")
    if any(high < low for low, high in zip(lower, upper, strict=True)):
        raise ValueError("interval upper bounds cannot be below lower bounds")
    return sum(low <= value <= high for value, low, high in zip(actual, lower, upper, strict=True)) / len(actual)


def unsafe_auto_accept_rate(auto_accepted: list[bool], materially_wrong: list[bool]) -> float:
    if len(auto_accepted) != len(materially_wrong) or not auto_accepted:
        raise ValueError("unsafe auto-accept rate requires non-empty, equal-length labels")
    accepted = [wrong for accepted, wrong in zip(auto_accepted, materially_wrong, strict=True) if accepted]
    return sum(accepted) / len(accepted) if accepted else 0.0


def event_rate(event_count: int, eligible_count: int) -> float:
    if event_count < 0 or eligible_count <= 0 or event_count > eligible_count:
        raise ValueError("event rate requires 0 <= events <= eligible and eligible > 0")
    return event_count / eligible_count


def simulate_thresholds(
    cases: list[ThresholdCase],
    thresholds: list[tuple[float, float]],
) -> list[ThresholdResult]:
    if not cases:
        raise ValueError("threshold simulation requires verified cases")
    results: list[ThresholdResult] = []
    for absolute, relative in thresholds:
        if absolute < 0 or relative < 0:
            raise ValueError("thresholds cannot be negative")
        accepted = [
            case.absolute_calorie_uncertainty <= absolute
            and case.relative_calorie_uncertainty <= relative
            for case in cases
        ]
        auto_rate = sum(accepted) / len(cases)
        results.append(ThresholdResult(
            absolute_threshold=absolute,
            relative_threshold=relative,
            auto_accept_rate=auto_rate,
            clarification_rate=1 - auto_rate,
            unsafe_auto_accept_rate=unsafe_auto_accept_rate(
                accepted, [case.materially_wrong for case in cases]
            ),
        ))
    return results
