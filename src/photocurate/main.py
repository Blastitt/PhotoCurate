"""PhotoCurate — FastAPI application entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from photocurate.config import settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    logger.info("PhotoCurate starting up (env=%s)", settings.app_env)

    # Connect message queue and register workers
    try:
        from photocurate.api.deps import get_message_queue
        queue = get_message_queue()
        await queue.connect()
        logger.info("Message queue connected")

        from photocurate.workers.image_processing import handle_image_processing_event
        from photocurate.workers.scoring import handle_scoring_event
        await queue.subscribe("photo.processing", handle_image_processing_event)
        await queue.subscribe("photo.scoring", handle_scoring_event)
        logger.info("Worker subscriptions registered")
    except Exception as e:
        logger.warning("Message queue not available: %s", e)

    yield

    # Shutdown
    try:
        from photocurate.api.deps import get_message_queue
        queue = get_message_queue()
        await queue.disconnect()
    except Exception:
        pass

    logger.info("PhotoCurate shut down")


app = FastAPI(
    title="PhotoCurate",
    description="Multi-tenant SaaS platform for photographers — AI-powered photo scoring, client galleries, and cloud delivery.",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.is_development else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Register routers ───────────────────────────────────────────────

from photocurate.api.routes.auth_routes import router as auth_router
from photocurate.api.routes.client_routes import router as client_router
from photocurate.api.routes.gallery_routes import router as gallery_mgmt_router
from photocurate.api.routes.session_routes import router as session_router
from photocurate.gallery.routes import router as gallery_public_router

app.include_router(auth_router, prefix="/api/v1")
app.include_router(session_router, prefix="/api/v1")
app.include_router(client_router, prefix="/api/v1")
app.include_router(gallery_mgmt_router, prefix="/api/v1")
app.include_router(gallery_public_router, prefix="/api/v1")  # Public gallery at /api/v1/gallery/:slug


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "version": "0.1.0"}
