from __future__ import annotations

import re
from collections import Counter
from typing import Any

EARLIER_BLOCKER_TYPES = frozenset({"CANONICAL_SELECTION", "FOOD_IDENTITY"})
MATERIAL_IMPACTS = frozenset({"MATERIAL", "UNKNOWN"})


def _enum_tail(value: Any) -> str:
    return str(value or "").rsplit(".", 1)[-1].upper()


def _normalize_tokens(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", value.lower()))


def hidden_overlaps_active_food(items: list[dict[str, Any]], hidden_name: str) -> bool:
    """Mirror the production overlap intent using fields persisted in benchmark artifacts."""
    ignored = {"additional", "added", "extra", "hidden", "possible", "cooking"}
    hidden_tokens = _normalize_tokens(hidden_name) - ignored
    if not hidden_tokens:
        return False
    for item in items:
        if item.get("removed"):
            continue
        visible = " ".join(
            str(value)
            for value in (
                item.get("observed_name"),
                item.get("selected_food_name"),
            )
            if value
        )
        if hidden_tokens <= _normalize_tokens(visible):
            return True
    return False


def _question_name(clarification: dict[str, Any]) -> str | None:
    value = clarification.get("ingredient_name")
    if value:
        return str(value)
    for option in clarification.get("options", []):
        name = option.get("value", {}).get("name")
        if name:
            return str(name)
    return None


def _is_pending(clarification: dict[str, Any]) -> bool:
    return _enum_tail(clarification.get("status")) == "PENDING"


def _is_blocking(clarification: dict[str, Any]) -> bool:
    return bool(clarification.get("blocking", True))


def summarize_clarifications(values: list[dict[str, Any]]) -> dict[str, Any]:
    counts = Counter(str(value.get("type") or "UNKNOWN") for value in values)
    pending = [value for value in values if _is_pending(value) and _is_blocking(value)]
    return {
        "type_counts": dict(sorted(counts.items())),
        "pending_blocking": [
            {
                "type": value.get("type"),
                "observed_name": value.get("observed_name"),
                "ingredient_name": _question_name(value),
                "status": value.get("status"),
                "resolvable": value.get("resolvable"),
            }
            for value in pending
        ],
    }


def classify_hidden_reachability(
    *,
    recognition_hidden_signals: list[dict[str, Any]],
    oracle_items: list[dict[str, Any]],
    oracle_clarifications: list[dict[str, Any]],
) -> tuple[str, dict[str, Any]]:
    """Classify why a hidden-positive case did or did not reach a hidden question.

    This is diagnostic only. It does not relabel hidden-ingredient truth and does not claim
    semantic ingredient identity correctness.
    """
    hidden_questions = [
        value for value in oracle_clarifications if value.get("type") == "HIDDEN_INGREDIENT"
    ]
    earlier_pending = [
        value
        for value in oracle_clarifications
        if value.get("type") in EARLIER_BLOCKER_TYPES
        and _is_pending(value)
        and _is_blocking(value)
    ]

    normalized_signals = []
    for raw in recognition_hidden_signals:
        name = str(raw.get("name") or "").strip()
        if not name:
            continue
        impact = _enum_tail(raw.get("potential_impact"))
        overlaps = hidden_overlaps_active_food(oracle_items, name)
        normalized_signals.append(
            {
                "name": name,
                "potential_impact": impact,
                "reason": raw.get("reason"),
                "overlaps_active_food": overlaps,
            }
        )

    material = [value for value in normalized_signals if value["potential_impact"] in MATERIAL_IMPACTS]
    eligible = [value for value in material if not value["overlaps_active_food"]]

    if hidden_questions:
        classification = "REACHED_HIDDEN_QUESTION"
    elif earlier_pending:
        classification = "DEFERRED_BY_PENDING_EARLIER_BLOCKER"
    elif not material:
        classification = "NO_MATERIAL_OR_UNKNOWN_SIGNAL"
    elif not eligible:
        classification = "SUPPRESSED_AS_VISIBLE_OVERLAP"
    else:
        classification = "UNEXPLAINED_REACHABILITY_GAP"

    details = {
        "recognition_hidden_signals": normalized_signals,
        "material_or_unknown_signal_count": len(material),
        "eligible_signal_count_after_visible_overlap": len(eligible),
        "oracle_hidden_question_names": [
            name for value in hidden_questions if (name := _question_name(value)) is not None
        ],
        "pending_earlier_blockers": [
            {
                "type": value.get("type"),
                "observed_name": value.get("observed_name"),
                "status": value.get("status"),
                "resolvable": value.get("resolvable"),
            }
            for value in earlier_pending
        ],
    }
    return classification, details
