from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable

from evals.recognition_metrics import ExpectedFood, normalize_food_name


class RecognitionMismatchKind(StrEnum):
    UNDER_SEGMENTATION = "UNDER_SEGMENTATION"
    OVER_SEGMENTATION = "OVER_SEGMENTATION"
    IDENTITY_WITH_EXTRA_MODIFIERS = "IDENTITY_WITH_EXTRA_MODIFIERS"
    BROADER_LABEL = "BROADER_LABEL"
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


def diagnose_recognition_mismatches(
    expected: list[ExpectedFood], predicted_names: list[str]
) -> RecognitionSegmentationDiagnostics:
    """Explain strict recognition mismatches without changing the primary metric.

    The diagnostic is deliberately lexical and conservative. It first performs the
    same exact normalized label/alias matching used by the primary recognition
    metric. Only the remaining strict misses/hallucinations are classified.

    A classification is explanatory evidence, not an alternate ground-truth match.
    Primary precision/recall/F1 remain unchanged.
    """

    unmatched_expected = set(range(len(expected)))
    unmatched_predicted = set(range(len(predicted_names)))
    exact_match_count = 0

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
        exact_match_count += 1

    strict_missed_count = len(unmatched_expected)
    strict_hallucinated_count = len(unmatched_predicted)
    events: list[RecognitionMismatchEvent] = []

    # One composite prediction contains two or more independently expected foods.
    for prediction_index in list(sorted(unmatched_predicted)):
        prediction_tokens = _tokens(predicted_names[prediction_index])
        contained_truths = [
            expected_index
            for expected_index in sorted(unmatched_expected)
            if _any_alias_subset(expected[expected_index], prediction_tokens, proper=False)
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

    # Multiple predicted fragments jointly cover one expected composite label.
    for expected_index in list(sorted(unmatched_expected)):
        aliases = _alias_token_sets(expected[expected_index])
        fragment_indices: list[int] = []
        for prediction_index in sorted(unmatched_predicted):
            prediction_tokens = _tokens(predicted_names[prediction_index])
            if any(
                prediction_tokens
                and prediction_tokens < alias_tokens
                for alias_tokens in aliases
            ):
                fragment_indices.append(prediction_index)
        if len(fragment_indices) < 2:
            continue
        if not any(
            alias_tokens <= set().union(
                *(_tokens(predicted_names[index]) for index in fragment_indices)
            )
            for alias_tokens in aliases
        ):
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

    # Prediction contains exactly one expected food plus descriptive modifiers.
    for prediction_index in list(sorted(unmatched_predicted)):
        prediction_tokens = _tokens(predicted_names[prediction_index])
        candidates = [
            expected_index
            for expected_index in sorted(unmatched_expected)
            if _any_alias_subset(expected[expected_index], prediction_tokens, proper=True)
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

    # Prediction is a broader lexical form of one expected label.
    for expected_index in list(sorted(unmatched_expected)):
        candidate_predictions = [
            prediction_index
            for prediction_index in sorted(unmatched_predicted)
            if _prediction_is_alias_subset(
                predicted_names[prediction_index], expected[expected_index]
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
        exact_match_count=exact_match_count,
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


def _alias_token_sets(value: ExpectedFood) -> tuple[frozenset[str], ...]:
    seen: set[frozenset[str]] = set()
    output: list[frozenset[str]] = []
    for alias in (value.name, *value.acceptable_aliases):
        tokens = _tokens(alias)
        if tokens and tokens not in seen:
            seen.add(tokens)
            output.append(tokens)
    return tuple(output)


def _any_alias_subset(
    expected: ExpectedFood, prediction_tokens: frozenset[str], *, proper: bool
) -> bool:
    for alias_tokens in _alias_token_sets(expected):
        if proper:
            if alias_tokens < prediction_tokens:
                return True
        elif alias_tokens <= prediction_tokens:
            return True
    return False


def _prediction_is_alias_subset(prediction: str, expected: ExpectedFood) -> bool:
    prediction_tokens = _tokens(prediction)
    return any(
        prediction_tokens and prediction_tokens < alias_tokens
        for alias_tokens in _alias_token_sets(expected)
    )
