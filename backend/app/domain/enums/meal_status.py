from enum import StrEnum


class MealStatus(StrEnum):
    UPLOADED = "UPLOADED"
    ANALYZING = "ANALYZING"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    CONFIRMED = "CONFIRMED"
    FAILED_RETRYABLE = "FAILED_RETRYABLE"
    FAILED_PERMANENT = "FAILED_PERMANENT"


ALLOWED_MEAL_TRANSITIONS: dict[MealStatus, frozenset[MealStatus]] = {
    MealStatus.UPLOADED: frozenset({MealStatus.ANALYZING}),
    MealStatus.ANALYZING: frozenset(
        {
            MealStatus.NEEDS_REVIEW,
            MealStatus.FAILED_RETRYABLE,
            MealStatus.FAILED_PERMANENT,
        }
    ),
    MealStatus.FAILED_RETRYABLE: frozenset({MealStatus.ANALYZING}),
    MealStatus.NEEDS_REVIEW: frozenset({MealStatus.CONFIRMED, MealStatus.ANALYZING}),
    MealStatus.CONFIRMED: frozenset(),
    MealStatus.FAILED_PERMANENT: frozenset(),
}
