"""
Agent CRUD routes + followup prompt management.
Manage agent configurations and prompts per tenant.
"""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from src.models.agent import (
    AgentCreate,
    AgentUpdate,
    AgentResponse,
    FollowupPromptResponse,
    FollowupPromptUpsert,
)
from src.api.deps import get_current_admin, resolve_tenant_id
from src.services.agent_service import AgentService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", response_model=List[AgentResponse])
async def list_agents(tenant_id: str = Depends(resolve_tenant_id)):
    """List all agents for the current tenant."""
    service = AgentService()
    return await service.list_by_tenant(tenant_id)


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: str,
    tenant_id: str = Depends(resolve_tenant_id),
):
    """Get a specific agent."""
    service = AgentService()
    agent = await service.get_by_id(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    if agent.get("tenant_id") != tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return agent


@router.post("/", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    data: AgentCreate,
    tenant_id: str = Depends(resolve_tenant_id),
    current_user: dict = Depends(get_current_admin),
):
    """Create a new agent for the tenant."""
    data.tenant_id = tenant_id
    service = AgentService()
    try:
        return await service.create(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: str,
    data: AgentUpdate,
    tenant_id: str = Depends(resolve_tenant_id),
    current_user: dict = Depends(get_current_admin),
):
    """Update an agent config."""
    service = AgentService()
    existing = await service.get_by_id(agent_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Agent not found")
    if existing.get("tenant_id") != tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")
    result = await service.update(agent_id, data)
    if not result:
        raise HTTPException(status_code=404, detail="Agent not found")
    return result


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: str,
    tenant_id: str = Depends(resolve_tenant_id),
    current_user: dict = Depends(get_current_admin),
):
    """Delete an agent."""
    service = AgentService()
    existing = await service.get_by_id(agent_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Agent not found")
    if existing.get("tenant_id") != tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")
    success = await service.delete(agent_id)
    if not success:
        raise HTTPException(status_code=404, detail="Agent not found")


# ---- Followup Prompts ----

@router.get("/{agent_id}/followup-prompts", response_model=List[FollowupPromptResponse])
async def get_followup_prompts(
    agent_id: str,
    tenant_id: str = Depends(resolve_tenant_id),
):
    """Get followup prompts for an agent."""
    service = AgentService()
    existing = await service.get_by_id(agent_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Agent not found")
    if existing.get("tenant_id") != tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return await service.get_followup_prompts(agent_id)


@router.put("/{agent_id}/followup-prompts/{followup_number}", response_model=FollowupPromptResponse)
async def upsert_followup_prompt(
    agent_id: str,
    followup_number: int,
    data: FollowupPromptUpsert,
    tenant_id: str = Depends(resolve_tenant_id),
    current_user: dict = Depends(get_current_admin),
):
    """Upsert a followup prompt for an agent (followup_number: 1, 2, or 3)."""
    if followup_number not in (1, 2, 3):
        raise HTTPException(status_code=400, detail="followup_number must be 1, 2, or 3")
    service = AgentService()
    existing = await service.get_by_id(agent_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Agent not found")
    if existing.get("tenant_id") != tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return await service.upsert_followup_prompt(
        agent_id, followup_number, data.prompt_template, data.active or True
    )
