import pytest

from evals.benchmark_metrics import (
    absolute_error_metrics,
    baseline_comparison,
    clarification_metrics,
    nutrition_metrics,
    portion_metrics,
    retrieval_metrics,
    unsafe_auto_accept_metrics,
)
from evals.canonicalization_metrics import SelectorCaseResult
from evals.benchmark_metrics import selector_metric_values
from evals.dataset import DatasetManifest
from evals.scoring import score_configuration
from evals.tests.test_p8_dataset import manifest, valid_case


def test_null_labels_are_excluded_from_denominator():
    metric = absolute_error_metrics([100, None, 200], [90, 999, None], unit="g")["mae"]
    assert metric.value == 10
    assert metric.denominator == 1


def test_retrieval_recall_supports_multiple_acceptable_ids():
    metrics = retrieval_metrics([{"20", "21"}, None, {"30"}], [["10", "20"], ["x"], ["30"]])
    assert metrics["recall_at_1"] == pytest.approx({"value": 0.5, "numerator": 1, "denominator": 2, "unit": "ratio", "exclusion": "unverified and unmappable labels excluded"})
    assert metrics["recall_at_3"]["value"] == 1


def test_selector_denominator_excludes_retrieval_misses_upstream():
    metrics = selector_metric_values([SelectorCaseResult(2, frozenset({1, 2}), "SELECT", 2, "STRONG")])
    assert metrics["selection_accuracy"]["numerator"] == 1
    assert metrics["selection_accuracy"]["denominator"] == 1


def test_portion_mae_mape_interval_coverage_and_width():
    metrics = portion_metrics([100, 0, None], [120, 50, 7], [80, 0, 0], [90, 60, 10])
    assert metrics["mae"]["value"] == 35
    assert metrics["mape"]["value"] == pytest.approx(0.2)
    assert metrics["mape"]["denominator"] == 1
    assert metrics["interval_coverage"]["value"] == 0.5
    assert metrics["median_interval_width"]["value"] == 35


def test_calorie_and_macro_metrics_with_practical_bands():
    truth = [{"calories_kcal": 100, "protein_g": 10, "carbs_g": 20, "fat_g": 5}, None]
    predicted = [{"calories_kcal": 119, "protein_g": 12, "carbs_g": 18, "fat_g": 6}, {"calories_kcal": 900}]
    metrics = nutrition_metrics(truth, predicted)
    assert metrics["calories_kcal_mae"]["value"] == 19
    assert metrics["protein_g_mae"]["value"] == 2
    assert metrics["meals_within_20_percent_calories"]["numerator"] == 1


def test_unsafe_auto_accept_rule_and_coverage():
    metrics = unsafe_auto_accept_metrics([True, True, False, True], [True, False, True, None], [0.21, 0.01, 0.9, None])
    assert metrics["unsafe_auto_accept_rate"]["value"] == 1
    assert metrics["unsafe_auto_accept_rate"]["denominator"] == 2
    assert metrics["auto_accept_coverage"]["value"] == pytest.approx(2 / 3)


def test_clarification_metrics_and_resolvability():
    metrics = clarification_metrics([[{"type": "PORTION", "blocking": True, "resolvable": True}], [], [{"type": "HIDDEN_INGREDIENT", "blocking": True, "resolvable": False}]])
    assert metrics["clarification_rate"]["value"] == pytest.approx(2 / 3)
    assert metrics["average_blocking_questions_per_meal"]["value"] == pytest.approx(2 / 3)
    assert metrics["clarification_resolvability"]["value"] == 0.5


def test_baseline_comparison_preserves_direction_without_claiming_improvement():
    result = baseline_comparison({"f1": {"value": 0.8}}, {"f1": {"value": 0.75}}, ["f1"])
    assert result["f1"]["delta"] == pytest.approx(-0.05)


def test_stage_scoring_keeps_retrieval_selector_portion_and_safety_separate():
    case = DatasetManifest.model_validate(manifest([valid_case()])).cases[0]
    item = {
        "observed_name": "fresh banana", "preparation_method": "raw",
        "candidates": [{"rank": 1, "food_id": "999", "name": "wrong"}, {"rank": 2, "food_id": "173944", "name": "Bananas, raw"}],
        "selected_rank": 2, "selected_food_id": "173944", "selected_food_name": "Bananas, raw", "match_quality": "STRONG",
        "portion_min_g": 90, "portion_max_g": 110, "confirmed_portion_g": 100,
        "portion_resolution_source": "AUTO_ESTIMATE", "nutrition": None, "removed": False,
    }
    output = {"items": [item], "nutrition_totals": {"calories_kcal": 89, "protein_g": 1.1, "carbs_g": 22.8, "fat_g": 0.3}, "clarifications": []}
    record = {
        "case_id": "meal_001", "status": "completed",
        "recognition_items": [{"observed_name": "fresh banana", "preparation_method": "raw"}],
        "possible_hidden_ingredients": [],
        "configurations": {"HYBRID_AUTO": output},
        "latency_ms": {"vision": 10, "retrieval": 20, "canonicalization": 30, "total": 60},
        "token_usage": {"input": 100, "output": 20},
    }
    metrics, errors = score_configuration([case], [record], "HYBRID_AUTO")
    assert metrics["retrieval"]["recall_at_1"]["value"] == 0
    assert metrics["retrieval"]["recall_at_3"]["value"] == 1
    assert metrics["canonicalization"]["selection_accuracy"]["value"] == 1
    assert metrics["portion"]["mae"]["value"] == 0
    assert metrics["safety"]["unsafe_auto_accept_rate"]["value"] == 0
    assert errors == []
