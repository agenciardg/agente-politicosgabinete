"""
Sync Routes
============
Endpoints para disparar e consultar sincronizacao
de dados do Helena CRM para o tenant.
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

from src.config.database import get_supabase_client
from src.services.sync_service import HelenaSyncService

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class SyncResponse(BaseModel):
    """Resposta do endpoint de sync."""
    panels: int = 0
    departments: int = 0
    contact_fields: int = 0
    synced_at: Optional[str] = None
    duration_seconds: Optional[float] = None
    status: str = "pending"
    errors: List[str] = []


class SyncStatusResponse(BaseModel):
    """Resposta do endpoint de status."""
    tenant_id: str
    last_sync_at: Optional[str] = None
    status: str = "never"


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

def _get_tenant(tenant_id: str) -> Dict[str, Any]:
    """Valida que o tenant existe e retorna seus dados."""
    supabase = get_supabase_client()
    resp = supabase.table("agentpolitico_tenants").select("*").eq(
        "id", tenant_id
    ).limit(1).execute()

    if not resp.data:
        raise HTTPException(status_code=404, detail=f"Tenant {tenant_id} nao encontrado")

    tenant = resp.data[0]

    if not tenant.get("active", False):
        raise HTTPException(status_code=403, detail=f"Tenant {tenant_id} nao esta ativo")

    if not tenant.get("helena_api_token"):
        raise HTTPException(
            status_code=400,
            detail=f"Tenant {tenant_id} nao possui helena_api_token configurado",
        )

    return tenant


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/tenants/{tenant_id}/sync", response_model=SyncResponse)
async def trigger_sync(
    tenant_id: str,
    background_tasks: BackgroundTasks,
) -> SyncResponse:
    """Dispara sincronizacao completa dos dados do Helena CRM para o tenant."""
    tenant = _get_tenant(tenant_id)
    helena_token: str = tenant["helena_api_token"]

    sync_service = HelenaSyncService()
    try:
        result = await sync_service.sync_all(
            tenant_id=tenant_id,
            helena_token=helena_token,
        )
    except Exception as exc:
        logger.exception("Sync failed for tenant %s", tenant_id)
        raise HTTPException(
            status_code=500,
            detail=f"Sync failed: {exc}",
        )
    finally:
        await sync_service.close()

    return SyncResponse(
        panels=result["panels"],
        departments=result["departments"],
        contact_fields=result["contact_fields"],
        synced_at=result["synced_at"],
        duration_seconds=result["duration_seconds"],
        status=result["status"],
        errors=result["errors"],
    )


@router.get("/tenants/{tenant_id}/sync/status", response_model=SyncStatusResponse)
async def get_sync_status(tenant_id: str) -> SyncStatusResponse:
    """Retorna timestamp da ultima sincronizacao do tenant."""
    _get_tenant(tenant_id)  # validates tenant exists and is active

    # Check latest synced_at from panels table as proxy
    supabase = get_supabase_client()
    resp = supabase.table("agentpolitico_tenant_panels").select("synced_at").eq(
        "tenant_id", tenant_id
    ).order("synced_at", desc=True).limit(1).execute()

    if not resp.data or not resp.data[0].get("synced_at"):
        return SyncStatusResponse(
            tenant_id=tenant_id,
            last_sync_at=None,
            status="never",
        )

    return SyncStatusResponse(
        tenant_id=tenant_id,
        last_sync_at=str(resp.data[0]["synced_at"]),
        status="synced",
    )
