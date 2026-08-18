from typing import Any


class ApplicationError(Exception):
    code = "APPLICATION_ERROR"
    status_code = 400

    def __init__(self, message: str, *, details: Any = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class NotFoundError(ApplicationError):
    code = "NOT_FOUND"
    status_code = 404


class ConflictError(ApplicationError):
    code = "CONFLICT"
    status_code = 409


class ValidationError(ApplicationError):
    code = "INVALID_REQUEST"
    status_code = 422


class ForbiddenError(ApplicationError):
    code = "FORBIDDEN"
    status_code = 403


class MealNotFoundError(NotFoundError):
    code = "MEAL_NOT_FOUND"


class ItemNotFoundError(NotFoundError):
    code = "ITEM_NOT_FOUND"


class ClarificationNotFoundError(NotFoundError):
    code = "CLARIFICATION_NOT_FOUND"


class ClarificationAnswerConflictError(ConflictError):
    code = "CLARIFICATION_ALREADY_ANSWERED"


class InvalidMealStateError(ConflictError):
    code = "INVALID_MEAL_STATE"


class UnsupportedImageError(ValidationError):
    code = "UNSUPPORTED_IMAGE"


class ImageTooLargeError(ApplicationError):
    code = "IMAGE_TOO_LARGE"
    status_code = 413


class UnresolvedClarificationsError(ConflictError):
    code = "UNRESOLVED_CLARIFICATIONS"


class CanonicalFoodNotFoundError(ValidationError):
    code = "CANONICAL_FOOD_NOT_FOUND"


class AnalysisFailedError(ApplicationError):
    code = "ANALYSIS_FAILED"
    status_code = 500


class RetryableProviderError(ApplicationError):
    code = "ANALYSIS_TEMPORARILY_UNAVAILABLE"
    status_code = 503


class PermanentProviderError(AnalysisFailedError):
    pass


class RateLimitedError(ApplicationError):
    code = "RATE_LIMITED"
    status_code = 429
