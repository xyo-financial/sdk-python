"""Shared pytest fixtures and test data."""

from __future__ import annotations

import io
import json
import tarfile

import pytest


@pytest.fixture
def mock_enrichment_response_json() -> dict:
    return {
        "merchant": "Costa Coffee",
        "description": "British coffeehouse chain.",
        "categories": ["Food & Dining", "Coffee Shops"],
        "logo": "https://cdn.xyo.financial/logos/costa.png",
        "location": "United Kingdom, London",
        "address": "40-42 Great Portland St, London W1W 7LZ",
    }


@pytest.fixture
def mock_batch_response_json() -> dict:
    return {
        "id": "batch_job_12345",
        "link": "https://download.xyo.financial/batches/12345.tar.gz",
    }


@pytest.fixture
def mock_status_response_json() -> dict:
    return {
        "status": "READY",
    }


def create_mock_tar_gz(entries: list[tuple[str, dict | str]]) -> bytes:
    """Helper to build an in-memory .tar.gz archive."""
    bio = io.BytesIO()
    with tarfile.open(fileobj=bio, mode="w:gz") as tar:
        for name, data in entries:
            raw_bytes = json.dumps(data).encode("utf-8") if isinstance(data, dict) else data.encode("utf-8")
            ti = tarfile.TarInfo(name=name)
            ti.size = len(raw_bytes)
            tar.addfile(ti, io.BytesIO(raw_bytes))
    return bio.getvalue()
