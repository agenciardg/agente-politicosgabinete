"""
Follow-up Pydantic models.
Data structures for follow-up message configuration.
"""

from typing import Optional
from pydantic import BaseModel, Field


class FollowupConfigCreate(BaseModel):
    """Schema for creating a follow-up config."""

    tenant_id: str = Field(..., description="Tenant UUID")
    name: str = Field(..., description="Config name (e.g., 'Post-transfer follow-up')")
    trigger_event: str = Field(
        ...,
        description="Event that triggers the follow-up: 'transfer_complete', 'no_response', 'session_idle'",
    )
    delay_minutes: int = Field(
        default=1440,
        description="Delay in minutes before sending follow-up (default: 24h)",
    )
    prompt_template: str = Field(
        ...,
        description="Prompt template for generating the follow-up message. "
        "Supports {contact_name}, {category}, {resumo} placeholders.",
    )
    enabled: bool = Field(default=True, description="Whether this config is active")
    max_followups: int = Field(default=1, description="Max follow-ups per conversation")


class FollowupConfigUpdate(BaseModel):
    """Schema for updating a follow-up config."""

    name: Optional[str] = None
    trigger_event: Optional[str] = None
    delay_minutes: Optional[int] = None
    prompt_template: Optional[str] = None
    enabled: Optional[bool] = None
    max_followups: Optional[int] = None


class FollowupConfigResponse(BaseModel):
    """Schema for follow-up config API responses."""

    id: str
    tenant_id: str
    name: str
    trigger_event: str
    delay_minutes: int
    enabled: bool
    max_followups: int
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True
