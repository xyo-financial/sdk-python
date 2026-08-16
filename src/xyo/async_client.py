"""Asynchronous high-level client for the XYO Financial AI Transaction Enrichment API."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import httpx

from xyo._builders import (
    build_download_headers,
    build_request_headers,
    validate_batch_enrichment_requests,
    validate_single_enrichment_request,
    validate_status_job_id,
)
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
from xyo.security import DownloadSecurityPolicy
from xyo.streaming import decompress_tar_gz_in_memory, stream_tar_gz_chunks_async


class AsyncClient:
    """Asynchronous client for the XYO Financial AI Transaction Enrichment API (FastAPI, Starlette, Tornado)."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        config: ClientConfig | None = None,
        http_client: httpx.AsyncClient | None = None,
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
            self._client = httpx.AsyncClient(
                timeout=self.config.timeout,
                follow_redirects=True,
            )
            self._owns_client = True

    async def enrich_transaction(
        self,
        content: str | EnrichmentRequest,
        country_code: str | None = None,
    ) -> EnrichmentResponse:
        """Asynchronously enriches a single bank transaction narrative."""
        req_dict = validate_single_enrichment_request(content, country_code)
        token = await self.config.resolve_token_async()
        headers = build_request_headers(self.config, token=token)

        url = f"{self.config.base_url}/v1/ai/finance/enrichment/transaction"
        response = await self._send_request("POST", url, headers=headers, json=req_dict)
        self._ensure_success(response)

        return EnrichmentResponse.from_dict(response.json())

    async def enrich_transactions(
        self,
        requests: list[EnrichmentRequest | dict[str, Any]],
        api_user: str | None = None,
    ) -> EnrichTransactionCollectionResponse:
        """Submits an asynchronous batch collection of transactions for high-throughput enrichment."""
        validated_requests = validate_batch_enrichment_requests(requests)
        token = await self.config.resolve_token_async()
        headers = build_request_headers(self.config, token=token, api_user=api_user)

        url = f"{self.config.base_url}/v1/ai/finance/enrichment/transactions"
        response = await self._send_request("POST", url, headers=headers, json=validated_requests)
        self._ensure_success(response)

        return EnrichTransactionCollectionResponse.from_dict(response.json())

    async def get_enrichment_status(
        self,
        id: str,
        api_user: str | None = None,
    ) -> EnrichmentCollectionStatusResponse:
        """Queries the lifecycle status of an asynchronous bulk enrichment batch job."""
        quoted_id = validate_status_job_id(id)
        token = await self.config.resolve_token_async()
        headers = build_request_headers(self.config, token=token, api_user=api_user, content_type=None)

        url = f"{self.config.base_url}/v1/ai/finance/enrichment/transaction/collection/status?id={quoted_id}"
        response = await self._send_request("GET", url, headers=headers)
        self._ensure_success(response)

        return EnrichmentCollectionStatusResponse.from_dict(response.json())

    async def download_enrichment_collection(self, download_url: str) -> list[EnrichmentResponse]:
        """Downloads and decompresses the results .tar.gz archive in memory with zero disk writes."""
        validated_url = self._security_policy.validate_download_url(download_url)
        token = await self.config.resolve_token_async()
        headers = build_download_headers(self.config, self._security_policy, validated_url, token)

        response = await self._send_request("GET", validated_url, headers=headers)
        self._ensure_success(response)

        return await asyncio.to_thread(
            decompress_tar_gz_in_memory,
            response.content,
            max_archive_bytes=self.config.max_archive_bytes,
            max_entry_bytes=self.config.max_entry_bytes,
            max_tar_entries=self.config.max_tar_entries,
        )

    async def stream_enrichment_collection(self, download_url: str) -> AsyncIterator[EnrichmentResponse]:
        """Asynchronously streams and yields enrichment records on-the-fly from the bulk results archive."""
        validated_url = self._security_policy.validate_download_url(download_url)
        token = await self.config.resolve_token_async()
        headers = build_download_headers(self.config, self._security_policy, validated_url, token)

        try:
            async with self._client.stream("GET", validated_url, headers=headers) as response:
                if not response.is_success:
                    await response.aread()
                self._ensure_success(response)
                async for record in stream_tar_gz_chunks_async(
                    response.aiter_bytes(chunk_size=65536),
                    max_archive_bytes=self.config.max_archive_bytes,
                    max_entry_bytes=self.config.max_entry_bytes,
                    max_tar_entries=self.config.max_tar_entries,
                ):
                    yield record
        except httpx.TransportError as ex:
            raise XyoNetworkException(f"Transport error during streaming download: {ex}", original_exception=ex) from ex

    async def _send_request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        try:
            return await self._client.request(method, url, **kwargs)
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

    async def close(self) -> None:
        """Closes the underlying HTTP client if owned."""
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> AsyncClient:
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()
