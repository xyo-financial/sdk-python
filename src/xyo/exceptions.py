"""Typed exception hierarchy for the XYO Financial Python SDK."""

from __future__ import annotations

import json
from typing import Any


class XyoException(Exception):
    """Base exception for all errors originating from the XYO SDK."""

    def __init__(self, message: str, *args: Any) -> None:
        super().__init__(message, *args)
        self.message = message


class XyoClientException(XyoException):
    """Exception raised when the API returns an HTTP 4xx client-side error."""

    def __init__(
        self,
        status_code: int,
        message: str,
        raw_body: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.raw_body = raw_body

    def is_auth(self) -> bool:
        """Returns True if the error is 401 Unauthorized or 403 Forbidden."""
        return self.status_code in (401, 403)

    def is_not_found(self) -> bool:
        """Returns True if the target resource was not found (404)."""
        return self.status_code == 404

    def is_rate_limited(self) -> bool:
        """Returns True if the request was rate-limited (429 Too Many Requests)."""
        return self.status_code == 429


class XyoProblemDetailsException(XyoClientException):
    """Exception raised when the API returns an RFC 7807 Problem Details document."""

    def __init__(
        self,
        status_code: int,
        message: str,
        type: str | None = None,
        title: str | None = None,
        status: int | None = None,
        detail: str | None = None,
        instance: str | None = None,
        errors: dict[str, list[str]] | None = None,
        raw_body: str | None = None,
    ) -> None:
        super().__init__(status_code, message, raw_body=raw_body)
        self.type = type
        self.title = title
        self.status = status or status_code
        self.detail = detail
        self.instance = instance
        self.errors = errors or {}

    @classmethod
    def from_json(cls, status_code: int, payload: str) -> XyoProblemDetailsException:
        """Attempts to parse an RFC 7807 problem details JSON string into a structured exception."""
        try:
            data = json.loads(payload)
            if isinstance(data, dict):
                p_type = data.get("type")
                p_title = data.get("title")
                p_status = data.get("status", status_code)
                p_detail = data.get("detail")
                p_instance = data.get("instance")
                raw_errors = data.get("errors")

                errors: dict[str, list[str]] = {}
                if isinstance(raw_errors, dict):
                    for k, v in raw_errors.items():
                        if isinstance(v, list):
                            errors[k] = [str(item) for item in v]
                        else:
                            errors[k] = [str(v)]

                msg = p_detail or p_title or f"[HTTP {status_code}] Request failed"
                return cls(
                    status_code=status_code,
                    message=msg,
                    type=p_type,
                    title=p_title,
                    status=p_status,
                    detail=p_detail,
                    instance=p_instance,
                    errors=errors,
                    raw_body=payload,
                )
        except Exception:
            pass

        sanitized = payload[:512] + "..." if len(payload) > 512 else payload
        return cls(
            status_code=status_code,
            message=f"[HTTP {status_code}] {sanitized}",
            status=status_code,
            raw_body=payload,
        )


class XyoServerException(XyoException):
    """Exception raised when the API returns an HTTP 5xx server-side error."""

    def __init__(
        self,
        status_code: int,
        message: str,
        raw_body: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.raw_body = raw_body

    def is_retryable(self) -> bool:
        """Returns True if the server error is transient and safe to retry."""
        return self.status_code in (500, 502, 503, 504)


class XyoNetworkException(XyoException):
    """Exception raised when a transport or network layer failure occurs."""

    def __init__(self, message: str, original_exception: Exception | None = None) -> None:
        super().__init__(message)
        self.original_exception = original_exception
        self.is_retryable = True


# Aliases for Acceptance Criteria and OpenAPI parity
ErrorResponse = XyoProblemDetailsException
APIError = XyoClientException
