from __future__ import annotations

from typing import Any

import pytest

from xyo._builders import (
    build_download_headers,
    build_request_headers,
    validate_batch_enrichment_requests,
    validate_single_enrichment_request,
    validate_status_job_id,
)
from xyo.config import ClientConfig
from xyo.exceptions import XyoClientException
from xyo.models import EnrichmentRequest
from xyo.security import DownloadSecurityPolicy


def test_validate_single_enrichment_request() -> None:
    req_obj = EnrichmentRequest("Costa", "GB")
    res1 = validate_single_enrichment_request(req_obj)
    assert res1["content"] == "Costa"
    assert res1["countryCode"] == "GB"

    res2 = validate_single_enrichment_request("Starbucks", "US")
    assert res2["content"] == "Starbucks"
    assert res2["countryCode"] == "US"

    with pytest.raises(XyoClientException) as exc_info:
        validate_single_enrichment_request("Costa", None)
    assert exc_info.value.status_code == 400
    assert "country_code is required" in exc_info.value.message


def test_validate_batch_enrichment_requests() -> None:
    with pytest.raises(XyoClientException) as exc_empty:
        validate_batch_enrichment_requests([])
    assert exc_empty.value.status_code == 400

    with pytest.raises(XyoClientException) as exc_null:
        validate_batch_enrichment_requests([None])  # type: ignore[list-item]
    assert exc_null.value.status_code == 400

    with pytest.raises(XyoClientException) as exc_type:
        validate_batch_enrichment_requests([12345])  # type: ignore
    assert exc_type.value.status_code == 400

    batch: list[EnrichmentRequest | dict[str, Any]] = [
        EnrichmentRequest("Costa", "GB"),
        {"content": "Starbucks", "countryCode": "US"},
    ]
    res = validate_batch_enrichment_requests(batch)
    assert len(res) == 2
    assert res[0]["content"] == "Costa"
    assert res[1]["content"] == "Starbucks"


def test_validate_batch_enrichment_requests_size_limits() -> None:
    # 50,001 items exceeds upper bound
    oversized = [{"content": f"Tx{i}", "countryCode": "US"} for i in range(50001)]
    with pytest.raises(XyoClientException) as exc_limit:
        validate_batch_enrichment_requests(oversized)
    assert exc_limit.value.status_code == 400
    assert "exceeds maximum allowed limit of 50000" in exc_limit.value.message


def test_validate_status_job_id() -> None:
    assert validate_status_job_id("job-123") == "job-123"
    assert validate_status_job_id("  job-456  ") == "job-456"

    with pytest.raises(XyoClientException) as exc_blank:
        validate_status_job_id("   ")
    assert exc_blank.value.status_code == 400

    with pytest.raises(XyoClientException) as exc_none:
        validate_status_job_id("")
    assert exc_none.value.status_code == 400


def test_build_request_headers() -> None:
    cfg = ClientConfig(
        correlation_id="corr-789",
        traceparent="00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
        default_headers={"X-Custom": "val", "Accept": "ignored"},
    )
    headers = build_request_headers(cfg, token="test-token", api_user="tenant-user")
    assert headers["Authorization"] == "Bearer test-token"
    assert headers["Accept"] == "application/json"
    assert headers["Content-Type"] == "application/json"
    assert headers["x-api-user"] == "tenant-user"
    assert headers["X-Correlation-ID"] == "corr-789"
    assert headers["traceparent"] == "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
    assert headers["X-Custom"] == "val"


def test_build_request_headers_override_tracing() -> None:
    cfg = ClientConfig(correlation_id="cfg-corr", traceparent="cfg-trace")
    headers = build_request_headers(
        cfg,
        token="test-token",
        correlation_id="method-corr",
        traceparent="method-trace",
    )
    assert headers["X-Correlation-ID"] == "method-corr"
    assert headers["traceparent"] == "method-trace"


def test_build_download_headers() -> None:
    cfg = ClientConfig(correlation_id="corr-123", traceparent="trace-123")
    policy = DownloadSecurityPolicy("https://api.xyo.financial")

    # API host should include Bearer token
    h1 = build_download_headers(cfg, policy, "https://api.xyo.financial/file.tar.gz", token="auth-token")
    assert h1["Authorization"] == "Bearer auth-token"
    assert h1["X-Correlation-ID"] == "corr-123"
    assert h1["traceparent"] == "trace-123"

    # External storage host should NOT include Bearer token
    h2 = build_download_headers(
        cfg,
        policy,
        "https://xyo-financial.s3.amazonaws.com/file.tar.gz",
        token="auth-token",
        correlation_id="method-corr",
        traceparent="method-trace",
    )
    assert "Authorization" not in h2
    assert h2["X-Correlation-ID"] == "method-corr"
    assert h2["traceparent"] == "method-trace"


def test_crlf_check_with_uuid() -> None:
    import uuid

    u1 = uuid.uuid4()
    u2 = uuid.uuid4()
    cfg = ClientConfig(correlation_id=u1, traceparent=u2)  # type: ignore[arg-type]
    headers = build_request_headers(cfg, token="test-token", correlation_id=u1, traceparent=u2)
    assert headers["X-Correlation-ID"] == str(u1)
    assert headers["traceparent"] == str(u2)
