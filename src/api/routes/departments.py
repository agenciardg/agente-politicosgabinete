"""
Department routes.
List departments synced from Helena CRM per tenant.
"""

import logging
from typing import List

from fastapi import APIRouter, Depends

from src.api.deps import resolve_tenant_id
from src.config.database import get_supabase_client

logger = logging.getLogger(__name__)

router = APIRouter()

DEPARTMENTS_TABLE = "agentpolitico_tenant_departments"


@router.get("/")
async def list_departments(tenant_id: str = Depends(resolve_tenant_id)):
    """List all departments for the current tenant."""
    sb = get_supabase_client()
    result = (
        sb.table(DEPARTMENTS_TABLE)
        .select("*")
        .eq("tenant_id", tenant_id)
        .execute()
    )
    return result.data or []
