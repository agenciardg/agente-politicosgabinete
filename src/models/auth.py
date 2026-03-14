"""
Pydantic models for authentication and admin user management.
"""

from typing import Optional
from pydantic import BaseModel, Field, EmailStr, ConfigDict


class LoginRequest(BaseModel):
    """Request body for login endpoint."""

    email: EmailStr
    password: str = Field(..., min_length=6)


class UserInfo(BaseModel):
    """User information returned in auth responses."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    name: str
    role: str
    tenant_id: Optional[str] = None


class LoginResponse(BaseModel):
    """Response body for login endpoint."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserInfo


class RefreshRequest(BaseModel):
    """Request body for token refresh endpoint."""

    refresh_token: str


class RefreshResponse(BaseModel):
    """Response body for token refresh endpoint."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class ChangePasswordRequest(BaseModel):
    """Request body for change password endpoint."""

    current_password: str = Field(..., min_length=6)
    new_password: str = Field(..., min_length=8)


class AdminUserCreate(BaseModel):
    """Request body for creating an admin user."""

    email: EmailStr
    password: str = Field(..., min_length=8)
    name: str = Field(..., min_length=2, max_length=255)
    role: str = Field(..., pattern=r"^(super_admin|tenant_admin)$")
    tenant_id: Optional[str] = None


class AdminUserUpdate(BaseModel):
    """Request body for updating an admin user."""

    email: Optional[EmailStr] = None
    name: Optional[str] = Field(default=None, min_length=2, max_length=255)
    role: Optional[str] = Field(default=None, pattern=r"^(super_admin|tenant_admin)$")
    active: Optional[bool] = None


class AdminUserResponse(BaseModel):
    """Response body for admin user endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    name: str
    role: str
    tenant_id: Optional[str] = None
    active: bool
    created_at: str
    updated_at: str


class PaginatedAdminUsersResponse(BaseModel):
    """Paginated response for listing admin users."""

    data: list[AdminUserResponse]
    meta: dict
