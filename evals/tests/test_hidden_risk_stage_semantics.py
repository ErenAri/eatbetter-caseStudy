from evals.run_hidden_risk_analysis import _question_stage_semantics


def test_hybrid_auto_is_labeled_initial_stage() -> None:
    assert "initial clarification state" in _question_stage_semantics("HYBRID_AUTO")


def test_oracle_hybrid_is_labeled_eventual_staged_reachability() -> None:
    assert "oracle-progressed staged state" in _question_stage_semantics("HYBRID_ORACLE_HITL")


def test_non_hybrid_configuration_is_not_mislabeled_as_reachability() -> None:
    assert "does not represent" in _question_stage_semantics("BASELINE_TOP1")
