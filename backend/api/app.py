"""FastAPI application — Witness API server."""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.analysis.naming_engine import refresh_all_titles
from backend.analysis.oracle import check_watches
from backend.analysis.story_feed import generate_feed_items
from backend.api.routes import router
from backend.bot.discord_bot import run_bot  # noqa: E402
from backend.core.config import settings
from backend.core.logger import get_logger
from backend.db.database import close_db, get_db
from backend.ingestion.poller import run_poller

logger = get_logger("app")


async def _run_intelligence_loops() -> None:
    """Oracle watches, story feed, and title refresh — runs alongside poller."""
    cycle = 0
    while True:
        try:
            await check_watches()
            generate_feed_items()
            # Refresh titles every 12th cycle (hourly at 5-min interval)
            if cycle % 12 == 0:
                db = get_db()
                refresh_all_titles(db)
            cycle += 1
        except Exception as e:
            logger.error("Intelligence loop error (continuing): %s", e)
        await asyncio.sleep(settings.POLL_INTERVAL_SECONDS * 10)  # ~5 min default


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Witness starting up")
    get_db()

    # Start background tasks
    poller_task = asyncio.create_task(run_poller())
    intelligence_task = asyncio.create_task(_run_intelligence_loops())
    bot_task = asyncio.create_task(run_bot())

    yield

    for task in (poller_task, intelligence_task, bot_task):
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    close_db()
    logger.info("Witness shut down")


app = FastAPI(
    title="Witness",
    description="The Living Memory of EVE Frontier",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")

# Serve frontend static files if built
FRONTEND_DIR = (Path(__file__).parent.parent.parent / "frontend" / "dist").resolve()
if FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIR / "assets")), name="assets")

    @app.get("/{path:path}")
    async def serve_frontend(path: str):
        """Serve React SPA — all non-API routes fall through to index.html."""
        file = (FRONTEND_DIR / path).resolve()
        if file.is_relative_to(FRONTEND_DIR) and file.exists() and file.is_file():
            return FileResponse(str(file))
        return FileResponse(str(FRONTEND_DIR / "index.html"))
