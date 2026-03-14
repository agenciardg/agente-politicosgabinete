"""
Dependency Injection
=====================
FastAPI dependencies for DB sessions, current user, tenant resolution.
"""

import logging
from typing import Optional

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from src.config.database import postgres_manager, get_supabase_client
from src.services.auth_service import decode_token

logger = logging.getLogger(__name__)

security = HTTPBearer()


async def get_db_session():
    """Yield an async SQLAlchemy session for PostgreSQL."""
    async with postgres_manager.get_session() as session:
        yield session


async def get_db_connection():
    """Yield a raw asyncpg connection."""
    async with postgres_manager.get_connection() as conn:
        yield conn


def get_supabase():
    """Get the Supabase client for config table operations."""
    return get_supabase_client()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """
    Extract and validate the current user from JWT token.

    Returns:
        dict with user_id, tenant_id, role, email
    """
    token = credentials.credentials

    try:
        payload = decode_token(token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return payload


async def get_current_admin(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Require admin role."""
    if current_user.get("role") not in ("tenant_admin", "super_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


async def get_current_superadmin(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Require superadmin role."""
    if current_user.get("role") != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superadmin access required",
        )
    return current_user


def resolve_tenant_id(
    request: Request,
    current_user: dict = Depends(get_current_user),
) -> str:
    """Extract tenant_id from JWT or query param (super_admin can pass ?tenant_id=)."""
    # Super admin can pass tenant_id as query param
    if current_user.get("role") == "super_admin":
        tenant_id = request.query_params.get("tenant_id")
        if tenant_id:
            return tenant_id
    # Fallback to JWT tenant_id
    tenant_id = current_user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No tenant_id associated with user. Super admin must pass ?tenant_id=",
        )
    return tenant_id
