from app.application.errors import ApplicationError, PermanentProviderError, RetryableProviderError


class CanonicalizationConfigurationError(ApplicationError):
    code = "CANONICALIZATION_CONFIGURATION_ERROR"
    status_code = 503


class CanonicalizationTimeoutError(RetryableProviderError):
    code = "CANONICALIZATION_TIMEOUT"


class CanonicalizationRateLimitedError(RetryableProviderError):
    code = "CANONICALIZATION_RATE_LIMITED"


class CanonicalizationUnavailableError(RetryableProviderError):
    code = "CANONICALIZATION_UNAVAILABLE"


class CanonicalizationRefusedError(PermanentProviderError):
    code = "CANONICALIZATION_REFUSED"
    status_code = 502


class CanonicalizationInvalidResponseError(PermanentProviderError):
    code = "CANONICALIZATION_INVALID_RESPONSE"
    status_code = 502


class CanonicalizationInvalidSelectionError(PermanentProviderError):
    code = "CANONICALIZATION_INVALID_SELECTION"
    status_code = 502
