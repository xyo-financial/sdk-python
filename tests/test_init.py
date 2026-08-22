"""Tests for package exports and aliases."""

from __future__ import annotations

import xyo
from xyo import AsyncClient, AsyncXyoClient, Client, RateLimitExceededError, XyoClient, XyoError, XyoException


def test_package_exports() -> None:
    assert AsyncXyoClient is AsyncClient
    assert XyoClient is Client
    assert XyoError is XyoException
    assert issubclass(RateLimitExceededError, XyoException)
    assert "AsyncXyoClient" in xyo.__all__
    assert "XyoClient" in xyo.__all__
    assert "XyoError" in xyo.__all__
    assert "RateLimitExceededError" in xyo.__all__

