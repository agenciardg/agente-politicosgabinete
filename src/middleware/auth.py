"""
FastAPI authentication middleware and dependency injection.

Provides dependencies for extracting and validating JWT tokens,
enforcing role-based access control (RBAC) for super_admin and tenant_admin.
"""

import logging
from typing import Annotated, Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from src.services.auth_service import decode_token, get_user_by_id

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
) -> dict:
    """Extract and validate JWT from Authorization header, return user.

    Args:
        token: JWT bearer token extracted by OAuth2PasswordBearer.

    Returns:
        User dict with id, email, name, role, tenant_id.

    Raises:
        HTTPException 401: If token is invalid, expired, or user not found.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token invalido ou expirado",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise credentials_exception

    if payload.get("type") != "access":
        raise credentials_exception

    user_id: Optional[str] = payload.get("sub")
    if user_id is None:
        raise credentials_exception

    user = await get_user_by_id(user_id)
    if user is None:
        raise credentials_exception

    return user


async def require_super_admin(
    user: Annotated[dict, Depends(get_current_user)],
) -> dict:
    """Require the current user to have super_admin role.

    Args:
        user: Current authenticated user from get_current_user.

    Returns:
        The user dict if they are a super_admin.

    Raises:
        HTTPException 403: If user is not a super_admin.
    """
    if user["role"] != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso nao autorizado para esta operacao",
        )
    return user


async def require_tenant_access(
    tenant_id: str,
    user: Annotated[dict, Depends(get_current_user)],
) -> dict:
    """Require the current user to have access to the specified tenant.

    super_admin has access to all tenants.
    tenant_admin only has access to their own tenant.

    Args:
        tenant_id: UUID of the tenant to check access for.
        user: Current authenticated user from get_current_user.

    Returns:
        The user dict if they have access.

    Raises:
        HTTPException 403: If user does not have access to the tenant.
    """
    if user["role"] == "super_admin":
        return user

    if user["role"] == "tenant_admin" and user.get("tenant_id") == tenant_id:
        return user

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Acesso nao autorizado para esta operacao",
    )
