from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from evals.dataset import EvaluationCase
from evals.recognition_metrics import normalize_food_name


@dataclass(frozen=True, slots=True)
class Metric:
    value: float | None
    numerator: float | int | None
    denominator: float | int
    unit: str = "ratio"
    exclusion: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "numerator": self.numerator,
            "denominator": self.denominator,
            "unit": self.unit,
            "exclusion": self.exclusion,
        }


def _safe_ratio(numerator: float | int, denominator: float | int) -> float | None:
    return float(numerator) / float(denominator) if denominator else None


def _hidden_question_names(clarifications: list[dict]) -> list[str]:
    output: list[str] = []
    for clarification in clarifications:
        if clarification.get("type") != "HIDDEN_INGREDIENT":
            continue
        name = clarification.get("ingredient_name")
        if not name:
            options = clarification.get("options") or []
            if options and isinstance(options[0], dict):
                value = options[0].get("value") or {}
                name = value.get("name") if isinstance(value, dict) else None
        if isinstance(name, str) and name.strip():
            output.append(name.strip())
    return output


def score_hidden_risk(
    cases: list[EvaluationCase],
    records: list[dict],
    *,
    configuration: str,
) -> dict[str, dict]:
    """Score hidden-ingredient identity and risk surfacing without semantic alias fitting.

    Identity metrics remain exact normalized-name matches. Risk-surfacing metrics intentionally ask a
    different product question: did the system surface *some* hidden-ingredient risk on a meal known
    to contain hidden ingredients? False-positive burden is measured only on cases whose hidden truth
    is explicitly complete and negative.
    """

    by_id = {
        record.get("case_id"): record
        for record in records
        if record.get("status") == "completed" and record.get("case_id")
    }
    completed = [case for case in cases if case.case_id in by_id]

    exact_truth_count = 0
    exact_recognition_hits = 0
    exact_question_hits = 0
    measured_hidden_kcal = 0.0
    exact_recognition_kcal = 0.0
    exact_question_kcal = 0.0

    positive_case_count = 0
    recognition_risk_positive_hits = 0
    question_risk_positive_hits = 0
    positive_hidden_question_count = 0

    complete_negative_case_count = 0
    recognition_risk_negative_hits = 0
    question_risk_negative_hits = 0
    negative_hidden_question_count = 0

    measured_positive_case_kcal = 0.0
    recognition_risk_case_kcal = 0.0
    question_risk_case_kcal = 0.0

    for case in completed:
        record = by_id[case.case_id]
        output = (record.get("configurations") or {}).get(configuration)
        if not isinstance(output, dict):
            raise ValueError(
                f"completed record {case.case_id} lacks configuration {configuration!r}"
            )

        suggested_names = {
            normalize_food_name(str(name))
            for name in (record.get("possible_hidden_ingredients") or [])
            if str(name).strip()
        }
        hidden_questions = [
            item
            for item in (output.get("clarifications") or [])
            if item.get("type") == "HIDDEN_INGREDIENT"
        ]
        question_names = {
            normalize_food_name(name) for name in _hidden_question_names(hidden_questions)
        }

        present_truth = [item for item in case.hidden_ingredients if item.present]
        case_measured_kcal = sum(
            float(item.calories_kcal)
            for item in present_truth
            if item.calories_kcal is not None
        )

        for truth in present_truth:
            truth_name = normalize_food_name(truth.name)
            recognition_hit = truth_name in suggested_names
            question_hit = truth_name in question_names
            exact_truth_count += 1
            exact_recognition_hits += int(recognition_hit)
            exact_question_hits += int(question_hit)
            if truth.calories_kcal is not None:
                kcal = float(truth.calories_kcal)
                measured_hidden_kcal += kcal
                if recognition_hit:
                    exact_recognition_kcal += kcal
                if question_hit:
                    exact_question_kcal += kcal

        has_recognition_risk = bool(suggested_names)
        has_question_risk = bool(hidden_questions)
        if present_truth:
            positive_case_count += 1
            recognition_risk_positive_hits += int(has_recognition_risk)
            question_risk_positive_hits += int(has_question_risk)
            positive_hidden_question_count += len(hidden_questions)
            if case_measured_kcal > 0:
                measured_positive_case_kcal += case_measured_kcal
                if has_recognition_risk:
                    recognition_risk_case_kcal += case_measured_kcal
                if has_question_risk:
                    question_risk_case_kcal += case_measured_kcal
        elif case.hidden_truth_complete:
            complete_negative_case_count += 1
            recognition_risk_negative_hits += int(has_recognition_risk)
            question_risk_negative_hits += int(has_question_risk)
            negative_hidden_question_count += len(hidden_questions)

    return {
        "exact_recognition_recall": Metric(
            _safe_ratio(exact_recognition_hits, exact_truth_count),
            exact_recognition_hits if exact_truth_count else None,
            exact_truth_count,
            exclusion="only ground-truth hidden ingredients marked present are evaluated",
        ).as_dict(),
        "exact_question_recall": Metric(
            _safe_ratio(exact_question_hits, exact_truth_count),
            exact_question_hits if exact_truth_count else None,
            exact_truth_count,
            exclusion="only exact normalized ingredient names in generated HIDDEN_INGREDIENT questions count",
        ).as_dict(),
        "exact_recognition_calorie_weighted_coverage": Metric(
            _safe_ratio(exact_recognition_kcal, measured_hidden_kcal),
            exact_recognition_kcal if measured_hidden_kcal else None,
            measured_hidden_kcal,
            exclusion="hidden ingredients without calorie truth are excluded from the kcal denominator",
        ).as_dict(),
        "exact_question_calorie_weighted_coverage": Metric(
            _safe_ratio(exact_question_kcal, measured_hidden_kcal),
            exact_question_kcal if measured_hidden_kcal else None,
            measured_hidden_kcal,
            exclusion="hidden ingredients without calorie truth are excluded from the kcal denominator",
        ).as_dict(),
        "recognition_risk_surface_case_recall": Metric(
            _safe_ratio(recognition_risk_positive_hits, positive_case_count),
            recognition_risk_positive_hits if positive_case_count else None,
            positive_case_count,
            exclusion="denominator is completed meals with at least one ground-truth hidden ingredient",
        ).as_dict(),
        "question_risk_surface_case_recall": Metric(
            _safe_ratio(question_risk_positive_hits, positive_case_count),
            question_risk_positive_hits if positive_case_count else None,
            positive_case_count,
            exclusion="identity need not match; metric means some hidden risk reached a user question",
        ).as_dict(),
        "recognition_risk_surface_calorie_weighted_case_coverage": Metric(
            _safe_ratio(recognition_risk_case_kcal, measured_positive_case_kcal),
            recognition_risk_case_kcal if measured_positive_case_kcal else None,
            measured_positive_case_kcal,
            exclusion="weights hidden-positive meals by their measured hidden kcal; does not claim ingredient identity",
        ).as_dict(),
        "question_risk_surface_calorie_weighted_case_coverage": Metric(
            _safe_ratio(question_risk_case_kcal, measured_positive_case_kcal),
            question_risk_case_kcal if measured_positive_case_kcal else None,
            measured_positive_case_kcal,
            exclusion="weights hidden-positive meals by their measured hidden kcal; any hidden question surfaces risk but not identity",
        ).as_dict(),
        "recognition_risk_surface_false_positive_rate": Metric(
            _safe_ratio(recognition_risk_negative_hits, complete_negative_case_count),
            recognition_risk_negative_hits if complete_negative_case_count else None,
            complete_negative_case_count,
            exclusion="only hidden_truth_complete meals with no present hidden ingredients are valid negatives",
        ).as_dict(),
        "question_risk_surface_false_positive_rate": Metric(
            _safe_ratio(question_risk_negative_hits, complete_negative_case_count),
            question_risk_negative_hits if complete_negative_case_count else None,
            complete_negative_case_count,
            exclusion="only hidden_truth_complete meals with no present hidden ingredients are valid negatives",
        ).as_dict(),
        "mean_hidden_questions_per_positive_meal": Metric(
            _safe_ratio(positive_hidden_question_count, positive_case_count),
            positive_hidden_question_count if positive_case_count else None,
            positive_case_count,
            unit="questions/meal",
            exclusion="completed meals with at least one present hidden ingredient",
        ).as_dict(),
        "mean_hidden_questions_per_complete_negative_meal": Metric(
            _safe_ratio(negative_hidden_question_count, complete_negative_case_count),
            negative_hidden_question_count if complete_negative_case_count else None,
            complete_negative_case_count,
            unit="questions/meal",
            exclusion="only hidden_truth_complete meals with no present hidden ingredients are valid negatives",
        ).as_dict(),
        "silent_hidden_risk_case_rate": Metric(
            _safe_ratio(positive_case_count - question_risk_positive_hits, positive_case_count),
            (positive_case_count - question_risk_positive_hits) if positive_case_count else None,
            positive_case_count,
            exclusion="hidden-positive meals with no generated HIDDEN_INGREDIENT question",
        ).as_dict(),
    }
