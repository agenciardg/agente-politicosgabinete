"""
Tool: Validate Contact Data (ETAPA 1) - Multi-Tenant
======================================================
Validates if contact has all required fields.
Multi-tenant: accepts required_fields list and Helena client as params.
"""

import logging
from typing import Dict, Any, Optional, List
import httpx
from langchain_core.tools import BaseTool
from pydantic import Field

from src.services.helena_client import HelenaClient

logger = logging.getLogger(__name__)

# Default required fields (can be overridden per tenant)
DEFAULT_REQUIRED_FIELDS = [
    "email", "data-nascimento", "endereco", "bairro",
    "cep", "cidade", "estado", "cpf",
]


class ValidateContactTool(BaseTool):
    """
    Tool to validate contact data completeness.

    Multi-tenant: accepts required_fields and helena_client as config.
    """

    name: str = "validate_contact_data"
    description: str = "Validates if contact has all required fields."

    helena_client: Any = Field(default=None)
    required_fields: List[str] = Field(default_factory=lambda: list(DEFAULT_REQUIRED_FIELDS))

    def _run(self, phone_number: str) -> Dict[str, Any]:
        """Sync execution (not recommended)."""
        import asyncio
        return asyncio.run(self._arun(phone_number))

    async def _arun(self, phone_number: str) -> Dict[str, Any]:
        """
        Async validation of contact data.

        Uses a fresh HelenaClient per call to avoid stale connections.
        """
        logger.info(f"ValidateContact: Looking up phone={phone_number}")

        client = self.helena_client or HelenaClient()
        owns_client = self.helena_client is None

        try:
            try:
                contact = await client.get_contact_by_phone(phone_number)
            except httpx.HTTPStatusError as http_err:
                status_code = http_err.response.status_code
                response_text = ""
                try:
                    response_text = http_err.response.text
                except Exception:
                    pass

                is_not_found = (
                    status_code == 404
                    or (status_code == 500 and "não encontrado" in response_text.lower())
                )

                if is_not_found:
                    return {
                        "status": "incomplete",
                        "missing_fields": list(self.required_fields),
                        "contact_data": {},
                        "contact_name": "",
                        "contact_id": "",
                    }
                raise

            # Check each required field
            missing_fields = []
            cf = contact.get("customFields") or {}

            _helena_key_aliases = {
                "endereco": ["endereco", "endere-o", "endereço"],
            }

            def _get_cf_value(field_name: str) -> Any:
                aliases = _helena_key_aliases.get(field_name, [field_name])
                for alias in aliases:
                    val = cf.get(alias)
                    if val:
                        return val
                return None

            for field in self.required_fields:
                if field == "email":
                    value = contact.get("email")
                else:
                    value = _get_cf_value(field)

                is_empty = not value or (isinstance(value, str) and value.strip().lower() in (
                    "", "-", "—", "n/a", "vazio", "nenhum", "não informado",
                    "não informou", "não possui", "nao informado", "nao informou",
                ))

                if is_empty:
                    missing_fields.append(field)

            status = "complete" if len(missing_fields) == 0 else "incomplete"

            return {
                "status": status,
                "missing_fields": missing_fields,
                "contact_data": contact,
                "contact_name": contact.get("name", ""),
                "contact_id": contact.get("id", ""),
            }

        except Exception as e:
            logger.error(f"ValidateContact: Exception for phone={phone_number}: {e}", exc_info=True)
            return {
                "status": "error",
                "missing_fields": list(self.required_fields),
                "contact_data": None,
                "contact_name": "",
                "contact_id": "",
                "error": str(e),
            }
        finally:
            if owns_client:
                await client.close()


def create_validate_contact_tool(
    helena_client: Optional[HelenaClient] = None,
    required_fields: Optional[List[str]] = None,
) -> ValidateContactTool:
    """Factory to create ValidateContactTool with optional tenant-specific config."""
    kwargs = {}
    if helena_client:
        kwargs["helena_client"] = helena_client
    if required_fields:
        kwargs["required_fields"] = required_fields
    return ValidateContactTool(**kwargs)
