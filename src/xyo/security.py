"""Zero-Trust egress security policies, SSRF prevention, and header sanitization."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from xyo.exceptions import XyoClientException

_DEFAULT_TRUSTED_HOSTS = {
    "api.xyo.financial",
    "download.xyo.financial",
    "xyo-financial.s3.amazonaws.com",
    "xyo-financial.s3.us-east-1.amazonaws.com",
}
_CRLF_RE = re.compile(r"[\r\n]")


class DownloadSecurityPolicy:
    """Enforces Zero-Trust egress domain validation (CWE-183) and SSRF defense on archive downloads."""

    def __init__(
        self,
        base_url: str | None = None,
        custom_trusted_hosts: tuple[str, ...] | list[str] | None = None,
    ) -> None:
        self.trusted_hosts = set(_DEFAULT_TRUSTED_HOSTS)
        self.configured_api_host: str | None = None

        if base_url:
            parsed = urlparse(base_url)
            if parsed.hostname:
                self.configured_api_host = parsed.hostname.lower()
                self.trusted_hosts.add(parsed.hostname.lower())

        if custom_trusted_hosts:
            for host in custom_trusted_hosts:
                if host and host.strip():
                    self.trusted_hosts.add(host.strip().lower())

    def validate_download_url(self, download_url: str) -> str:
        """Validates the target download URL against scheme and host allowlist policies."""
        if not download_url or not download_url.strip():
            raise XyoClientException(400, "Download URL cannot be null, empty, or whitespace.")

        parsed = urlparse(download_url.strip())
        if not parsed.scheme or not parsed.netloc:
            raise XyoClientException(400, f"Invalid download URL '{download_url}'.")

        scheme = parsed.scheme.lower()
        if scheme != "https":
            if scheme == "http":
                # Allow HTTP only for local development
                is_local = parsed.hostname in ("localhost", "127.0.0.1")
                if not is_local:
                    raise XyoClientException(
                        400,
                        "Insecure HTTP scheme rejected for remote archive download. HTTPS is strictly mandated.",
                    )
            else:
                raise XyoClientException(
                    400,
                    f"Unsupported URI scheme '{scheme}' rejected for archive download.",
                )

        host = (parsed.hostname or "").lower()
        if host not in self.trusted_hosts:
            raise XyoClientException(
                400,
                f"Target download host '{host}' is not in the trusted domain allowlist. "
                f"Register host via ClientConfig if using dedicated private storage.",
            )

        return download_url.strip()

    def is_external_storage_host(self, host: str) -> bool:
        """Returns True if the target host is an external S3 / storage host where Bearer headers should be stripped."""
        host_lower = host.lower()
        if self.configured_api_host and host_lower == self.configured_api_host:
            return False
        return host_lower != "api.xyo.financial"


def validate_api_user(api_user: str | None) -> None:
    """Validates that tenant user identifier contains no CRLF characters (CWE-113)."""
    if api_user and _CRLF_RE.search(api_user):
        raise XyoClientException(400, "Tenant user identifier contains forbidden CRLF injection characters (CWE-113).")
