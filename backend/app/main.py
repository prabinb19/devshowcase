"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.graph import init_graph, shutdown_graph
from app.middleware.rate_limit import RateLimitMiddleware
from app.routes.drafts import router as drafts_router
from app.routes.linkedin import router as linkedin_router
from app.routes.runs import router as runs_router
from app.routes.settings import router as settings_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


_pipeline_healthy = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _pipeline_healthy  # noqa: PLW0603
    try:
        await init_graph(settings.checkpoint_url)
        _pipeline_healthy = True
        logger.info("Pipeline initialized successfully")
    except Exception as exc:
        logger.error("Failed to initialize pipeline: %s", exc, exc_info=True)
    yield
    await shutdown_graph()


app = FastAPI(title="DevShowcase API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware)

app.include_router(runs_router, prefix="/api")
app.include_router(drafts_router, prefix="/api")
app.include_router(linkedin_router, prefix="/api")
app.include_router(settings_router, prefix="/api")


@app.get("/health")
async def health() -> dict[str, str]:
    status = "ok" if _pipeline_healthy else "degraded"
    return {"status": status}
