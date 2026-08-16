#!/usr/bin/env python3
"""Synchronous transaction enrichment quickstart."""

import os

from xyo import Client, EnrichmentRequest, XyoException

API_KEY = os.getenv("XYO_API_KEY", "xyo_sandbox_token_demo")


def main() -> None:
    print("==================================================")
    print("  XYO Financial Python SDK - Synchronous Example  ")
    print("==================================================")

    with Client(api_key=API_KEY) as client:
        try:
            print("\n[1] Enriching Single Bank Transaction Narrative:")
            response = client.enrich_transaction(
                content="SQ *COSTA COFFEE GREENWICH",
                country_code="GB",
            )
            print(f"    Merchant:    {response.merchant}")
            print(f"    Description: {response.description}")
            print(f"    Categories:  {', '.join(response.categories)}")
            print(f"    Logo:        {response.logo}")
            print(f"    Location:    {response.location}")
            print(f"    Address:     {response.address}")

            print("\n[2] Submitting High-Throughput Bulk Batch Job:")
            batch = [
                EnrichmentRequest(content="UBER *TRIP 12345", country_code="GB"),
                EnrichmentRequest(content="STARBUCKS #10423", country_code="US"),
            ]
            batch_res = client.enrich_transactions(batch, api_user="tenant_retail_01")
            print(f"    Job ID:       {batch_res.id}")
            print(f"    Download URL: {batch_res.link}")

        except XyoException as ex:
            print(f"    Handled XYO SDK Exception: {ex}")


if __name__ == "__main__":
    main()
