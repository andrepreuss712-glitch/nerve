"""
NERVE Real-Time Engine — FastAPI Application

Entry point for the async WebSocket engine.
Runs on port 8001 alongside the Flask app (port 5000).
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from nerve_rt.config import settings
from nerve_rt.redis_bridge import redis_bridge

logger = logging.getLogger("nerve_rt")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events for the FastAPI app."""
    # Startup
    await redis_bridge.connect()
    logger.info(f"[RT] Engine started on {settings.host}:{settings.port}")
    yield
    # Shutdown
    await redis_bridge.close()
    logger.info("[RT] Engine stopped")


app = FastAPI(
    title="NERVE Real-Time Engine",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.cors_origin] if settings.cors_origin != '*' else ['*'],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    """Health check endpoint. Returns Redis connection status."""
    redis_ok = await redis_bridge.ping()
    return {"status": "ok", "redis": redis_ok}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "nerve_rt.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )
