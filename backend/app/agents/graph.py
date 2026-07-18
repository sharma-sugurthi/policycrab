"""
LangGraph State Machine — the central orchestrator.

Wires together all 6 agents and 3 deterministic functions into
a single executable graph with conditional routing.

Three entry paths:
1. Policy Upload → Agent 1 (Ingestion) → Agent 4 (Explain) → END
2. Claim Evaluation → Agent 2 (Intake) → Cost Engine → Router →
   [if denied] → Agent 4 (Policy Analyzer) → Agent 3 (Grievance) → Agent 5 (Explain) → END
   [if approved] → Agent 5 (Explain) → END
3. Chat → Agent 6 (Chat) → END
"""

import logging
from langgraph.graph import StateGraph, END

from app.agents.state import AgentState
from app.agents.policy_ingestion import policy_ingestion_node
from app.agents.claim_intake import claim_intake_node
from app.agents.policy_analyzer import policy_analyzer_node
from app.agents.triage import triage_node
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

    supplied_allowed_amount = state.get("allowed_amount")
    if supplied_allowed_amount is not None and supplied_allowed_amount > claim.billed_amount:
        return {
            "claim_case": claim.model_dump(mode="json"),
            "cost_breakdown": None,
            "route_decision": "error",
            "current_phase": "calculation",
            "errors": state.get("errors", []) + [
                "Allowed amount cannot be greater than the billed amount. Enter the allowed amount exactly as shown on the EOB, or leave it blank for an estimate."
            ],
        }

    if supplied_allowed_amount is None:
        allowed_amount = claim.billed_amount
        allowed_amount_source = "billed_amount_estimate"
    else:
        allowed_amount = supplied_allowed_amount
        allowed_amount_source = "eob"

    cost = calculate_cost(policy, claim, allowed_amount=allowed_amount)
    cost.allowed_amount_source = allowed_amount_source

    if allowed_amount_source == "billed_amount_estimate":
        cost.calculation_notes.insert(
            0,
            "ESTIMATE ONLY: No EOB allowed amount was provided. The calculator used the billed amount as a conservative placeholder, not a negotiated insurer rate. Do not use this estimate for financial planning.",
        )
    else:
        cost.calculation_notes.insert(
            0,
            "Allowed amount supplied by the user from an EOB/ERA or insurer document.",
        )

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
    """Route after cost calculation: approved → explain, denied → policy_analyzer → grievance."""
    route = state.get("route_decision", "approved")
    if route == "denied":
        logger.info("Routing → Policy Analyzer (claim denied)")
        return "policy_analyzer"
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
    claim_intake → cost_calculation → [denied?] → policy_analyzer → grievance → explain_appeal → END
                                    → [approved?] → explain_cost → END
    """
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("claim_intake", claim_intake_node)
    graph.add_node("cost_calculation", cost_calculation_node)
    graph.add_node("policy_analyzer", policy_analyzer_node)
    graph.add_node("triage", triage_node)                     # NEW: Triage agent
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
            "policy_analyzer": "policy_analyzer",  # denied path
            "explain_cost": "explain_cost",         # approved path
        }
    )
    graph.add_edge("policy_analyzer", "triage")     # Analyzer → Triage
    graph.add_edge("triage", "grievance")           # Triage → Grievance
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
