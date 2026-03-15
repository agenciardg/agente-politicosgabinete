"""
Memory Service
===============
LangGraph memory/checkpoint cleanup + long-term memory for multi-tenant.
Manages checkpoint lifecycle and conversation history per tenant.

Checkpoint data and memory tables live in PostgreSQL dedicated (get_postgres_pool).

Tables:
- memory_agentepolitico: Active memory (1 row per citizen/tenant, upserted)
- memory_agentepolitico_history: Permanent log of all completed interactions
"""

import json
import logging
from typing import Optional, Dict, Any, List

from src.config.database import get_postgres_pool

logger = logging.getLogger(__name__)


class MemoryService:
    """Service for LangGraph memory/checkpoint management."""

    async def cleanup_session_memory(self, tenant_id: str, session_id: str) -> bool:
        """Clean up all LangGraph data for a session.

        Called after: transfer complete OR follow-up 3 complete.

        Deletes from PostgreSQL dedicated:
        - checkpoints WHERE thread_id = session_id
        - checkpoint_writes WHERE thread_id = session_id
        - checkpoint_blobs WHERE thread_id = session_id

        Args:
            tenant_id: The tenant UUID (for logging).
            session_id: The Helena session ID used as LangGraph thread_id.

        Returns:
            True if cleanup succeeded.
        """
        try:
            pool = await get_postgres_pool()
            async with pool.acquire() as conn:
                await conn.execute(
                    "DELETE FROM checkpoint_writes WHERE thread_id = $1",
                    session_id,
                )
                await conn.execute(
                    "DELETE FROM checkpoint_blobs WHERE thread_id = $1",
                    session_id,
                )
                await conn.execute(
                    "DELETE FROM checkpoints WHERE thread_id = $1",
                    session_id,
                )

            logger.info(
                "Checkpoints cleaned for session %s (tenant %s)",
                session_id,
                tenant_id,
            )
            return True
        except Exception as e:
            logger.error(
                "Failed to cleanup checkpoints for session %s (tenant %s): %s",
                session_id,
                tenant_id,
                e,
            )
            return False

    async def cleanup_thread(self, thread_id: str) -> bool:
        """Clean up checkpoints for a specific thread (session).

        Legacy helper -- delegates to cleanup_session_memory with empty tenant_id.
        """
        return await self.cleanup_session_memory(tenant_id="", session_id=thread_id)

    async def cleanup_tenant(self, tenant_id: str) -> int:
        """Clean up ALL checkpoints for a tenant.

        Used when resetting a tenant or during maintenance.

        Args:
            tenant_id: The tenant UUID.

        Returns:
            Number of threads cleaned.
        """
        try:
            pool = await get_postgres_pool()
            async with pool.acquire() as conn:
                result = await conn.execute(
                    "DELETE FROM checkpoints WHERE thread_id LIKE $1",
                    f"tenant_{tenant_id}_%",
                )
                logger.info("Cleaned checkpoints for tenant %s", tenant_id)
                return 0  # TODO: parse result for count
        except Exception as e:
            logger.error("Failed to cleanup tenant %s checkpoints: %s", tenant_id, e)
            return 0

    async def get_active_threads(self, tenant_id: str) -> int:
        """Count active checkpoint threads for a tenant.

        Returns:
            Number of active threads.
        """
        try:
            pool = await get_postgres_pool()
            async with pool.acquire() as conn:
                count = await conn.fetchval(
                    "SELECT COUNT(DISTINCT thread_id) FROM checkpoints WHERE thread_id LIKE $1",
                    f"tenant_{tenant_id}_%",
                )
                return count or 0
        except Exception as e:
            logger.error("Failed to count threads for %s: %s", tenant_id, e)
            return 0

    # ==========================================================
    # LONG-TERM MEMORY: memory_agentepolitico + _history
    # ==========================================================

    async def save_interaction_memory(
        self,
        tenant_id: str,
        phone_number: str,
        contact_name: str,
        session_id: str,
        classification: Dict[str, Any],
        agent_type: str = "principal",
        transferred_to_department: str = "",
        new_card_id: str = "",
    ) -> bool:
        """Save completed interaction to both memory tables.

        Called after successful transfer in transfer_node.

        1. INSERT into memory_agentepolitico_history (permanent log)
        2. UPSERT into memory_agentepolitico (active memory for LLM context)

        Args:
            tenant_id: Tenant UUID.
            phone_number: Citizen phone number.
            contact_name: Citizen name.
            session_id: Helena session ID.
            classification: Full classification dict from classify_demand_node.
            agent_type: "principal" or "assessor".
            transferred_to_department: Department UUID transferred to.
            new_card_id: New card UUID created.

        Returns:
            True if both saves succeeded.
        """
        category = classification.get("equipe", "")
        urgency = classification.get("urgencia", "")
        resumo_curto = classification.get("resumo_curto", "")
        resumo_longo = classification.get("resumo_longo", "")

        try:
            pool = await get_postgres_pool()
            async with pool.acquire() as conn:
                # 1. INSERT into history (permanent log)
                await conn.execute(
                    """INSERT INTO memory_agentepolitico_history
                    (tenant_id, phone_number, contact_name, session_id,
                     category, urgency, resumo_curto, resumo_longo,
                     classification, transferred_to_department,
                     new_card_id, agent_type)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                    """,
                    tenant_id, phone_number, contact_name, session_id,
                    category, urgency, resumo_curto, resumo_longo,
                    json.dumps(classification), transferred_to_department,
                    new_card_id, agent_type,
                )

                # 2. UPSERT into active memory
                await conn.execute(
                    """INSERT INTO memory_agentepolitico
                    (tenant_id, phone_number, contact_name, content,
                     last_category, last_urgency, total_contacts, metadata,
                     updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, 1, $7, NOW())
                    ON CONFLICT (tenant_id, phone_number) DO UPDATE SET
                        contact_name = $3,
                        content = $4,
                        last_category = $5,
                        last_urgency = $6,
                        total_contacts = memory_agentepolitico.total_contacts + 1,
                        metadata = $7,
                        updated_at = NOW()
                    """,
                    tenant_id, phone_number, contact_name,
                    resumo_curto or resumo_longo,
                    category, urgency,
                    json.dumps({
                        "last_session_id": session_id,
                        "last_agent_type": agent_type,
                        "last_department": transferred_to_department,
                    }),
                )

            logger.info(
                "Memory saved for %s (tenant=%s): category=%s, urgency=%s",
                phone_number, tenant_id, category, urgency,
            )
            return True

        except Exception as e:
            logger.error(
                "Failed to save memory for %s (tenant=%s): %s",
                phone_number, tenant_id, e,
                exc_info=True,
            )
            return False

    async def get_citizen_memory(
        self,
        tenant_id: str,
        phone_number: str,
    ) -> Optional[Dict[str, Any]]:
        """Get active memory for a citizen in a tenant.

        Used by agent_node to inject conversation context.

        Returns:
            Dict with memory data or None if no history.
        """
        try:
            pool = await get_postgres_pool()
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    """SELECT contact_name, content, last_category,
                              last_urgency, total_contacts, metadata,
                              updated_at
                    FROM memory_agentepolitico
                    WHERE tenant_id = $1 AND phone_number = $2
                    """,
                    tenant_id, phone_number,
                )

            if not row:
                return None

            return {
                "contact_name": row["contact_name"],
                "content": row["content"],
                "last_category": row["last_category"],
                "last_urgency": row["last_urgency"],
                "total_contacts": row["total_contacts"],
                "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
                "updated_at": str(row["updated_at"]),
            }

        except Exception as e:
            logger.error(
                "Failed to get memory for %s (tenant=%s): %s",
                phone_number, tenant_id, e,
            )
            return None

    async def get_citizen_history(
        self,
        tenant_id: str,
        phone_number: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Get full interaction history for a citizen.

        Used for dashboards/reports or detailed LLM context.

        Returns:
            List of interaction records, newest first.
        """
        try:
            pool = await get_postgres_pool()
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    """SELECT category, urgency, resumo_curto,
                              resumo_longo, agent_type, created_at
                    FROM memory_agentepolitico_history
                    WHERE tenant_id = $1 AND phone_number = $2
                    ORDER BY created_at DESC
                    LIMIT $3
                    """,
                    tenant_id, phone_number, limit,
                )

            return [
                {
                    "category": r["category"],
                    "urgency": r["urgency"],
                    "resumo_curto": r["resumo_curto"],
                    "resumo_longo": r["resumo_longo"],
                    "agent_type": r["agent_type"],
                    "created_at": str(r["created_at"]),
                }
                for r in rows
            ]

        except Exception as e:
            logger.error(
                "Failed to get history for %s (tenant=%s): %s",
                phone_number, tenant_id, e,
            )
            return []
