"""Memory-safe in-memory and streaming TAR.GZ archive decompressor."""

from __future__ import annotations

import contextlib
import io
import json
import tarfile
from collections.abc import AsyncIterator, Iterator
from typing import Any, BinaryIO

from xyo.exceptions import XyoClientException
from xyo.models import EnrichmentResponse


def _sanitize_entry_name(name: str) -> None:
    """Enforces Zip Slip (CWE-22) and control character (CWE-117) defenses."""
    if not name:
        return

    for char in name:
        if ord(char) < 32 or ord(char) == 127:
            raise XyoClientException(400, "Tar entry contains forbidden control characters.")

    if ".." in name or name.startswith("/") or name.startswith("\\"):
        raise XyoClientException(400, f"Path traversal detected in archive entry name: '{name}'.")


def _read_and_parse_entry(
    tar: tarfile.TarFile,
    member: tarfile.TarInfo,
    max_entry_bytes: int,
) -> EnrichmentResponse | None:
    """Safely extracts and parses a single JSON entry with CWE-409 decompression bomb defense."""
    _sanitize_entry_name(member.name)

    if not member.isfile() or not member.name.lower().endswith(".json"):
        return None

    if member.size > max_entry_bytes:
        raise XyoClientException(
            422,
            f"Tar entry '{member.name}' exceeds maximum size limit ({max_entry_bytes} bytes). Decompression bomb rejected.",
        )

    extracted = tar.extractfile(member)
    if extracted is None:
        return None

    content = extracted.read(max_entry_bytes + 1)
    if len(content) > max_entry_bytes:
        raise XyoClientException(
            422,
            f"Tar entry '{member.name}' decompressed size exceeds limit ({max_entry_bytes} bytes). Decompression bomb rejected.",
        )

    try:
        payload = json.loads(content.decode("utf-8"))
        return EnrichmentResponse.from_dict(payload)
    except Exception as ex:
        raise XyoClientException(
            422,
            f"Failed to deserialize JSON record from archive entry '{member.name}': {ex}",
        ) from ex


def decompress_tar_gz_in_memory(
    archive_input: bytes | io.IOBase | BinaryIO,
    max_archive_bytes: int = 104_857_600,
    max_entry_bytes: int = 10_485_760,
    max_tar_entries: int = 50_000,
) -> list[EnrichmentResponse]:
    """Decompresses and parses a .tar.gz archive in memory with zero disk I/O and strict safety limits."""
    fileobj: io.IOBase | BinaryIO
    if isinstance(archive_input, bytes):
        if len(archive_input) > max_archive_bytes:
            raise XyoClientException(
                422,
                f"Archive download exceeded maximum allowed byte size ({max_archive_bytes} bytes). Decompression bomb rejected.",
            )
        fileobj = io.BytesIO(archive_input)
    else:
        fileobj = archive_input
        if hasattr(fileobj, "seek"):
            with contextlib.suppress(io.UnsupportedOperation, AttributeError):
                fileobj.seek(0)

    results: list[EnrichmentResponse] = []
    try:
        with tarfile.open(fileobj=fileobj, mode="r|gz") as tar:
            for entry_count, member in enumerate(tar, start=1):
                if entry_count > max_tar_entries:
                    raise XyoClientException(
                        422,
                        f"Tar archive exceeds maximum entry count limit ({max_tar_entries} entries). Possible tar bomb DoS attack.",
                    )

                record = _read_and_parse_entry(tar, member, max_entry_bytes)
                if record is not None:
                    results.append(record)
    except tarfile.TarError as ex:
        raise XyoClientException(422, f"Corrupted or invalid tar archive: {ex}") from ex

    return results


class _ChunkReader(io.RawIOBase):
    """Raw IO stream wrapping an Iterator[bytes] with archive size ceiling enforcement."""

    def __init__(self, iterator: Iterator[bytes], max_archive_bytes: int) -> None:
        self._iterator = iterator
        self._max_archive_bytes = max_archive_bytes
        self._buffer = b""
        self._total_bytes = 0

    def readable(self) -> bool:
        return True

    def readinto(self, b: Any) -> int:
        while not self._buffer:
            try:
                chunk = next(self._iterator)
            except StopIteration:
                return 0
            self._total_bytes += len(chunk)
            if self._total_bytes > self._max_archive_bytes:
                raise XyoClientException(
                    422,
                    f"Archive download exceeded maximum allowed byte size ({self._max_archive_bytes} bytes). Decompression bomb rejected.",
                )
            self._buffer = chunk

        n = min(len(b), len(self._buffer))
        b[:n] = self._buffer[:n]
        self._buffer = self._buffer[n:]
        return n


def stream_tar_gz_chunks(
    chunk_iterator: Iterator[bytes],
    max_archive_bytes: int = 104_857_600,
    max_entry_bytes: int = 10_485_760,
    max_tar_entries: int = 50_000,
) -> Iterator[EnrichmentResponse]:
    """Streams and yields enrichment records on-the-fly from incoming byte chunks using true stream parsing."""
    raw_reader = _ChunkReader(chunk_iterator, max_archive_bytes=max_archive_bytes)
    buffered_stream = io.BufferedReader(raw_reader)

    try:
        with tarfile.open(fileobj=buffered_stream, mode="r|gz") as tar:
            for entry_count, member in enumerate(tar, start=1):
                if entry_count > max_tar_entries:
                    raise XyoClientException(
                        422,
                        f"Tar archive exceeds maximum entry count limit ({max_tar_entries} entries). Possible tar bomb DoS attack.",
                    )

                record = _read_and_parse_entry(tar, member, max_entry_bytes)
                if record is not None:
                    yield record
    except tarfile.TarError as ex:
        raise XyoClientException(422, f"Corrupted or invalid tar archive: {ex}") from ex


async def stream_tar_gz_chunks_async(
    async_chunk_iterator: AsyncIterator[bytes],
    max_archive_bytes: int = 104_857_600,
    max_entry_bytes: int = 10_485_760,
    max_tar_entries: int = 50_000,
) -> AsyncIterator[EnrichmentResponse]:
    """Asynchronously streams and yields enrichment records from incoming async byte chunks."""
    buffer = io.BytesIO()
    total_bytes = 0

    async for chunk in async_chunk_iterator:
        total_bytes += len(chunk)
        if total_bytes > max_archive_bytes:
            raise XyoClientException(
                422,
                f"Archive download exceeded maximum allowed byte size ({max_archive_bytes} bytes). Decompression bomb rejected.",
            )
        buffer.write(chunk)

    buffer.seek(0)
    for record in decompress_tar_gz_in_memory(
        buffer,
        max_archive_bytes=max_archive_bytes,
        max_entry_bytes=max_entry_bytes,
        max_tar_entries=max_tar_entries,
    ):
        yield record
