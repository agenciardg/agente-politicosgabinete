"""
Authentication service with JWT + bcrypt.

Handles password hashing, JWT token creation/verification,
and user authentication against agentpolitico_admin_users in Supabase RDG.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt

from src.config.settings import settings
from src.config.database import get_supabase_client

logger = logging.getLogger(__name__)


def hash_password(password: str) -> str:
    """Hash a password using bcrypt with 12 salt rounds."""
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Verify a plain-text password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(
            password.encode("utf-8"), hashed.encode("utf-8")
        )
    except Exception:
        return False


def create_access_token(
    data: dict, expires_delta: Optional[timedelta] = None
) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    now = datetime.now(timezone.utc)

    if expires_delta is not None:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)

    to_encode.update({
        "exp": expire,
        "iat": now,
        "type": "access",
    })

    return jwt.encode(
        to_encode,
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )


def create_refresh_token(data: dict) -> str:
    """Create a JWT refresh token with longer expiry."""
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=settings.JWT_REFRESH_EXPIRE_DAYS)

    to_encode.update({
        "exp": expire,
        "iat": now,
        "type": "refresh",
    })

    return jwt.encode(
        to_encode,
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_token(token: str) -> dict:
    """Decode and validate a JWT token."""
    return jwt.decode(
        token,
        settings.JWT_SECRET,
        algorithms=[settings.JWT_ALGORITHM],
    )


async def authenticate_user(email: str, password: str) -> Optional[dict]:
    """Authenticate a user by email and password.

    Uses Supabase REST client to query agentpolitico_admin_users.
    """
    supabase = get_supabase_client()

    result = supabase.table("agentpolitico_admin_users").select(
        "id, email, password_hash, name, role, tenant_id, active"
    ).eq("email", email).limit(1).execute()

    if not result.data:
        return None

    row = result.data[0]

    if not row.get("active"):
        return None

    if not verify_password(password, row["password_hash"]):
        return None

    return {
        "id": str(row["id"]),
        "email": row["email"],
        "name": row["name"],
        "role": row["role"],
        "tenant_id": str(row["tenant_id"]) if row.get("tenant_id") else None,
    }


async def get_user_by_id(user_id: str) -> Optional[dict]:
    """Fetch a user by ID from agentpolitico_admin_users."""
    supabase = get_supabase_client()

    result = supabase.table("agentpolitico_admin_users").select(
        "id, email, name, role, tenant_id, active"
    ).eq("id", user_id).limit(1).execute()

    if not result.data:
        return None

    row = result.data[0]

    if not row.get("active"):
        return None

    return {
        "id": str(row["id"]),
        "email": row["email"],
        "name": row["name"],
        "role": row["role"],
        "tenant_id": str(row["tenant_id"]) if row.get("tenant_id") else None,
    }
