"""Request preparation and validation helpers for synchronous and asynchronous clients."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote, urlparse

from xyo.config import ClientConfig
from xyo.exceptions import XyoClientException
from xyo.models import EnrichmentRequest
from xyo.security import DownloadSecurityPolicy, validate_api_user


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
    requests: list[EnrichmentRequest | dict[str, Any]],
) -> list[dict[str, str]]:
    """Validates bulk transaction enrichment batch items and returns list of dictionaries."""
    if not requests:
        raise XyoClientException(400, "Transaction collection batch cannot be empty.")

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

    _apply_config_headers(config, headers)
    return headers


def build_download_headers(
    config: ClientConfig,
    security_policy: DownloadSecurityPolicy,
    validated_url: str,
    token: str | None = None,
) -> dict[str, str]:
    """Builds headers for archive download respecting Zero-Trust egress host policy."""
    parsed = urlparse(validated_url)
    headers: dict[str, str] = {
        "Accept": "application/gzip, application/x-tar, application/octet-stream, */*",
    }
    if token and not security_policy.is_external_storage_host(parsed.hostname or ""):
        headers["Authorization"] = f"Bearer {token}"

    _apply_config_headers(config, headers)
    return headers


def _apply_config_headers(config: ClientConfig, headers: dict[str, str]) -> None:
    """Applies correlation ID and default headers from ClientConfig."""
    if config.correlation_id and "X-Correlation-ID" not in headers:
        headers["X-Correlation-ID"] = config.correlation_id
    for k, v in config.default_headers.items():
        if k not in headers:
            headers[k] = v
