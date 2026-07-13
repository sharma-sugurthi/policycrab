"""
Shared Agent State — the central TypedDict that flows through
the entire LangGraph state machine.

Every agent reads from and writes to this shared state.
"""

from typing import Annotated, Any
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages

from app.models.policy import PolicyProfile
from app.models.claim import ClaimCase, CostBreakdown
from app.models.appeal import AppealOutput


class AgentState(TypedDict):
    """
    Shared state for the LangGraph pipeline.
    All agents read from and write to this state.
    """

    # ── Conversation (for Chat Agent) ─────────────────────────────
    messages: Annotated[list, add_messages]

    # ── Raw Inputs ────────────────────────────────────────────────
    raw_policy_text: str            # Raw SBC/EOB text uploaded by user
    raw_claim_text: str             # Raw patient description of their claim

    # ── Structured Pipeline Data ──────────────────────────────────
    policy_profile: dict | None     # PolicyProfile as dict (serializable)
    claim_case: dict | None         # ClaimCase as dict
    allowed_amount: float | None    # EOB allowed amount supplied by the user, if available
    cost_breakdown: dict | None     # CostBreakdown as dict
    appeal_output: dict | None      # AppealOutput as dict

    # ── Control Flow ──────────────────────────────────────────────
    current_phase: str              # "ingestion", "intake", "calculation", "routing", "appeal", "explanation", "chat"
    route_decision: str             # "approved", "denied", "chat"

    # ── Error Handling ────────────────────────────────────────────
    errors: list[str]

    # ── Explanations (populated by Explanation Agent) ─────────────
    explanations: dict[str, str]    # phase → plain English explanation
