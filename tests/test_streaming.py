"""Tests for in-memory and streaming TAR archive decompression."""

from __future__ import annotations

import io
import json
import tarfile

import httpx
import pytest
import respx

from xyo import AsyncClient, Client, XyoClientException
from xyo.streaming import decompress_tar_gz_in_memory


def create_mock_tar_gz(entries: list[tuple[str, dict | str | bytes]]) -> bytes:
    """Helper to build an in-memory .tar.gz archive."""
    bio = io.BytesIO()
    with tarfile.open(fileobj=bio, mode="w:gz") as tar:
        for name, data in entries:
            if isinstance(data, dict):
                raw_bytes = json.dumps(data).encode("utf-8")
            elif isinstance(data, str):
                raw_bytes = data.encode("utf-8")
            else:
                raw_bytes = data
            ti = tarfile.TarInfo(name=name)
            ti.size = len(raw_bytes)
            tar.addfile(ti, io.BytesIO(raw_bytes))
    return bio.getvalue()


def test_download_enrichment_collection_success() -> None:
    record1 = {
        "merchant": "Costa Coffee",
        "description": "Desc 1",
        "categories": ["Food & Dining"],
        "logo": "https://cdn.xyo.financial/logo1.png",
        "location": "London, UK",
        "address": "1 High St",
    }
    record2 = {
        "merchant": "Starbucks",
        "description": "Desc 2",
        "categories": ["Coffee Shops"],
        "logo": "https://cdn.xyo.financial/logo2.png",
        "location": "Seattle, US",
        "address": "1 Pike St",
    }

    tar_gz_bytes = create_mock_tar_gz(
        [
            ("001.json", record1),
            ("002.json", record2),
            ("notes.txt", "some plain text"),
        ]
    )

    with respx.mock(base_url="https://download.xyo.financial") as respx_mock:
        respx_mock.get("/batches/12345.tar.gz").mock(return_value=httpx.Response(200, content=tar_gz_bytes))

        with Client(api_key="xyo_test_key") as client:
            records = client.download_enrichment_collection("https://download.xyo.financial/batches/12345.tar.gz")
            assert len(records) == 2
            assert records[0].merchant == "Costa Coffee"
            assert records[1].merchant == "Starbucks"


def test_stream_enrichment_collection_sync() -> None:
    record = {
        "merchant": "Uber",
        "description": "Ride hailing",
        "categories": ["Transportation"],
    }
    tar_gz_bytes = create_mock_tar_gz([("uber.json", record)])

    with respx.mock(base_url="https://download.xyo.financial") as respx_mock:
        respx_mock.get("/batches/12345.tar.gz").mock(return_value=httpx.Response(200, content=tar_gz_bytes))

        with Client(api_key="xyo_test_key") as client:
            streamed = list(client.stream_enrichment_collection("https://download.xyo.financial/batches/12345.tar.gz"))
            assert len(streamed) == 1
            assert streamed[0].merchant == "Uber"


@pytest.mark.asyncio
async def test_stream_enrichment_collection_async() -> None:
    record = {
        "merchant": "TfL",
        "description": "Transport for London",
        "categories": ["Public Transit"],
    }
    tar_gz_bytes = create_mock_tar_gz([("tfl.json", record)])

    with respx.mock(base_url="https://download.xyo.financial") as respx_mock:
        respx_mock.get("/batches/12345.tar.gz").mock(return_value=httpx.Response(200, content=tar_gz_bytes))

        async with AsyncClient(api_key="xyo_test_key") as client:
            records = await client.download_enrichment_collection("https://download.xyo.financial/batches/12345.tar.gz")
            assert len(records) == 1
            assert records[0].merchant == "TfL"


def test_zip_slip_path_traversal_rejected() -> None:
    tar_gz_bytes = create_mock_tar_gz([("../evil.json", {"merchant": "Evil"})])

    with pytest.raises(XyoClientException) as exc_info:
        decompress_tar_gz_in_memory(tar_gz_bytes)
    assert exc_info.value.status_code in (400, 422)
    assert "Path traversal" in exc_info.value.message


def test_control_character_in_tar_entry_rejected() -> None:
    tar_gz_bytes = create_mock_tar_gz([("entry\nname.json", {"merchant": "M"})])

    with pytest.raises(XyoClientException) as exc_info:
        decompress_tar_gz_in_memory(tar_gz_bytes)
    assert exc_info.value.status_code == 400
    assert "control characters" in exc_info.value.message


def test_corrupted_tar_archive_rejected() -> None:
    with pytest.raises(XyoClientException) as exc_info:
        decompress_tar_gz_in_memory(b"invalid corrupt bytes not a tar gz")
    assert exc_info.value.status_code == 422
    assert "Corrupted or invalid tar archive" in exc_info.value.message


def test_invalid_json_in_tar_entry_rejected() -> None:
    tar_gz_bytes = create_mock_tar_gz([("bad.json", b"{invalid json}")])

    with pytest.raises(XyoClientException) as exc_info:
        decompress_tar_gz_in_memory(tar_gz_bytes)
    assert exc_info.value.status_code == 422
    assert "Failed to deserialize JSON" in exc_info.value.message


def test_max_entry_bytes_exceeded_rejected() -> None:
    tar_gz_bytes = create_mock_tar_gz([("big.json", {"merchant": "A" * 100})])

    with pytest.raises(XyoClientException) as exc_info:
        decompress_tar_gz_in_memory(tar_gz_bytes, max_entry_bytes=10)
    assert exc_info.value.status_code == 422
    assert "exceeds maximum size limit" in exc_info.value.message


def test_max_archive_bytes_exceeded_rejected() -> None:
    tar_gz_bytes = create_mock_tar_gz([("01.json", {"merchant": "M"})])

    with pytest.raises(XyoClientException) as exc_info:
        decompress_tar_gz_in_memory(tar_gz_bytes, max_archive_bytes=10)
    assert exc_info.value.status_code == 422
    assert "exceeded maximum allowed byte size" in exc_info.value.message


def test_max_tar_entries_exceeded_rejected() -> None:
    tar_gz_bytes = create_mock_tar_gz(
        [
            ("1.json", {"merchant": "M1"}),
            ("2.json", {"merchant": "M2"}),
            ("3.json", {"merchant": "M3"}),
        ]
    )

    with pytest.raises(XyoClientException) as exc_info:
        decompress_tar_gz_in_memory(tar_gz_bytes, max_tar_entries=2)
    assert exc_info.value.status_code == 422
    assert "exceeds maximum entry count" in exc_info.value.message
