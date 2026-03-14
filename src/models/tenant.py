"""
Tenant Pydantic models.
Data structures for tenant (gabinete) management.
Matches agentpolitico_tenants table columns.
"""

from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime


class TenantCreate(BaseModel):
    """Schema for creating a new tenant."""

    name: str = Field(..., description="Tenant name (e.g., 'Gabinete Vereador X')")
    slug: str = Field(..., description="URL-safe slug (e.g., 'vereador-x')")
    helena_api_token: Optional[str] = Field(None, description="Helena CRM API token for this tenant")
    llm_api_key: Optional[str] = Field(None, description="LLM API key")
    llm_provider: Optional[str] = Field(default="grok", description="LLM provider: grok, openai, etc.")
    followup_1_minutes: Optional[int] = Field(default=1440, description="Follow-up 1 delay in minutes")
    followup_2_minutes: Optional[int] = Field(default=2880, description="Follow-up 2 delay in minutes")
    followup_3_minutes: Optional[int] = Field(default=4320, description="Follow-up 3 delay in minutes")
    due_hours: Optional[int] = Field(default=48, description="Due hours for tasks")
    checkpoint_timeout_hours: Optional[int] = Field(default=24, description="Checkpoint timeout in hours")
    active: Optional[bool] = Field(default=True, description="Whether tenant is active")


class TenantUpdate(BaseModel):
    """Schema for updating a tenant."""

    name: Optional[str] = None
    slug: Optional[str] = None
    helena_api_token: Optional[str] = None
    llm_api_key: Optional[str] = None
    llm_provider: Optional[str] = None
    followup_1_minutes: Optional[int] = None
    followup_2_minutes: Optional[int] = None
    followup_3_minutes: Optional[int] = None
    due_hours: Optional[int] = None
    checkpoint_timeout_hours: Optional[int] = None
    active: Optional[bool] = None


class TenantResponse(BaseModel):
    """Schema for tenant API responses."""

    id: str = Field(..., description="Tenant UUID")
    name: str
    slug: str
    helena_api_token: Optional[str] = None
    llm_api_key: Optional[str] = None
    llm_provider: Optional[str] = None
    followup_1_minutes: Optional[int] = None
    followup_2_minutes: Optional[int] = None
    followup_3_minutes: Optional[int] = None
    due_hours: Optional[int] = None
    checkpoint_timeout_hours: Optional[int] = None
    active: Optional[bool] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True
