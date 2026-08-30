"""Synchronous high-level client for the XYO Financial AI Transaction Enrichment API."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Any
from uuid import UUID

import httpx

from xyo._builders import (
    build_download_headers,
    build_request_headers,
    handle_http_error,
    validate_batch_enrichment_requests,
    validate_single_enrichment_request,
    validate_status_job_id,
)
from xyo.config import ClientConfig
from xyo.exceptions import (
    XyoNetworkException,
)
from xyo.models import (
    EnrichmentCollectionStatusResponse,
    EnrichmentRequest,
    EnrichmentResponse,
    EnrichTransactionCollectionResponse,
)
from xyo.security import DownloadSecurityPolicy
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
        correlation_id: str | UUID | None = None,
        traceparent: str | UUID | None = None,
    ) -> EnrichmentResponse:
        """Synchronously enriches a single bank transaction narrative.

        Args:
            content: Raw transaction text or structured EnrichmentRequest instance.
            country_code: ISO 3166-1 alpha-2 two-character country code (e.g. 'GB', 'US').
            correlation_id: Distributed tracing correlation header value (X-Correlation-ID).
            traceparent: Standard W3C TraceContext header value.

        Returns:
            EnrichmentResponse with merchant, categories, logo, and address.
        """
        req_dict = validate_single_enrichment_request(content, country_code)
        token = self.config.resolve_token()
        headers = build_request_headers(
            self.config, token=token, correlation_id=correlation_id, traceparent=traceparent
        )

        url = f"{self.config.base_url}/v1/ai/finance/enrichment/transaction"
        response = self._send_request("POST", url, headers=headers, json=req_dict)
        self._ensure_success(response)

        return EnrichmentResponse.from_dict(response.json())

    def enrich_transactions(
        self,
        requests: Sequence[EnrichmentRequest | dict[str, Any]],
        api_user: str | None = None,
        correlation_id: str | UUID | None = None,
        traceparent: str | UUID | None = None,
    ) -> EnrichTransactionCollectionResponse:
        """Submits an asynchronous batch collection of transactions for high-throughput enrichment.

        Args:
            requests: List of EnrichmentRequest objects or dictionaries.
            api_user: Optional tenant identifier (x-api-user).
            correlation_id: Distributed tracing correlation header value (X-Correlation-ID).
            traceparent: Standard W3C TraceContext header value.

        Returns:
            EnrichTransactionCollectionResponse with batch job ID and download link.
        """
        validated_requests = validate_batch_enrichment_requests(requests)
        token = self.config.resolve_token()
        headers = build_request_headers(
            self.config, token=token, api_user=api_user, correlation_id=correlation_id, traceparent=traceparent
        )

        url = f"{self.config.base_url}/v1/ai/finance/enrichment/transactions"
        response = self._send_request("POST", url, headers=headers, json=validated_requests)
        self._ensure_success(response)

        return EnrichTransactionCollectionResponse.from_dict(response.json())

    def get_enrichment_status(
        self,
        id: str,
        api_user: str | None = None,
        correlation_id: str | UUID | None = None,
        traceparent: str | UUID | None = None,
    ) -> EnrichmentCollectionStatusResponse:
        """Queries the lifecycle status of an asynchronous bulk enrichment batch job.

        Args:
            id: The work identifier returned as ``id`` by :meth:`enrich_transactions`,
                interpolated into the request path as
                ``/v1/ai/finance/enrichment/status/{id}``.
        """
        quoted_id = validate_status_job_id(id)
        token = self.config.resolve_token()
        headers = build_request_headers(
            self.config,
            token=token,
            api_user=api_user,
            content_type=None,
            correlation_id=correlation_id,
            traceparent=traceparent,
        )

        url = f"{self.config.base_url}/v1/ai/finance/enrichment/status/{quoted_id}"
        response = self._send_request("GET", url, headers=headers)
        self._ensure_success(response)

        return EnrichmentCollectionStatusResponse.from_dict(response.json())

    def download_enrichment_collection(
        self,
        download_url: str,
        correlation_id: str | UUID | None = None,
        traceparent: str | UUID | None = None,
    ) -> list[EnrichmentResponse]:
        """Downloads and decompresses the results .tar.gz archive in memory with zero disk writes."""
        validated_url = self._security_policy.validate_download_url(download_url)
        token = self.config.resolve_token()
        headers = build_download_headers(
            self.config,
            self._security_policy,
            validated_url,
            token,
            correlation_id=correlation_id,
            traceparent=traceparent,
        )

        response = self._send_request("GET", validated_url, headers=headers)
        self._ensure_success(response)

        return decompress_tar_gz_in_memory(
            response.content,
            max_archive_bytes=self.config.max_archive_bytes,
            max_entry_bytes=self.config.max_entry_bytes,
            max_tar_entries=self.config.max_tar_entries,
        )

    def stream_enrichment_collection(
        self,
        download_url: str,
        correlation_id: str | UUID | None = None,
        traceparent: str | UUID | None = None,
    ) -> Iterator[EnrichmentResponse]:
        """Streams and yields enrichment records on-the-fly from the bulk results archive."""
        validated_url = self._security_policy.validate_download_url(download_url)
        token = self.config.resolve_token()
        headers = build_download_headers(
            self.config,
            self._security_policy,
            validated_url,
            token,
            correlation_id=correlation_id,
            traceparent=traceparent,
        )

        try:
            with self._client.stream("GET", validated_url, headers=headers) as response:
                if not response.is_success:
                    response.read()
                self._ensure_success(response)
                yield from stream_tar_gz_chunks(
                    response.iter_bytes(chunk_size=65536),
                    max_archive_bytes=self.config.max_archive_bytes,
                    max_entry_bytes=self.config.max_entry_bytes,
                    max_tar_entries=self.config.max_tar_entries,
                )
        except httpx.TransportError as ex:
            raise XyoNetworkException(f"Transport error during streaming download: {ex}", original_exception=ex) from ex

    def _send_request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        try:
            return self._client.request(method, url, **kwargs)
        except httpx.TransportError as ex:
            raise XyoNetworkException(
                f"Network transport failure while calling {url}: {ex}", original_exception=ex
            ) from ex

    def _ensure_success(self, response: httpx.Response) -> None:
        handle_http_error(response)

    def close(self) -> None:
        """Closes the underlying HTTP client if owned."""
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> Client:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()
