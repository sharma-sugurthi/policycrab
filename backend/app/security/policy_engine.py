import logging
from typing import Optional

from app.models.security import ProposedAction, PolicyDecision, PolicyDecisionOutcome

logger = logging.getLogger(__name__)


class PolicyEngine:
    """
    Deterministic rule-based policy engine for evaluating AI agent actions.
    The LLM proposes an action, but this engine decides if it's permitted.
    """

    def evaluate(self, proposed_action: ProposedAction) -> PolicyDecision:
        """
        Evaluate a proposed action against enterprise security rules.
        """
        logger.info(
            f"Policy Engine evaluating action '{proposed_action.action_type}' "
            f"from agent '{proposed_action.agent_id}'"
        )
        
        action_type = proposed_action.action_type
        
        # Rule 1: Direct submission to external carriers always requires human approval.
        # This prevents autonomous systems from sending unauthorized legal appeals.
        if action_type == "carrier.submit":
            return PolicyDecision(
                outcome=PolicyDecisionOutcome.REQUIRE_APPROVAL,
                reason="Direct submission of appeals to external insurance carriers requires human review.",
                policy_id="SEC-001-EXTERNAL-SUBMIT",
                requires_human_approval=True
            )
            
        # Rule 2: Generating an appeal document is allowed, but we might want to 
        # restrict it if the environment is locked down or if it involves highly sensitive PII.
        if action_type == "appeal.generate":
            # Example check: if context flags the user as restricted
            if proposed_action.context.get("user_role") == "READ_ONLY":
                return PolicyDecision(
                    outcome=PolicyDecisionOutcome.DENY,
                    reason="User lacks permissions to generate legal documents.",
                    policy_id="SEC-002-RBAC",
                    requires_human_approval=False
                )
            
            return PolicyDecision(
                outcome=PolicyDecisionOutcome.ALLOW,
                reason="User is authorized to generate appeal documents.",
                policy_id="SEC-002-RBAC",
                requires_human_approval=False
            )
            
        # Rule 3: Accessing raw financial/cost data might require redaction 
        # based on context (e.g. support agents vs actual patients)
        if action_type == "data.access.financial":
            if proposed_action.context.get("user_role") == "SUPPORT":
                return PolicyDecision(
                    outcome=PolicyDecisionOutcome.REDACT_DATA,
                    reason="Support agents may only view redacted financial data.",
                    policy_id="SEC-003-DATA-ACCESS",
                    modified_parameters={"redact_fields": ["ssn", "credit_card", "full_balance"]},
                    requires_human_approval=False
                )

        # Default Fallback: Deny by default for unknown actions (Zero Trust)
        logger.warning(f"Unknown action proposed: {action_type}. Denying by default.")
        return PolicyDecision(
            outcome=PolicyDecisionOutcome.DENY,
            reason=f"Action '{action_type}' is not explicitly permitted by any policy.",
            policy_id="SEC-000-DEFAULT-DENY",
            requires_human_approval=False
        )

# Singleton instance for easy import
policy_engine = PolicyEngine()
