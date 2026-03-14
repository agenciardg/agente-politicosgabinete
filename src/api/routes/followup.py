"""
Follow-up routes.
Manage follow-up prompt templates (admin) and queue visibility.
"""

import logging
from typing import List, Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.api.deps import get_current_admin, resolve_tenant_id
from src.config.database import get_supabase_client, get_postgres_pool
from src.services.followup_service import FollowupService

logger = logging.getLogger(__name__)

SP_TZ = ZoneInfo("America/Sao_Paulo")

router = APIRouter()

PROMPTS_TABLE = "agentpolitico_tenant_agent_followup_prompts"
QUEUE_TABLE = "agentpolitico_follow_up_queue"


# ------------------------------------------------------------------
# Pydantic schemas
# ------------------------------------------------------------------

class FollowupPromptResponse(BaseModel):
    id: str
    agent_id: str
    followup_number: int
    prompt_template: str
    active: bool

    class Config:
        from_attributes = True


class FollowupPromptUpsert(BaseModel):
    prompt_template: str = Field(..., min_length=1)
    active: bool = Field(default=True)


class FollowupQueueItem(BaseModel):
    id: str
    tenant_id: str
    session_id: str
    phone_number: str
    agent_type: str
    follow_up_number: int
    scheduled_at: str
    status: str
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


# ------------------------------------------------------------------
# Prompt template endpoints
# ------------------------------------------------------------------

@router.get("/prompts/{agent_id}", response_model=List[FollowupPromptResponse])
async def list_followup_prompts(
    agent_id: str,
    tenant_id: str = Depends(resolve_tenant_id),
):
    """List the 3 follow-up prompts for an agent."""
    sb = get_supabase_client()

    # Verify agent belongs to tenant
    agent_check = (
        sb.table("agentpolitico_tenant_agents")
        .select("id")
        .eq("id", agent_id)
        .eq("tenant_id", tenant_id)
        .execute()
    )
    if not agent_check.data:
        return []

    result = (
        sb.table(PROMPTS_TABLE)
        .select("id, agent_id, followup_number, prompt_template, active")
        .eq("agent_id", agent_id)
        .order("followup_number")
        .execute()
    )
    return [
        FollowupPromptResponse(
            id=str(r["id"]),
            agent_id=str(r["agent_id"]),
            followup_number=r["followup_number"],
            prompt_template=r["prompt_template"],
            active=r["active"],
        )
        for r in result.data
    ]


@router.put("/prompts/{agent_id}/{followup_number}", response_model=FollowupPromptResponse)
async def upsert_followup_prompt(
    agent_id: str,
    followup_number: int,
    data: FollowupPromptUpsert,
    tenant_id: str = Depends(resolve_tenant_id),
    current_user: dict = Depends(get_current_admin),
):
    """Upsert a follow-up prompt template for a specific agent and number (1-3)."""
    if followup_number not in (1, 2, 3):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="followup_number must be 1, 2, or 3",
        )

    sb = get_supabase_client()

    # Verify the agent belongs to the tenant
    agent_check = (
        sb.table("agentpolitico_tenant_agents")
        .select("id")
        .eq("id", agent_id)
        .eq("tenant_id", tenant_id)
        .execute()
    )
    if not agent_check.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found for this tenant",
        )

    # Upsert: check if exists, then insert or update
    existing = (
        sb.table(PROMPTS_TABLE)
        .select("id")
        .eq("agent_id", agent_id)
        .eq("followup_number", followup_number)
        .execute()
    )

    upsert_data = {
        "agent_id": agent_id,
        "followup_number": followup_number,
        "prompt_template": data.prompt_template,
        "active": data.active,
    }

    if existing.data:
        result = (
            sb.table(PROMPTS_TABLE)
            .update({"prompt_template": data.prompt_template, "active": data.active})
            .eq("agent_id", agent_id)
            .eq("followup_number", followup_number)
            .execute()
        )
    else:
        result = sb.table(PROMPTS_TABLE).insert(upsert_data).execute()

    row = result.data[0]

    return FollowupPromptResponse(
        id=str(row["id"]),
        agent_id=str(row["agent_id"]),
        followup_number=row["followup_number"],
        prompt_template=row["prompt_template"],
        active=row["active"],
    )


# ------------------------------------------------------------------
# Queue / processing endpoints
# ------------------------------------------------------------------

@router.post("/process")
async def trigger_followup_processing(
    tenant_id: str = Depends(resolve_tenant_id),
    current_user: dict = Depends(get_current_admin),
):
    """Manually trigger follow-up processing (admin tool)."""
    followup_service = FollowupService()
    result = await followup_service.process_pending_followups()
    return {"success": True, "result": result}


@router.get("/queue", response_model=List[FollowupQueueItem])
async def list_followup_queue(
    tenant_id: str = Depends(resolve_tenant_id),
    status_filter: Optional[str] = None,
    limit: int = 50,
):
    """List follow-up queue items for the tenant (admin view)."""
    pool = await get_postgres_pool()
    async with pool.acquire() as conn:
        if status_filter:
            rows = await conn.fetch(
                f"""
                SELECT id, tenant_id, session_id, phone_number, agent_type,
                       follow_up_number, scheduled_at, status, created_at
                FROM {QUEUE_TABLE}
                WHERE tenant_id = $1 AND status = $2
                ORDER BY scheduled_at DESC
                LIMIT $3
                """,
                tenant_id,
                status_filter,
                limit,
            )
        else:
            rows = await conn.fetch(
                f"""
                SELECT id, tenant_id, session_id, phone_number, agent_type,
                       follow_up_number, scheduled_at, status, created_at
                FROM {QUEUE_TABLE}
                WHERE tenant_id = $1
                ORDER BY scheduled_at DESC
                LIMIT $2
                """,
                tenant_id,
                limit,
            )

    return [
        FollowupQueueItem(
            id=str(r["id"]),
            tenant_id=str(r["tenant_id"]),
            session_id=r["session_id"],
            phone_number=r["phone_number"],
            agent_type=r["agent_type"],
            follow_up_number=r["follow_up_number"],
            scheduled_at=r["scheduled_at"].isoformat() if r["scheduled_at"] else "",
            status=r["status"],
            created_at=r["created_at"].isoformat() if r["created_at"] else None,
        )
        for r in rows
    ]
