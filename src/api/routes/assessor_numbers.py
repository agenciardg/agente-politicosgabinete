"""
Assessor numbers CRUD routes.
Manage assessor phone numbers per tenant.
"""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from src.models.agent import AssessorNumberCreate, AssessorNumberResponse
from src.api.deps import get_current_admin, resolve_tenant_id
from src.services.agent_service import AgentService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", response_model=List[AssessorNumberResponse])
async def list_assessor_numbers(tenant_id: str = Depends(resolve_tenant_id)):
    """List all assessor numbers for the current tenant."""
    service = AgentService()
    return await service.list_assessor_numbers(tenant_id)


@router.post("/", response_model=AssessorNumberResponse, status_code=status.HTTP_201_CREATED)
async def create_assessor_number(
    data: AssessorNumberCreate,
    tenant_id: str = Depends(resolve_tenant_id),
    current_user: dict = Depends(get_current_admin),
):
    """Add a new assessor phone number for the tenant."""
    service = AgentService()
    return await service.add_assessor_number(
        tenant_id, data.agent_id, data.phone_number, data.label
    )


@router.delete("/{number_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_assessor_number(
    number_id: str,
    tenant_id: str = Depends(resolve_tenant_id),
    current_user: dict = Depends(get_current_admin),
):
    """Remove an assessor number."""
    service = AgentService()
    success = await service.delete_assessor_number(number_id)
    if not success:
        raise HTTPException(status_code=404, detail="Assessor number not found")
