"""Data models and request/response payloads for the XYO Python SDK.

These are the ergonomic, dependency-free dataclasses the public API exposes.
The wire contract itself lives in the generated layer under ``xyo._generated``,
which is produced from the OpenAPI specification: every model here parses and
serialises through its generated counterpart rather than reading raw dicts, so
a specification change reaches this layer through the generator rather than by
someone remembering to update a field list by hand.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from xyo._generated.models.enrich_transaction_collection_response import (
    EnrichTransactionCollectionResponse as GeneratedCollectionResponse,
)
from xyo._generated.models.enrichment_collection_status_response import (
    EnrichmentCollectionStatusResponse as GeneratedStatusResponse,
)
from xyo._generated.models.enrichment_request import EnrichmentRequest as GeneratedRequest
from xyo._generated.models.enrichment_response import EnrichmentResponse as GeneratedResponse
from xyo.exceptions import XyoClientException

_COUNTRY_CODE_RE = re.compile(r"^[A-Za-z]{2}$")


@dataclass
class EnrichmentRequest:
    """Request payload for synchronous or asynchronous transaction enrichment.

    Attributes:
        content: Payment description narrative (maximum 128 characters).
        country_code: ISO 3166-1 alpha-2 two-character country code (e.g. 'GB', 'US').
    """

    content: str
    country_code: str

    def __post_init__(self) -> None:
        if not self.content or not self.content.strip():
            raise XyoClientException(400, "Transaction content cannot be null, empty, or whitespace.")
        if len(self.content) > 128:
            raise XyoClientException(
                400,
                f"Transaction content exceeds maximum length of 128 characters (got {len(self.content)} chars).",
            )
        if not self.country_code or not self.country_code.strip():
            raise XyoClientException(400, "Country code cannot be null, empty, or whitespace.")

        trimmed = self.country_code.strip()
        if not _COUNTRY_CODE_RE.match(trimmed):
            raise XyoClientException(
                400,
                f"Invalid country code '{self.country_code}'. Must be a 2-letter ISO 3166-1 alpha-2 country code.",
            )
        self.country_code = trimmed.upper()

    def to_generated(self) -> GeneratedRequest:
        """Converts to the generated specification model."""
        return GeneratedRequest(content=self.content, countryCode=self.country_code)

    def to_dict(self) -> dict[str, str]:
        """Converts to the OpenAPI wire payload.

        Serialisation goes through the generated model so field names and casing
        come from the specification rather than being restated here. A renamed
        field therefore reaches the wire via regeneration, not by hand.
        """
        return self.to_generated().to_dict()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EnrichmentRequest:
        """Instantiates EnrichmentRequest from dictionary."""
        return cls(
            content=data.get("content", ""),
            country_code=data.get("countryCode") or data.get("country_code", ""),
        )


@dataclass
class EnrichmentResponse:
    """Enriched merchant metadata and categorization response.

    Attributes:
        merchant: Clean merchant name.
        description: Brief editorial summary of the merchant.
        categories: Hierarchical category tags.
        logo: Data URI or CDN URL representing merchant logo.
        location: City and country descriptor.
        address: Exact purchase street address if available.
    """

    merchant: str
    description: str
    categories: list[str] = field(default_factory=list)
    logo: str = ""
    location: str = ""
    address: str = ""

    @property
    def name(self) -> str:
        """Alias for merchant name."""
        return self.merchant

    @property
    def category(self) -> str:
        """Returns primary category tag."""
        return self.categories[0] if self.categories else ""

    @property
    def country_code(self) -> str:
        """Extracts country code from location if available."""
        if "," in self.location:
            return self.location.split(",")[-1].strip()
        return self.location.strip()

    @classmethod
    def from_generated(cls, model: GeneratedResponse) -> EnrichmentResponse:
        """Adapts the generated specification model into the public dataclass."""
        return cls(
            merchant=model.merchant,
            description=model.description,
            categories=list(model.categories or []),
            logo=model.logo or "",
            location=model.location or "",
            address=model.address or "",
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EnrichmentResponse:
        """Instantiates EnrichmentResponse from a raw API payload.

        Parsing goes through the generated model so the specification stays the
        single source of truth for field names and types. Payloads that predate
        a field, or null out an optional one, are tolerated by filling defaults
        before validation rather than by hand-reading keys here.
        """
        cats = data.get("categories", [])
        if isinstance(cats, str):
            cats = [cats]
        normalised = {
            "merchant": data.get("merchant") or data.get("name", "") or "",
            "description": data.get("description") or "",
            "categories": list(cats or []),
            "logo": data.get("logo") or "",
            "location": data.get("location") or "",
            "address": data.get("address") or "",
        }
        return cls.from_generated(GeneratedResponse.model_validate(normalised))


@dataclass
class EnrichTransactionCollectionResponse:
    """Batch submission response containing tracking ID and download link."""

    id: str
    link: str

    @classmethod
    def from_generated(cls, model: GeneratedCollectionResponse) -> EnrichTransactionCollectionResponse:
        """Adapts the generated specification model into the public dataclass."""
        return cls(id=model.id, link=model.link)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EnrichTransactionCollectionResponse:
        """Parses a raw API payload through the generated specification model."""
        normalised = {"id": data.get("id") or "", "link": data.get("link") or ""}
        return cls.from_generated(GeneratedCollectionResponse.model_validate(normalised))


@dataclass
class EnrichmentCollectionStatusResponse:
    """Batch enrichment job processing lifecycle status."""

    status: str

    @classmethod
    def from_generated(cls, model: GeneratedStatusResponse) -> EnrichmentCollectionStatusResponse:
        """Adapts the generated specification model into the public dataclass."""
        return cls(status=model.status)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EnrichmentCollectionStatusResponse:
        """Parses a raw API payload through the generated specification model."""
        normalised = {"status": data.get("status") or ""}
        return cls.from_generated(GeneratedStatusResponse.model_validate(normalised))
