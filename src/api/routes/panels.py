"""
Panel config routes + field mapping.
Manage Helena CRM panel configurations per tenant.
"""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from src.models.panel import (
    PanelResponse,
    AgentPanelConfigure,
    AgentPanelUpdate,
    AgentPanelResponse,
    FieldMappingUpsert,
    FieldMappingResponse,
)
from src.api.deps import get_current_admin, resolve_tenant_id
from src.services.panel_service import PanelService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", response_model=List[PanelResponse])
async def list_panels(tenant_id: str = Depends(resolve_tenant_id)):
    """List all tenant panels with steps and custom fields."""
    service = PanelService()
    return await service.list_panels_by_tenant(tenant_id)


@router.get("/{panel_id}", response_model=PanelResponse)
async def get_panel(
    panel_id: str,
    tenant_id: str = Depends(resolve_tenant_id),
):
    """Get a specific panel with steps and custom fields."""
    service = PanelService()
    panel = await service.get_panel(panel_id)
    if not panel:
        raise HTTPException(status_code=404, detail="Panel not found")
    if panel.get("tenant_id") != tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return panel


# ---- Agent Panels ----

@router.get("/agent/{agent_id}", response_model=List[AgentPanelResponse])
async def list_agent_panels(
    agent_id: str,
    tenant_id: str = Depends(resolve_tenant_id),
):
    """List panels configured for a specific agent."""
    service = PanelService()
    return await service.list_agent_panels(agent_id)


@router.post("/agent/{agent_id}", response_model=AgentPanelResponse, status_code=status.HTTP_201_CREATED)
async def configure_agent_panel(
    agent_id: str,
    data: AgentPanelConfigure,
    tenant_id: str = Depends(resolve_tenant_id),
    current_user: dict = Depends(get_current_admin),
):
    """Configure a panel for an agent."""
    service = PanelService()
    return await service.configure_agent_panel(agent_id, data)


@router.put("/agent-panel/{agent_panel_id}", response_model=AgentPanelResponse)
async def update_agent_panel(
    agent_panel_id: str,
    data: AgentPanelUpdate,
    tenant_id: str = Depends(resolve_tenant_id),
    current_user: dict = Depends(get_current_admin),
):
    """Update an agent panel config."""
    service = PanelService()
    result = await service.update_agent_panel(agent_panel_id, data)
    if not result:
        raise HTTPException(status_code=404, detail="Agent panel not found")
    return result


# ---- Field Mappings ----

@router.get("/{agent_panel_id}/field-mappings", response_model=List[FieldMappingResponse])
async def get_field_mappings(
    agent_panel_id: str,
    tenant_id: str = Depends(resolve_tenant_id),
):
    """Get field mappings for an agent panel."""
    from src.config.database import get_supabase_client

    sb = get_supabase_client()
    result = (
        sb.table("agentpolitico_tenant_agent_panel_field_mappings")
        .select("*")
        .eq("agent_panel_id", agent_panel_id)
        .execute()
    )
    return result.data


@router.put("/{agent_panel_id}/field-mappings", response_model=FieldMappingResponse)
async def upsert_field_mapping(
    agent_panel_id: str,
    data: FieldMappingUpsert,
    tenant_id: str = Depends(resolve_tenant_id),
    current_user: dict = Depends(get_current_admin),
):
    """Upsert a field mapping for an agent panel."""
    service = PanelService()
    return await service.upsert_field_mapping(
        agent_panel_id, data.panel_custom_field_id, data.storage_instruction,
        data.active if data.active is not None else True,
        data.fill_type or "auto"
    )


@router.delete("/field-mappings/{mapping_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_field_mapping(
    mapping_id: str,
    tenant_id: str = Depends(resolve_tenant_id),
    current_user: dict = Depends(get_current_admin),
):
    """Delete a field mapping."""
    service = PanelService()
    success = await service.delete_field_mapping(mapping_id)
    if not success:
        raise HTTPException(status_code=404, detail="Field mapping not found")
