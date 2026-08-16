"""Synchronous high-level client for the XYO Financial AI Transaction Enrichment API."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from urllib.parse import quote, urlparse

import httpx

from xyo.config import ClientConfig
from xyo.exceptions import (
    XyoClientException,
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
from xyo.security import DownloadSecurityPolicy, validate_api_user
from xyo.streaming import decompress_tar_gz_in_memory, stream_tar_gz_chunks


class Client:
    """Synchronous client for the XYO Financial AI Transaction Enrichment API."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        config: ClientConfig | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        if config is not None:
            self.config = config
        else:
            kwargs: dict[str, Any] = {}
            if api_key is not None:
                kwargs["api_key"] = api_key
            if base_url is not None:
                kwargs["base_url"] = base_url
            self.config = ClientConfig(**kwargs)

        self._security_policy = DownloadSecurityPolicy(
            self.config.base_url,
            self.config.trusted_download_hosts,
        )

        if http_client is not None:
            self._client = http_client
            self._owns_client = False
        else:
            self._client = httpx.Client(
                timeout=self.config.timeout,
                follow_redirects=True,
            )
            self._owns_client = True

    def enrich_transaction(
        self,
        content: str | EnrichmentRequest,
        country_code: str | None = None,
    ) -> EnrichmentResponse:
        """Synchronously enriches a single bank transaction narrative.

        Args:
            content: Raw transaction text or structured EnrichmentRequest instance.
            country_code: ISO 3166-1 alpha-2 two-character country code (e.g. 'GB', 'US').

        Returns:
            EnrichmentResponse with merchant, categories, logo, and address.
        """
        if isinstance(content, EnrichmentRequest):
            req = content
        else:
            if country_code is None:
                raise XyoClientException(400, "country_code is required when content is passed as a string.")
            req = EnrichmentRequest(content=content, country_code=country_code)

        token = self.config.resolve_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        self._apply_default_headers(headers)

        url = f"{self.config.base_url}/v1/ai/finance/enrichment/transaction"
        response = self._send_request("POST", url, headers=headers, json=req.to_dict())
        self._ensure_success(response)

        return EnrichmentResponse.from_dict(response.json())

    def enrich_transactions(
        self,
        requests: list[EnrichmentRequest | dict[str, Any]],
        api_user: str | None = None,
    ) -> EnrichTransactionCollectionResponse:
        """Submits an asynchronous batch collection of transactions for high-throughput enrichment.

        Args:
            requests: List of EnrichmentRequest objects or dictionaries.
            api_user: Optional tenant identifier (x-api-user).

        Returns:
            EnrichTransactionCollectionResponse with batch job ID and download link.
        """
        if not requests:
            raise XyoClientException(400, "Transaction collection batch cannot be empty.")

        validated_requests: list[dict[str, str]] = []
        for i, item in enumerate(requests):
            if item is None:
                raise XyoClientException(400, f"Transaction item at index {i} cannot be null.")
            if isinstance(item, EnrichmentRequest):
                validated_requests.append(item.to_dict())
            elif isinstance(item, dict):
                req = EnrichmentRequest.from_dict(item)
                validated_requests.append(req.to_dict())
            else:
                raise XyoClientException(400, f"Invalid request item type at index {i}: {type(item)}")

        validate_api_user(api_user)

        token = self.config.resolve_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if api_user:
            headers["x-api-user"] = api_user.strip()
        self._apply_default_headers(headers)

        url = f"{self.config.base_url}/v1/ai/finance/enrichment/transactions"
        response = self._send_request("POST", url, headers=headers, json=validated_requests)
        self._ensure_success(response)

        return EnrichTransactionCollectionResponse.from_dict(response.json())

    def get_enrichment_status(
        self,
        id: str,
        api_user: str | None = None,
    ) -> EnrichmentCollectionStatusResponse:
        """Queries the lifecycle status of an asynchronous bulk enrichment batch job."""
        if not id or not id.strip():
            raise XyoClientException(400, "Enrichment job identifier cannot be null, empty, or whitespace.")

        validate_api_user(api_user)

        token = self.config.resolve_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }
        if api_user:
            headers["x-api-user"] = api_user.strip()
        self._apply_default_headers(headers)

        url = f"{self.config.base_url}/v1/ai/finance/enrichment/transaction/collection/status?id={quote(id.strip())}"
        response = self._send_request("GET", url, headers=headers)
        self._ensure_success(response)

        return EnrichmentCollectionStatusResponse.from_dict(response.json())

    def download_enrichment_collection(self, download_url: str) -> list[EnrichmentResponse]:
        """Downloads and decompresses the results .tar.gz archive in memory with zero disk writes."""
        validated_url = self._security_policy.validate_download_url(download_url)
        parsed = urlparse(validated_url)

        headers = {
            "Accept": "application/gzip, application/x-tar, application/octet-stream, */*",
        }
        if not self._security_policy.is_external_storage_host(parsed.hostname or ""):
            token = self.config.resolve_token()
            headers["Authorization"] = f"Bearer {token}"
        self._apply_default_headers(headers)

        response = self._send_request("GET", validated_url, headers=headers)
        self._ensure_success(response)

        return decompress_tar_gz_in_memory(
            response.content,
            max_archive_bytes=self.config.max_archive_bytes,
            max_entry_bytes=self.config.max_entry_bytes,
            max_tar_entries=self.config.max_tar_entries,
        )

    def stream_enrichment_collection(self, download_url: str) -> Iterator[EnrichmentResponse]:
        """Streams and yields enrichment records on-the-fly from the bulk results archive."""
        validated_url = self._security_policy.validate_download_url(download_url)
        parsed = urlparse(validated_url)

        headers = {
            "Accept": "application/gzip, application/x-tar, application/octet-stream, */*",
        }
        if not self._security_policy.is_external_storage_host(parsed.hostname or ""):
            token = self.config.resolve_token()
            headers["Authorization"] = f"Bearer {token}"
        self._apply_default_headers(headers)

        try:
            with self._client.stream("GET", validated_url, headers=headers) as response:
                self._ensure_success(response)
                yield from stream_tar_gz_chunks(
                    response.iter_bytes(chunk_size=65536),
                    max_archive_bytes=self.config.max_archive_bytes,
                    max_entry_bytes=self.config.max_entry_bytes,
                    max_tar_entries=self.config.max_tar_entries,
                )
        except httpx.TransportError as ex:
            raise XyoNetworkException(f"Transport error during streaming download: {ex}", original_exception=ex) from ex

    def _apply_default_headers(self, headers: dict[str, str]) -> None:
        if self.config.correlation_id and "X-Correlation-ID" not in headers:
            headers["X-Correlation-ID"] = self.config.correlation_id
        for k, v in self.config.default_headers.items():
            if k not in headers:
                headers[k] = v

    def _send_request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        try:
            return self._client.request(method, url, **kwargs)
        except httpx.TransportError as ex:
            raise XyoNetworkException(
                f"Network transport failure while calling {url}: {ex}", original_exception=ex
            ) from ex

    def _ensure_success(self, response: httpx.Response) -> None:
        if response.is_success:
            return

        status = response.status_code
        text = response.text

        if status >= 500:
            raise XyoServerException(status, text or f"[HTTP {status}] Server error", raw_body=text)

        if status >= 400:
            if text and (text.strip().startswith("{") or text.strip().startswith("[")):
                raise XyoProblemDetailsException.from_json(status, text)
            raise XyoClientException(status, text or f"[HTTP {status}] Client error", raw_body=text)

        raise XyoClientException(status, f"[HTTP {status}] Unexpected HTTP response", raw_body=text)

    def close(self) -> None:
        """Closes the underlying HTTP client if owned."""
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> Client:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()
