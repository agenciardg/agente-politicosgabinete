"""
Agent Pydantic models.
Data structures for agent configuration management.
Matches agentpolitico_tenant_agents table columns.
"""

from typing import Optional
from pydantic import BaseModel, Field


class AgentCreate(BaseModel):
    """Schema for creating an agent."""

    tenant_id: str = Field(..., description="Tenant UUID")
    agent_type: str = Field(..., description="Agent type: 'principal' or 'assessor'")
    name: str = Field(..., description="Agent display name")
    persona_prompt: Optional[str] = Field(None, description="Persona prompt for the agent")
    behavior_prompt: Optional[str] = Field(None, description="Behavior prompt for the agent")
    active: Optional[bool] = Field(default=True, description="Whether agent is active")


class AgentUpdate(BaseModel):
    """Schema for updating an agent."""

    name: Optional[str] = None
    persona_prompt: Optional[str] = None
    behavior_prompt: Optional[str] = None
    initial_message: Optional[str] = None
    active: Optional[bool] = None


class AgentResponse(BaseModel):
    """Schema for agent API responses."""

    id: str
    tenant_id: str
    agent_type: str
    name: str
    persona_prompt: Optional[str] = None
    behavior_prompt: Optional[str] = None
    initial_message: Optional[str] = None
    active: Optional[bool] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True


class FollowupPromptResponse(BaseModel):
    """Schema for followup prompt."""

    agent_id: str
    followup_number: int
    prompt_template: str
    active: Optional[bool] = None


class FollowupPromptUpsert(BaseModel):
    """Schema for upserting a followup prompt."""

    prompt_template: str = Field(..., description="Prompt template text")
    active: Optional[bool] = Field(default=True)


class AssessorNumberCreate(BaseModel):
    """Schema for creating an assessor number."""

    agent_id: str = Field(..., description="Agent UUID")
    phone_number: str = Field(..., description="WhatsApp phone number")
    label: Optional[str] = Field(None, description="Label for this number")


class AssessorNumberResponse(BaseModel):
    """Schema for assessor number API responses."""

    id: str
    tenant_id: str
    agent_id: str
    phone_number: str
    label: Optional[str] = None
    active: Optional[bool] = None
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


# Keep old names as aliases for backward compatibility
AgentConfigCreate = AgentCreate
AgentConfigUpdate = AgentUpdate
AgentConfigResponse = AgentResponse
