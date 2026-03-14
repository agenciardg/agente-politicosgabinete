"""
Tool: Classify Demand (ETAPA 2) - Multi-Tenant
================================================
Classifies citizen demand using LLM.
Multi-tenant: accepts custom categories and LLM instance.
"""

import json
import logging
from typing import Dict, Any, List, Optional
from langchain_core.tools import BaseTool
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from pydantic import Field

from src.services.grok_client import get_grok_llm
from src.agent.prompts import format_classification_prompt

logger = logging.getLogger(__name__)

# Default valid categories
DEFAULT_CATEGORIES = [
    "saude", "zeladoria", "educacao", "habitacao", "seguranca",
    "servico_social", "regularizacao", "juridico", "legislativo",
    "orienta_ong", "espaco_publico", "atendimento_geral",
]

URGENCY_LEVELS = ["baixa", "media", "alta"]


class ClassifyDemandTool(BaseTool):
    """
    Tool to classify citizen demand.

    Multi-tenant: accepts custom categories and LLM.
    """

    name: str = "classify_demand"
    description: str = "Classifies the citizen demand into a specific category."

    llm: Any = Field(default_factory=get_grok_llm)
    valid_categories: List[str] = Field(default_factory=lambda: list(DEFAULT_CATEGORIES))
    categories_descriptions: Optional[Dict[str, str]] = Field(default=None)

    def _format_conversation(self, messages: List[BaseMessage]) -> str:
        """Format message list for the prompt."""
        formatted = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                formatted.append(f"Cidadao: {msg.content}")
            elif isinstance(msg, AIMessage):
                formatted.append(f"Assistente: {msg.content}")
        return "\n".join(formatted)

    def _run(self, conversation_history: List[BaseMessage]) -> Dict[str, Any]:
        """Sync execution (not recommended)."""
        import asyncio
        return asyncio.run(self._arun(conversation_history))

    async def _arun(self, conversation_history: List[BaseMessage]) -> Dict[str, Any]:
        """Async classification."""
        try:
            conversation_text = self._format_conversation(conversation_history)
            prompt = format_classification_prompt(
                conversation_text,
                categories=self.categories_descriptions,
            )

            response = await self.llm.ainvoke(prompt)
            content = response.content

            # Parse JSON from response
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0].strip()
            else:
                json_str = content.strip()

            classification = json.loads(json_str)

            # Validate category
            if classification.get("equipe") not in self.valid_categories:
                classification["equipe"] = "atendimento_geral"

            # Validate urgency
            if classification.get("urgencia") not in URGENCY_LEVELS:
                classification["urgencia"] = "media"

            # Ensure required fields
            for field in ["equipe", "solicitacao", "tipo_solicitacao",
                          "descricao", "resumo_longo", "resumo_curto", "urgencia"]:
                if field not in classification:
                    classification[field] = ""

            return classification

        except json.JSONDecodeError as e:
            return {
                "equipe": "atendimento_geral",
                "solicitacao": "Atendimento Geral",
                "tipo_solicitacao": "Solicitacao Geral",
                "descricao": "Demanda a ser analisada pela equipe de atendimento geral.",
                "resumo_longo": "Demanda direcionada para atendimento geral.",
                "resumo_curto": "Demanda geral",
                "urgencia": "media",
                "error": f"JSON parse error: {str(e)}",
            }

        except Exception as e:
            return {
                "equipe": "atendimento_geral",
                "solicitacao": "Atendimento Geral",
                "tipo_solicitacao": "Erro na Classificacao",
                "descricao": f"Erro durante classificacao: {str(e)}",
                "resumo_longo": "Erro ao processar. Encaminhada para atendimento geral.",
                "resumo_curto": "Erro na classificacao",
                "urgencia": "media",
                "error": str(e),
            }


def create_classify_demand_tool(
    llm=None,
    valid_categories: Optional[List[str]] = None,
    categories_descriptions: Optional[Dict[str, str]] = None,
) -> ClassifyDemandTool:
    """Factory to create ClassifyDemandTool with optional tenant-specific config."""
    kwargs = {}
    if llm:
        kwargs["llm"] = llm
    if valid_categories:
        kwargs["valid_categories"] = valid_categories
    if categories_descriptions:
        kwargs["categories_descriptions"] = categories_descriptions
    return ClassifyDemandTool(**kwargs)
