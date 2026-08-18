from app.application.errors import (
    ApplicationError,
    PermanentProviderError,
    RetryableProviderError,
    ValidationError,
)


class VisionConfigurationError(ApplicationError):
    code = "VISION_CONFIGURATION_ERROR"
    status_code = 503


class VisionTimeoutError(RetryableProviderError):
    code = "VISION_TIMEOUT"


class VisionRateLimitedError(RetryableProviderError):
    code = "VISION_RATE_LIMITED"


class VisionUnavailableError(RetryableProviderError):
    code = "VISION_UNAVAILABLE"


class VisionRefusedError(PermanentProviderError):
    code = "VISION_REFUSED"
    status_code = 502


class VisionInvalidResponseError(PermanentProviderError):
    code = "VISION_INVALID_RESPONSE"
    status_code = 502


class VisionUnsupportedImageError(ValidationError):
    code = "VISION_UNSUPPORTED_IMAGE"


class VisionImageUnavailableError(PermanentProviderError):
    code = "VISION_IMAGE_UNAVAILABLE"
    status_code = 500
