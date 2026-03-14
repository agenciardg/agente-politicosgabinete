"""
Agent State - Multi-Tenant LangGraph State
============================================
Defines the shared state for all graph nodes.
Extended with dynamic tenant config fields loaded from Supabase.
"""

from typing import Annotated, List, Optional, Literal, TypedDict
from langgraph.graph import add_messages
from langchain_core.messages import BaseMessage


class AgentState(TypedDict):
    """
    Multi-tenant LangGraph agent state.

    This state is passed between all graph nodes and persists
    between executions via PostgresCheckpointer.
    """

    # ==========================================
    # CORE - Messages and Context
    # ==========================================

    messages: Annotated[List[BaseMessage], add_messages]
    """List of conversation messages (Human + AI)"""

    # ==========================================
    # MULTI-TENANT - Tenant Context
    # ==========================================

    tenant_id: str
    """UUID of the tenant (gabinete) this conversation belongs to"""

    agent_type: Optional[str]
    """Agent type: 'principal' or 'assessor'"""

    # Dynamic config (loaded from Supabase at start)
    tenant_config: Optional[dict]
    """Full tenant row data from agentpolitico_tenants"""

    agent_config: Optional[dict]
    """Agent row data (persona_prompt, behavior_prompt, etc.)"""

    active_panels: Optional[list]
    """Panels configured for this agent with field mappings"""

    active_fields: Optional[list]
    """Contact fields to collect, ordered by field_order"""

    field_mappings: Optional[dict]
    """panel_name -> field mappings for card creation"""

    # Assessor detection
    is_assessor: Optional[bool]
    """Whether the phone number belongs to an assessor"""

    # ==========================================
    # SESSION - Identifiers
    # ==========================================

    session_id: str
    """Session ID (Helena session UUID)"""

    phone_number: str
    """Citizen phone number in E.164 format"""

    card_id: Optional[str]
    """Helena CRM card UUID"""

    contact_id: Optional[str]
    """Helena CRM contact UUID"""

    # ==========================================
    # PHASES - Flow Control
    # ==========================================

    current_phase: Literal["ETAPA_1", "ETAPA_2", "ETAPA_3", "COMPLETED"]
    """Current phase of the conversation"""

    should_continue: bool
    """Flag to control whether the loop should continue"""

    # ==========================================
    # ETAPA 1 - Data Validation
    # ==========================================

    contact_data: Optional[dict]
    """Complete contact data from Helena API"""

    validation_status: Optional[Literal["complete", "incomplete"]]
    """Validation status: complete or incomplete"""

    missing_fields: Optional[List[str]]
    """List of missing required fields"""

    contact_name: Optional[str]
    """Citizen name from CRM"""

    cep_lookup_result: Optional[dict]
    """ViaCEP lookup result"""

    pending_data: Optional[dict]
    """Data collected in conversation awaiting confirmation"""

    awaiting_confirmation: Optional[bool]
    """Flag: data summary was presented and awaiting confirmation?"""

    data_saved: Optional[bool]
    """Flag: data has been saved to Helena CRM?"""

    insistence_count: Optional[int]
    """Counter for insistence budget in ETAPA 1"""

    max_insistence: Optional[int]
    """Maximum insistence count (from tenant config, default 2)"""

    refused_all_data: Optional[bool]
    """Flag: citizen refused to provide all data"""

    # ==========================================
    # ETAPA 2 - Demand Classification
    # ==========================================

    demand_asked: Optional[bool]
    """Flag: agent already asked about the demand?"""

    etapa2_turns: Optional[int]
    """Turn counter in ETAPA 2"""

    demand_ready: Optional[bool]
    """Flag: enough info collected for classification?"""

    category: Optional[str]
    """Demand category (technical key)"""

    classification: Optional[dict]
    """Full AI classification result"""

    urgency: Optional[Literal["baixa", "media", "alta"]]
    """Demand urgency level"""

    # ==========================================
    # ETAPA 3 - Transfer
    # ==========================================

    transferred_to_department: Optional[str]
    """Helena department UUID where session was transferred"""

    new_card_id: Optional[str]
    """UUID of the new card created in destination panel"""

    transfer_status: Optional[Literal["pending", "success", "failed"]]
    """Transfer status"""

    # ==========================================
    # METADATA AND CONTROL
    # ==========================================

    error: Optional[str]
    """Error message (if any)"""

    metadata: Optional[dict]
    """Flexible additional metadata"""

    # ==========================================
    # CONTROL FLAGS
    # ==========================================

    data_collected: bool
    """Flag: required data collected?"""

    demand_classified: bool
    """Flag: demand classified?"""

    transferred: bool
    """Flag: transfer completed?"""


def create_initial_state(
    tenant_id: str,
    session_id: str,
    phone_number: str,
    card_id: str,
    initial_message: str,
    agent_type: str = "principal",
    tenant_config: Optional[dict] = None,
    agent_config: Optional[dict] = None,
    active_panels: Optional[list] = None,
    active_fields: Optional[list] = None,
    field_mappings: Optional[dict] = None,
    is_assessor: bool = False,
) -> AgentState:
    """Create the initial agent state for a multi-tenant conversation."""
    from langchain_core.messages import HumanMessage

    return AgentState(
        # Core
        messages=[HumanMessage(content=initial_message)],
        # Multi-tenant
        tenant_id=tenant_id,
        agent_type=agent_type,
        tenant_config=tenant_config or {},
        agent_config=agent_config or {},
        active_panels=active_panels or [],
        active_fields=active_fields or [],
        field_mappings=field_mappings or {},
        is_assessor=is_assessor,
        # Session
        session_id=session_id,
        phone_number=phone_number,
        card_id=card_id,
        contact_id=None,
        # Phases
        current_phase="ETAPA_1",
        should_continue=True,
        # ETAPA 1
        contact_data=None,
        validation_status=None,
        missing_fields=None,
        contact_name=None,
        cep_lookup_result=None,
        pending_data=None,
        awaiting_confirmation=False,
        data_saved=False,
        insistence_count=0,
        max_insistence=2,
        refused_all_data=False,
        # ETAPA 2
        demand_asked=False,
        etapa2_turns=0,
        demand_ready=False,
        category=None,
        classification=None,
        urgency=None,
        # ETAPA 3
        transferred_to_department=None,
        new_card_id=None,
        transfer_status=None,
        # Metadata
        error=None,
        metadata={},
        # Flags
        data_collected=False,
        demand_classified=False,
        transferred=False,
    )
