"""Tests for package exports and aliases."""

from __future__ import annotations

import xyo
from xyo import AsyncClient, AsyncXyoClient, Client, XyoClient


def test_package_exports() -> None:
    assert AsyncXyoClient is AsyncClient
    assert XyoClient is Client
    assert "AsyncXyoClient" in xyo.__all__
    assert "XyoClient" in xyo.__all__
