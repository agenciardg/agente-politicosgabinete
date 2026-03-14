"""
Tool: Transfer and Route (ETAPA 3) - Multi-Tenant
===================================================
Transfers session and creates card in the correct panel.
Multi-tenant: accepts dynamic panel config instead of hardcoded CATEGORIAS.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from langchain_core.tools import BaseTool
from pydantic import Field
import pytz

from src.services.helena_client import HelenaClient

logger = logging.getLogger(__name__)

# Default card due hours
DEFAULT_CARD_DUE_HOURS = 24


class TransferRouteTool(BaseTool):
    """
    Tool to transfer session and route card.

    Multi-tenant: accepts panel_config dict instead of hardcoded CATEGORIAS.
    panel_config format:
    {
        "category_key": {
            "pipe": "uuid", "stepid": "uuid", "equipe": "uuid", "nome": "Display Name"
        }
    }
    """

    name: str = "transfer_and_route"
    description: str = "Transfers chat session and creates card in the correct panel."

    helena_client: Any = Field(default=None)
    panel_config: Dict[str, Dict[str, str]] = Field(default_factory=dict)
    card_due_hours: int = Field(default=DEFAULT_CARD_DUE_HOURS)

    def _run(self, session_id: str, card_id: str, category: str,
             classification: Dict[str, Any], contact_data: Dict[str, Any],
             phone_number: str = "") -> Dict[str, Any]:
        """Sync execution (not recommended)."""
        import asyncio
        return asyncio.run(
            self._arun(session_id, card_id, category, classification, contact_data, phone_number)
        )

    async def _arun(
        self,
        session_id: str,
        card_id: str,
        category: str,
        classification: Dict[str, Any],
        contact_data: Dict[str, Any],
        phone_number: str = "",
    ) -> Dict[str, Any]:
        """
        Execute the full transfer flow.

        1. Transfer chat session to department
        2. Fetch panel custom fields
        3. Duplicate card to destination panel
        4. Update card with classification data
        5. Add tags to contact
        """
        client = self.helena_client or HelenaClient()
        owns_client = self.helena_client is None

        try:
            # Get category config
            if category not in self.panel_config:
                raise ValueError(f"Invalid category: {category}")

            config = self.panel_config[category]
            panel_id = config["pipe"]
            step_id = config["stepid"]
            department_id = config["equipe"]

            # 1. Transfer session
            await client.transfer_session(
                session_id=session_id,
                department_id=department_id,
            )

            # 2. Get panel custom fields
            custom_fields_list = await client.get_panel_custom_fields(panel_id=panel_id)

            # 3. Build field mapping
            field_mapping = {cf["name"]: cf["key"] for cf in custom_fields_list}

            # 4. Duplicate card
            new_card = await client.duplicate_card(
                card_id=card_id,
                target_step_id=step_id,
                archive_original=True,
            )
            new_card_id = new_card.get("id")
            if not new_card_id:
                raise ValueError("Duplicated card did not return ID")

            # 5. Prepare custom fields
            custom_fields_data = {}
            cf = contact_data.get("customFields", {})
            field_map_config = {
                "Solicitacao": classification.get("tipo_solicitacao", ""),
                "Data Cadastro": cf.get("data-cadastro", ""),
                "Nome Completo": contact_data.get("name", ""),
                "Descricao Manifestacao": classification.get("resumo_longo", ""),
                "Manifestacao": classification.get("resumo_curto", ""),
                "CPF": cf.get("cpf", ""),
                "Data Nascimento": cf.get("data-nascimento", ""),
                "Email": contact_data.get("email", ""),
                "CEP": cf.get("cep", ""),
                "Endereco": cf.get("endereco", ""),
                "Bairro": cf.get("bairro", ""),
                "Cidade": cf.get("cidade", ""),
                "Estado": cf.get("estado", ""),
            }

            for field_name, field_value in field_map_config.items():
                if field_name in field_mapping and field_value:
                    custom_fields_data[field_mapping[field_name]] = field_value

            # 6. Due date
            tz = pytz.timezone("America/Sao_Paulo")
            due_date = datetime.now(tz) + timedelta(hours=self.card_due_hours)

            # 7. Tags
            category_tag = config.get("nome", "")
            urgency_tag = classification.get("urgencia", "media")
            tag_names = [t for t in [category_tag, urgency_tag, "whatsapp"] if t]

            # 8. Update card
            await client.update_card(
                card_id=new_card_id,
                title=contact_data.get("name", ""),
                description=classification.get("descricao", ""),
                contact_ids=[contact_data.get("id")],
                due_date=due_date,
                tag_names=tag_names,
                custom_fields=custom_fields_data,
            )

            # 9. Add tag to contact
            phone = phone_number or contact_data.get("phoneNumber", "")
            if phone and category_tag:
                await client.add_contact_tags(phone=phone, tag_names=[category_tag])

            return {
                "status": "success",
                "new_card_id": new_card_id,
                "department_id": department_id,
                "panel_id": panel_id,
                "step_id": step_id,
                "category": category,
            }

        except Exception as e:
            logger.error(f"Transfer failed for category={category}: {e}", exc_info=True)
            return {
                "status": "failed",
                "new_card_id": None,
                "department_id": None,
                "panel_id": None,
                "step_id": None,
                "category": category,
                "error": str(e),
            }
        finally:
            if owns_client:
                await client.close()


def create_transfer_route_tool(
    helena_client: Optional[HelenaClient] = None,
    panel_config: Optional[Dict[str, Dict[str, str]]] = None,
    card_due_hours: int = DEFAULT_CARD_DUE_HOURS,
) -> TransferRouteTool:
    """Factory to create TransferRouteTool with optional tenant-specific config."""
    kwargs = {"card_due_hours": card_due_hours}
    if helena_client:
        kwargs["helena_client"] = helena_client
    if panel_config:
        kwargs["panel_config"] = panel_config
    return TransferRouteTool(**kwargs)
