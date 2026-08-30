# 📜 Changelog

All notable changes to the XYO Financial Python Client SDK (`sdk-python`) will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Removed
- Deleted the unused `xyo._generated` package. Nothing outside it imported it, it was excluded from coverage, ruff and mypy, and it imported `pydantic`, `pydantic_core`, `dateutil` and `typing_extensions`, none of which are declared runtime dependencies. It was nevertheless published in the wheel, so `import xyo._generated` raised `ModuleNotFoundError` on a clean install. The public API is unchanged: nothing exported from `xyo` ever referenced it.

### Added
- `scripts/check_spec_coverage.py` and a `make spec-check` target, which fail when the specification declares a request path the hand-written client does not issue.

### Changed
- Replaced the `generate.yml` regeneration workflow with `spec-check.yml`. It consumes the same `spec_tagged` dispatch, verifies path coverage, runs the test suite, and opens a `spec-drift` issue instead of raising a regeneration pull request.
- Corrected `CONTRIBUTING.md`, which described `xyo._generated` as the transport layer; the transport is `httpx` and the client is hand-written throughout.
- Spec synchronization now verifies rather than regenerates, superseding the unreleased regeneration pipeline previously listed here.

### Added (previously unreleased)
- GitHub release workflow (`.github/workflows/release.yml`) with PyPI publishing, SBOM generation, SHA-256 checksums, and artifact provenance attestations.
- Standalone `Python Runtime Support Schedule` SVG graphic in `docs/lts_schedule.svg` and proactive 3-month LTS sunset policy in `SECURITY.md`.

---

## [2.0.0] - 2026-08-16

### Added
- **Dual Synchronous & Asynchronous Architecture:**
  - `xyo.Client`: Synchronous client based on `httpx.Client`.
  - `xyo.AsyncClient`: Asynchronous native async/await client based on `httpx.AsyncClient` (FastAPI, Starlette, Tornado compatible).
- **Core Operations:**
  - `enrich_transaction`: Real-time single transaction enrichment with merchant metadata, category tags, logo, location, and address.
  - `enrich_transactions`: High-throughput asynchronous bulk batch submission.
  - `get_enrichment_status`: Bulk job lifecycle status polling.
  - `download_enrichment_collection`: In-memory streaming `.tar.gz` archive download and decompression with zero disk I/O.
  - `stream_enrichment_collection`: $O(1)$ memory generator yielding records on-the-fly.
- **Defensive Engineering & Security:**
  - Zero-Trust Egress Domain Validation (CWE-183) with domain pinning and HTTPS enforcement.
  - Decompression bomb protection (CWE-400) enforcing hard stream ceilings.
  - Zip Slip & path traversal defense (CWE-22 / CWE-29).
  - CRLF injection prevention (CWE-113) for `x-api-user` and correlation IDs.
  - Token leakage prevention stripping Bearer headers when accessing external S3 storage hosts.
- **RFC 7807 Exception Hierarchy:** Strongly-typed `XyoProblemDetailsException`, `XyoClientException`, `XyoServerException`, `XyoNetworkException`, and aliases `ErrorResponse`, `APIError`.
- **Type Safety:** 100% PEP 484 type hints and PEP 561 `py.typed` marker.
