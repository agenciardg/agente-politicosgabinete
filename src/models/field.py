"""
Field Pydantic models.
Data structures for contact field configuration.
Matches agentpolitico_tenant_contact_fields and agentpolitico_tenant_agent_contact_fields.
"""

from typing import Optional
from pydantic import BaseModel, Field


class ContactFieldResponse(BaseModel):
    """Schema for tenant contact field API responses (synced from Helena)."""

    id: str
    tenant_id: str
    helena_field_key: Optional[str] = None
    helena_field_name: Optional[str] = None
    sync_status: Optional[str] = None
    synced_at: Optional[str] = None

    class Config:
        from_attributes = True


class AgentFieldConfigure(BaseModel):
    """Schema for configuring a contact field for an agent."""

    contact_field_id: str = Field(..., description="Tenant contact field UUID")
    instruction: Optional[str] = Field(None, description="Instruction for the agent on this field")
    field_order: Optional[int] = Field(default=0, description="Display/collection order")
    required: Optional[bool] = Field(default=False)
    active: Optional[bool] = Field(default=True)


class AgentFieldUpdate(BaseModel):
    """Schema for updating an agent contact field config."""

    instruction: Optional[str] = None
    field_order: Optional[int] = None
    required: Optional[bool] = None
    active: Optional[bool] = None


class AgentFieldResponse(BaseModel):
    """Schema for agent contact field API responses."""

    id: str
    agent_id: str
    contact_field_id: str
    instruction: Optional[str] = None
    field_order: Optional[int] = None
    required: Optional[bool] = None
    active: Optional[bool] = None
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


# Keep old names as aliases for backward compatibility
FieldCreate = AgentFieldConfigure
FieldUpdate = AgentFieldUpdate
FieldResponse = AgentFieldResponse
