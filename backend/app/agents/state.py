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
    benchmark_policy_excerpt: str | None # Benchmark testing injected excerpt

    # ── Session & RAG Indexing (NEW) ──────────────────────────────
    session_id: str | None          # Unique session ID for Supabase policy chunk scoping
    policy_indexed: bool            # True if the policy PDF was successfully chunked & embedded
    policy_page_count: int | None   # Total pages extracted from the policy PDF
    claim_overrides: dict | None    # Optional ground truth overrides for automated benchmark testing

    # ── Structured Pipeline Data ──────────────────────────────────
    policy_profile: dict | None     # PolicyProfile as dict (serializable)
    claim_case: dict | None         # ClaimCase as dict
    allowed_amount: float | None    # EOB allowed amount supplied by the user, if available
    cost_breakdown: dict | None     # CostBreakdown as dict
    contradiction_analysis: dict | None  # ContradictionAnalysis from Policy Analyzer Agent (NEW)
    triage_decision: dict | None    # TriageDecision from Triage Agent — PROVIDER_CODING_ERROR vs PAYER_ILLEGAL_DENIAL
    appeal_output: dict | None      # AppealOutput as dict

    # ── Control Flow ──────────────────────────────────────────────
    current_phase: str              # "ingestion", "intake", "calculation", "analysis", "triage", "appeal", "explanation", "chat"
    route_decision: str             # "approved", "denied", "chat"

    # ── Error Handling ────────────────────────────────────────────
    errors: list[str]

    # ── Extraction Quality (populated by Policy Ingestion Agent) ──
    extraction_warnings: list[str]       # Sanity-check warnings for extracted fields
    extraction_confidence: str | None    # "HIGH", "MEDIUM", or "LOW"

    # ── Explanations (populated by Explanation Agent) ─────────────
    explanations: dict[str, str]    # phase → plain English explanation
