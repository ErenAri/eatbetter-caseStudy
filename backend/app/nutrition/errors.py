from app.application.errors import ApplicationError, RetryableProviderError


class USDAProviderError(ApplicationError):
    status_code = 502


class USDAConfigurationError(USDAProviderError):
    code = "USDA_CONFIGURATION_ERROR"
    status_code = 503


class USDATimeoutError(RetryableProviderError):
    code = "USDA_TIMEOUT"


class USDARateLimitedError(RetryableProviderError):
    code = "USDA_RATE_LIMITED"


class USDAUnavailableError(RetryableProviderError):
    code = "USDA_UNAVAILABLE"


class USDAInvalidResponseError(USDAProviderError):
    code = "USDA_INVALID_RESPONSE"


class USDAAuthenticationError(USDAProviderError):
    code = "USDA_AUTHENTICATION_FAILED"
    status_code = 503


class USDAFoodNotFoundError(USDAProviderError):
    code = "USDA_FOOD_NOT_FOUND"
    status_code = 404


class USDAIncompleteNutritionError(USDAProviderError):
    code = "USDA_INCOMPLETE_NUTRITION"
    status_code = 422
