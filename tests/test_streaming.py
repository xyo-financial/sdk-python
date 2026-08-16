"""Tests for in-memory and streaming TAR archive decompression."""

from __future__ import annotations

import asyncio
import io
import json
import tarfile
from collections.abc import AsyncIterator, Iterator
from unittest.mock import patch

import httpx
import pytest
import respx

from xyo import AsyncClient, Client, XyoClientException
from xyo.streaming import (
    _ChunkReader,
    decompress_tar_gz_in_memory,
    stream_tar_gz_chunks,
    stream_tar_gz_chunks_async,
)


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


def test_decompress_tar_gz_in_memory_accepts_fileobj() -> None:
    tar_gz_bytes = create_mock_tar_gz([("test.json", {"merchant": "Greggs"})])
    bio = io.BytesIO(tar_gz_bytes)
    results = decompress_tar_gz_in_memory(bio)
    assert len(results) == 1
    assert results[0].merchant == "Greggs"


def test_stream_tar_gz_chunks_true_streaming() -> None:
    record1 = {"merchant": "Merchant A"}
    record2 = {"merchant": "Merchant B"}
    tar_gz_bytes = create_mock_tar_gz([("a.json", record1), ("b.json", record2)])

    def chunk_generator() -> Iterator[bytes]:
        for i in range(0, len(tar_gz_bytes), 16):
            yield tar_gz_bytes[i : i + 16]

    streamed = list(stream_tar_gz_chunks(chunk_generator()))
    assert len(streamed) == 2
    assert streamed[0].merchant == "Merchant A"
    assert streamed[1].merchant == "Merchant B"


def test_stream_tar_gz_chunks_archive_limit_exceeded() -> None:
    tar_gz_bytes = create_mock_tar_gz([("a.json", {"merchant": "M"})])

    def chunk_generator() -> Iterator[bytes]:
        yield tar_gz_bytes

    with pytest.raises(XyoClientException) as exc_info:
        list(stream_tar_gz_chunks(chunk_generator(), max_archive_bytes=10))
    assert exc_info.value.status_code == 422
    assert "exceeded maximum allowed byte size" in exc_info.value.message


@pytest.mark.asyncio
async def test_stream_tar_gz_chunks_async_success() -> None:
    record1 = {"merchant": "Merchant A", "category": "Shopping"}
    record2 = {"merchant": "Merchant B", "category": "Dining"}
    tar_gz_bytes = create_mock_tar_gz([("a.json", record1), ("b.json", record2)])

    async def async_chunks() -> AsyncIterator[bytes]:
        for i in range(0, len(tar_gz_bytes), 32):
            yield tar_gz_bytes[i : i + 32]

    results = []
    async for record in stream_tar_gz_chunks_async(async_chunks()):
        results.append(record)

    assert len(results) == 2
    assert results[0].merchant == "Merchant A"
    assert results[1].merchant == "Merchant B"


@pytest.mark.asyncio
async def test_stream_tar_gz_chunks_async_offloaded_to_thread() -> None:
    record = {"merchant": "Async Offload Test"}
    tar_gz_bytes = create_mock_tar_gz([("test.json", record)])

    async def async_chunks() -> AsyncIterator[bytes]:
        yield tar_gz_bytes

    with patch("asyncio.to_thread", wraps=asyncio.to_thread) as mock_to_thread:
        results = []
        async for item in stream_tar_gz_chunks_async(async_chunks()):
            results.append(item)

        assert len(results) == 1
        assert results[0].merchant == "Async Offload Test"
        mock_to_thread.assert_called_once()
        assert mock_to_thread.call_args[0][0] is decompress_tar_gz_in_memory


@pytest.mark.asyncio
async def test_stream_tar_gz_chunks_async_corrupted_archive_propagates() -> None:
    async def async_chunks() -> AsyncIterator[bytes]:
        yield b"not a valid tar gz stream"

    with pytest.raises(XyoClientException) as exc_info:
        async for _ in stream_tar_gz_chunks_async(async_chunks()):
            pass
    assert exc_info.value.status_code == 422
    assert "Corrupted or invalid tar archive" in exc_info.value.message


@pytest.mark.asyncio
async def test_stream_tar_gz_chunks_async_non_blocking_event_loop() -> None:
    record = {"merchant": "Non Blocking Test"}
    tar_gz_bytes = create_mock_tar_gz([("nb.json", record)])

    async def async_chunks() -> AsyncIterator[bytes]:
        yield tar_gz_bytes

    ticks = 0

    async def background_counter() -> None:
        nonlocal ticks
        for _ in range(5):
            await asyncio.sleep(0.001)
            ticks += 1

    bg_task = asyncio.create_task(background_counter())
    results = []
    async for item in stream_tar_gz_chunks_async(async_chunks()):
        results.append(item)

    await bg_task
    assert len(results) == 1
    assert ticks == 5


@pytest.mark.asyncio
async def test_stream_tar_gz_chunks_async_archive_limit_exceeded() -> None:
    tar_gz_bytes = create_mock_tar_gz([("a.json", {"merchant": "M"})])

    async def async_chunks() -> AsyncIterator[bytes]:
        yield tar_gz_bytes

    with pytest.raises(XyoClientException) as exc_info:
        async for _ in stream_tar_gz_chunks_async(async_chunks(), max_archive_bytes=10):
            pass
    assert exc_info.value.status_code == 422
    assert "exceeded maximum allowed byte size" in exc_info.value.message


def test_decompression_bomb_cwe_409_bounded_read() -> None:
    large_payload = {"merchant": "X" * 200}
    tar_gz_bytes = create_mock_tar_gz([("large.json", large_payload)])

    with pytest.raises(XyoClientException) as exc_info:
        decompress_tar_gz_in_memory(tar_gz_bytes, max_entry_bytes=50)
    assert exc_info.value.status_code == 422
    assert "exceeds" in exc_info.value.message


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


def test_chunk_reader_readinto_buffer_types() -> None:
    chunks = [b"hello", b" ", b"world"]
    reader = _ChunkReader(iter(chunks), max_archive_bytes=100)
    assert reader.readable() is True

    # Test with bytearray
    buf1 = bytearray(5)
    n1 = reader.readinto(buf1)
    assert n1 == 5
    assert bytes(buf1) == b"hello"

    # Test with memoryview (next chunk is b" ")
    arr = bytearray(10)
    mview = memoryview(arr)
    n2 = reader.readinto(mview)
    assert n2 == 1
    assert bytes(arr[:1]) == b" "

    # Test with memoryview (next chunk is b"world")
    n3 = reader.readinto(mview)
    assert n3 == 5
    assert bytes(arr[:5]) == b"world"

    # Test EOF
    n4 = reader.readinto(buf1)
    assert n4 == 0
