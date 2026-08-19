from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

from .dataset import EvaluationCase, GroundTruthItem
from .recognition_metrics import normalize_food_name


@dataclass(frozen=True)
class OracleAnswer:
    option_id: str | None = None
    custom_grams: Decimal | None = None
    resolvable: bool = False


def match_truth_item(observed_name: str, case: EvaluationCase) -> GroundTruthItem | None:
    normalized = normalize_food_name(observed_name)
    return next(
        (
            item
            for item in case.items
            if normalized
            in {
                normalize_food_name(name)
                for name in (item.label, *item.acceptable_aliases)
            }
        ),
        None,
    )


def _atomic_hidden_hypothesis(value: str) -> bool:
    """Closed-world negatives are safe only for one concrete ingredient hypothesis."""
    normalized = value.strip().lower()
    return bool(normalized) and re.search(r"\b(?:or|and)\b|/", normalized) is None


def _hidden_hypothesis_overlaps_truth(value: str, case: EvaluationCase) -> bool:
    """Avoid false negatives for semantically adjacent labels such as cooking oil vs olive oil."""
    hypothesis_tokens = set(normalize_food_name(value).split())
    if not hypothesis_tokens:
        return False
    return any(
        hypothesis_tokens & set(normalize_food_name(item.name).split())
        for item in case.hidden_ingredients
    )


def answer_generated_clarification(
    clarification: dict,
    case: EvaluationCase,
    *,
    observed_name: str | None,
) -> OracleAnswer:
    """Grade a generated question only; this function has no pipeline/provider dependency."""
    kind = clarification.get("type")
    options = clarification.get("options", [])
    truth = match_truth_item(observed_name, case) if observed_name else None
    if kind == "CANONICAL_SELECTION" and truth:
        for option in options:
            food_id = option.get("grader_food_id")
            if food_id in truth.acceptable_canonical_ids:
                return OracleAnswer(option_id=option.get("id"), resolvable=True)
        return OracleAnswer()
    if kind == "PORTION" and truth and truth.portion_truth_g is not None:
        return OracleAnswer(custom_grams=truth.portion_truth_g, resolvable=True)
    if kind == "HIDDEN_INGREDIENT":
        raw_name = str(clarification.get("ingredient_name", ""))
        name = normalize_food_name(raw_name)
        hidden = next(
            (
                item
                for item in case.hidden_ingredients
                if normalize_food_name(item.name) == name
            ),
            None,
        )
        if hidden is None:
            if (
                case.hidden_truth_complete
                and _atomic_hidden_hypothesis(raw_name)
                and not _hidden_hypothesis_overlaps_truth(raw_name, case)
            ):
                option = next(
                    (
                        item
                        for item in options
                        if item.get("value", {}).get("presence") == "NO"
                    ),
                    None,
                )
                return OracleAnswer(
                    option_id=option.get("id") if option else None,
                    resolvable=option is not None,
                )
            return OracleAnswer()
        expected_presence = "YES" if hidden.present else "NO"
        option = next(
            (
                item
                for item in options
                if item.get("value", {}).get("presence") == expected_presence
            ),
            None,
        )
        return OracleAnswer(
            option_id=option.get("id") if option else None,
            resolvable=option is not None,
        )
    if kind == "FOOD_IDENTITY" and truth is None:
        option = next(
            (
                item
                for item in options
                if item.get("value", {}).get("action") == "REMOVE_ITEM"
            ),
            None,
        )
        return OracleAnswer(
            option_id=option.get("id") if option else None,
            resolvable=option is not None,
        )
    return OracleAnswer()
