from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

class PolicyDecisionOutcome(str, Enum):
    """The deterministic outcome from the Policy Engine."""
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    REDACT_DATA = "REDACT_DATA"
    RESTRICT_SCOPE = "RESTRICT_SCOPE"

class ProposedAction(BaseModel):
    """A structured action proposed by an AI agent before execution."""
    agent_id: str = Field(..., description="The ID of the agent proposing the action.")
    action_type: str = Field(..., description="The capability being requested (e.g., 'appeal.generate', 'carrier.submit').")
    resource_id: Optional[str] = Field(None, description="The specific resource being acted upon.")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Action parameters.")
    context: Dict[str, Any] = Field(default_factory=dict, description="Security context (user_id, tenant, environment, etc).")

class PolicyDecision(BaseModel):
    """The deterministic ruling made by the Policy Engine."""
    outcome: PolicyDecisionOutcome
    reason: str = Field(..., description="The justification for the policy decision.")
    policy_id: Optional[str] = Field(None, description="The specific policy rule that was triggered.")
    modified_parameters: Optional[Dict[str, Any]] = Field(None, description="If REDACT_DATA or RESTRICT_SCOPE, the modified payload.")
    requires_human_approval: bool = False

class AuditRecord(BaseModel):
    """A log of every deterministic decision made across the boundary."""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    agent_id: str
    user_id: Optional[str]
    requested_action: str
    resource: Optional[str]
    decision: PolicyDecisionOutcome
    policy_reason: str
