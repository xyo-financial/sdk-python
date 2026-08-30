# 📜 Changelog

All notable changes to the XYO Financial Python Client SDK (`sdk-python`) will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Fixed
- Declared the generated client's runtime dependencies (`pydantic`, `python-dateutil`, `typing-extensions`). They were always required by `xyo._generated`, which ships in the wheel, but were never declared, so `import xyo._generated` raised `ModuleNotFoundError` on a clean install.

### Changed
- The wrapper now parses and serialises through the generated specification models rather than reading raw dictionaries. `models.py` gains `from_generated()` and `to_generated()`, so field names, casing and types come from the OpenAPI specification and reach the SDK through regeneration instead of hand edits. The public dataclasses, their fields and the wire payload are unchanged.
- Documented the generated code policy in `CONTRIBUTING.md`: `src/xyo/_generated/` is committed exactly as the generator emits it, is never hand-edited or reformatted, is excluded from ruff, mypy and coverage, and is out of scope for review and audit.

### Added
- Automated spec regeneration pipeline (`.github/workflows/generate.yml`) listening to `repository_dispatch` from `xyo-financial/specs`.
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
