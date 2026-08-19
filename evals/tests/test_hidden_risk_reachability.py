from evals.hidden_risk_reachability import (
    classify_hidden_reachability,
    hidden_overlaps_active_food,
)


def signal(name: str, impact: str = "MATERIAL") -> dict:
    return {"name": name, "potential_impact": impact, "reason": "fixture"}


def clarification(kind: str, *, status: str = "PENDING", blocking: bool = True) -> dict:
    return {
        "type": kind,
        "status": status,
        "blocking": blocking,
        "observed_name": "food",
        "options": [],
    }


def test_reached_hidden_question_has_priority() -> None:
    hidden = clarification("HIDDEN_INGREDIENT")
    hidden["ingredient_name"] = "oil"
    classification, details = classify_hidden_reachability(
        recognition_hidden_signals=[signal("oil")],
        oracle_items=[],
        oracle_clarifications=[hidden, clarification("CANONICAL_SELECTION")],
    )
    assert classification == "REACHED_HIDDEN_QUESTION"
    assert details["oracle_hidden_question_names"] == ["oil"]


def test_pending_canonical_or_identity_blocker_explains_deferred_stage() -> None:
    classification, details = classify_hidden_reachability(
        recognition_hidden_signals=[signal("olive oil")],
        oracle_items=[{"observed_name": "chicken", "selected_food_name": "Chicken, grilled"}],
        oracle_clarifications=[clarification("CANONICAL_SELECTION")],
    )
    assert classification == "DEFERRED_BY_PENDING_EARLIER_BLOCKER"
    assert len(details["pending_earlier_blockers"]) == 1


def test_portion_question_is_not_mislabeled_as_an_earlier_blocker() -> None:
    classification, _ = classify_hidden_reachability(
        recognition_hidden_signals=[signal("olive oil")],
        oracle_items=[{"observed_name": "chicken"}],
        oracle_clarifications=[clarification("PORTION")],
    )
    assert classification == "UNEXPLAINED_REACHABILITY_GAP"


def test_low_impact_only_signal_does_not_require_hidden_question() -> None:
    classification, details = classify_hidden_reachability(
        recognition_hidden_signals=[signal("salt", "LOW")],
        oracle_items=[],
        oracle_clarifications=[],
    )
    assert classification == "NO_MATERIAL_OR_UNKNOWN_SIGNAL"
    assert details["material_or_unknown_signal_count"] == 0


def test_visible_overlap_suppression_is_separate_from_missing_question() -> None:
    classification, details = classify_hidden_reachability(
        recognition_hidden_signals=[signal("additional cheese")],
        oracle_items=[{"observed_name": "Parmesan cheese", "selected_food_name": "Cheese, Parmesan, grated"}],
        oracle_clarifications=[],
    )
    assert classification == "SUPPRESSED_AS_VISIBLE_OVERLAP"
    assert details["eligible_signal_count_after_visible_overlap"] == 0


def test_eligible_material_signal_without_blocker_is_unexplained_gap() -> None:
    classification, details = classify_hidden_reachability(
        recognition_hidden_signals=[signal("cooking oil")],
        oracle_items=[{"observed_name": "scrambled eggs"}],
        oracle_clarifications=[],
    )
    assert classification == "UNEXPLAINED_REACHABILITY_GAP"
    assert details["eligible_signal_count_after_visible_overlap"] == 1


def test_overlap_helper_ignores_generic_hidden_modifiers() -> None:
    assert hidden_overlaps_active_food(
        [{"observed_name": "Parmesan cheese", "selected_food_name": None}],
        "possible additional cheese",
    )
