"""FastAPI microservice integration example using XYO AsyncClient."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel

from xyo import AsyncClient, EnrichmentResponse, XyoProblemDetailsException


class TransactionDto(BaseModel):
    narrative: str
    country_code: str


# Global async client lifecycle
client: AsyncClient | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    global client
    client = AsyncClient(api_key="xyo_live_api_token")
    yield
    await client.close()


app = FastAPI(title="Core Banking Enrichment Gateway", lifespan=lifespan)


def get_xyo_client() -> AsyncClient:
    assert client is not None
    return client


@app.post("/enrich", response_model=dict)
async def enrich_endpoint(
    dto: TransactionDto,
    xyo: AsyncClient = Depends(get_xyo_client),  # noqa: B008
) -> dict:
    try:
        enriched: EnrichmentResponse = await xyo.enrich_transaction(
            content=dto.narrative,
            country_code=dto.country_code,
        )
        return {
            "merchant": enriched.merchant,
            "description": enriched.description,
            "categories": enriched.categories,
            "logo": enriched.logo,
        }
    except XyoProblemDetailsException as ex:
        raise HTTPException(status_code=ex.status, detail=ex.detail or ex.message) from ex
