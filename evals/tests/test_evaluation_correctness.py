import pytest
from pydantic import ValidationError

from evals.benchmark_metrics import hidden_ingredient_metrics
from evals.dataset import DatasetManifest
from evals.oracle import answer_generated_clarification
from evals.public.nutrition5k.build_subset import build_case
from evals.tests.test_p8_dataset import manifest, valid_case


def hidden_question(name: str) -> dict:
    return {
        "type": "HIDDEN_INGREDIENT",
        "ingredient_name": name,
        "options": [
            {"id": "no", "value": {"presence": "NO", "name": name}},
            {"id": "yes", "value": {"presence": "YES", "name": name}},
            {"id": "not-sure", "value": {"presence": "NOT_SURE", "name": name}},
        ],
    }


def parsed_case(*, complete: bool, hidden: list[dict] | None = None):
    case = valid_case()
    case["hidden_truth_complete"] = complete
    case["hidden_ingredients"] = hidden or []
    return DatasetManifest.model_validate(manifest([case])).cases[0]


def test_hidden_truth_defaults_to_incomplete_for_backward_compatibility():
    case = DatasetManifest.model_validate(manifest([valid_case()])).cases[0]
    assert case.hidden_truth_complete is False


def test_hidden_calorie_truth_requires_measurement_method():
    case = valid_case()
    case["hidden_ingredients"] = [
        {
            "name": "olive oil",
            "present": True,
            "calories_kcal": "63",
            "measurement_method": None,
        }
    ]
    with pytest.raises(ValidationError, match="measured hidden ingredients require measurement_method"):
        DatasetManifest.model_validate(manifest([case]))


def test_closed_world_hidden_truth_can_answer_atomic_absence_as_no():
    case = parsed_case(complete=True)
    answer = answer_generated_clarification(
        hidden_question("cheese"),
        case,
        observed_name=None,
    )
    assert answer.resolvable is True
    assert answer.option_id == "no"


def test_incomplete_hidden_truth_does_not_infer_absence():
    case = parsed_case(complete=False)
    answer = answer_generated_clarification(
        hidden_question("cheese"),
        case,
        observed_name=None,
    )
    assert answer.resolvable is False
    assert answer.option_id is None


def test_compound_hidden_hypothesis_stays_unresolved_even_with_closed_world_truth():
    case = parsed_case(complete=True)
    answer = answer_generated_clarification(
        hidden_question("butter or cooking oil"),
        case,
        observed_name=None,
    )
    assert answer.resolvable is False
    assert answer.option_id is None


def test_semantically_overlapping_hidden_label_does_not_infer_false_no():
    case = parsed_case(
        complete=True,
        hidden=[
            {
                "name": "olive oil",
                "present": True,
                "portion_truth_g": "7",
                "calories_kcal": "63",
                "measurement_method": "weighed",
            }
        ],
    )
    answer = answer_generated_clarification(
        hidden_question("cooking oil"),
        case,
        observed_name=None,
    )
    assert answer.resolvable is False
    assert answer.option_id is None


def test_explicit_hidden_truth_still_answers_yes():
    case = parsed_case(
        complete=True,
        hidden=[
            {
                "name": "olive oil",
                "present": True,
                "portion_truth_g": "7",
                "calories_kcal": "63",
                "measurement_method": "weighed",
            }
        ],
    )
    answer = answer_generated_clarification(
        hidden_question("olive oil"),
        case,
        observed_name=None,
    )
    assert answer.resolvable is True
    assert answer.option_id == "yes"


def test_hidden_metrics_report_count_recall_and_calorie_weighted_coverage():
    metrics = hidden_ingredient_metrics(
        [[("olive oil", 63.0), ("thyme", 1.0)], [("salt", None)]],
        [["olive oil"], []],
    )
    assert metrics["recall_all"]["value"] == pytest.approx(1 / 3)
    assert metrics["recall_all"]["numerator"] == 1
    assert metrics["recall_all"]["denominator"] == 3
    assert metrics["calorie_weighted_coverage"]["value"] == pytest.approx(63 / 64)
    assert metrics["calorie_weighted_coverage"]["numerator"] == pytest.approx(63)
    assert metrics["calorie_weighted_coverage"]["denominator"] == pytest.approx(64)


def test_nutrition5k_builder_marks_hidden_truth_complete_and_preserves_hidden_calories():
    row = [
        "dish_1559332418",
        "482.1",
        "259.0",
        "24.4",
        "10.7",
        "50.3",
        "1",
        "salmon",
        "203.5",
        "400.0",
        "20.0",
        "0.0",
        "40.0",
        "2",
        "brown rice",
        "40.7",
        "50.0",
        "1.0",
        "10.0",
        "1.0",
        "3",
        "arugula",
        "8.1",
        "2.0",
        "0.0",
        "0.4",
        "0.2",
        "4",
        "olive oil",
        "7.7",
        "68.0",
        "7.7",
        "0.0",
        "0.0",
    ]
    case = build_case("dish_1559332418", "development", row, "abc123")
    assert case["hidden_truth_complete"] is True
    assert case["hidden_ingredients"] == [
        {
            "name": "olive oil",
            "present": True,
            "portion_truth_g": "7.7",
            "calories_kcal": "68.0",
            "measurement_method": "Published Nutrition5k per-ingredient mass and calorie label.",
        }
    ]
