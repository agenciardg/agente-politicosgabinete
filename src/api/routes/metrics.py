"""
Metrics endpoints.
Expose conversation and performance metrics per tenant.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query

from src.models.metrics import MetricsSummary
from src.api.deps import resolve_tenant_id
from src.services.metrics_service import MetricsService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/summary", response_model=MetricsSummary)
async def get_metrics_summary(
    tenant_id: str = Depends(resolve_tenant_id),
    period: str = Query(default="7d", description="Period: 24h, 7d, 30d"),
):
    """Get summary metrics for the tenant."""
    service = MetricsService()
    return await service.get_summary(tenant_id, period)


@router.get("/daily")
async def get_daily_breakdown(
    tenant_id: str = Depends(resolve_tenant_id),
    period: str = Query(default="7d"),
):
    """Get daily event breakdown."""
    service = MetricsService()
    breakdown = await service.get_daily_breakdown(tenant_id, period)
    return {"daily": breakdown, "period": period}


@router.get("/conversations")
async def get_conversation_metrics(
    tenant_id: str = Depends(resolve_tenant_id),
    period: str = Query(default="7d"),
    category: Optional[str] = Query(default=None),
):
    """Get conversation list with optional category filter."""
    service = MetricsService()
    conversations = await service.get_conversation_list(tenant_id, period, category)
    return {"conversations": conversations, "total": len(conversations), "period": period}
