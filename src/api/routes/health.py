"""
Health check endpoints.
Provides health and readiness checks for Docker/K8s deployments.
"""

import logging
from datetime import datetime

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from src.config.database import postgres_manager

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
async def health_check():
    """
    Health check with database verification.
    Used by Docker healthcheck and load balancers.
    """
    db_ok = False
    supabase_ok = False

    try:
        db_ok = await postgres_manager.health_check()
    except Exception as e:
        logger.warning(f"Health check PostgreSQL error: {e}")

    try:
        from src.config.database import get_supabase_client
        client = get_supabase_client()
        supabase_ok = client is not None
    except Exception as e:
        logger.warning(f"Health check Supabase error: {e}")

    all_ok = db_ok and supabase_ok
    svc_status = "healthy" if all_ok else "degraded"
    http_status = status.HTTP_200_OK if all_ok else status.HTTP_503_SERVICE_UNAVAILABLE

    return JSONResponse(
        status_code=http_status,
        content={
            "status": svc_status,
            "timestamp": datetime.utcnow().isoformat(),
            "database": db_ok,
            "supabase": supabase_ok,
            "version": "2.0.0",
        },
    )


@router.get("/ready")
async def readiness_check():
    """Readiness check for K8s readiness probes."""
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "ready": True,
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


@router.get("/live")
async def liveness_check():
    """Liveness check for K8s liveness probes."""
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "alive": True,
            "timestamp": datetime.utcnow().isoformat(),
        },
    )
