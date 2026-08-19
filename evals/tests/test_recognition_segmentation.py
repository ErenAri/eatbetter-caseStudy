from evals.recognition_metrics import ExpectedFood
from evals.recognition_segmentation import (
    RecognitionMismatchKind,
    aggregate_segmentation_diagnostics,
    diagnose_recognition_mismatches,
)


def test_under_segmentation_collapses_composite_strict_errors_into_one_event() -> None:
    result = diagnose_recognition_mismatches(
        [ExpectedFood("bagel"), ExpectedFood("cream cheese")],
        ["bagel with cream cheese"],
    )

    assert result.strict_missed_count == 2
    assert result.strict_hallucinated_count == 1
    assert len(result.events) == 1
    event = result.events[0]
    assert event.kind == RecognitionMismatchKind.UNDER_SEGMENTATION
    assert event.expected_labels == ("bagel", "cream cheese")
    assert event.predicted_labels == ("bagel with cream cheese",)
    assert event.strict_error_units == 3


def test_extra_modifiers_explain_identity_without_changing_primary_match() -> None:
    result = diagnose_recognition_mismatches(
        [ExpectedFood("chicken")],
        ["chopped cooked chicken"],
    )

    assert result.strict_missed_count == 1
    assert result.strict_hallucinated_count == 1
    assert result.events[0].kind == RecognitionMismatchKind.IDENTITY_WITH_EXTRA_MODIFIERS
    assert result.events[0].strict_error_units == 2


def test_preapproved_alias_stays_exact_and_never_becomes_diagnostic_error() -> None:
    result = diagnose_recognition_mismatches(
        [ExpectedFood("chicken", ("grilled chicken",))],
        ["grilled chicken"],
    )

    assert result.exact_match_count == 1
    assert result.strict_missed_count == 0
    assert result.strict_hallucinated_count == 0
    assert result.events == ()


def test_broader_label_is_reported_after_exact_matching() -> None:
    result = diagnose_recognition_mismatches(
        [ExpectedFood("grilled chicken")],
        ["chicken"],
    )

    assert result.events[0].kind == RecognitionMismatchKind.BROADER_LABEL
    assert result.events[0].strict_error_units == 2


def test_over_segmentation_requires_fragments_to_jointly_cover_expected_label() -> None:
    result = diagnose_recognition_mismatches(
        [ExpectedFood("bagel cream cheese")],
        ["bagel", "cream cheese"],
    )

    assert len(result.events) == 1
    event = result.events[0]
    assert event.kind == RecognitionMismatchKind.OVER_SEGMENTATION
    assert event.strict_error_units == 3


def test_unexplained_errors_remain_explicit_and_conserve_strict_error_units() -> None:
    result = diagnose_recognition_mismatches(
        [ExpectedFood("salmon"), ExpectedFood("arugula")],
        ["shrimp", "leafy greens"],
    )

    assert result.strict_missed_count == 2
    assert result.strict_hallucinated_count == 2
    assert sum(event.strict_error_units for event in result.events) == 4
    assert {event.kind for event in result.events} == {
        RecognitionMismatchKind.UNEXPLAINED_MISS,
        RecognitionMismatchKind.UNEXPLAINED_PREDICTION,
    }


def test_aggregate_reports_event_counts_separately_from_strict_error_units() -> None:
    under = diagnose_recognition_mismatches(
        [ExpectedFood("bagel"), ExpectedFood("cream cheese")],
        ["bagel with cream cheese"],
    )
    modified = diagnose_recognition_mismatches(
        [ExpectedFood("chicken")],
        ["chopped cooked chicken"],
    )

    result = aggregate_segmentation_diagnostics([under, modified])

    assert result["case_count"] == 2
    assert result["strict_error_units"] == 5
    assert result["structural_event_count"] == 2
    assert result["category_event_counts"]["UNDER_SEGMENTATION"] == 1
    assert result["category_event_counts"]["IDENTITY_WITH_EXTRA_MODIFIERS"] == 1
    assert result["category_strict_error_units"]["UNDER_SEGMENTATION"] == 3
    assert result["category_strict_error_units"]["IDENTITY_WITH_EXTRA_MODIFIERS"] == 2
