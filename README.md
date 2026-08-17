<p align="center">
  <a href="https://xyo.financial" target="_blank" rel="noopener noreferrer">
    <img alt="XYO Financial Python Mascot" width="380" src="https://raw.githubusercontent.com/xyo-financial/sdk-python/main/docs/mascot.png" />
  </a>
</p>

<h1 align="center">XYO Financial SDK for Python</h1>

<p align="center">
  <a href="https://pypi.org/project/xyo-sdk/"><img src="https://img.shields.io/pypi/v/xyo-sdk?style=flat-square&logo=pypi&logoColor=white&color=blue" alt="PyPI Version" /></a>
  <a href="https://github.com/xyo-financial/sdk-python/actions/workflows/makefile.yml"><img src="https://github.com/xyo-financial/sdk-python/actions/workflows/makefile.yml/badge.svg?branch=main" alt="CI / Build & Test" /></a>
  <img src="https://img.shields.io/badge/Python-3.9%20%7C%203.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-3776AB?logo=python&logoColor=white" alt="Python Versions" />
  <img src="https://img.shields.io/badge/Typing-Strict%20MyPy-blue" alt="Strict Typing" />
  <img src="https://img.shields.io/badge/RFC_7807-Compliant-brightgreen" alt="RFC 7807" />
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-Apache_2.0-blue.svg" alt="License" /></a>
</p>

<p align="center">
  <strong>The official Python SDK for <a href="https://xyo.financial">XYO Financial</a>.</strong><br>
  Seamlessly enrich raw financial transactions into clean merchant profiles, intelligent business categorizations, high-res logos, and geolocated address metadata using AI-powered enrichment pipelines.
</p>

---

## ✨ Key Features

- **⚡ Dual Sync & Async Architecture:** Native `Client` (sync) and `AsyncClient` (async/await) built on top of high-performance `httpx`.
- **🚀 AI/ML & Pipeline Ready:** Seamless integration into Pandas, PySpark, Airflow, FastAPI, and Django payment microservices.
- **🌊 Memory-Safe Batch Streaming:** In-memory streaming `.tar.gz` decompression yielding records on-the-fly with zero disk I/O bottlenecks.
- **🛡️ Enterprise Security Hardening:** Zero-Trust domain validation (CWE-183), SSRF defense, Zip Slip mitigation (CWE-22), and decompression bomb limits (CWE-400).
- **📋 RFC 7807 Problem Details:** Rich, typed exception hierarchy mapping API validation errors and HTTP status codes to actionable diagnostics.
- **🔄 Dynamic Token Rotation:** Seamless support for cloud secret stores (AWS Secrets Manager, Azure Key Vault, HashiCorp Vault) via sync/async key suppliers.
- **🏷️ Type Safe:** 100% PEP 484 type annotations and PEP 561 `py.typed` compliance.

---

## ⚙️ Requirements & Compatibility

| Python Version | Support Status | Notes |
| :--- | :--- | :--- |
| **Python 3.13** | 🟢 Supported | Latest stable release |
| **Python 3.12** | 🟢 Supported | **Recommended runtime** for performance and modern typing |
| **Python 3.11** | 🟢 Supported | Active security maintenance |
| **Python 3.10** | 🟢 Supported | Supported for LTS enterprise deployments |
| **Python 3.9** | 🟡 Minimum Baseline | **Minimum required Python interpreter** |
| **Python <= 3.8** | 🔴 Unsupported | Legacy releases reached PSF End of Life |

---

## 📦 Installation

Install from [PyPI](https://pypi.org/project/xyo-sdk/):

```bash
pip install xyo-sdk
```

Or using Poetry:

```bash
poetry add xyo-sdk
```

Or using `uv`:

```bash
uv add xyo-sdk
```

---

## 🚀 Quickstart Guide

### 1. Synchronous Enrichment

```python
from xyo import Client

# Initialize client with API key
with Client(api_key="xyo_live_your_api_key_here") as client:
    # Synchronously enrich a single transaction description
    response = client.enrich_transaction(
        content="SQ *COSTA COFFEE GREENWICH",
        country_code="GB",
    )

    print(f"Merchant:    {response.merchant}")
    print(f"Description: {response.description}")
    print(f"Categories:  {', '.join(response.categories)}")
    print(f"Logo URL:    {response.logo}")
    print(f"Address:     {response.address}")
```

### 2. Asynchronous Enrichment

```python
import asyncio

from xyo import AsyncClient


async def main():
    async with AsyncClient(api_key="xyo_live_your_api_key_here") as client:
        response = await client.enrich_transaction(
            content="SQ *COSTA COFFEE GREENWICH",
            country_code="GB",
        )
        print(f"Merchant: {response.merchant} ({response.category})")


asyncio.run(main())
```

---

## 📚 Core Operations & Code Examples

### 1. Real-Time Single Transaction Enrichment

```python
from xyo import Client, EnrichmentRequest

request = EnrichmentRequest(
    content="TFL TRAVEL CHARGE TFL.GOV.UK",
    country_code="GB",
)

with Client(api_key="xyo_api_key") as client:
    response = client.enrich_transaction(request)
    print(f"Enriched: {response.merchant} -> {response.categories}")
```

### 2. High-Throughput Bulk Batch Submission

Submit batches of transactions for asynchronous parallel processing:

```python
from xyo import Client, EnrichmentRequest

batch = [
    EnrichmentRequest("UBER *TRIP 12345", "GB"),
    EnrichmentRequest("STARBUCKS STORE #10423", "US"),
    EnrichmentRequest("AMZN Mktp US*1A2B3C", "US"),
]

with Client(api_key="xyo_api_key") as client:
    batch_res = client.enrich_transactions(batch, api_user="tenant_bank_01")
    print(f"Job ID:       {batch_res.id}")
    print(f"Download URL: {batch_res.link}")

    # Check status
    status_res = client.get_enrichment_status(batch_res.id)
    print(f"Job Status:   {status_res.status}")
```

### 3. Memory-Safe In-Memory & Streaming Batch Download

Stream records on-the-fly or deserialize directly in memory with **zero disk writes**:

```python
with Client(api_key="xyo_api_key") as client:
    # Option A: Stream records one-by-one with O(1) memory
    for record in client.stream_enrichment_collection(batch_res.link):
        print(f"[Enriched] {record.merchant} -> {record.categories}")

    # Option B: Download all records into a typed list
    records = client.download_enrichment_collection(batch_res.link)
    print(f"Downloaded {len(records)} records.")
```

### 4. Dynamic Token Rotation (AWS Secrets Manager / Vault)

Configure a dynamic key supplier for zero-downtime secret rotation:

```python
from xyo import Client, ClientConfig


def get_secret_from_vault() -> str:
    # Retrieve fresh token from AWS Secrets Manager, Vault, etc.
    return vault_client.get_secret("XYO_TOKEN")


config = ClientConfig(token_supplier=get_secret_from_vault)
client = Client(config=config)
```

---

## 🚀 Framework & Architecture Integration

### 1. FastAPI Dependency Injection & Lifespan Management

Integrate `AsyncXyoClient` into high-performance FastAPI microservices using idiomatic dependency injection or lifespan application-state pooling:

```python
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException

from xyo import AsyncXyoClient, EnrichmentRequest, EnrichmentResponse, XyoProblemDetailsException


# Option A: Request-scoped dependency injection (yield client context)
async def get_xyo_client() -> AsyncGenerator[AsyncXyoClient, None]:
    async with AsyncXyoClient(api_key="xyo_live_your_api_key_here") as client:
        yield client


# Option B: Application lifespan singleton with shared connection pool (Recommended for high concurrency)
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    app.state.xyo_client = AsyncXyoClient(api_key="xyo_live_your_api_key_here")
    yield
    await app.state.xyo_client.close()


app = FastAPI(title="Payment Enrichment Service", lifespan=lifespan)


def get_shared_xyo_client() -> AsyncXyoClient:
    return app.state.xyo_client


@app.post("/enrich", response_model=EnrichmentResponse)
async def enrich_transaction(
    request: EnrichmentRequest,
    xyo: AsyncXyoClient = Depends(get_xyo_client),
) -> EnrichmentResponse:
    """Enrich a single banking transaction narrative."""
    try:
        return await xyo.enrich_transaction(request)
    except XyoProblemDetailsException as ex:
        raise HTTPException(status_code=ex.status, detail=ex.detail) from ex
```

### 2. Django & Celery Distributed Background Worker Pattern

Process transaction streams asynchronously within worker queues (Celery, RQ, Dramatiq) with automatic exponential backoff retries and atomic database persistence:

```python
import logging

from celery import shared_task
from django.db import transaction

from xyo import Client, EnrichmentRequest, XyoNetworkException, XyoProblemDetailsException, XyoServerException

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    autoretry_for=(XyoServerException, XyoNetworkException),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=5,
)
def enrich_transaction_task(self, transaction_id: str) -> dict:
    """Background task to enrich ledger transactions with exponential backoff retries."""
    from payments.models import RawTransaction  # Django ORM Model

    txn = RawTransaction.objects.get(id=transaction_id)
    if txn.is_enriched:
        return {"status": "already_enriched", "transaction_id": transaction_id}

    with Client(api_key="xyo_live_your_api_key_here") as xyo:
        try:
            req = EnrichmentRequest(
                content=txn.raw_description,
                country_code=txn.country_code,
            )
            enriched = xyo.enrich_transaction(req)

            with transaction.atomic():
                txn.merchant_name = enriched.merchant
                txn.clean_description = enriched.description
                txn.category = enriched.category
                txn.categories = enriched.categories
                txn.logo_url = enriched.logo
                txn.location_address = enriched.address
                txn.is_enriched = True
                txn.save(
                    update_fields=[
                        "merchant_name",
                        "clean_description",
                        "category",
                        "categories",
                        "logo_url",
                        "location_address",
                        "is_enriched",
                    ]
                )

            return {"status": "success", "merchant": enriched.merchant}

        except XyoProblemDetailsException as ex:
            # 4xx client validation errors should not be retried
            logger.error("Non-retryable XYO API validation error: %s (HTTP %d)", ex.detail, ex.status)
            txn.enrichment_error = ex.detail
            txn.save(update_fields=["enrichment_error"])
            raise
```

### 3. High-Concurrency Non-Blocking AsyncIO & Thread-Offloaded Decompression

Decompressing large `.tar.gz` archives in bulk processing pipelines is CPU-bound. `AsyncXyoClient` ensures the Python AsyncIO event loop remains 100% responsive by offloading archive extraction to background worker threads via `asyncio.to_thread`:

```python
import asyncio

from xyo import AsyncXyoClient, EnrichmentResponse


async def process_bulk_settlement_feed(download_url: str) -> None:
    """Download and process high-volume bulk settlement records without blocking the AsyncIO event loop."""
    async with AsyncXyoClient(api_key="xyo_live_your_api_key_here") as client:
        # 1. Non-Blocking Thread-Offloaded In-Memory Archive Extraction
        # Tar/GZip decompression executes in a separate thread pool worker, preventing event-loop freezing
        records: list[EnrichmentResponse] = await client.download_enrichment_collection(download_url)
        print(f"Successfully processed {len(records)} records with zero disk writes.")

        # 2. Memory-Safe O(1) Streaming for Gigabyte-Scale Batches
        # Stream individual records on-the-fly chunk-by-chunk without loading entire archive into RAM
        async for record in client.stream_enrichment_collection(download_url):
            await save_record_async(record)
```

---

## 🛡 Exception Handling & RFC 7807 Problem Details

The SDK throws strongly-typed exceptions conforming to the RFC 7807 Problem Details specification:

```python
from xyo import Client, XyoNetworkException, XyoProblemDetailsException, XyoServerException

with Client(api_key="xyo_token") as client:
    try:
        result = client.enrich_transaction("COSTA", "INVALID_CODE")
    except XyoProblemDetailsException as ex:
        # RFC 7807 Structured Problem Details
        print(f"HTTP Status: {ex.status}")
        print(f"Title:       {ex.title}")
        print(f"Detail:      {ex.detail}")
        print(f"Type:        {ex.type}")
        print(f"Errors:      {ex.errors}")
    except XyoServerException as ex:
        # Transient 5xx server errors
        if ex.is_retryable():
            print(f"Transient error: {ex.status_code}. Retrying...")
    except XyoNetworkException as ex:
        # Transport errors (DNS, timeout, connection resets)
        print(f"Network failure: {ex.message}")
```

---

## 🔒 Security & Defensive Architecture

- **Zero-Trust Domain Egress Allowlist:** Validates all archive download URLs against pinned official domains (`api.xyo.financial`, `download.xyo.financial`, AWS S3 storage hosts) and strictly rejects cleartext HTTP.
- **Credential Leakage Prevention:** Strips Bearer authorization headers when following download links to third-party or S3 storage buckets.
- **Decompression Bomb Defense (CWE-400):** Streaming Tar and GZip decoders enforce hard limits on total archive byte ingestion, per-entry sizes, and entry counts.
- **Zip Slip Defense (CWE-22):** Rejects directory traversal sequences and rooted paths in archive entry names.
- **CRLF Injection Prevention (CWE-113):** Validates custom headers and user IDs against carriage return and newline characters.

---

## 📄 License

Distributed under the **Apache License, Version 2.0**. See [`LICENSE`](LICENSE) for details.

---

## 🤝 Support & Security

- **Documentation & Portal:** [xyo.financial](https://xyo.financial)
- **Security Policy & Vulnerability Reporting:** [`SECURITY.md`](SECURITY.md) / `security@syniol.com`
- **Contribution Guidelines:** [`CONTRIBUTING.md`](CONTRIBUTING.md)
