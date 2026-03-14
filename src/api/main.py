"""
FastAPI application with multi-tenant LangGraph agent integration.

Main entry point for the multi-tenant gabinete agent API.
Extended from single-tenant with CORS, JWT auth, APScheduler, and tenant routing.
"""

import logging
import time
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from src.config.settings import settings
from src.config.database import postgres_manager, init_database, close_database, get_supabase_client

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Global state
start_time = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifecycle manager.
    Handles startup/shutdown for DB connections, Supabase, and scheduled jobs.
    """
    # Startup
    logger.info("Starting multi-tenant gabinete agent API...")

    try:
        # Initialize PostgreSQL (memory/checkpoints)
        logger.info("Initializing PostgreSQL connection...")
        await init_database()
        logger.info("PostgreSQL connection established")

        # Initialize Supabase client (config tables)
        logger.info("Initializing Supabase client...")
        get_supabase_client()
        logger.info("Supabase client ready")

        # Initialize APScheduler for follow-up cron jobs
        try:
            from apscheduler.schedulers.asyncio import AsyncIOScheduler
            from src.services.followup_service import FollowupService

            followup_service = FollowupService()
            scheduler = AsyncIOScheduler()
            scheduler.add_job(
                followup_service.process_pending_followups,
                'interval',
                minutes=1,
                id='followup_processor',
                name='Process pending follow-ups',
            )
            scheduler.start()
            app.state.scheduler = scheduler
            logger.info("APScheduler started with follow-up processor (1min interval)")
        except ImportError:
            logger.warning("APScheduler not installed, follow-up cron disabled")

        logger.info("Application startup complete!")

    except Exception as e:
        logger.error(f"Failed to initialize application: {e}", exc_info=True)
        raise

    yield

    # Shutdown
    logger.info("Shutting down application...")

    try:
        # Stop scheduler
        if hasattr(app.state, "scheduler"):
            app.state.scheduler.shutdown()
            logger.info("APScheduler stopped")

        # Close database connections
        await close_database()
        logger.info("Database connections closed")

    except Exception as e:
        logger.error(f"Error during shutdown: {e}", exc_info=True)

    logger.info("Application shutdown complete!")


# Create FastAPI app
app = FastAPI(
    title="Agente Gabinete - Multi-Tenant",
    description="API multi-tenant para agentes inteligentes de gabinetes parlamentares",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(GZipMiddleware, minimum_size=1000)


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests with timing."""
    start_time_req = time.time()

    logger.info(f"{request.method} {request.url.path}")

    response = await call_next(request)

    process_time = time.time() - start_time_req
    logger.info(
        f"{request.method} {request.url.path} - "
        f"Status: {response.status_code} - "
        f"Time: {process_time:.2f}s"
    )

    response.headers["X-Process-Time"] = str(process_time)
    return response


# Exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for uncaught errors."""
    logger.error(
        f"Unhandled exception: {exc}",
        exc_info=True,
        extra={"path": request.url.path, "method": request.method},
    )

    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal server error",
            "message": str(exc) if not settings.is_production else "An error occurred",
        },
    )


# Import and include routers
from src.api.routes import (
    health,
    auth,
    webhook,
    tenants,
    agents,
    panels,
    fields,
    departments,
    assessor_numbers,
    sync,
    followup,
    metrics,
    admin_users,
)

app.include_router(health.router, prefix="/api/v1", tags=["Health"])
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(webhook.router, prefix="/api/v1", tags=["Webhook"])
app.include_router(tenants.router, prefix="/api/v1/tenants", tags=["Tenants"])
app.include_router(agents.router, prefix="/api/v1/agents", tags=["Agents"])
app.include_router(panels.router, prefix="/api/v1/panels", tags=["Panels"])
app.include_router(fields.router, prefix="/api/v1/fields", tags=["Fields"])
app.include_router(departments.router, prefix="/api/v1/departments", tags=["Departments"])
app.include_router(assessor_numbers.router, prefix="/api/v1/assessor-numbers", tags=["Assessor Numbers"])
app.include_router(sync.router, prefix="/api/v1", tags=["Sync"])
app.include_router(followup.router, prefix="/api/v1/followup", tags=["Follow-up"])
app.include_router(metrics.router, prefix="/api/v1/metrics", tags=["Metrics"])
app.include_router(admin_users.router, prefix="/api/v1/admin-users", tags=["Admin Users"])


# Root endpoint
@app.get("/", include_in_schema=False)
async def root():
    """Root endpoint."""
    return {
        "service": "Agente Gabinete - Multi-Tenant",
        "version": "2.0.0",
        "status": "running",
        "docs": "/docs" if not settings.is_production else None,
    }


# Utility functions
def get_uptime() -> float:
    """Get application uptime in seconds."""
    return time.time() - start_time
