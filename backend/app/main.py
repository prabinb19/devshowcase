"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.middleware.rate_limit import RateLimitMiddleware
from app.routes.drafts import router as drafts_router
from app.routes.images import router as images_router
from app.routes.linkedin import router as linkedin_router
from app.routes.runs import router as runs_router
from app.routes.settings import router as settings_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("DevShowcase API started")
    yield
    logger.info("DevShowcase API shutting down")


app = FastAPI(title="DevShowcase API", version="0.1.0", lifespan=lifespan)

MAX_REQUEST_BODY_BYTES = 1_048_576  # 1 MB


@app.middleware("http")
async def limit_request_size(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_REQUEST_BODY_BYTES:
        return JSONResponse(
            status_code=413, content={"detail": "Request body too large"}
        )
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)
app.add_middleware(RateLimitMiddleware)

app.include_router(runs_router, prefix="/api")
app.include_router(drafts_router, prefix="/api")
app.include_router(images_router, prefix="/api")
app.include_router(linkedin_router, prefix="/api")
app.include_router(settings_router, prefix="/api")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
