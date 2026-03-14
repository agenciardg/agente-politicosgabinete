"""
Admin user management routes (super_admin only).

CRUD operations for agentpolitico_admin_users table.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.config.database import get_supabase_client
from src.middleware.auth import require_super_admin
from src.models.auth import (
    AdminUserCreate,
    AdminUserResponse,
    AdminUserUpdate,
    PaginatedAdminUsersResponse,
)
from src.services.auth_service import hash_password

logger = logging.getLogger(__name__)

router = APIRouter()


def _row_to_response(row: dict) -> AdminUserResponse:
    """Convert a database row (dict) to AdminUserResponse."""
    return AdminUserResponse(
        id=str(row["id"]),
        email=row["email"],
        name=row["name"],
        role=row["role"],
        tenant_id=str(row["tenant_id"]) if row.get("tenant_id") else None,
        active=row["active"],
        created_at=row["created_at"] if isinstance(row["created_at"], str) else row["created_at"].isoformat(),
        updated_at=row["updated_at"] if isinstance(row["updated_at"], str) else row["updated_at"].isoformat(),
    )


@router.get("", response_model=PaginatedAdminUsersResponse)
async def list_admin_users(
    current_user: Annotated[dict, Depends(require_super_admin)],
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
) -> PaginatedAdminUsersResponse:
    """List all admin users with pagination.

    Args:
        current_user: Authenticated super_admin user.
        page: Page number (starts at 1).
        per_page: Number of items per page.

    Returns:
        Paginated list of admin users.
    """
    sb = get_supabase_client()
    offset = (page - 1) * per_page

    # Get total count
    count_result = sb.table("agentpolitico_admin_users").select("*", count="exact").execute()
    total = count_result.count

    # Get paginated rows
    result = (
        sb.table("agentpolitico_admin_users")
        .select("id, email, name, role, tenant_id, active, created_at, updated_at")
        .order("created_at", desc=True)
        .range(offset, offset + per_page - 1)
        .execute()
    )

    users = [_row_to_response(row) for row in result.data]

    return PaginatedAdminUsersResponse(
        data=users,
        meta={
            "page": page,
            "per_page": per_page,
            "total": total,
        },
    )


@router.post("", response_model=AdminUserResponse, status_code=status.HTTP_201_CREATED)
async def create_admin_user(
    data: AdminUserCreate,
    current_user: Annotated[dict, Depends(require_super_admin)],
) -> AdminUserResponse:
    """Create a new admin user.

    Args:
        data: Admin user creation data.
        current_user: Authenticated super_admin user.

    Returns:
        Created admin user.

    Raises:
        HTTPException 409: If email already exists.
        HTTPException 400: If tenant_admin has no tenant_id.
    """
    if data.role == "tenant_admin" and not data.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="tenant_id e obrigatorio para tenant_admin",
        )

    if data.role == "super_admin" and data.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="super_admin nao deve ter tenant_id",
        )

    sb = get_supabase_client()
    password_hash = hash_password(data.password)

    # Check email uniqueness
    existing = sb.table("agentpolitico_admin_users").select("id").eq("email", data.email).execute()

    if existing.data:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email ja cadastrado",
        )

    insert_data = {
        "email": data.email,
        "password_hash": password_hash,
        "name": data.name,
        "role": data.role,
        "tenant_id": data.tenant_id,
    }

    result = (
        sb.table("agentpolitico_admin_users")
        .insert(insert_data)
        .execute()
    )
    row = result.data[0]

    logger.info(
        f"Admin user created: {row['id']} ({data.email}) by {current_user['id']}"
    )

    return _row_to_response(row)


@router.get("/{user_id}", response_model=AdminUserResponse)
async def get_admin_user(
    user_id: str,
    current_user: Annotated[dict, Depends(require_super_admin)],
) -> AdminUserResponse:
    """Get a specific admin user by ID.

    Args:
        user_id: UUID of the admin user.
        current_user: Authenticated super_admin user.

    Returns:
        Admin user details.

    Raises:
        HTTPException 404: If user not found.
    """
    sb = get_supabase_client()

    result = (
        sb.table("agentpolitico_admin_users")
        .select("id, email, name, role, tenant_id, active, created_at, updated_at")
        .eq("id", user_id)
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario nao encontrado",
        )

    return _row_to_response(result.data[0])


@router.put("/{user_id}", response_model=AdminUserResponse)
async def update_admin_user(
    user_id: str,
    data: AdminUserUpdate,
    current_user: Annotated[dict, Depends(require_super_admin)],
) -> AdminUserResponse:
    """Update an admin user.

    Args:
        user_id: UUID of the admin user to update.
        data: Fields to update.
        current_user: Authenticated super_admin user.

    Returns:
        Updated admin user.

    Raises:
        HTTPException 404: If user not found.
        HTTPException 409: If email already taken by another user.
    """
    sb = get_supabase_client()

    # Check user exists
    existing_result = (
        sb.table("agentpolitico_admin_users")
        .select("id, email, name, role, tenant_id, active, created_at, updated_at")
        .eq("id", user_id)
        .execute()
    )

    if not existing_result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario nao encontrado",
        )

    existing = existing_result.data[0]

    # Build update dict
    update_fields: dict = {}

    if data.email is not None:
        # Check uniqueness
        dup = (
            sb.table("agentpolitico_admin_users")
            .select("id")
            .eq("email", data.email)
            .neq("id", user_id)
            .execute()
        )
        if dup.data:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email ja cadastrado por outro usuario",
            )
        update_fields["email"] = data.email

    if data.name is not None:
        update_fields["name"] = data.name

    if data.role is not None:
        update_fields["role"] = data.role

    if data.active is not None:
        update_fields["active"] = data.active

    if not update_fields:
        return _row_to_response(existing)

    result = (
        sb.table("agentpolitico_admin_users")
        .update(update_fields)
        .eq("id", user_id)
        .execute()
    )
    row = result.data[0]

    logger.info(f"Admin user updated: {user_id} by {current_user['id']}")

    return _row_to_response(row)


@router.delete("/{user_id}", status_code=status.HTTP_200_OK)
async def delete_admin_user(
    user_id: str,
    current_user: Annotated[dict, Depends(require_super_admin)],
) -> dict:
    """Delete (soft-delete) an admin user.

    Cannot delete yourself.

    Args:
        user_id: UUID of the admin user to delete.
        current_user: Authenticated super_admin user.

    Returns:
        Success message.

    Raises:
        HTTPException 400: If trying to delete yourself.
        HTTPException 404: If user not found.
    """
    if user_id == current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nao e possivel excluir seu proprio usuario",
        )

    sb = get_supabase_client()

    existing = sb.table("agentpolitico_admin_users").select("id").eq("id", user_id).execute()

    if not existing.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario nao encontrado",
        )

    sb.table("agentpolitico_admin_users").update({
        "active": False,
    }).eq("id", user_id).execute()

    logger.info(f"Admin user soft-deleted: {user_id} by {current_user['id']}")

    return {"message": "Usuario desativado com sucesso"}
