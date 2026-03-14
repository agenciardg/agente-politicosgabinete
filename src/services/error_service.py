"""
Error Service
==============
Logs errors to Supabase for admin visibility.
Table: agentpolitico_error_logs (Supabase REST client).
"""

import logging
from typing import Optional, Dict, Any, List

from src.config.database import get_supabase_client

logger = logging.getLogger(__name__)


class ErrorService:
    """Service for logging and querying tenant errors."""

    TABLE = "agentpolitico_error_logs"

    async def log_error(
        self,
        tenant_id: str,
        error_type: str,
        error_message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log an error to Supabase for admin visibility.

        Args:
            tenant_id: UUID of the tenant.
            error_type: Category (e.g. 'followup_send_failed', 'helena_api_error').
            error_message: Human-readable description.
            context: Optional JSON-serialisable dict with extra details.
        """
        try:
            supabase = get_supabase_client()
            data = {
                "tenant_id": tenant_id,
                "error_type": error_type,
                "error_message": error_message,
                "context": context or {},
            }
            supabase.table(self.TABLE).insert(data).execute()
            logger.info("Error logged for tenant %s: %s", tenant_id, error_type)
        except Exception as e:
            # Last-resort: at least make sure the error shows in logs
            logger.error(
                "Failed to persist error log for tenant %s: %s (original: %s / %s)",
                tenant_id,
                e,
                error_type,
                error_message,
            )

    async def get_errors(
        self,
        tenant_id: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get recent errors for a tenant.

        Args:
            tenant_id: UUID of the tenant.
            limit: Maximum number of rows to return.

        Returns:
            List of error log dicts ordered by created_at DESC.
        """
        supabase = get_supabase_client()
        result = (
            supabase.table(self.TABLE)
            .select("id,tenant_id,error_type,error_message,context,created_at")
            .eq("tenant_id", tenant_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data or []
