"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.graph import init_graph, shutdown_graph
from app.middleware.rate_limit import RateLimitMiddleware
from app.routes.runs import router as runs_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_graph(settings.checkpoint_url)
    yield
    await shutdown_graph()


app = FastAPI(title="DevShowcase API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware)

app.include_router(runs_router, prefix="/api")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
