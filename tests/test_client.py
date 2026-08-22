"""Unit and integration tests for the synchronous Client."""

from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx

from xyo import Client, ClientConfig, EnrichmentRequest, XyoClientException, XyoServerException


def test_enrich_transaction_valid_request(mock_enrichment_response_json: dict[str, Any]) -> None:
    with respx.mock(base_url="https://api.xyo.financial") as respx_mock:
        route = respx_mock.post("/v1/ai/finance/enrichment/transaction").mock(
            return_value=httpx.Response(200, json=mock_enrichment_response_json)
        )

        with Client(api_key="xyo_test_key_123") as client:
            resp = client.enrich_transaction(content="SQ *COSTA COFFEE GREENWICH", country_code="GB")

            assert resp.merchant == "Costa Coffee"
            assert resp.name == "Costa Coffee"
            assert resp.description == "British coffeehouse chain."
            assert resp.categories == ["Food & Dining", "Coffee Shops"]
            assert resp.category == "Food & Dining"
            assert resp.logo == "https://cdn.xyo.financial/logos/costa.png"
            assert resp.location == "United Kingdom, London"
            assert resp.address == "40-42 Great Portland St, London W1W 7LZ"

            assert route.called
            req = route.calls.last.request
            assert req.headers["Authorization"] == "Bearer xyo_test_key_123"


def test_enrich_transaction_structured_model(mock_enrichment_response_json: dict[str, Any]) -> None:
    with respx.mock(base_url="https://api.xyo.financial") as respx_mock:
        respx_mock.post("/v1/ai/finance/enrichment/transaction").mock(
            return_value=httpx.Response(200, json=mock_enrichment_response_json)
        )

        with Client(api_key="xyo_test_key_123") as client:
            req = EnrichmentRequest(content="COSTA", country_code="gb")
            assert req.country_code == "GB"
            resp = client.enrich_transaction(req)
            assert resp.merchant == "Costa Coffee"


def test_enrich_transaction_tracing_headers(mock_enrichment_response_json: dict[str, Any]) -> None:
    with respx.mock(base_url="https://api.xyo.financial") as respx_mock:
        route = respx_mock.post("/v1/ai/finance/enrichment/transaction").mock(
            return_value=httpx.Response(200, json=mock_enrichment_response_json)
        )

        with Client(api_key="key") as client:
            client.enrich_transaction(
                content="COSTA",
                country_code="GB",
                correlation_id="corr-m-1",
                traceparent="00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
            )

            assert route.called
            req = route.calls.last.request
            assert req.headers["X-Correlation-ID"] == "corr-m-1"
            assert req.headers["traceparent"] == "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"


def test_enrich_transaction_validation_errors() -> None:
    with Client(api_key="xyo_test_key_123") as client:
        with pytest.raises(XyoClientException):
            client.enrich_transaction(content="COSTA")

        with pytest.raises(XyoClientException) as exc_info:
            client.enrich_transaction(content="", country_code="GB")
        assert exc_info.value.status_code == 400

        with pytest.raises(XyoClientException) as exc_info:
            client.enrich_transaction(content="A" * 129, country_code="GB")
        assert exc_info.value.status_code == 400

        with pytest.raises(XyoClientException) as exc_info:
            client.enrich_transaction(content="Valid Text", country_code="GBR")
        assert exc_info.value.status_code == 400


def test_enrich_transactions_batch_submission(mock_batch_response_json: dict[str, Any]) -> None:
    with respx.mock(base_url="https://api.xyo.financial") as respx_mock:
        route = respx_mock.post("/v1/ai/finance/enrichment/transactions").mock(
            return_value=httpx.Response(200, json=mock_batch_response_json)
        )

        config = ClientConfig(api_key="xyo_test_key_123", correlation_id="trace_001")
        with Client(config=config) as client:
            batch: list[EnrichmentRequest | dict[str, Any]] = [
                EnrichmentRequest("COSTA", "GB"),
                {"content": "STARBUCKS", "countryCode": "US"},
            ]
            resp = client.enrich_transactions(batch, api_user="tenant_alpha")

            assert resp.id == "batch_job_12345"
            assert resp.link == "https://download.xyo.financial/batches/12345.tar.gz"

            assert route.called
            req = route.calls.last.request
            assert req.headers["x-api-user"] == "tenant_alpha"
            assert req.headers["X-Correlation-ID"] == "trace_001"


def test_enrich_transactions_empty_batch_rejected() -> None:
    with Client(api_key="xyo_test_key_123") as client:
        with pytest.raises(XyoClientException) as exc_info:
            client.enrich_transactions([])
        assert exc_info.value.status_code == 400

        with pytest.raises(XyoClientException):
            client.enrich_transactions([None])  # type: ignore

        with pytest.raises(XyoClientException):
            client.enrich_transactions([123])  # type: ignore


def test_get_enrichment_status(mock_status_response_json: dict[str, Any]) -> None:
    with respx.mock(base_url="https://api.xyo.financial") as respx_mock:
        route = respx_mock.get("/v1/ai/finance/enrichment/transaction/collection/status").mock(
            return_value=httpx.Response(200, json=mock_status_response_json)
        )

        with Client(api_key="xyo_test_key_123") as client:
            status = client.get_enrichment_status("batch_job_12345")
            assert status.status == "READY"
            assert route.called

            with pytest.raises(XyoClientException):
                client.get_enrichment_status("")


def test_client_config_repr_and_resolution() -> None:
    cfg = ClientConfig(api_key="secret_token", correlation_id="trace_123")
    repr_str = repr(cfg)
    assert "secret_token" not in repr_str
    assert "[REDACTED]" in repr_str
    assert cfg.resolve_token() == "secret_token"

    empty_cfg = ClientConfig()
    with pytest.raises(ValueError):
        empty_cfg.resolve_token()


def test_server_error_and_raw_client_error() -> None:
    with respx.mock(base_url="https://api.xyo.financial") as respx_mock:
        respx_mock.post("/v1/ai/finance/enrichment/transaction").mock(
            return_value=httpx.Response(500, text="Server Fault")
        )

        with Client(api_key="key") as client, pytest.raises(XyoServerException):
            client.enrich_transaction("COSTA", "GB")


def test_dynamic_token_supplier() -> None:
    call_count = 0

    def supplier() -> str:
        nonlocal call_count
        call_count += 1
        return f"dynamic_key_{call_count}"

    with respx.mock(base_url="https://api.xyo.financial") as respx_mock:
        route = respx_mock.post("/v1/ai/finance/enrichment/transaction").mock(
            return_value=httpx.Response(200, json={"merchant": "Merchant", "description": "Desc"})
        )

        config = ClientConfig(token_supplier=supplier)
        with Client(config=config) as client:
            client.enrich_transaction("Item 1", "GB")
            client.enrich_transaction("Item 2", "GB")

            assert call_count == 2
            assert route.calls[0].request.headers["Authorization"] == "Bearer dynamic_key_1"
            assert route.calls[1].request.headers["Authorization"] == "Bearer dynamic_key_2"


def test_stream_enrichment_collection_http_error_handling() -> None:
    with respx.mock(base_url="https://download.xyo.financial") as respx_mock:
        respx_mock.get("/batches/notfound.tar.gz").mock(return_value=httpx.Response(404, text="Archive not found"))

        with Client(api_key="key") as client:
            with pytest.raises(XyoClientException) as exc_info:
                list(client.stream_enrichment_collection("https://download.xyo.financial/batches/notfound.tar.gz"))
            assert exc_info.value.status_code == 404
            assert "Archive not found" in exc_info.value.message


def test_client_config_crlf_headers_rejected() -> None:
    with pytest.raises(ValueError, match="CRLF injection"):
        ClientConfig(default_headers={"X-Custom\r\nInjected": "val"})

    with pytest.raises(ValueError, match="CRLF injection"):
        ClientConfig(default_headers={"X-Custom": "val\r\nInjected: true"})
