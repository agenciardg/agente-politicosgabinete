"""
Memory Service
===============
LangGraph memory/checkpoint cleanup for multi-tenant.
Manages checkpoint lifecycle per tenant.

Checkpoint data lives in PostgreSQL dedicated (get_postgres_pool).
"""

import logging
from typing import Optional

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
