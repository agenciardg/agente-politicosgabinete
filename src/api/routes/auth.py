"""
Authentication routes: login, refresh, change password, current user.
"""

import logging
from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, HTTPException, status

from src.config.database import get_supabase_client
from src.middleware.auth import get_current_user
from src.models.auth import (
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    RefreshResponse,
    UserInfo,
)
from src.services.auth_service import (
    authenticate_user,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_user_by_id,
    hash_password,
    verify_password,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/login", response_model=LoginResponse)
async def login(data: LoginRequest) -> LoginResponse:
    """Authenticate user and return access + refresh tokens.

    Args:
        data: Login credentials (email, password).

    Returns:
        LoginResponse with tokens and user info.

    Raises:
        HTTPException 401: If credentials are invalid.
    """
    user = await authenticate_user(data.email, data.password)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou senha invalidos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_data = {
        "sub": user["id"],
        "email": user["email"],
        "role": user["role"],
        "tenant_id": user["tenant_id"],
    }

    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token({"sub": user["id"]})

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        user=UserInfo(**user),
    )


@router.post("/refresh", response_model=RefreshResponse)
async def refresh_token(data: RefreshRequest) -> RefreshResponse:
    """Refresh access token using a valid refresh token.

    Args:
        data: Refresh token request body.

    Returns:
        New access and refresh tokens.

    Raises:
        HTTPException 401: If refresh token is invalid or expired.
    """
    try:
        payload = decode_token(data.refresh_token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expirado, faca login novamente",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token invalido",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalido para esta operacao",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalido",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await get_user_by_id(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario nao encontrado ou inativo",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_data = {
        "sub": user["id"],
        "email": user["email"],
        "role": user["role"],
        "tenant_id": user["tenant_id"],
    }

    new_access_token = create_access_token(token_data)
    new_refresh_token = create_refresh_token({"sub": user["id"]})

    return RefreshResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
    )


@router.post("/change-password")
async def change_password(
    data: ChangePasswordRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
) -> dict:
    """Change the current user's password.

    Args:
        data: Current and new password.
        current_user: Authenticated user from JWT.

    Returns:
        Success message.

    Raises:
        HTTPException 400: If current password is incorrect.
    """
    sb = get_supabase_client()

    result = sb.table("agentpolitico_admin_users").select("password_hash").eq("id", current_user["id"]).execute()

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario nao encontrado",
        )

    row = result.data[0]

    if not verify_password(data.current_password, row["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Senha atual incorreta",
        )

    new_hash = hash_password(data.new_password)

    sb.table("agentpolitico_admin_users").update({
        "password_hash": new_hash,
    }).eq("id", current_user["id"]).execute()

    logger.info(f"Password changed for user {current_user['id']}")

    return {"message": "Senha alterada com sucesso"}


@router.get("/me", response_model=UserInfo)
async def get_me(
    current_user: Annotated[dict, Depends(get_current_user)],
) -> UserInfo:
    """Return the current authenticated user's info.

    Args:
        current_user: Authenticated user from JWT.

    Returns:
        UserInfo with user details.
    """
    return UserInfo(**current_user)
