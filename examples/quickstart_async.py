#!/usr/bin/env python3
"""Asynchronous transaction enrichment quickstart."""

import asyncio
import os

from xyo import AsyncClient, XyoException

API_KEY = os.getenv("XYO_API_KEY", "xyo_sandbox_token_demo")


async def main() -> None:
    print("===================================================")
    print("  XYO Financial Python SDK - Asynchronous Example  ")
    print("===================================================")

    async with AsyncClient(api_key=API_KEY) as client:
        try:
            print("\n[1] Asynchronously Enriching Single Transaction:")
            response = await client.enrich_transaction(
                content="TFL TRAVEL CHARGE TFL.GOV.UK",
                country_code="GB",
            )
            print(f"    Merchant:    {response.merchant}")
            print(f"    Categories:  {', '.join(response.categories)}")

        except XyoException as ex:
            print(f"    Handled XYO SDK Exception: {ex}")


if __name__ == "__main__":
    asyncio.run(main())
