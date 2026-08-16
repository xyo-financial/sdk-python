# XYO.Financial SDK for Python

<p align="center">
    <a href="https://xyo.financial" target="_blank"><img alt="Python Mascot for XYO.Financial" width="420" src="docs/mascot.png" /></a>
    <br/>
    <b>Enterprise Financial Transaction Enrichment SDK for Python</b>
</p>

<p align="center">
    <a href="https://github.com/xyo-financial/sdk-python/actions/workflows/makefile.yml"><img src="https://github.com/xyo-financial/sdk-python/actions/workflows/makefile.yml/badge.svg" alt="CI / Build & Test" /></a>
    <a href="https://pypi.org/project/xyo-sdk/"><img src="https://img.shields.io/pypi/v/xyo-sdk.svg" alt="PyPI version" /></a>
    <a href="https://pypi.org/project/xyo-sdk/"><img src="https://img.shields.io/pypi/pyversions/xyo-sdk.svg" alt="Python Versions" /></a>
    <a href="LICENSE"><img src="https://img.shields.io/badge/License-Apache_2.0-blue.svg" alt="License" /></a>
    <a href="SECURITY.md"><img src="https://img.shields.io/badge/Security-LTS_Guaranteed-10B981" alt="Security Policy" /></a>
</p>

Official, institutional-grade Python Client SDK for the **[XYO Financial](https://xyo.financial)** AI Transaction Enrichment Platform. Built for Data Engineers, ML Engineers, and Fintech Backend Developers demanding high throughput, dual sync/async ergonomics, zero memory leaks, and enterprise-grade resilience.

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

---

## ⚡ Asynchronous Integration (FastAPI & Starlette)

```python
from fastapi import FastAPI, Depends, HTTPException
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from xyo import AsyncClient, XyoProblemDetailsException

client: AsyncClient | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    global client
    client = AsyncClient(api_key="xyo_live_api_token")
    yield
    await client.close()


app = FastAPI(lifespan=lifespan)


@app.post("/api/enrich")
async def enrich_payment(narrative: str, country_code: str):
    try:
        enriched = await client.enrich_transaction(narrative, country_code)
        return {
            "merchant": enriched.merchant,
            "categories": enriched.categories,
            "logo": enriched.logo,
        }
    except XyoProblemDetailsException as ex:
        raise HTTPException(status_code=ex.status, detail=ex.detail)
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

## 🛡 Exception Handling & RFC 7807 Problem Details

The SDK throws strongly-typed exceptions conforming to the RFC 7807 Problem Details specification:

```python
from xyo import Client, XyoProblemDetailsException, XyoServerException, XyoNetworkException

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

## 🔒 Enterprise Security & Defensive Architecture

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
