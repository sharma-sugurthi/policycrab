"""
LangGraph State Machine — the central orchestrator.

Wires together all 5 agents and 3 deterministic functions into
a single executable graph with conditional routing.

Three entry paths:
1. Policy Upload → Agent 1 (Ingestion) → Agent 4 (Explain) → END
2. Claim Evaluation → Agent 2 (Intake) → Cost Engine → Router →
   [if denied] → Agent 3 (Grievance) → Agent 4 (Explain) → END
   [if approved] → Agent 4 (Explain) → END
3. Chat → Agent 5 (Chat) → END
"""

import logging
from langgraph.graph import StateGraph, END

from app.agents.state import AgentState
from app.agents.policy_ingestion import policy_ingestion_node
from app.agents.claim_intake import claim_intake_node
from app.agents.grievance import grievance_node
from app.agents.explanation import explanation_node
from app.agents.chat import chat_node
from app.engine.cost_calculator import calculate_cost
from app.engine.regulatory_router import route_to_appeal_framework
from app.models.policy import PolicyProfile
from app.models.claim import ClaimCase
from app.models.enums import ClaimStatus

logger = logging.getLogger(__name__)


# ── Deterministic Nodes (wrappers for the engine functions) ───────

async def cost_calculation_node(state: AgentState) -> dict:
    """Run the deterministic cost calculator."""
    logger.info("Deterministic: Running cost calculation")

    if not state.get("policy_profile") or not state.get("claim_case"):
        return {
            "errors": state.get("errors", []) + ["Cost calculator: Missing policy or claim data"],
            "current_phase": "calculation",
        }

    policy = PolicyProfile(**state["policy_profile"])
    claim = ClaimCase(**state["claim_case"])

    # Use 60% of billed amount as default allowed amount (typical PPO discount)
    allowed_amount = claim.billed_amount * 0.60

    cost = calculate_cost(policy, claim, allowed_amount=allowed_amount)

    # Determine route decision based on cost calculation result
    if cost.claim_status == ClaimStatus.DENIED:
        route = "denied"
    elif cost.claim_status == ClaimStatus.PARTIALLY_APPROVED:
        route = "denied"  # Partial approvals can still be appealed
    else:
        route = "approved"

    # If the claim was already marked as denied (from patient input), keep it
    if claim.is_denied:
        route = "denied"

    logger.info(f"Cost calculation: Status={cost.claim_status.value}, Route={route}")

    return {
        "cost_breakdown": cost.model_dump(mode="json"),
        "route_decision": route,
        "current_phase": "calculation",
        "errors": state.get("errors", []),
    }


# ── Routing Functions ─────────────────────────────────────────────

def route_after_intake(state: AgentState) -> str:
    """Route after claim intake: always go to cost calculation."""
    return "cost_calculation"


def route_after_cost(state: AgentState) -> str:
    """Route after cost calculation: approved → explain, denied → grievance."""
    route = state.get("route_decision", "approved")
    if route == "denied":
        logger.info("Routing → Grievance Agent (claim denied)")
        return "grievance"
    else:
        logger.info("Routing → Explanation Agent (claim approved)")
        return "explain_cost"


def route_after_grievance(state: AgentState) -> str:
    """After grievance drafting, always explain."""
    return "explain_appeal"


# ── Build the Graph ───────────────────────────────────────────────

def build_claim_evaluation_graph() -> StateGraph:
    """
    Build the claim evaluation pipeline graph.

    Flow:
    claim_intake → cost_calculation → [denied?] → grievance → explain_appeal → END
                                    → [approved?] → explain_cost → END
    """
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("claim_intake", claim_intake_node)
    graph.add_node("cost_calculation", cost_calculation_node)
    graph.add_node("grievance", grievance_node)
    graph.add_node("explain_cost", explanation_node)
    graph.add_node("explain_appeal", explanation_node)

    # Set entry point
    graph.set_entry_point("claim_intake")

    # Add edges
    graph.add_edge("claim_intake", "cost_calculation")
    graph.add_conditional_edges(
        "cost_calculation",
        route_after_cost,
        {
            "grievance": "grievance",
            "explain_cost": "explain_cost",
        }
    )
    graph.add_edge("grievance", "explain_appeal")
    graph.add_edge("explain_cost", END)
    graph.add_edge("explain_appeal", END)

    return graph.compile()


def build_policy_ingestion_graph() -> StateGraph:
    """
    Build the policy ingestion pipeline graph.

    Flow: policy_ingestion → explanation → END
    """
    graph = StateGraph(AgentState)

    graph.add_node("policy_ingestion", policy_ingestion_node)
    graph.add_node("explanation", explanation_node)

    graph.set_entry_point("policy_ingestion")
    graph.add_edge("policy_ingestion", "explanation")
    graph.add_edge("explanation", END)

    return graph.compile()


def build_chat_graph() -> StateGraph:
    """
    Build the chat interaction graph.

    Flow: chat → END
    """
    graph = StateGraph(AgentState)

    graph.add_node("chat", chat_node)

    graph.set_entry_point("chat")
    graph.add_edge("chat", END)

    return graph.compile()


# ── Compiled graph instances (singletons) ─────────────────────────

_claim_graph = None
_policy_graph = None
_chat_graph = None


def get_claim_evaluation_graph():
    """Get or create the claim evaluation graph."""
    global _claim_graph
    if _claim_graph is None:
        _claim_graph = build_claim_evaluation_graph()
    return _claim_graph


def get_policy_ingestion_graph():
    """Get or create the policy ingestion graph."""
    global _policy_graph
    if _policy_graph is None:
        _policy_graph = build_policy_ingestion_graph()
    return _policy_graph


def get_chat_graph():
    """Get or create the chat graph."""
    global _chat_graph
    if _chat_graph is None:
        _chat_graph = build_chat_graph()
    return _chat_graph
