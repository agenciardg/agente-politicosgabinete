"""
Pydantic models for webhook requests and responses (multi-tenant).
Extended from original with tenant_slug field.
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, field_validator
from datetime import datetime


class ContactData(BaseModel):
    """Contact information from Helena CRM."""

    phone_number: str = Field(..., description="Phone number in E.164 format")
    name: Optional[str] = Field(None, description="Contact name")
    email: Optional[str] = Field(None, description="Contact email")
    cpf: Optional[str] = Field(None, description="CPF document")
    data_nascimento: Optional[str] = Field(None, description="Birth date")
    endereco: Optional[str] = Field(None, description="Street address")
    bairro: Optional[str] = Field(None, description="Neighborhood")
    cep: Optional[str] = Field(None, description="ZIP code")
    estado: Optional[str] = Field(None, description="State")
    custom_fields: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional custom fields")

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        """Ensure phone number is not empty."""
        if not v or not v.strip():
            raise ValueError("Phone number cannot be empty")
        return v.strip()


class MessageData(BaseModel):
    """Message data from WhatsApp."""

    text: str = Field(..., description="Message text content")
    timestamp: Optional[datetime] = Field(None, description="Message timestamp")
    message_id: Optional[str] = Field(None, description="Unique message ID")
    media_url: Optional[str] = Field(None, description="Media URL if message contains media")
    media_type: Optional[str] = Field(None, description="Media type (image, audio, video, document)")

    @field_validator("text")
    @classmethod
    def validate_text(cls, v: str) -> str:
        """Ensure message text is not empty."""
        if not v or not v.strip():
            raise ValueError("Message text cannot be empty")
        return v.strip()


class WebhookRequest(BaseModel):
    """
    Webhook request from n8n/Helena integration.

    Format received from n8n:
    {
        "mensagem": "Ola",
        "numero": "+5511941204082",
        "sessionID": "0811ea72-a84a-4014-9131-dccbd2a56147",
        "card_id": "cb791a55-d3b7-47f2-b4d2-f196084c6399"
    }

    The tenant_slug comes from the URL path parameter, not the payload.
    """

    mensagem: str = Field(..., description="Message text from user")
    numero: str = Field(..., description="Phone number in E.164 format")
    sessionID: str = Field(..., description="Helena session ID")
    card_id: str = Field(..., description="Helena card ID")

    @field_validator("mensagem")
    @classmethod
    def validate_message(cls, v: str) -> str:
        """Ensure message is not empty."""
        if not v or not v.strip():
            raise ValueError("Message cannot be empty")
        return v.strip()

    @field_validator("numero")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        """Ensure phone number is not empty."""
        if not v or not v.strip():
            raise ValueError("Phone number cannot be empty")
        return v.strip()

    @field_validator("sessionID")
    @classmethod
    def validate_session(cls, v: str) -> str:
        """Ensure session ID is not empty."""
        if not v or not v.strip():
            raise ValueError("Session ID cannot be empty")
        return v.strip()

    class Config:
        populate_by_name = True


class MediaData(BaseModel):
    """Media data for image, video, or document messages."""

    type: str = Field(..., description="Media type: image, video, document")
    url: str = Field(..., description="URL of the media file")
    caption: Optional[str] = Field(None, description="Caption for the media")
    filename: Optional[str] = Field(None, description="Filename for documents")

    @field_validator("type")
    @classmethod
    def validate_media_type(cls, v: str) -> str:
        """Ensure media type is valid."""
        valid_types = ["image", "video", "document"]
        if v not in valid_types:
            raise ValueError(f"Media type must be one of {valid_types}")
        return v


class WebhookResponse(BaseModel):
    """Response to webhook request."""

    success: bool = Field(..., description="Whether the request was processed successfully")
    message: str = Field(..., description="Response message sent to user")
    session_id: str = Field(..., description="Session ID")
    current_phase: str = Field(..., description="Current phase (ETAPA_1, ETAPA_2, ETAPA_3, COMPLETED)")
    data_collected: bool = Field(default=False, description="Whether all required data has been collected")
    category: Optional[str] = Field(None, description="Classified category")
    transferred: bool = Field(default=False, description="Whether the session has been transferred")
    already_sent: bool = Field(default=False, description="Whether the message was already sent via Helena API")
    error: Optional[str] = Field(None, description="Error message if any")
    media: Optional[MediaData] = Field(None, description="Media data if sending image/video/document")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Mensagem processada com sucesso.",
                "session_id": "session_123",
                "current_phase": "ETAPA_1",
                "data_collected": False,
                "category": None,
                "transferred": False,
                "error": None,
                "metadata": {},
            }
        }


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(..., description="Service status")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Current timestamp")
    database: bool = Field(..., description="Database connection status")
    supabase: bool = Field(default=False, description="Supabase connection status")
    version: str = Field(default="2.0.0", description="API version")
    uptime: Optional[float] = Field(None, description="Service uptime in seconds")
