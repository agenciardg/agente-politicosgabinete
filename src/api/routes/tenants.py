"""
Tenant CRUD routes.
Manage tenants (gabinetes) in the multi-tenant system.
"""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from src.models.tenant import TenantCreate, TenantUpdate, TenantResponse
from src.api.deps import get_current_admin, get_current_superadmin
from src.services.tenant_service import TenantService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", response_model=List[TenantResponse])
async def list_tenants(current_user: dict = Depends(get_current_superadmin)):
    """List all tenants (superadmin only)."""
    service = TenantService()
    return await service.list_all()


@router.get("/{tenant_id}", response_model=TenantResponse)
async def get_tenant(
    tenant_id: str,
    current_user: dict = Depends(get_current_admin),
):
    """Get a specific tenant by ID."""
    service = TenantService()
    tenant = await service.get_by_id(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


@router.post("/", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    data: TenantCreate,
    current_user: dict = Depends(get_current_superadmin),
):
    """Create a new tenant (superadmin only)."""
    service = TenantService()
    return await service.create(data)


@router.put("/{tenant_id}", response_model=TenantResponse)
async def update_tenant(
    tenant_id: str,
    data: TenantUpdate,
    current_user: dict = Depends(get_current_admin),
):
    """Update a tenant."""
    service = TenantService()
    tenant = await service.update(tenant_id, data)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


@router.delete("/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tenant(
    tenant_id: str,
    current_user: dict = Depends(get_current_superadmin),
):
    """Delete a tenant (superadmin only). CASCADE: also cleans PostgreSQL dedicated data."""
    service = TenantService()
    success = await service.delete(tenant_id)
    if not success:
        raise HTTPException(status_code=404, detail="Tenant not found")
