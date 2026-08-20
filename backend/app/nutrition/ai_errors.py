from app.application.errors import ApplicationError, RetryableProviderError


class AINutritionProviderError(ApplicationError):
    code = "AI_NUTRITION_ERROR"
    status_code = 502


class AINutritionConfigurationError(AINutritionProviderError):
    code = "AI_NUTRITION_CONFIGURATION"


class AINutritionInvalidResponseError(AINutritionProviderError):
    code = "AI_NUTRITION_INVALID_RESPONSE"


class AINutritionTimeoutError(RetryableProviderError):
    code = "AI_NUTRITION_TIMEOUT"


class AINutritionRateLimitedError(RetryableProviderError):
    code = "AI_NUTRITION_RATE_LIMITED"


class AINutritionUnavailableError(RetryableProviderError):
    code = "AI_NUTRITION_UNAVAILABLE"
