from dataclasses import dataclass


ERROR_TAXONOMY = (
    "MISSED_FOOD", "HALLUCINATED_FOOD", "WRONG_VARIANT", "WRONG_COOKING_METHOD",
    "WRONG_PORTION", "HIDDEN_INGREDIENT", "DATABASE_MISMATCH", "RETRIEVAL_MISS",
    "SELECTOR_WRONG", "SELECTOR_UNNECESSARY_ABSTAIN", "DUPLICATE_ITEM",
    "UNIT_CONVERSION", "RECIPE_DECOMPOSITION", "PACKAGED_FOOD_ERROR",
)


@dataclass(frozen=True)
class FoodSetMetrics:
    precision: float
    recall: float
    f1: float


def food_set_metrics(expected: set[str], predicted: set[str]) -> FoodSetMetrics:
    true_positive = len(expected & predicted)
    precision = true_positive / len(predicted) if predicted else (1.0 if not expected else 0.0)
    recall = true_positive / len(expected) if expected else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return FoodSetMetrics(precision, recall, f1)


def mean_absolute_error(expected: list[float], predicted: list[float]) -> float:
    if len(expected) != len(predicted) or not expected:
        raise ValueError("expected and predicted must be non-empty and the same length")
    return sum(abs(a - b) for a, b in zip(expected, predicted, strict=True)) / len(expected)


def high_confidence_wrong_rate(correct: list[bool], confidences: list[float], threshold: float = 0.8) -> float:
    if len(correct) != len(confidences):
        raise ValueError("correct and confidences must have the same length")
    high_confidence = [right for right, confidence in zip(correct, confidences, strict=True) if confidence >= threshold]
    return sum(not right for right in high_confidence) / len(high_confidence) if high_confidence else 0.0


def retrieval_recall_at_k(expected_fdc_id: str, ranked_fdc_ids: list[str], k: int) -> float:
    """Score one manually verified retrieval label; null/unverified labels are excluded upstream."""
    if k < 1:
        raise ValueError("k must be at least 1")
    return float(expected_fdc_id in ranked_fdc_ids[:k])
