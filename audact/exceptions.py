"""
Audact SDK exceptions.

All exceptions raised by the SDK inherit from AudactError so callers can
catch the entire SDK error hierarchy with a single except clause.
"""

from __future__ import annotations

from typing import Any

from .models import RateLimitInfo


class AudactError(Exception):
    """Base class for all Audact SDK errors."""


class AudactAPIError(AudactError):
    """
    Raised when the Audact API returns a non-2xx response.

    The server writes every error as a nested envelope::

        {"error": {"code", "message", "hint", "details", "request_id"}}

    ``hint``/``details``/``request_id`` are ``omitempty`` on the wire, so
    they may be absent even on a real error.

    Attributes:
        status_code: The HTTP status code returned by the server.
        code:        The machine-readable error code from ``error.code``
                     (e.g. ``"INVALID_REQUEST"``, ``"NOT_FOUND"``).
        message:     The human-readable error message from ``error.message``.
        details:     Optional extra context dict from ``error.details``.
        hint:        Optional human-readable remediation suggestion from
                     ``error.hint``, or ``None`` if the server did not send one.
        request_id:  The request id to quote when contacting support, read
                     from ``error.request_id`` (falling back to the
                     ``X-Request-ID`` response header), or ``None`` if
                     neither was present.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        code: str = "UNKNOWN",
        details: dict[str, Any] | None = None,
        hint: str | None = None,
        request_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}
        self.hint = hint
        self.request_id = request_id

    def __repr__(self) -> str:
        return (
            f"AudactAPIError(status_code={self.status_code!r}, "
            f"code={self.code!r}, message={self.message!r}, "
            f"request_id={self.request_id!r})"
        )


class AudactAuthError(AudactAPIError):
    """Raised when authentication fails (HTTP 401)."""


class AudactForbiddenError(AudactAPIError):
    """Raised when the caller lacks permission for the operation (HTTP 403)."""


class AudactNotFoundError(AudactAPIError):
    """Raised when a requested resource does not exist (HTTP 404)."""


class AudactRateLimitError(AudactAPIError):
    """
    Raised when a rate limit is exceeded (HTTP 429).

    Attributes:
        retry_after: Seconds to wait before retrying, parsed from the
                     ``Retry-After`` response header (set by
                     the API), or ``None`` if the server did not send one.
        rate_limit:  A :class:`~audact.models.RateLimitInfo` snapshot of the
                     ``X-RateLimit-Limit``/``X-RateLimit-Remaining``/
                     ``X-RateLimit-Reset`` response headers, or ``None`` if
                     none of them were present.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        code: str = "UNKNOWN",
        details: dict[str, Any] | None = None,
        hint: str | None = None,
        request_id: str | None = None,
        retry_after: int | None = None,
        rate_limit: RateLimitInfo | None = None,
    ) -> None:
        super().__init__(
            message,
            status_code=status_code,
            code=code,
            details=details,
            hint=hint,
            request_id=request_id,
        )
        self.retry_after = retry_after
        self.rate_limit = rate_limit


class AudactTimeoutError(AudactError):
    """Raised when a request times out before the server responds."""


class AudactConnectionError(AudactError):
    """Raised when the SDK cannot connect to an Audact service."""
