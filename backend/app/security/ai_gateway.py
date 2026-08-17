import logging
from typing import Tuple

from app.security.prompt_shields import detect_prompt_injection
from app.security.policy_engine import policy_engine
from app.security.audit_logger import audit_logger
from app.models.security import ProposedAction, PolicyDecision, PolicyDecisionOutcome, AuditRecord

logger = logging.getLogger(__name__)

class AISecurityGateway:
    """
    The centralized Security Gateway for all AI operations.
    Acts as the enforcement boundary between non-deterministic LLMs and deterministic execution.
    """
    
    @staticmethod
    def inspect_input(text: str) -> Tuple[bool, str]:
        """
        Inspect incoming text (prompts, RAG context, user input) for injection or malicious intent.
        
        Returns:
            Tuple[bool, str]: True if safe, False if malicious/blocked, with a reason.
        """
        is_injection, violation = detect_prompt_injection(text)
        if is_injection:
            logger.error(f"AI Gateway Blocked Input: {violation}")
            return False, violation
            
        # Here we could also run phi_scrubber or presidio_scrubber on the input if needed.
        return True, "Input is safe."

    @staticmethod
    def request_action_execution(proposed_action: ProposedAction) -> PolicyDecision:
        """
        Request permission to execute an action.
        This ties into the deterministic policy engine to ensure the LLM isn't allowed
        to bypass RBAC, context, or workflow rules.
        """
        decision = policy_engine.evaluate(proposed_action)
        
        if decision.outcome == PolicyDecisionOutcome.DENY:
            logger.warning(
                f"AI Gateway Denied Action: {proposed_action.action_type} "
                f"by {proposed_action.agent_id}. Reason: {decision.reason}"
            )
        elif decision.outcome == PolicyDecisionOutcome.REQUIRE_APPROVAL:
            logger.info(
                f"AI Gateway Pausing Action (Approval Required): {proposed_action.action_type} "
                f"by {proposed_action.agent_id}. Reason: {decision.reason}"
            )
        else:
            logger.info(
                f"AI Gateway Allowed Action: {proposed_action.action_type} "
                f"by {proposed_action.agent_id}."
            )
            
        # Log to the persistent audit trail
        audit_record = AuditRecord(
            agent_id=proposed_action.agent_id,
            user_id=proposed_action.context.get("user_id"),
            requested_action=proposed_action.action_type,
            resource=proposed_action.resource_id,
            decision=decision.outcome,
            policy_reason=decision.reason
        )
        audit_logger.log_decision(audit_record)
            
        return decision

# Singleton instance
ai_gateway = AISecurityGateway()
