"""
Metrics Pydantic models.
Data structures for metrics endpoints.
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class MetricsSummary(BaseModel):
    """Summary metrics for a tenant."""

    total_conversations: int = Field(default=0, description="Total conversations in period")
    total_transfers: int = Field(default=0, description="Total successful transfers")
    avg_response_time_seconds: float = Field(default=0.0, description="Average response time")
    categories_breakdown: Dict[str, int] = Field(
        default_factory=dict,
        description="Conversation count per category",
    )
    period: str = Field(default="7d", description="Metrics period")


class MetricsResponse(BaseModel):
    """Detailed metrics response."""

    tenant_id: str
    summary: MetricsSummary
    daily_breakdown: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Daily conversation counts",
    )
