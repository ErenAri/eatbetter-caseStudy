from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable

from evals.recognition_metrics import ExpectedFood, normalize_food_name


class RecognitionMismatchKind(StrEnum):
    UNDER_SEGMENTATION = "UNDER_SEGMENTATION"
    OVER_SEGMENTATION = "OVER_SEGMENTATION"
    COMPOSITE_ALIAS_WITH_EXTRA_PREDICTIONS = "COMPOSITE_ALIAS_WITH_EXTRA_PREDICTIONS"
    IDENTITY_WITH_EXTRA_MODIFIERS = "IDENTITY_WITH_EXTRA_MODIFIERS"
    BROADER_LABEL = "BROADER_LABEL"
    PARTIAL_IDENTITY_OVERLAP = "PARTIAL_IDENTITY_OVERLAP"
    UNEXPLAINED_MISS = "UNEXPLAINED_MISS"
    UNEXPLAINED_PREDICTION = "UNEXPLAINED_PREDICTION"


@dataclass(frozen=True, slots=True)
class RecognitionMismatchEvent:
    kind: RecognitionMismatchKind
    expected_labels: tuple[str, ...]
    predicted_labels: tuple[str, ...]
    strict_error_units: int

    def as_dict(self) -> dict:
        return {
            "kind": str(self.kind),
            "expected_labels": list(self.expected_labels),
            "predicted_labels": list(self.predicted_labels),
            "strict_error_units": self.strict_error_units,
        }


@dataclass(frozen=True, slots=True)
class RecognitionSegmentationDiagnostics:
    exact_match_count: int
    strict_missed_count: int
    strict_hallucinated_count: int
    events: tuple[RecognitionMismatchEvent, ...]

    def as_dict(self) -> dict:
        category_events = Counter(str(event.kind) for event in self.events)
        category_error_units = Counter()
        for event in self.events:
            category_error_units[str(event.kind)] += event.strict_error_units
        return {
            "exact_match_count": self.exact_match_count,
            "strict_missed_count": self.strict_missed_count,
            "strict_hallucinated_count": self.strict_hallucinated_count,
            "strict_error_units": self.strict_missed_count + self.strict_hallucinated_count,
            "structural_event_count": len(self.events),
            "category_event_counts": dict(sorted(category_events.items())),
            "category_strict_error_units": dict(sorted(category_error_units.items())),
            "events": [event.as_dict() for event in self.events],
        }


@dataclass(frozen=True, slots=True)
class _ExactMatch:
    expected_index: int
    prediction_index: int
    matched_primary_label: bool


def diagnose_recognition_mismatches(
    expected: list[ExpectedFood], predicted_names: list[str]
) -> RecognitionSegmentationDiagnostics:
    """Explain strict recognition mismatches without changing the primary metric.

    Exact normalized label/alias matching is identical to the primary recognition
    metric. Residual structural relationships deliberately use only the primary
    expected label, not broad acceptable aliases. This prevents an alias such as
    ``rice`` or ``salad`` from being promoted into evidence that two different
    residual labels share the same identity.

    A classification is explanatory evidence, not an alternate ground-truth match.
    Primary precision/recall/F1 remain unchanged.
    """

    unmatched_expected = set(range(len(expected)))
    unmatched_predicted = set(range(len(predicted_names)))
    exact_matches: list[_ExactMatch] = []

    # Preserve the primary metric's one-to-one exact/alias behavior first.
    for prediction_index, prediction in enumerate(predicted_names):
        normalized = normalize_food_name(prediction)
        match = next(
            (
                index
                for index in sorted(unmatched_expected)
                if normalized in expected[index].normalized_names
            ),
            None,
        )
        if match is None:
            continue
        unmatched_expected.remove(match)
        unmatched_predicted.remove(prediction_index)
        exact_matches.append(
            _ExactMatch(
                expected_index=match,
                prediction_index=prediction_index,
                matched_primary_label=(
                    normalized == normalize_food_name(expected[match].name)
                ),
            )
        )

    strict_missed_count = len(unmatched_expected)
    strict_hallucinated_count = len(unmatched_predicted)
    events: list[RecognitionMismatchEvent] = []

    # A single composite truth can be accepted through a broader alias while the
    # model also emits additional visible components. This neutral category records
    # the pattern without claiming those extras are semantically correct components.
    if (
        len(expected) == 1
        and len(exact_matches) == 1
        and unmatched_predicted
        and not exact_matches[0].matched_primary_label
    ):
        match = exact_matches[0]
        primary_tokens = _primary_tokens(expected[match.expected_index])
        matched_tokens = _tokens(predicted_names[match.prediction_index])
        if matched_tokens and matched_tokens < primary_tokens:
            extra_indices = sorted(unmatched_predicted)
            events.append(
                RecognitionMismatchEvent(
                    kind=RecognitionMismatchKind.COMPOSITE_ALIAS_WITH_EXTRA_PREDICTIONS,
                    expected_labels=(expected[match.expected_index].name,),
                    predicted_labels=(
                        predicted_names[match.prediction_index],
                        *(predicted_names[index] for index in extra_indices),
                    ),
                    strict_error_units=len(extra_indices),
                )
            )
            unmatched_predicted.difference_update(extra_indices)

    # One composite prediction contains two or more independently expected foods.
    for prediction_index in list(sorted(unmatched_predicted)):
        prediction_tokens = _tokens(predicted_names[prediction_index])
        contained_truths = [
            expected_index
            for expected_index in sorted(unmatched_expected)
            if _primary_tokens(expected[expected_index])
            and _primary_tokens(expected[expected_index]) <= prediction_tokens
        ]
        if len(contained_truths) < 2:
            continue
        events.append(
            RecognitionMismatchEvent(
                kind=RecognitionMismatchKind.UNDER_SEGMENTATION,
                expected_labels=tuple(expected[index].name for index in contained_truths),
                predicted_labels=(predicted_names[prediction_index],),
                strict_error_units=len(contained_truths) + 1,
            )
        )
        unmatched_predicted.remove(prediction_index)
        unmatched_expected.difference_update(contained_truths)

    # Multiple predicted fragments jointly cover one expected composite primary label.
    for expected_index in list(sorted(unmatched_expected)):
        primary_tokens = _primary_tokens(expected[expected_index])
        fragment_indices: list[int] = []
        for prediction_index in sorted(unmatched_predicted):
            prediction_tokens = _tokens(predicted_names[prediction_index])
            if prediction_tokens and prediction_tokens < primary_tokens:
                fragment_indices.append(prediction_index)
        if len(fragment_indices) < 2:
            continue
        covered = set().union(
            *(_tokens(predicted_names[index]) for index in fragment_indices)
        )
        if not primary_tokens <= covered:
            continue
        events.append(
            RecognitionMismatchEvent(
                kind=RecognitionMismatchKind.OVER_SEGMENTATION,
                expected_labels=(expected[expected_index].name,),
                predicted_labels=tuple(predicted_names[index] for index in fragment_indices),
                strict_error_units=len(fragment_indices) + 1,
            )
        )
        unmatched_expected.remove(expected_index)
        unmatched_predicted.difference_update(fragment_indices)

    # Prediction contains exactly one primary expected label plus modifiers.
    for prediction_index in list(sorted(unmatched_predicted)):
        prediction_tokens = _tokens(predicted_names[prediction_index])
        candidates = [
            expected_index
            for expected_index in sorted(unmatched_expected)
            if _primary_tokens(expected[expected_index]) < prediction_tokens
        ]
        if len(candidates) != 1:
            continue
        expected_index = candidates[0]
        events.append(
            RecognitionMismatchEvent(
                kind=RecognitionMismatchKind.IDENTITY_WITH_EXTRA_MODIFIERS,
                expected_labels=(expected[expected_index].name,),
                predicted_labels=(predicted_names[prediction_index],),
                strict_error_units=2,
            )
        )
        unmatched_expected.remove(expected_index)
        unmatched_predicted.remove(prediction_index)

    # Prediction is a broader lexical form of one primary expected label.
    for expected_index in list(sorted(unmatched_expected)):
        primary_tokens = _primary_tokens(expected[expected_index])
        candidate_predictions = [
            prediction_index
            for prediction_index in sorted(unmatched_predicted)
            if (
                _tokens(predicted_names[prediction_index])
                and _tokens(predicted_names[prediction_index]) < primary_tokens
            )
        ]
        if len(candidate_predictions) != 1:
            continue
        prediction_index = candidate_predictions[0]
        events.append(
            RecognitionMismatchEvent(
                kind=RecognitionMismatchKind.BROADER_LABEL,
                expected_labels=(expected[expected_index].name,),
                predicted_labels=(predicted_names[prediction_index],),
                strict_error_units=2,
            )
        )
        unmatched_expected.remove(expected_index)
        unmatched_predicted.remove(prediction_index)

    # Shared primary-label token(s), but neither side contains the other. This is
    # intentionally neutral and does not imply semantic equivalence.
    for expected_index in list(sorted(unmatched_expected)):
        primary_tokens = _primary_tokens(expected[expected_index])
        candidate_predictions = [
            prediction_index
            for prediction_index in sorted(unmatched_predicted)
            if _partial_overlap(primary_tokens, _tokens(predicted_names[prediction_index]))
        ]
        if len(candidate_predictions) != 1:
            continue
        prediction_index = candidate_predictions[0]
        reverse_candidates = [
            other_expected_index
            for other_expected_index in sorted(unmatched_expected)
            if _partial_overlap(
                _primary_tokens(expected[other_expected_index]),
                _tokens(predicted_names[prediction_index]),
            )
        ]
        if reverse_candidates != [expected_index]:
            continue
        events.append(
            RecognitionMismatchEvent(
                kind=RecognitionMismatchKind.PARTIAL_IDENTITY_OVERLAP,
                expected_labels=(expected[expected_index].name,),
                predicted_labels=(predicted_names[prediction_index],),
                strict_error_units=2,
            )
        )
        unmatched_expected.remove(expected_index)
        unmatched_predicted.remove(prediction_index)

    for expected_index in sorted(unmatched_expected):
        events.append(
            RecognitionMismatchEvent(
                kind=RecognitionMismatchKind.UNEXPLAINED_MISS,
                expected_labels=(expected[expected_index].name,),
                predicted_labels=(),
                strict_error_units=1,
            )
        )
    for prediction_index in sorted(unmatched_predicted):
        events.append(
            RecognitionMismatchEvent(
                kind=RecognitionMismatchKind.UNEXPLAINED_PREDICTION,
                expected_labels=(),
                predicted_labels=(predicted_names[prediction_index],),
                strict_error_units=1,
            )
        )

    if sum(event.strict_error_units for event in events) != (
        strict_missed_count + strict_hallucinated_count
    ):
        raise AssertionError("recognition diagnostic did not conserve strict error units")

    return RecognitionSegmentationDiagnostics(
        exact_match_count=len(exact_matches),
        strict_missed_count=strict_missed_count,
        strict_hallucinated_count=strict_hallucinated_count,
        events=tuple(events),
    )


def aggregate_segmentation_diagnostics(values: Iterable[RecognitionSegmentationDiagnostics]) -> dict:
    values = list(values)
    event_counts: Counter[str] = Counter()
    error_units: Counter[str] = Counter()
    strict_missed = 0
    strict_hallucinated = 0
    exact_matches = 0
    for value in values:
        strict_missed += value.strict_missed_count
        strict_hallucinated += value.strict_hallucinated_count
        exact_matches += value.exact_match_count
        for event in value.events:
            event_counts[str(event.kind)] += 1
            error_units[str(event.kind)] += event.strict_error_units
    return {
        "case_count": len(values),
        "exact_match_count": exact_matches,
        "strict_missed_count": strict_missed,
        "strict_hallucinated_count": strict_hallucinated,
        "strict_error_units": strict_missed + strict_hallucinated,
        "structural_event_count": sum(event_counts.values()),
        "category_event_counts": dict(sorted(event_counts.items())),
        "category_strict_error_units": dict(sorted(error_units.items())),
        "note": (
            "Diagnostic taxonomy only. Primary strict normalized exact label/alias "
            "precision/recall/F1 are not modified."
        ),
    }


def _tokens(value: str) -> frozenset[str]:
    return frozenset(normalize_food_name(value).split())


def _primary_tokens(value: ExpectedFood) -> frozenset[str]:
    return _tokens(value.name)


def _partial_overlap(
    expected_tokens: frozenset[str], prediction_tokens: frozenset[str]
) -> bool:
    return bool(
        expected_tokens
        and prediction_tokens
        and expected_tokens & prediction_tokens
        and not expected_tokens <= prediction_tokens
        and not prediction_tokens <= expected_tokens
    )
