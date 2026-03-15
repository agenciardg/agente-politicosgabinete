"""
LangGraph - Multi-Tenant Agent Graph
======================================
Builds the StateGraph with dynamic tenant configuration.
Uses per-tenant checkpoint namespacing.
"""

import logging
from typing import Optional, Dict, Any
from psycopg_pool import AsyncConnectionPool
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from src.agent.state import AgentState
from src.agent.nodes import (
    validate_data_node,
    agent_node,
    post_process_node,
    post_process_router,
    classify_demand_node,
    classify_router,
    transfer_node,
    router_node,
    should_continue_node,
)
from src.config.settings import settings

logger = logging.getLogger(__name__)

# Singleton global for pool and checkpointer
_pool: Optional[AsyncConnectionPool] = None
_checkpointer: Optional[AsyncPostgresSaver] = None


async def _get_checkpointer() -> AsyncPostgresSaver:
    """Returns async checkpointer singleton."""
    global _pool, _checkpointer

    if _checkpointer is None:
        db_url = settings.postgres_uri

        _pool = AsyncConnectionPool(
            conninfo=db_url,
            min_size=2,
            max_size=10,
            open=False,
            check=AsyncConnectionPool.check_connection,
            kwargs={
                "autocommit": True,
                "prepare_threshold": 0,
            },
        )
        await _pool.open()
        logger.info("AsyncConnectionPool opened for checkpointer")

        _checkpointer = AsyncPostgresSaver(_pool)
        await _checkpointer.setup()
        logger.info("AsyncPostgresSaver initialized and tables verified")

    return _checkpointer


def get_pool() -> Optional[AsyncConnectionPool]:
    """Return the checkpointer connection pool (or None if not initialized)."""
    return _pool


async def close_checkpointer():
    """Close checkpointer pool on shutdown."""
    global _pool, _checkpointer
    if _pool is not None:
        await _pool.close()
        _pool = None
        _checkpointer = None
        logger.info("AsyncConnectionPool closed")


async def create_agent_graph() -> StateGraph:
    """
    Create the multi-tenant agent graph.

    The graph structure is the same for all tenants. Tenant-specific behavior
    is injected via state fields:
    - tenant_config: tenant settings (Helena token, LLM config, timezone, etc.)
    - agent_config: agent prompts (persona_prompt, behavior_prompt, agent_name)
    - active_panels: panel categories for classification and routing
    - active_fields: contact fields to collect

    Flow:
    START -> validate -> router_node (conditional)

    Router decides:
    - ETAPA_1/ETAPA_2/ETAPA_2_5 -> agent -> post_process -> post_process_router
        - If [CLASSIFICAR_DEMANDA] -> classify -> classify_router
            - If pre-transfer collection needed -> END (ETAPA_2_5, await next message)
            - Otherwise -> transfer -> END
        - If [COLETA_PRE_TRANSFER] -> END (ETAPA_3, next invocation routes to transfer)
        - Otherwise -> END (await next message)
    - ETAPA_3 (retry) -> transfer -> END
    - COMPLETED -> END

    Returns:
        Compiled StateGraph with checkpointer
    """
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("validate", validate_data_node)
    workflow.add_node("agent", agent_node)
    workflow.add_node("post_process", post_process_node)
    workflow.add_node("classify", classify_demand_node)
    workflow.add_node("transfer", transfer_node)

    # Entry point
    workflow.set_entry_point("validate")

    # Edges
    workflow.add_conditional_edges(
        "validate",
        router_node,
        {
            "agent": "agent",
            "classify": "classify",
            "transfer": "transfer",
            "end": END,
        }
    )

    workflow.add_edge("agent", "post_process")
    workflow.add_conditional_edges(
        "post_process",
        post_process_router,
        {
            "classify": "classify",
            "end": END,
        }
    )

    workflow.add_conditional_edges(
        "classify",
        classify_router,
        {
            "collect": END,      # Needs pre-transfer collection, end this invocation
            "transfer": "transfer",  # No collection needed, proceed to transfer
        }
    )
    workflow.add_edge("transfer", END)

    # Get checkpointer
    checkpointer = await _get_checkpointer()

    # Compile
    app = workflow.compile(checkpointer=checkpointer)

    return app


# Singleton (graph structure is tenant-agnostic; tenant config lives in state)
_agent_graph = None


async def get_agent_graph():
    """Return singleton agent graph instance."""
    global _agent_graph
    if _agent_graph is None:
        _agent_graph = await create_agent_graph()
    return _agent_graph


async def has_existing_checkpoint(thread_id: str, checkpoint_ns: str) -> bool:
    """Check if a conversation thread has any existing checkpoint (prior history)."""
    checkpointer = await _get_checkpointer()
    config = {"configurable": {"thread_id": thread_id, "checkpoint_ns": checkpoint_ns}}
    checkpoint = await checkpointer.aget_tuple(config)
    return checkpoint is not None
