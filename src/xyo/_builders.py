"""Request preparation and validation helpers for synchronous and asynchronous clients."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from typing import Any
from urllib.parse import quote, urlparse

import httpx

from xyo.config import ClientConfig
from xyo.exceptions import (
    RateLimitExceededError,
    XyoClientException,
    XyoProblemDetailsException,
    XyoServerException,
    parse_rate_limit_headers,
)
from xyo.models import EnrichmentRequest
from xyo.security import DownloadSecurityPolicy, validate_api_user

_CRLF_RE = re.compile(r"[\r\n]")
MAX_BATCH_ITEMS = 50_000


def validate_single_enrichment_request(
    content: str | EnrichmentRequest,
    country_code: str | None = None,
) -> dict[str, str]:
    """Validates single transaction enrichment arguments and returns normalized request payload."""
    if isinstance(content, EnrichmentRequest):
        req = content
    else:
        if country_code is None:
            raise XyoClientException(400, "country_code is required when content is passed as a string.")
        req = EnrichmentRequest(content=content, country_code=country_code)
    return req.to_dict()


def validate_batch_enrichment_requests(
    requests: Sequence[EnrichmentRequest | dict[str, Any]],
) -> list[dict[str, str]]:
    """Validates bulk transaction enrichment batch items and returns list of dictionaries."""
    if not requests:
        raise XyoClientException(
            400, "Transaction collection batch cannot be empty. Batch size must be between 1 and 50,000 items."
        )
    if len(requests) > MAX_BATCH_ITEMS:
        raise XyoClientException(
            400,
            f"Transaction collection batch size ({len(requests)}) exceeds maximum allowed limit of {MAX_BATCH_ITEMS} items.",
        )

    validated_requests: list[dict[str, str]] = []
    for i, item in enumerate(requests):
        if item is None:
            raise XyoClientException(400, f"Transaction item at index {i} cannot be null.")
        if isinstance(item, EnrichmentRequest):
            validated_requests.append(item.to_dict())
        elif isinstance(item, dict):
            req = EnrichmentRequest.from_dict(item)
            validated_requests.append(req.to_dict())
        else:
            raise XyoClientException(400, f"Invalid request item type at index {i}: {type(item)}")

    return validated_requests


def validate_status_job_id(id: str) -> str:
    """Validates and quotes enrichment batch job identifier."""
    if not id or not id.strip():
        raise XyoClientException(400, "Enrichment job identifier cannot be null, empty, or whitespace.")
    return quote(id.strip())


def build_request_headers(
    config: ClientConfig,
    token: str,
    api_user: str | None = None,
    content_type: str | None = "application/json",
    accept: str = "application/json",
    correlation_id: str | Any | None = None,
    traceparent: str | Any | None = None,
) -> dict[str, str]:
    """Builds and sanitizes HTTP request headers with authentication and tracing."""
    validate_api_user(api_user)

    headers: dict[str, str] = {
        "Accept": accept,
    }
    if content_type:
        headers["Content-Type"] = content_type
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if api_user:
        headers["x-api-user"] = api_user.strip()

    _apply_config_headers(config, headers, correlation_id=correlation_id, traceparent=traceparent)
    return headers


def build_download_headers(
    config: ClientConfig,
    security_policy: DownloadSecurityPolicy,
    validated_url: str,
    token: str | None = None,
    correlation_id: str | Any | None = None,
    traceparent: str | Any | None = None,
) -> dict[str, str]:
    """Builds headers for archive download respecting Zero-Trust egress host policy."""
    parsed = urlparse(validated_url)
    headers: dict[str, str] = {
        "Accept": "application/gzip, application/x-tar, application/octet-stream, */*",
    }
    if token and not security_policy.is_external_storage_host(parsed.hostname or ""):
        headers["Authorization"] = f"Bearer {token}"

    _apply_config_headers(config, headers, correlation_id=correlation_id, traceparent=traceparent)
    return headers


def _apply_config_headers(
    config: ClientConfig,
    headers: dict[str, str],
    correlation_id: str | Any | None = None,
    traceparent: str | Any | None = None,
) -> None:
    """Applies correlation ID, traceparent, and default headers from ClientConfig or method parameters."""
    eff_corr = correlation_id if correlation_id is not None else config.correlation_id
    eff_trace = traceparent if traceparent is not None else config.traceparent

    if eff_corr is not None:
        eff_corr_str = str(eff_corr)
        if _CRLF_RE.search(eff_corr_str):
            raise ValueError("Correlation ID contains forbidden CRLF injection characters (CWE-113).")
        headers["X-Correlation-ID"] = eff_corr_str
    if eff_trace is not None:
        eff_trace_str = str(eff_trace)
        if _CRLF_RE.search(eff_trace_str):
            raise ValueError("Traceparent contains forbidden CRLF injection characters (CWE-113).")
        headers["traceparent"] = eff_trace_str

    for k, v in config.default_headers.items():
        if k not in headers:
            headers[k] = str(v)


def handle_http_error(response: httpx.Response) -> None:
    """Evaluates HTTP response status and raises structured SDK exception for error responses."""
    if response.is_success:
        return

    status = response.status_code
    text = response.text
    resp_headers = {k.lower(): v for k, v in response.headers.items()}

    if status >= 500:
        raise XyoServerException(status, text or f"[HTTP {status}] Server error", raw_body=text)

    if status == 429:
        rl_info = parse_rate_limit_headers(response.headers)
        msg = "[HTTP 429] Rate limit exceeded"
        if text and (text.strip().startswith("{") or text.strip().startswith("[")):
            try:
                data = json.loads(text)
                if isinstance(data, dict):
                    msg = data.get("detail") or data.get("title") or msg
            except json.JSONDecodeError:
                pass
        raise RateLimitExceededError(
            status_code=429,
            message=msg,
            raw_body=text,
            retry_after=rl_info["retry_after"],
            rate_limit_limit=rl_info["rate_limit_limit"],
            rate_limit_remaining=rl_info["rate_limit_remaining"],
            rate_limit_reset=rl_info["rate_limit_reset"],
            headers=resp_headers,
        )

    if status >= 400:
        if text and (text.strip().startswith("{") or text.strip().startswith("[")):
            raise XyoProblemDetailsException.from_json(status, text, headers=resp_headers)
        raise XyoClientException(
            status,
            text or f"[HTTP {status}] Client error",
            raw_body=text,
            headers=resp_headers,
        )

    raise XyoClientException(
        status,
        f"[HTTP {status}] Unexpected HTTP response",
        raw_body=text,
        headers=resp_headers,
    )
