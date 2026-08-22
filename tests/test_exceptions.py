from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

import httpx
import pytest
import respx

from xyo import (
    APIError,
    Client,
    ErrorResponse,
    RateLimitExceededError,
    XyoClientException,
    XyoException,
    XyoNetworkException,
    XyoProblemDetailsException,
    XyoServerException,
)
from xyo.exceptions import parse_rate_limit_headers


def test_rfc7807_problem_details_parsing() -> None:
    problem_json = {
        "type": "https://api.xyo.financial/errors/validation-error",
        "title": "Invalid Request Parameters",
        "status": 422,
        "detail": "The transaction content or country code is invalid.",
        "instance": "/errors/req_998877",
        "errors": {
            "countryCode": ["Must be an ISO 3166-1 alpha-2 format"],
        },
    }

    with respx.mock(base_url="https://api.xyo.financial") as respx_mock:
        respx_mock.post("/v1/ai/finance/enrichment/transaction").mock(
            return_value=httpx.Response(422, json=problem_json)
        )

        with Client(api_key="xyo_test_key") as client:
            with pytest.raises(XyoProblemDetailsException) as exc_info:
                client.enrich_transaction("COSTA", "GB")

            ex = exc_info.value
            assert ex.status_code == 422
            assert ex.type == "https://api.xyo.financial/errors/validation-error"
            assert ex.title == "Invalid Request Parameters"
            assert ex.status == 422
            assert ex.detail == "The transaction content or country code is invalid."
            assert ex.instance == "/errors/req_998877"
            assert "countryCode" in ex.errors
            assert ex.errors["countryCode"] == ["Must be an ISO 3166-1 alpha-2 format"]


def test_error_aliases_compatibility() -> None:
    """Verifies that ErrorResponse and APIError aliases work for acceptance criteria."""
    assert issubclass(ErrorResponse, XyoClientException)
    assert issubclass(APIError, XyoException)


def test_http_401_auth_exception() -> None:
    with respx.mock(base_url="https://api.xyo.financial") as respx_mock:
        respx_mock.post("/v1/ai/finance/enrichment/transaction").mock(
            return_value=httpx.Response(401, json={"title": "Unauthorized", "detail": "Invalid API token."})
        )

        with Client(api_key="invalid_token") as client:
            with pytest.raises(XyoClientException) as exc_info:
                client.enrich_transaction("COSTA", "GB")

            assert exc_info.value.status_code == 401
            assert exc_info.value.is_auth()
            assert not exc_info.value.is_rate_limited()
            assert not exc_info.value.is_not_found()


def test_http_404_not_found_exception() -> None:
    with respx.mock(base_url="https://api.xyo.financial") as respx_mock:
        respx_mock.post("/v1/ai/finance/enrichment/transaction").mock(
            return_value=httpx.Response(404, json={"title": "Not Found", "detail": "Resource not found."})
        )

        with Client(api_key="token") as client:
            with pytest.raises(XyoClientException) as exc_info:
                client.enrich_transaction("COSTA", "GB")

            assert exc_info.value.status_code == 404
            assert exc_info.value.is_not_found()


def test_http_429_rate_limited_exception() -> None:
    headers = {
        "Retry-After": "60",
        "RateLimit-Limit": "1000",
        "RateLimit-Remaining": "0",
        "RateLimit-Reset": "120",
    }
    with respx.mock(base_url="https://api.xyo.financial") as respx_mock:
        respx_mock.post("/v1/ai/finance/enrichment/transaction").mock(
            return_value=httpx.Response(
                429,
                json={"title": "Too Many Requests", "detail": "Rate limit exceeded."},
                headers=headers,
            )
        )

        with Client(api_key="token") as client:
            with pytest.raises(XyoClientException) as exc_info:
                client.enrich_transaction("COSTA", "GB")

            ex = exc_info.value
            assert isinstance(ex, RateLimitExceededError)
            assert ex.status_code == 429
            assert ex.is_rate_limited()
            assert ex.retry_after == 60
            assert ex.rate_limit_limit == 1000
            assert ex.rate_limit_remaining == 0
            assert ex.rate_limit_reset == 120
            assert ex.headers.get("retry-after") == "60" or ex.headers.get("Retry-After") == "60"


def test_http_500_server_exception_is_retryable() -> None:
    with respx.mock(base_url="https://api.xyo.financial") as respx_mock:
        respx_mock.post("/v1/ai/finance/enrichment/transaction").mock(
            return_value=httpx.Response(502, text="Bad Gateway")
        )

        with Client(api_key="token") as client:
            with pytest.raises(XyoServerException) as exc_info:
                client.enrich_transaction("COSTA", "GB")

            assert exc_info.value.status_code == 502
            assert exc_info.value.is_retryable()


def test_network_exception() -> None:
    net_ex = XyoNetworkException("DNS resolution failed")
    assert net_ex.is_retryable
    assert "DNS" in str(net_ex)


def test_problem_details_non_json_fallback() -> None:
    ex = XyoProblemDetailsException.from_json(400, "non-json error message")
    assert ex.status_code == 400
    assert "[HTTP 400] non-json error message" in ex.message


def test_normalized_header_keys_in_exceptions() -> None:
    headers = {"X-RateLimit-Limit": "100", "Content-Type": "application/json"}
    ex = XyoClientException(400, "Bad Request", headers=headers)
    assert "x-ratelimit-limit" in ex.headers
    assert "content-type" in ex.headers
    assert ex.headers["x-ratelimit-limit"] == "100"


def test_problem_details_invalid_json_handling() -> None:
    ex = XyoProblemDetailsException.from_json(400, "{invalid json body")
    assert ex.status_code == 400
    assert "[HTTP 400] {invalid json body" in ex.message


def test_http_500_server_exception_headers_and_retry_after() -> None:
    headers = {
        "Retry-After": "30",
        "X-Correlation-ID": "corr-500-123",
        "Authorization": "Bearer secret-token",
    }
    with respx.mock(base_url="https://api.xyo.financial") as respx_mock:
        respx_mock.post("/v1/ai/finance/enrichment/transaction").mock(
            return_value=httpx.Response(503, text="Service Unavailable", headers=headers)
        )

        with Client(api_key="token") as client:
            with pytest.raises(XyoServerException) as exc_info:
                client.enrich_transaction("COSTA", "GB")

            ex = exc_info.value
            assert ex.status_code == 503
            assert ex.is_retryable()
            assert ex.retry_after == 30
            assert ex.headers.get("x-correlation-id") == "corr-500-123"
            assert "authorization" not in ex.headers


def test_parse_rate_limit_headers_rfc9110_http_date() -> None:
    future = datetime.now(timezone.utc) + timedelta(seconds=120)
    http_date_str = format_datetime(future, usegmt=True)

    headers = {"Retry-After": http_date_str}
    rl_info = parse_rate_limit_headers(headers)

    assert rl_info["retry_after"] is not None
    assert isinstance(rl_info["retry_after"], (int, float))
    assert 110 <= rl_info["retry_after"] <= 130
