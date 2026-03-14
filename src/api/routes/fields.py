"""
Contact field config routes.
Manage contact fields per tenant and agent field configurations.
"""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from src.models.field import (
    ContactFieldResponse,
    AgentFieldConfigure,
    AgentFieldUpdate,
    AgentFieldResponse,
)
from src.api.deps import get_current_admin, resolve_tenant_id
from src.services.field_service import FieldService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", response_model=List[ContactFieldResponse])
async def list_fields(tenant_id: str = Depends(resolve_tenant_id)):
    """List all synced contact fields for the current tenant."""
    service = FieldService()
    return await service.list_contact_fields(tenant_id)


@router.get("/agent/{agent_id}", response_model=List[AgentFieldResponse])
async def list_agent_fields(
    agent_id: str,
    tenant_id: str = Depends(resolve_tenant_id),
):
    """List contact fields configured for an agent."""
    service = FieldService()
    return await service.list_agent_contact_fields(agent_id)


@router.post("/agent/{agent_id}", response_model=AgentFieldResponse, status_code=status.HTTP_201_CREATED)
async def configure_agent_field(
    agent_id: str,
    data: AgentFieldConfigure,
    tenant_id: str = Depends(resolve_tenant_id),
    current_user: dict = Depends(get_current_admin),
):
    """Configure a contact field for an agent."""
    service = FieldService()
    return await service.configure_agent_field(agent_id, data)


@router.put("/agent-field/{config_id}", response_model=AgentFieldResponse)
async def update_agent_field(
    config_id: str,
    data: AgentFieldUpdate,
    tenant_id: str = Depends(resolve_tenant_id),
    current_user: dict = Depends(get_current_admin),
):
    """Update an agent contact field config."""
    service = FieldService()
    result = await service.update_agent_field(config_id, data)
    if not result:
        raise HTTPException(status_code=404, detail="Agent field config not found")
    return result
