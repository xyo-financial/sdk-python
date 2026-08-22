"""XYO Financial Python Client SDK.

Official, institutional-grade Python SDK for real-time and batch financial transaction enrichment.
"""

from __future__ import annotations

from xyo import exceptions
from xyo.async_client import AsyncClient
from xyo.client import Client
from xyo.config import ClientConfig
from xyo.exceptions import (
    APIError,
    ErrorResponse,
    RateLimitExceededError,
    XyoClientException,
    XyoError,
    XyoException,
    XyoNetworkException,
    XyoProblemDetailsException,
    XyoServerException,
)
from xyo.models import (
    EnrichmentCollectionStatusResponse,
    EnrichmentRequest,
    EnrichmentResponse,
    EnrichTransactionCollectionResponse,
)

# Canonical and framework aliases
AsyncXyoClient = AsyncClient
XyoClient = Client

__version__ = "2.1.0"

__all__ = [
    "Client",
    "AsyncClient",
    "XyoClient",
    "AsyncXyoClient",
    "ClientConfig",
    "EnrichmentRequest",
    "EnrichmentResponse",
    "EnrichTransactionCollectionResponse",
    "EnrichmentCollectionStatusResponse",
    "XyoException",
    "XyoError",
    "XyoClientException",
    "RateLimitExceededError",
    "XyoServerException",
    "XyoNetworkException",
    "XyoProblemDetailsException",
    "ErrorResponse",
    "APIError",
    "exceptions",
]
