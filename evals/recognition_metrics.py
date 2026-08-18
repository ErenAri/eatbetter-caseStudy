from dataclasses import dataclass
import re


def normalize_food_name(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.lower()))


@dataclass(frozen=True)
class ExpectedFood:
    name: str
    acceptable_aliases: tuple[str, ...] = ()

    @property
    def normalized_names(self) -> set[str]:
        return {
            normalize_food_name(value)
            for value in (self.name, *self.acceptable_aliases)
        }


@dataclass(frozen=True)
class RecognitionMetrics:
    food_precision: float
    food_recall: float
    food_f1: float
    hallucinated_food_count: int
    missed_food_count: int


def recognition_metrics(
    expected: list[ExpectedFood], predicted_names: list[str]
) -> RecognitionMetrics:
    unmatched = set(range(len(expected)))
    true_positives = 0
    hallucinated = 0
    for prediction in predicted_names:
        normalized = normalize_food_name(prediction)
        match = next(
            (
                index
                for index in sorted(unmatched)
                if normalized in expected[index].normalized_names
            ),
            None,
        )
        if match is None:
            hallucinated += 1
        else:
            unmatched.remove(match)
            true_positives += 1
    precision = (
        true_positives / len(predicted_names)
        if predicted_names
        else (1.0 if not expected else 0.0)
    )
    recall = true_positives / len(expected) if expected else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return RecognitionMetrics(
        food_precision=precision,
        food_recall=recall,
        food_f1=f1,
        hallucinated_food_count=hallucinated,
        missed_food_count=len(unmatched),
    )


def preparation_accuracy(expected: list[str | None], predicted: list[str | None]) -> float:
    labeled = [
        (truth, guess)
        for truth, guess in zip(expected, predicted, strict=True)
        if truth is not None
    ]
    if not labeled:
        raise ValueError("preparation accuracy requires measured ground truth")
    return sum(
        normalize_food_name(truth) == normalize_food_name(guess or "")
        for truth, guess in labeled
    ) / len(labeled)
