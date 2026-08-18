from __future__ import annotations

from collections import Counter

from .benchmark_metrics import (
    clarification_metrics,
    interval_metrics,
    latency_metrics,
    nutrition_metrics,
    portion_metrics,
    recognition_metric_values,
    retrieval_metrics,
    selector_metric_values,
    unsafe_auto_accept_metrics,
)
from .canonicalization_metrics import SelectorCaseResult
from .dataset import CanonicalGroundTruthStatus, EvaluationCase
from .metrics import ERROR_TAXONOMY
from .recognition_metrics import ExpectedFood, normalize_food_name


def _truth_match(name: str, case: EvaluationCase, used: set[str] | None = None):
    normalized = normalize_food_name(name)
    return next((item for item in case.items if (used is None or item.item_id not in used) and normalized in {normalize_food_name(value) for value in (item.label, *item.acceptable_aliases)}), None)


def _matched_items(case: EvaluationCase, predicted: list[dict]):
    used: set[str] = set()
    pairs = []
    for item in predicted:
        truth = _truth_match(str(item.get("observed_name", "")), case, used)
        if truth:
            used.add(truth.item_id)
        pairs.append((truth, item))
    return pairs, used


def score_configuration(cases: list[EvaluationCase], records: list[dict], configuration: str) -> tuple[dict, list[dict]]:
    by_id = {record["case_id"]: record for record in records if record.get("status") == "completed"}
    completed_cases = [case for case in cases if case.case_id in by_id]
    predicted_by_case = [by_id[case.case_id]["recognition_items"] for case in completed_cases]
    recognition = recognition_metric_values(
        [[ExpectedFood(item.label, tuple(item.acceptable_aliases)) for item in case.items] for case in completed_cases],
        [[item["observed_name"] for item in predicted] for predicted in predicted_by_case],
    )
    preparation_pairs = []
    for case in completed_cases:
        for truth, predicted in _matched_items(case, by_id[case.case_id]["recognition_items"])[0]:
            if truth is not None and truth.preparation is not None:
                preparation_pairs.append((truth.preparation, predicted.get("preparation_method")))
    preparation_hits = sum(normalize_food_name(truth) == normalize_food_name(predicted or "") for truth, predicted in preparation_pairs)
    recognition["preparation_accuracy"] = {
        "value": preparation_hits / len(preparation_pairs) if preparation_pairs else None,
        "numerator": preparation_hits if preparation_pairs else None,
        "denominator": len(preparation_pairs),
        "unit": "ratio",
        "exclusion": "unlabeled preparation and unmatched recognition items excluded",
    }

    category_metrics = {}
    for category in sorted({str(category) for case in completed_cases for category in case.categories}):
        sliced = [case for case in completed_cases if category in {str(value) for value in case.categories}]
        category_metrics[category] = recognition_metric_values(
            [[ExpectedFood(item.label, tuple(item.acceptable_aliases)) for item in case.items] for case in sliced],
            [[item["observed_name"] for item in by_id[case.case_id]["recognition_items"]] for case in sliced],
        )
        category_preparation = []
        for case in sliced:
            for truth, predicted in _matched_items(case, by_id[case.case_id]["recognition_items"])[0]:
                if truth is not None and truth.preparation is not None:
                    category_preparation.append((truth.preparation, predicted.get("preparation_method")))
        category_hits = sum(normalize_food_name(truth) == normalize_food_name(predicted or "") for truth, predicted in category_preparation)
        category_metrics[category]["preparation_accuracy"] = {
            "value": category_hits / len(category_preparation) if category_preparation else None,
            "numerator": category_hits if category_preparation else None,
            "denominator": len(category_preparation),
            "unit": "ratio",
            "exclusion": "unlabeled preparation and unmatched recognition items excluded",
        }

    retrieval_labels: list[set[str] | None] = []
    retrieval_ranks: list[list[str]] = []
    selector_cases: list[SelectorCaseResult] = []
    truth_portions: list[float | None] = []
    predicted_portions: list[float | None] = []
    lower_portions: list[float | None] = []
    upper_portions: list[float | None] = []
    auto_flags: list[bool] = []
    canonical_correct: list[bool | None] = []
    item_calorie_errors: list[float | None] = []
    truth_nutrition: list[dict | None] = []
    predicted_nutrition: list[dict | None] = []
    calorie_lower: list[float | None] = []
    calorie_upper: list[float | None] = []
    clarifications: list[list[dict]] = []
    latencies: dict[str, list[float | None]] = {"vision": [], "retrieval": [], "canonicalization": [], "total": []}
    errors: list[dict] = []

    for case in completed_cases:
        record = by_id[case.case_id]
        output = record["configurations"][configuration]
        pairs, matched_ids = _matched_items(case, output["items"])
        recognition_pairs, recognition_matched_ids = _matched_items(case, record["recognition_items"])
        verified_results: list[bool] = []
        for truth in case.items:
            if truth.item_id not in recognition_matched_ids:
                errors.append(_error(case, "recognition", "MISSED_FOOD", truth.label, None))
        seen_names: set[str] = set()
        for _, recognized in recognition_pairs:
            normalized_name = normalize_food_name(recognized.get("observed_name", ""))
            if normalized_name in seen_names:
                errors.append(_error(case, "recognition", "DUPLICATE_ITEM", None, recognized.get("observed_name")))
            seen_names.add(normalized_name)
        suggested_hidden = {normalize_food_name(value) for value in record.get("possible_hidden_ingredients", [])}
        for hidden in case.hidden_ingredients:
            if hidden.present and normalize_food_name(hidden.name) not in suggested_hidden:
                errors.append(_error(case, "recognition", "HIDDEN_INGREDIENT", hidden.name, None))
        for truth, item in pairs:
            if truth is None:
                continue
            ranked = [str(candidate["food_id"]) for candidate in item.get("candidates", [])]
            label = truth.acceptable_canonical_ids if truth.canonical_ground_truth_status == CanonicalGroundTruthStatus.VERIFIED else None
            retrieval_labels.append(label)
            retrieval_ranks.append(ranked)
            if label:
                expected_rank = next((index + 1 for index, food_id in enumerate(ranked) if food_id in label), None)
                if expected_rank is None or expected_rank > 5:
                    errors.append(_error(case, "retrieval", "RETRIEVAL_MISS", sorted(label), ranked[:5]))
                else:
                    selected_rank = item.get("selected_rank")
                    selected_food_id = item.get("selected_food_id")
                    acceptable_ranks = [index + 1 for index, food_id in enumerate(ranked) if food_id in label]
                    expected_rank = selected_rank if selected_food_id in label else min(acceptable_ranks)
                    decision = "SELECT" if selected_rank is not None else "ABSTAIN"
                    selector_cases.append(SelectorCaseResult(expected_rank, frozenset(range(1, min(5, len(ranked)) + 1)), decision, selected_rank, str(item.get("match_quality") or "NO_MATCH")))
                    if selected_rank is None:
                        errors.append(_error(case, "canonicalization", "SELECTOR_UNNECESSARY_ABSTAIN", expected_rank, None))
                    elif selected_rank != expected_rank:
                        errors.append(_error(case, "canonicalization", "SELECTOR_WRONG", expected_rank, selected_rank))
            truth_value = float(truth.portion_truth_g) if truth.portion_truth_g is not None else None
            predicted_value = item.get("confirmed_portion_g")
            truth_portions.append(truth_value)
            predicted_portions.append(predicted_value)
            lower_portions.append(item.get("portion_min_g"))
            upper_portions.append(item.get("portion_max_g"))
            if truth_value is not None and predicted_value is not None and truth_value > 0 and abs(predicted_value - truth_value) / truth_value > 0.20:
                errors.append(_error(case, "portion", "WRONG_PORTION", truth_value, predicted_value))
            selected = item.get("selected_food_id")
            correct = None if not label else selected in label
            if correct is not None:
                verified_results.append(correct)
        for truth, recognized in recognition_pairs:
            if truth is None:
                errors.append(_error(case, "recognition", "HALLUCINATED_FOOD", None, recognized.get("observed_name")))
            elif truth.preparation is not None and normalize_food_name(truth.preparation) != normalize_food_name(recognized.get("preparation_method") or ""):
                errors.append(_error(case, "recognition", "WRONG_COOKING_METHOD", truth.preparation, recognized.get("preparation_method")))
        truth_nutrition.append(case.nutrition_truth.model_dump(mode="json", exclude={"measurement_method"}) if case.nutrition_truth else None)
        predicted_nutrition.append(output.get("nutrition_totals"))
        interval_items = [item for item in output["items"] if not item.get("removed")]
        has_calorie_interval = all(
            item.get("nutrition_per_100g") is not None
            and item.get("nutrition_per_100g", {}).get("calories_kcal") is not None
            and item.get("portion_min_g") is not None
            and item.get("portion_max_g") is not None
            for item in interval_items
        )
        calorie_lower.append(sum(item["nutrition_per_100g"]["calories_kcal"] * item["portion_min_g"] / 100 for item in interval_items) if interval_items and has_calorie_interval else None)
        calorie_upper.append(sum(item["nutrition_per_100g"]["calories_kcal"] * item["portion_max_g"] / 100 for item in interval_items) if interval_items and has_calorie_interval else None)
        active_items = [item for item in output["items"] if not item.get("removed")]
        auto_flags.append(bool(active_items) and all(
            item.get("portion_resolution_source") in {"AUTO_ESTIMATE", "BASELINE_MIDPOINT"}
            and item.get("selected_food_id") is not None
            for item in active_items
        ) and not any(item.get("blocking", True) and item.get("status") == "PENDING" for item in output.get("clarifications", [])))
        missing_verified = any(
            truth.canonical_ground_truth_status == CanonicalGroundTruthStatus.VERIFIED
            and truth.item_id not in matched_ids
            for truth in case.items
        )
        canonical_correct.append(False if missing_verified or any(not value for value in verified_results) else (True if verified_results else None))
        truth_calories = float(case.nutrition_truth.calories_kcal) if case.nutrition_truth and case.nutrition_truth.calories_kcal is not None else None
        predicted_totals = output.get("nutrition_totals")
        predicted_calories = predicted_totals.get("calories_kcal") if predicted_totals else None
        item_calorie_errors.append(abs(predicted_calories - truth_calories) / truth_calories if truth_calories and predicted_calories is not None else None)
        clarifications.append(output.get("clarifications", []))
        for stage in latencies:
            latencies[stage].append(record.get("latency_ms", {}).get(stage))

    total_requested = len(cases)
    completed = len(completed_cases)
    input_tokens = [record.get("token_usage", {}).get("input") for record in by_id.values()]
    output_tokens = [record.get("token_usage", {}).get("output") for record in by_id.values()]
    input_tokens = [value for value in input_tokens if value is not None]
    output_tokens = [value for value in output_tokens if value is not None]
    scored_nutrition = nutrition_metrics(truth_nutrition, predicted_nutrition)
    truth_calorie_values = [None if row is None else row.get("calories_kcal") for row in truth_nutrition]
    calorie_intervals = interval_metrics(truth_calorie_values, calorie_lower, calorie_upper, unit="kcal")
    scored_nutrition["calorie_interval_coverage"] = calorie_intervals["interval_coverage"]
    scored_nutrition["median_calorie_interval_width"] = calorie_intervals["median_interval_width"]
    metrics = {
        "completion": {"value": completed / total_requested if total_requested else None, "numerator": completed, "denominator": total_requested, "unit": "ratio"},
        "recognition": recognition,
        "recognition_by_category": category_metrics,
        "retrieval": retrieval_metrics(retrieval_labels, retrieval_ranks),
        "canonicalization": selector_metric_values(selector_cases),
        "portion": portion_metrics(truth_portions, predicted_portions, lower_portions, upper_portions),
        "nutrition": scored_nutrition,
        "safety": unsafe_auto_accept_metrics(auto_flags, canonical_correct, item_calorie_errors),
        "clarification": clarification_metrics(clarifications),
        "latency": latency_metrics(latencies),
        "token_usage": {
            "mean_input_tokens_per_meal": {"value": sum(input_tokens) / len(input_tokens) if input_tokens else None, "numerator": sum(input_tokens) if input_tokens else None, "denominator": len(input_tokens), "unit": "tokens/meal", "exclusion": "provider runs without token usage excluded"},
            "mean_output_tokens_per_meal": {"value": sum(output_tokens) / len(output_tokens) if output_tokens else None, "numerator": sum(output_tokens) if output_tokens else None, "denominator": len(output_tokens), "unit": "tokens/meal", "exclusion": "provider runs without token usage excluded"},
        },
    }
    return metrics, errors


def ranked_errors(errors: list[dict]) -> list[dict]:
    counts = Counter(error["taxonomy"] for error in errors)
    total = sum(counts.values())
    return [
        {"error_type": name, "count": count, "percent_of_errors": count / total if total else None}
        for name, count in sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))
    ]


def _error(case: EvaluationCase, stage: str, taxonomy: str, expected, predicted) -> dict:
    if taxonomy not in ERROR_TAXONOMY:
        raise ValueError(f"unknown error taxonomy: {taxonomy}")
    return {
        "case_id": case.case_id,
        "image_reference": case.image,
        "stage": stage,
        "taxonomy": taxonomy,
        "expected": expected,
        "predicted": predicted,
        "likely_cause": None,
        "potential_fix": None,
    }
