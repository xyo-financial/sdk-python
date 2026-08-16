"""Memory-safe in-memory and streaming TAR.GZ archive decompressor."""

from __future__ import annotations

import io
import json
import tarfile
from collections.abc import AsyncIterator, Iterator

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


def decompress_tar_gz_in_memory(
    archive_bytes: bytes,
    max_archive_bytes: int = 104_857_600,
    max_entry_bytes: int = 10_485_760,
    max_tar_entries: int = 50_000,
) -> list[EnrichmentResponse]:
    """Decompresses and parses a .tar.gz archive in memory with zero disk I/O and strict safety limits."""
    if len(archive_bytes) > max_archive_bytes:
        raise XyoClientException(
            422,
            f"Archive download exceeded maximum allowed byte size ({max_archive_bytes} bytes). Decompression bomb rejected.",
        )

    results: list[EnrichmentResponse] = []
    bio = io.BytesIO(archive_bytes)

    try:
        with tarfile.open(fileobj=bio, mode="r:gz") as tar:
            entry_count = 0
            for member in tar:
                entry_count += 1
                if entry_count > max_tar_entries:
                    raise XyoClientException(
                        422,
                        f"Tar archive exceeds maximum entry count limit ({max_tar_entries} entries). Possible tar bomb DoS attack.",
                    )

                _sanitize_entry_name(member.name)

                if not member.isfile() or not member.name.lower().endswith(".json"):
                    continue

                if member.size > max_entry_bytes:
                    raise XyoClientException(
                        422,
                        f"Tar entry '{member.name}' exceeds maximum size limit ({max_entry_bytes} bytes). Decompression bomb rejected.",
                    )

                extracted = tar.extractfile(member)
                if extracted is None:
                    continue

                content = extracted.read()
                if len(content) > max_entry_bytes:
                    raise XyoClientException(
                        422,
                        f"Tar entry '{member.name}' decompressed size exceeds limit ({max_entry_bytes} bytes).",
                    )

                try:
                    payload = json.loads(content.decode("utf-8"))
                    results.append(EnrichmentResponse.from_dict(payload))
                except Exception as ex:
                    raise XyoClientException(
                        422,
                        f"Failed to deserialize JSON record from archive entry '{member.name}': {ex}",
                    ) from ex
    except tarfile.TarError as ex:
        raise XyoClientException(422, f"Corrupted or invalid tar archive: {ex}") from ex

    return results


def stream_tar_gz_chunks(
    chunk_iterator: Iterator[bytes],
    max_archive_bytes: int = 104_857_600,
    max_entry_bytes: int = 10_485_760,
    max_tar_entries: int = 50_000,
) -> Iterator[EnrichmentResponse]:
    """Streams and yields enrichment records on-the-fly from incoming byte chunks."""
    buffer = io.BytesIO()
    total_bytes = 0

    for chunk in chunk_iterator:
        total_bytes += len(chunk)
        if total_bytes > max_archive_bytes:
            raise XyoClientException(
                422,
                f"Archive download exceeded maximum allowed byte size ({max_archive_bytes} bytes).",
            )
        buffer.write(chunk)

    buffer.seek(0)
    yield from decompress_tar_gz_in_memory(buffer.getvalue(), max_archive_bytes, max_entry_bytes, max_tar_entries)


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
                f"Archive download exceeded maximum allowed byte size ({max_archive_bytes} bytes).",
            )
        buffer.write(chunk)

    buffer.seek(0)
    for record in decompress_tar_gz_in_memory(buffer.getvalue(), max_archive_bytes, max_entry_bytes, max_tar_entries):
        yield record
