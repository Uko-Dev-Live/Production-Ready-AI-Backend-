"""
app/main.py
────────────
FastAPI application entry point.

This file:
  1. Creates the FastAPI app instance
  2. Registers all routers (auth, users, jobs)
  3. Adds startup/shutdown lifecycle hooks
  4. Serves a health-check endpoint at GET /health

Everything is wired here. Uvicorn imports this module to start the server.
"""

import structlog
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logging import setup_logging
from app.api.routes import auth, users, jobs

# Configure structured logging as early as possible
setup_logging(debug=settings.DEBUG)
logger = structlog.get_logger(__name__)


# ── Lifespan: startup & shutdown hooks ──────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Code before 'yield' runs on startup.
    Code after 'yield' runs on shutdown.

    Use this for: opening DB pools, loading ML models into memory,
    warming caches, gracefully closing connections, etc.
    """
    logger.info(
        "Starting AI Backend",
        version=settings.APP_VERSION,
        env=settings.APP_ENV,
    )
    yield
    logger.info("Shutting down AI Backend")


# ── Application factory ──────────────────────────────────────────────

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "Production-ready AI backend with FastAPI, Celery, PostgreSQL, "
        "Alembic migrations, and MCP server integration."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS — allow all origins in development; restrict in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.DEBUG else ["https://yourdomain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Register routers ─────────────────────────────────────────────────

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(jobs.router)


# ── Health check ─────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
async def health_check():
    """
    Quick liveness probe — used by Docker health checks and load balancers.
    Returns 200 if the app is running.
    """
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "env": settings.APP_ENV,
    }


@app.get("/", tags=["System"])
async def root():
    return JSONResponse({
        "message": f"Welcome to {settings.APP_NAME}",
        "docs": "/docs",
        "health": "/health",
    })
