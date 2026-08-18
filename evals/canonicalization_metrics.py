from dataclasses import dataclass


SELECTOR_ERROR_TAXONOMY = (
    "RETRIEVAL_MISS",
    "SELECTOR_WRONG",
    "SELECTOR_UNNECESSARY_ABSTAIN",
    "SELECTOR_INVALID_RANK",
    "SELECTOR_BRAND_MISMATCH",
    "SELECTOR_PREPARATION_MISMATCH",
    "SELECTOR_VARIANT_MISMATCH",
)


@dataclass(frozen=True)
class SelectorCaseResult:
    expected_rank: int
    supplied_ranks: frozenset[int]
    decision: str
    selected_rank: int | None
    match_quality: str


@dataclass(frozen=True)
class SelectorMetrics:
    selection_accuracy: float
    selective_accuracy: float
    coverage: float
    abstention_rate: float
    wrong_selection_rate: float
    invalid_rank_rate: float
    wrong_strong_selection_rate: float


def selector_metrics(cases: list[SelectorCaseResult]) -> SelectorMetrics:
    if not cases:
        raise ValueError("selector metrics require verified evaluable cases")
    selected = [case for case in cases if case.decision == "SELECT"]
    valid_selected = [
        case for case in selected if case.selected_rank in case.supplied_ranks
    ]
    correct_selected = [
        case for case in valid_selected if case.selected_rank == case.expected_rank
    ]
    wrong_selected = [
        case for case in valid_selected if case.selected_rank != case.expected_rank
    ]
    invalid = [case for case in selected if case.selected_rank not in case.supplied_ranks]
    wrong_strong = [
        case
        for case in wrong_selected
        if case.match_quality in {"EXACT", "STRONG"}
    ]
    total = len(cases)
    return SelectorMetrics(
        selection_accuracy=len(correct_selected) / total,
        selective_accuracy=len(correct_selected) / len(selected) if selected else 0.0,
        coverage=len(selected) / total,
        abstention_rate=(total - len(selected)) / total,
        wrong_selection_rate=len(wrong_selected) / total,
        invalid_rank_rate=len(invalid) / total,
        wrong_strong_selection_rate=len(wrong_strong) / total,
    )


def usda_top_1_accuracy(expected_ranks: list[int]) -> float:
    if not expected_ranks:
        raise ValueError("USDA top-1 baseline requires verified evaluable cases")
    return sum(rank == 1 for rank in expected_ranks) / len(expected_ranks)
