"""One-time backfill of all historical data from the World API."""

import asyncio

import httpx

from backend.core.config import settings
from backend.core.logger import get_logger
from backend.db.database import get_db
from backend.ingestion.poller import (
    _ingest_killmails,
    _ingest_smart_assemblies,
    _update_entities,
)

logger = get_logger("backfill")

PAGE_SIZE = 100


async def _fetch_all(client: httpx.AsyncClient, endpoint: str) -> list[dict]:
    """Fetch all pages from a paginated endpoint."""
    all_items: list[dict] = []
    offset = 0

    while True:
        r = await client.get(
            f"{settings.WORLD_API_BASE}/{endpoint}",
            params={"limit": PAGE_SIZE, "offset": offset},
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        items = data.get("data", [])
        all_items.extend(items)
        total = data.get("metadata", {}).get("total", 0)
        logger.info("%s: %d/%d fetched", endpoint, len(all_items), total)
        if offset + PAGE_SIZE >= total:
            break
        offset += PAGE_SIZE

    return all_items


async def main() -> None:
    """Backfill all killmails and smart assemblies."""
    db = get_db()

    async with httpx.AsyncClient() as client:
        logger.info("Fetching all killmails...")
        kills = await _fetch_all(client, "v2/killmails")

        logger.info("Fetching all smart assemblies...")
        assemblies = await _fetch_all(client, "v2/smartassemblies")

    logger.info("Ingesting %d killmails...", len(kills))
    _ingest_killmails(db, kills)

    logger.info("Ingesting %d assemblies...", len(assemblies))
    _ingest_smart_assemblies(db, assemblies)

    logger.info("Updating entities...")
    _update_entities(db)
    db.commit()

    stats = db.execute(
        "SELECT "
        "(SELECT COUNT(*) FROM killmails) as kills, "
        "(SELECT COUNT(*) FROM smart_assemblies) as assemblies, "
        "(SELECT COUNT(*) FROM entities) as entities"
    ).fetchone()

    logger.info(
        "Backfill complete: %d killmails, %d assemblies, %d entities",
        stats["kills"],
        stats["assemblies"],
        stats["entities"],
    )


if __name__ == "__main__":
    asyncio.run(main())
