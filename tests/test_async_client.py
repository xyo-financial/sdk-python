"""Unit and integration tests for the asynchronous AsyncClient."""

from __future__ import annotations

import io
import json
import tarfile

import httpx
import pytest
import respx

from xyo import (
    AsyncClient,
    ClientConfig,
    EnrichmentRequest,
    XyoClientException,
    XyoServerException,
)


def create_tar_gz_bytes(entries: list[tuple[str, dict | str]]) -> bytes:
    bio = io.BytesIO()
    with tarfile.open(fileobj=bio, mode="w:gz") as tar:
        for name, data in entries:
            raw_bytes = json.dumps(data).encode("utf-8") if isinstance(data, dict) else data.encode("utf-8")
            ti = tarfile.TarInfo(name=name)
            ti.size = len(raw_bytes)
            tar.addfile(ti, io.BytesIO(raw_bytes))
    return bio.getvalue()


@pytest.mark.asyncio
async def test_async_enrich_transaction(mock_enrichment_response_json: dict) -> None:
    with respx.mock(base_url="https://api.xyo.financial") as respx_mock:
        route = respx_mock.post("/v1/ai/finance/enrichment/transaction").mock(
            return_value=httpx.Response(200, json=mock_enrichment_response_json)
        )

        async with AsyncClient(api_key="xyo_async_test_key") as client:
            resp = await client.enrich_transaction(content="SQ *COSTA COFFEE GREENWICH", country_code="GB")

            assert resp.merchant == "Costa Coffee"
            assert resp.name == "Costa Coffee"
            assert resp.category == "Food & Dining"
            assert route.called
            req = route.calls.last.request
            assert req.headers["Authorization"] == "Bearer xyo_async_test_key"


@pytest.mark.asyncio
async def test_async_enrich_transaction_model_input(mock_enrichment_response_json: dict) -> None:
    with respx.mock(base_url="https://api.xyo.financial") as respx_mock:
        respx_mock.post("/v1/ai/finance/enrichment/transaction").mock(
            return_value=httpx.Response(200, json=mock_enrichment_response_json)
        )

        async with AsyncClient(api_key="xyo_async_test_key") as client:
            req = EnrichmentRequest(content="COSTA", country_code="GB")
            resp = await client.enrich_transaction(req)
            assert resp.merchant == "Costa Coffee"


@pytest.mark.asyncio
async def test_async_enrich_transactions_batch(mock_batch_response_json: dict) -> None:
    with respx.mock(base_url="https://api.xyo.financial") as respx_mock:
        route = respx_mock.post("/v1/ai/finance/enrichment/transactions").mock(
            return_value=httpx.Response(200, json=mock_batch_response_json)
        )

        async with AsyncClient(api_key="xyo_async_test_key") as client:
            batch = [
                EnrichmentRequest("COSTA", "GB"),
                {"content": "STARBUCKS", "countryCode": "US"},
            ]
            resp = await client.enrich_transactions(batch, api_user="tenant_beta")

            assert resp.id == "batch_job_12345"
            assert resp.link == "https://download.xyo.financial/batches/12345.tar.gz"
            assert route.called


@pytest.mark.asyncio
async def test_async_get_enrichment_status(mock_status_response_json: dict) -> None:
    with respx.mock(base_url="https://api.xyo.financial") as respx_mock:
        route = respx_mock.get("/v1/ai/finance/enrichment/transaction/collection/status").mock(
            return_value=httpx.Response(200, json=mock_status_response_json)
        )

        async with AsyncClient(api_key="xyo_async_test_key") as client:
            status = await client.get_enrichment_status("batch_job_12345", api_user="tenant_test")
            assert status.status == "READY"
            assert route.called


@pytest.mark.asyncio
async def test_async_stream_and_download_collection() -> None:
    record = {
        "merchant": "Costa Coffee",
        "description": "Desc",
        "categories": ["Food"],
    }
    tar_bytes = create_tar_gz_bytes([("costa.json", record)])

    with respx.mock(base_url="https://download.xyo.financial") as respx_mock:
        respx_mock.get("/batches/12345.tar.gz").mock(return_value=httpx.Response(200, content=tar_bytes))

        async with AsyncClient(api_key="xyo_async_test_key") as client:
            records = await client.download_enrichment_collection("https://download.xyo.financial/batches/12345.tar.gz")
            assert len(records) == 1
            assert records[0].merchant == "Costa Coffee"

            streamed: list = []
            async for item in client.stream_enrichment_collection(
                "https://download.xyo.financial/batches/12345.tar.gz"
            ):
                streamed.append(item)
            assert len(streamed) == 1
            assert streamed[0].merchant == "Costa Coffee"


@pytest.mark.asyncio
async def test_async_validation_errors() -> None:
    async with AsyncClient(api_key="xyo_key") as client:
        with pytest.raises(XyoClientException):
            await client.enrich_transaction(content="COSTA")  # missing country_code

        with pytest.raises(XyoClientException):
            await client.enrich_transactions([])

        with pytest.raises(XyoClientException):
            await client.enrich_transactions([None])  # type: ignore[list-item]

        with pytest.raises(XyoClientException):
            await client.enrich_transactions([123])  # type: ignore[list-item]

        with pytest.raises(XyoClientException):
            await client.get_enrichment_status("")


@pytest.mark.asyncio
async def test_async_error_responses() -> None:
    with respx.mock(base_url="https://api.xyo.financial") as respx_mock:
        respx_mock.post("/v1/ai/finance/enrichment/transaction").mock(
            return_value=httpx.Response(500, text="Internal Server Error")
        )

        async with AsyncClient(api_key="xyo_key") as client:
            with pytest.raises(XyoServerException) as exc_info:
                await client.enrich_transaction("COSTA", "GB")
            assert exc_info.value.status_code == 500


@pytest.mark.asyncio
async def test_async_dynamic_token_supplier() -> None:
    async def async_supplier() -> str:
        return "async_vault_secret"

    with respx.mock(base_url="https://api.xyo.financial") as respx_mock:
        route = respx_mock.post("/v1/ai/finance/enrichment/transaction").mock(
            return_value=httpx.Response(200, json={"merchant": "Merchant", "description": "Desc"})
        )

        config = ClientConfig(token_supplier=async_supplier)
        async with AsyncClient(config=config) as client:
            await client.enrich_transaction("COSTA", "GB")
            assert route.calls.last.request.headers["Authorization"] == "Bearer async_vault_secret"
