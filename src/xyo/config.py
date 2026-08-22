"""Client configuration and authentication state for the XYO Python SDK."""

from __future__ import annotations

import os
import re
from collections.abc import Awaitable
from dataclasses import dataclass, field
from typing import Any, Callable
from uuid import UUID

_CRLF_RE = re.compile(r"[\r\n]")
DEFAULT_BASE_URL = "https://api.xyo.financial"


@dataclass
class ClientConfig:
    """Immutable configuration object for XYO synchronous and asynchronous clients.

    Attributes:
        api_key: Static API authentication token.
        token_supplier: Synchronous or asynchronous callable for dynamic token rotation.
        base_url: API root endpoint (defaults to https://api.xyo.financial or XYO_API_BASE_URL env).
        correlation_id: Distributed tracing correlation header value (X-Correlation-ID).
        timeout: Request timeout duration in seconds (default 30.0s).
        max_archive_bytes: Hard ceiling on download archive decompression in bytes (default 100 MiB).
        max_entry_bytes: Hard ceiling on single extracted TAR entry in bytes (default 10 MiB).
        max_tar_entries: Maximum number of entries allowed inside a TAR archive (default 50,000).
        trusted_download_hosts: Allowlisted hostnames for Zero-Trust egress download verification.
        default_headers: Custom HTTP headers attached to all outbound requests.
    """

    api_key: str | None = None
    token_supplier: Callable[[], str | Awaitable[str]] | None = None
    base_url: str = field(default_factory=lambda: os.getenv("XYO_API_BASE_URL", DEFAULT_BASE_URL).rstrip("/"))
    correlation_id: str | UUID | None = None
    traceparent: str | UUID | None = None
    timeout: float = 30.0
    max_archive_bytes: int = 104_857_600  # 100 MiB
    max_entry_bytes: int = 10_485_760  # 10 MiB
    max_tar_entries: int = 50_000
    trusted_download_hosts: tuple[str, ...] = ()
    default_headers: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.base_url = self.base_url.rstrip("/")
        if self.correlation_id and _CRLF_RE.search(str(self.correlation_id)):
            raise ValueError("Correlation ID contains forbidden CRLF injection characters (CWE-113).")
        if self.traceparent and _CRLF_RE.search(str(self.traceparent)):
            raise ValueError("Traceparent contains forbidden CRLF injection characters (CWE-113).")
        for key, val in self.default_headers.items():
            if _CRLF_RE.search(str(key)) or _CRLF_RE.search(str(val)):
                raise ValueError(f"Default header '{key}' contains forbidden CRLF injection characters (CWE-113).")

    def resolve_token(self) -> str:
        """Resolves the Bearer token synchronously, evaluating token_supplier if configured."""
        if self.token_supplier is not None:
            token = self.token_supplier()
            if isinstance(token, str) and token.strip():
                return token.strip()
        if self.api_key and self.api_key.strip():
            return self.api_key.strip()
        raise ValueError("No API key or dynamic token supplier configured for XYO client.")

    async def resolve_token_async(self) -> str:
        """Resolves the Bearer token asynchronously, evaluating async token_supplier if configured."""
        if self.token_supplier is not None:
            res = self.token_supplier()
            if hasattr(res, "__await__"):
                token = await res
            else:
                token = res
            if isinstance(token, str) and token.strip():
                return token.strip()
        if self.api_key and self.api_key.strip():
            return self.api_key.strip()
        raise ValueError("No API key or dynamic token supplier configured for XYO client.")

    def __repr__(self) -> str:
        token_display = "[REDACTED]" if self.api_key else "(Dynamic/None)"
        return (
            f"ClientConfig(base_url='{self.base_url}', api_key='{token_display}', "
            f"timeout={self.timeout}, correlation_id='{self.correlation_id}', "
            f"traceparent='{self.traceparent}')"
        )
