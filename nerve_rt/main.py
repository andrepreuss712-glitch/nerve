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
from nerve_rt.routers.ws_router import router as ws_router, set_session_manager
from nerve_rt.services.stt.deepgram_adapter import DeepgramAdapter
from nerve_rt.services.llm.claude_adapter import ClaudeAdapter
from nerve_rt.services.llm.shadow_logger import ShadowLogger
from nerve_rt.services.session_manager import SessionManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("nerve_rt")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events for the FastAPI app."""
    # Startup
    await redis_bridge.connect()

    # Initialize providers
    stt = DeepgramAdapter(api_key=settings.deepgram_api_key, sample_rate=settings.sample_rate)
    llm = ClaudeAdapter(api_key=settings.anthropic_api_key)
    shadow = ShadowLogger(primary=llm, shadow=None)  # No shadow provider yet
    manager = SessionManager(stt_provider=stt, shadow_logger=shadow)
    set_session_manager(manager)

    logger.info("[RT] Engine started on %s:%s", settings.host, settings.port)
    logger.info("[RT] STT: %s, LLM: %s", stt.provider_name, llm.model_id)
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


# Include routers
app.include_router(ws_router)


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
