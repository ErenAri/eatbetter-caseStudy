from __future__ import annotations

from dataclasses import asdict, dataclass
from statistics import mean, median
from typing import Iterable

from .canonicalization_metrics import SelectorCaseResult, selector_metrics
from .recognition_metrics import ExpectedFood, normalize_food_name, recognition_metrics


@dataclass(frozen=True)
class MetricValue:
    value: float | None
    numerator: float | int | None
    denominator: float | int
    unit: str
    exclusion: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _paired(expected: Iterable[float | None], predicted: Iterable[float | None]) -> list[tuple[float, float]]:
    return [(float(a), float(b)) for a, b in zip(expected, predicted, strict=True) if a is not None and b is not None]


def absolute_error_metrics(expected: list[float | None], predicted: list[float | None], *, unit: str) -> dict[str, MetricValue]:
    pairs = _paired(expected, predicted)
    errors = [abs(a - b) for a, b in pairs]
    return {
        "mae": MetricValue(mean(errors) if errors else None, sum(errors) if errors else None, len(errors), unit, "null labels or predictions excluded"),
        "median_absolute_error": MetricValue(median(errors) if errors else None, None, len(errors), unit, "null labels or predictions excluded"),
    }


def mape_metric(expected: list[float | None], predicted: list[float | None]) -> MetricValue:
    pairs = [(a, b) for a, b in _paired(expected, predicted) if a != 0]
    errors = [abs(a - b) / a for a, b in pairs]
    return MetricValue(mean(errors) if errors else None, sum(errors) if errors else None, len(errors), "ratio", "null values and true zero denominators excluded")


def portion_metrics(
    truth_g: list[float | None],
    predicted_g: list[float | None],
    lower_g: list[float | None],
    upper_g: list[float | None],
) -> dict[str, dict]:
    if not (len(truth_g) == len(predicted_g) == len(lower_g) == len(upper_g)):
        raise ValueError("portion inputs must have equal lengths")
    output = {key: value.to_dict() for key, value in absolute_error_metrics(truth_g, predicted_g, unit="g").items()}
    output["mape"] = mape_metric(truth_g, predicted_g).to_dict()
    output.update(interval_metrics(truth_g, lower_g, upper_g, unit="g"))
    return output


def interval_metrics(actual: list[float | None], lower: list[float | None], upper: list[float | None], *, unit: str) -> dict[str, dict]:
    if not (len(actual) == len(lower) == len(upper)):
        raise ValueError("interval inputs must have equal lengths")
    intervals = [
        (float(truth), float(low), float(high))
        for truth, low, high in zip(actual, lower, upper, strict=True)
        if truth is not None and low is not None and high is not None
    ]
    if any(high < low for _, low, high in intervals):
        raise ValueError("portion interval upper bound cannot be below lower bound")
    covered = sum(low <= truth <= high for truth, low, high in intervals)
    widths = [high - low for _, low, high in intervals]
    return {
        "interval_coverage": MetricValue(covered / len(intervals) if intervals else None, covered if intervals else None, len(intervals), "ratio", "unmeasured or missing intervals excluded").to_dict(),
        "median_interval_width": MetricValue(median(widths) if widths else None, None, len(widths), unit, "unmeasured or missing intervals excluded").to_dict(),
    }


def retrieval_metrics(labels: list[set[str] | None], ranked_ids: list[list[str]]) -> dict[str, dict]:
    if len(labels) != len(ranked_ids):
        raise ValueError("retrieval inputs must have equal lengths")
    evaluable = [(truth, ranks) for truth, ranks in zip(labels, ranked_ids, strict=True) if truth]
    result: dict[str, dict] = {}
    for k in (1, 3, 5):
        hits = sum(bool(truth & set(ranks[:k])) for truth, ranks in evaluable)
        result[f"recall_at_{k}"] = MetricValue(hits / len(evaluable) if evaluable else None, hits if evaluable else None, len(evaluable), "ratio", "unverified and unmappable labels excluded").to_dict()
    return result


def selector_metric_values(cases: list[SelectorCaseResult]) -> dict[str, dict]:
    if not cases:
        names = ("selection_accuracy", "selective_accuracy", "coverage", "abstention_rate", "wrong_selection_rate", "invalid_rank_rate", "wrong_strong_selection_rate")
        return {name: MetricValue(None, None, 0, "ratio", "retrieval misses, unverified, and unmappable cases excluded").to_dict() for name in names}
    values = selector_metrics(cases)
    total = len(cases)
    selected = sum(case.decision == "SELECT" for case in cases)
    denominators = {"selective_accuracy": selected}
    output = {}
    for name, value in asdict(values).items():
        denominator = denominators.get(name, total)
        output[name] = MetricValue(value, round(value * denominator), denominator, "ratio", "only cases with verified truth present in supplied candidates").to_dict()
    return output


def nutrition_metrics(truth: list[dict | None], predicted: list[dict | None]) -> dict[str, dict]:
    if len(truth) != len(predicted):
        raise ValueError("nutrition inputs must have equal lengths")
    result: dict[str, dict] = {}
    fields = (("calories_kcal", "kcal"), ("protein_g", "g"), ("carbs_g", "g"), ("fat_g", "g"))
    for field, unit in fields:
        expected = [None if row is None else row.get(field) for row in truth]
        guesses = [None if row is None else row.get(field) for row in predicted]
        for metric_name, metric in absolute_error_metrics(expected, guesses, unit=unit).items():
            result[f"{field}_{metric_name}"] = metric.to_dict()
        if field == "calories_kcal":
            result["calorie_mape"] = mape_metric(expected, guesses).to_dict()
            pairs = [(a, b) for a, b in _paired(expected, guesses) if a > 0]
            for band in (10, 20, 30):
                hits = sum(abs(a - b) / a <= band / 100 for a, b in pairs)
                result[f"meals_within_{band}_percent_calories"] = MetricValue(hits / len(pairs) if pairs else None, hits if pairs else None, len(pairs), "ratio", "null values and non-positive calorie truths excluded").to_dict()
    return result


def unsafe_auto_accept_metrics(auto_accepted: list[bool], canonical_correct: list[bool | None], calorie_relative_error: list[float | None]) -> dict[str, dict]:
    if not (len(auto_accepted) == len(canonical_correct) == len(calorie_relative_error)):
        raise ValueError("auto-accept inputs must have equal lengths")
    eligible = [index for index, correct in enumerate(canonical_correct) if correct is not None or calorie_relative_error[index] is not None]
    accepted = [index for index in eligible if auto_accepted[index]]
    unsafe = sum(
        canonical_correct[index] is False
        or (calorie_relative_error[index] is not None and calorie_relative_error[index] > 0.20)
        for index in accepted
    )
    return {
        "unsafe_auto_accept_rate": MetricValue(unsafe / len(accepted) if accepted else None, unsafe if accepted else None, len(accepted), "ratio", "materially wrong means incorrect canonical food or calorie error >20%; unevaluable labels excluded").to_dict(),
        "auto_accept_coverage": MetricValue(len(accepted) / len(eligible) if eligible else None, len(accepted) if eligible else None, len(eligible), "ratio", "unevaluable labels excluded").to_dict(),
    }


def clarification_metrics(clarifications_by_meal: list[list[dict]]) -> dict[str, dict]:
    meal_count = len(clarifications_by_meal)
    blocking_counts = [sum(bool(item.get("blocking", True)) for item in entries) for entries in clarifications_by_meal]
    meals_asked = sum(count > 0 for count in blocking_counts)
    output = {
        "clarification_rate": MetricValue(meals_asked / meal_count if meal_count else None, meals_asked if meal_count else None, meal_count, "ratio").to_dict(),
        "average_blocking_questions_per_meal": MetricValue(sum(blocking_counts) / meal_count if meal_count else None, sum(blocking_counts) if meal_count else None, meal_count, "questions/meal").to_dict(),
    }
    for kind, name in (("PORTION", "portion_clarification_rate"), ("HIDDEN_INGREDIENT", "hidden_ingredient_clarification_rate")):
        hits = sum(any(entry.get("type") == kind for entry in entries) for entries in clarifications_by_meal)
        output[name] = MetricValue(hits / meal_count if meal_count else None, hits if meal_count else None, meal_count, "ratio").to_dict()
    canonical_hits = sum(any(entry.get("type") in {"CANONICAL_SELECTION", "FOOD_IDENTITY"} for entry in entries) for entries in clarifications_by_meal)
    output["canonical_clarification_rate"] = MetricValue(canonical_hits / meal_count if meal_count else None, canonical_hits if meal_count else None, meal_count, "ratio").to_dict()
    generated = [item for entries in clarifications_by_meal for item in entries]
    labeled = [item for item in generated if item.get("resolvable") is not None]
    resolvable = sum(bool(item["resolvable"]) for item in labeled)
    output["clarification_resolvability"] = MetricValue(resolvable / len(labeled) if labeled else None, resolvable if labeled else None, len(labeled), "ratio", "clarifications without grader-resolvability labels excluded").to_dict()
    return output


def hidden_ingredient_metrics(
    expected_by_case: list[list[tuple[str, float | None]]],
    predicted_by_case: list[list[str]],
) -> dict[str, dict]:
    if len(expected_by_case) != len(predicted_by_case):
        raise ValueError("hidden ingredient inputs must have equal lengths")

    total = 0
    matched = 0
    measured_kcal = 0.0
    matched_kcal = 0.0
    for expected, predicted in zip(expected_by_case, predicted_by_case, strict=True):
        predicted_names = {normalize_food_name(name) for name in predicted}
        for name, calories_kcal in expected:
            total += 1
            hit = normalize_food_name(name) in predicted_names
            matched += int(hit)
            if calories_kcal is not None:
                calories = float(calories_kcal)
                measured_kcal += calories
                if hit:
                    matched_kcal += calories

    return {
        "recall_all": MetricValue(
            matched / total if total else None,
            matched if total else None,
            total,
            "ratio",
            "only ground-truth hidden ingredients marked present are evaluated",
        ).to_dict(),
        "calorie_weighted_coverage": MetricValue(
            matched_kcal / measured_kcal if measured_kcal > 0 else None,
            matched_kcal if measured_kcal > 0 else None,
            measured_kcal,
            "ratio",
            "hidden ingredients without calorie truth are excluded; denominator is total measured hidden kcal",
        ).to_dict(),
    }


def latency_metrics(stage_values_ms: dict[str, list[float | None]]) -> dict[str, dict]:
    output: dict[str, dict] = {}
    for stage, raw in stage_values_ms.items():
        values = sorted(float(value) for value in raw if value is not None)
        for percentile, fraction in (("p50", 0.50), ("p95", 0.95)):
            index = max(0, min(len(values) - 1, int((len(values) - 1) * fraction + 0.999999))) if values else 0
            output[f"{stage}_{percentile}_latency_ms"] = MetricValue(values[index] if values else None, None, len(values), "ms", "missing timings excluded").to_dict()
    return output


def recognition_metric_values(expected_by_case: list[list[ExpectedFood]], predicted_by_case: list[list[str]]) -> dict[str, dict]:
    if len(expected_by_case) != len(predicted_by_case):
        raise ValueError("recognition inputs must have equal lengths")
    case_values = [recognition_metrics(expected, predicted) for expected, predicted in zip(expected_by_case, predicted_by_case, strict=True)]
    expected_count = sum(len(case) for case in expected_by_case)
    predicted_count = sum(len(case) for case in predicted_by_case)
    missed = sum(value.missed_food_count for value in case_values)
    hallucinated = sum(value.hallucinated_food_count for value in case_values)
    tp = expected_count - missed
    precision = tp / predicted_count if predicted_count else (1.0 if not expected_count else 0.0)
    recall = tp / expected_count if expected_count else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "food_precision": MetricValue(precision, tp, predicted_count, "ratio").to_dict(),
        "food_recall": MetricValue(recall, tp, expected_count, "ratio").to_dict(),
        "food_f1": MetricValue(f1, None, expected_count, "ratio", "derived harmonic mean").to_dict(),
        "hallucinated_food_count": MetricValue(float(hallucinated), hallucinated, predicted_count, "count").to_dict(),
        "missed_food_count": MetricValue(float(missed), missed, expected_count, "count").to_dict(),
    }


def baseline_comparison(baseline: dict[str, dict], hybrid: dict[str, dict], metric_names: list[str]) -> dict[str, dict]:
    output = {}
    for name in metric_names:
        before = baseline.get(name, {}).get("value")
        after = hybrid.get(name, {}).get("value")
        output[name] = {"baseline": before, "hybrid": after, "delta": None if before is None or after is None else after - before}
    return output
