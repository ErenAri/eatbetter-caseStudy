import pytest

from evals.dataset import DatasetManifest
from evals.hidden_risk_metrics import score_hidden_risk
from evals.tests.test_p8_dataset import manifest, valid_case


def hidden(name: str, calories: str) -> dict:
    return {
        "name": name,
        "present": True,
        "portion_truth_g": "5",
        "calories_kcal": calories,
        "measurement_method": "measured fixture",
    }


def record(case_id: str, *, suggestions=None, questions=None) -> dict:
    questions = questions or []
    return {
        "case_id": case_id,
        "status": "completed",
        "possible_hidden_ingredients": suggestions or [],
        "configurations": {
            "HYBRID_AUTO": {
                "items": [],
                "nutrition_totals": None,
                "clarifications": questions,
            }
        },
    }


def question(name: str) -> dict:
    return {
        "type": "HIDDEN_INGREDIENT",
        "ingredient_name": name,
        "blocking": True,
        "status": "PENDING",
        "options": [],
    }


def dataset_and_records():
    positive_a = valid_case(
        case_id="positive_a",
        hidden_truth_complete=True,
        hidden_ingredients=[hidden("olive oil", "80")],
    )
    positive_b = valid_case(
        case_id="positive_b",
        hidden_truth_complete=True,
        hidden_ingredients=[hidden("butter", "100")],
    )
    negative_a = valid_case(
        case_id="negative_a", hidden_truth_complete=True, hidden_ingredients=[]
    )
    negative_b = valid_case(
        case_id="negative_b", hidden_truth_complete=True, hidden_ingredients=[]
    )
    incomplete_negative = valid_case(
        case_id="incomplete_negative", hidden_truth_complete=False, hidden_ingredients=[]
    )
    cases = DatasetManifest.model_validate(
        manifest([positive_a, positive_b, negative_a, negative_b, incomplete_negative])
    ).cases
    records = [
        record(
            "positive_a",
            suggestions=["cooking oil"],
            questions=[question("cooking oil")],
        ),
        record(
            "positive_b",
            suggestions=["butter"],
            questions=[question("butter")],
        ),
        record(
            "negative_a",
            suggestions=["oil"],
            questions=[question("oil")],
        ),
        record("negative_b"),
        record(
            "incomplete_negative",
            suggestions=["mystery sauce"],
            questions=[question("mystery sauce")],
        ),
    ]
    return cases, records


def test_hidden_risk_separates_exact_identity_from_case_level_risk_surface() -> None:
    cases, records = dataset_and_records()
    metrics = score_hidden_risk(cases, records, configuration="HYBRID_AUTO")

    assert metrics["exact_recognition_recall"]["value"] == 0.5
    assert metrics["exact_question_recall"]["value"] == 0.5
    assert metrics["question_risk_surface_case_recall"]["value"] == 1.0
    assert metrics["recognition_risk_surface_case_recall"]["value"] == 1.0


def test_hidden_risk_calorie_weighting_does_not_turn_risk_surface_into_identity() -> None:
    cases, records = dataset_and_records()
    metrics = score_hidden_risk(cases, records, configuration="HYBRID_AUTO")

    assert metrics["exact_recognition_calorie_weighted_coverage"]["value"] == pytest.approx(100 / 180)
    assert metrics["exact_question_calorie_weighted_coverage"]["value"] == pytest.approx(100 / 180)
    assert metrics["question_risk_surface_calorie_weighted_case_coverage"]["value"] == 1.0
    assert metrics["question_risk_surface_calorie_weighted_case_coverage"]["denominator"] == 180


def test_complete_negative_truth_controls_false_positive_denominator() -> None:
    cases, records = dataset_and_records()
    metrics = score_hidden_risk(cases, records, configuration="HYBRID_AUTO")

    assert metrics["question_risk_surface_false_positive_rate"]["numerator"] == 1
    assert metrics["question_risk_surface_false_positive_rate"]["denominator"] == 2
    assert metrics["question_risk_surface_false_positive_rate"]["value"] == 0.5
    assert metrics["recognition_risk_surface_false_positive_rate"]["value"] == 0.5
    assert metrics["mean_hidden_questions_per_complete_negative_meal"]["value"] == 0.5


def test_silent_risk_and_question_burden_are_explicit() -> None:
    cases, records = dataset_and_records()
    records[0]["configurations"]["HYBRID_AUTO"]["clarifications"] = []
    metrics = score_hidden_risk(cases, records, configuration="HYBRID_AUTO")

    assert metrics["question_risk_surface_case_recall"]["value"] == 0.5
    assert metrics["silent_hidden_risk_case_rate"]["value"] == 0.5
    assert metrics["mean_hidden_questions_per_positive_meal"]["value"] == 0.5
    assert metrics["question_risk_surface_calorie_weighted_case_coverage"]["value"] == pytest.approx(100 / 180)


def test_question_name_can_be_recovered_from_first_option_for_historical_artifacts() -> None:
    case = valid_case(
        case_id="legacy",
        hidden_truth_complete=True,
        hidden_ingredients=[hidden("olive oil", "80")],
    )
    cases = DatasetManifest.model_validate(manifest([case])).cases
    records = [
        record(
            "legacy",
            suggestions=[],
            questions=[
                {
                    "type": "HIDDEN_INGREDIENT",
                    "ingredient_name": None,
                    "options": [{"value": {"name": "olive oil"}}],
                }
            ],
        )
    ]

    metrics = score_hidden_risk(cases, records, configuration="HYBRID_AUTO")
    assert metrics["exact_question_recall"]["value"] == 1.0


def test_missing_requested_configuration_fails_closed() -> None:
    case = DatasetManifest.model_validate(manifest([valid_case(case_id="meal")])).cases[0]
    records = [{"case_id": "meal", "status": "completed", "configurations": {}}]

    with pytest.raises(ValueError, match="lacks configuration"):
        score_hidden_risk([case], records, configuration="HYBRID_AUTO")
