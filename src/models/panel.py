"""
Panel Pydantic models.
Data structures for Helena CRM panel configuration.
Matches agentpolitico_tenant_panels and related tables.
"""

from typing import Optional, List
from pydantic import BaseModel, Field


class PanelResponse(BaseModel):
    """Schema for tenant panel API responses."""

    id: str
    tenant_id: str
    name: Optional[str] = None
    steps: Optional[List[dict]] = None
    custom_fields: Optional[List[dict]] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True


class AgentPanelConfigure(BaseModel):
    """Schema for configuring a panel for an agent."""

    tenant_panel_id: str = Field(..., description="Tenant panel UUID")
    agent_description: Optional[str] = Field(None, description="Description for the agent")
    step_id: Optional[str] = Field(None, description="Helena step UUID")
    department_id: Optional[str] = Field(None, description="Helena department UUID")
    active: Optional[bool] = Field(default=True)
    pre_transfer_requirements: Optional[str] = Field(None, description="Requirements to collect before transfer")


class AgentPanelUpdate(BaseModel):
    """Schema for updating an agent panel config."""

    agent_description: Optional[str] = None
    step_id: Optional[str] = None
    department_id: Optional[str] = None
    active: Optional[bool] = None
    pre_transfer_requirements: Optional[str] = Field(None, description="Requirements to collect before transfer")


class AgentPanelResponse(BaseModel):
    """Schema for agent panel API responses."""

    id: str
    agent_id: str
    tenant_panel_id: str
    agent_description: Optional[str] = None
    step_id: Optional[str] = None
    department_id: Optional[str] = None
    active: Optional[bool] = None
    pre_transfer_requirements: Optional[str] = None
    field_mappings: Optional[List[dict]] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True


class FieldMappingUpsert(BaseModel):
    """Schema for upserting a field mapping."""

    panel_custom_field_id: str = Field(..., description="Panel custom field UUID")
    storage_instruction: str = Field(..., description="Storage instruction for the field")
    active: Optional[bool] = Field(default=True)
    fill_type: Optional[str] = Field(default="auto", description="How to fill: auto, contact, collect")


class FieldMappingResponse(BaseModel):
    """Schema for field mapping API responses."""

    id: str
    agent_panel_id: str
    panel_custom_field_id: str
    storage_instruction: str
    active: Optional[bool] = True
    fill_type: Optional[str] = Field(default="auto", description="How to fill: auto, contact, collect")
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


# Keep old names as aliases for backward compatibility
PanelCreate = AgentPanelConfigure
PanelUpdate = AgentPanelUpdate
