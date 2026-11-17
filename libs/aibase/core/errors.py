from typing import Any


class AppError(Exception):
    status_code = 500
    code = "internal_error"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class BadRequest(AppError):
    status_code = 400
    code = "bad_request"


class Unauthorized(AppError):
    status_code = 401
    code = "unauthorized"


class Forbidden(AppError):
    status_code = 403
    code = "forbidden"


class NotFound(AppError):
    status_code = 404
    code = "not_found"


class PayloadTooLarge(AppError):
    status_code = 413
    code = "payload_too_large"


class GuardrailViolation(AppError):
    status_code = 422
    code = "guardrail_violation"


class RateLimited(AppError):
    status_code = 429
    code = "rate_limited"


class ProviderError(AppError):
    status_code = 502
    code = "provider_error"


class ProviderUnavailable(AppError):
    status_code = 503
    code = "provider_unavailable"


class PHIRedactionError(AppError):
    """Redaction failed; the request must not proceed. Message must never contain PHI."""

    status_code = 500
    code = "phi_redaction_failed"


class ConfigError(AppError):
    status_code = 500
    code = "config_error"
