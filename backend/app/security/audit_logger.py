import json
import logging
from typing import Any

from app.models.security import AuditRecord
from app.services.audit_trail import record_audit

# Create a dedicated logger for security audits
audit_logger_instance = logging.getLogger("security_audit")
audit_logger_instance.setLevel(logging.INFO)

# In Google Cloud Run, structured JSON logs printed to stdout 
# are automatically parsed by Cloud Logging.
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(message)s'))
if not audit_logger_instance.handlers:
    audit_logger_instance.addHandler(handler)
    audit_logger_instance.propagate = False

class AuditLogger:
    """
    Handles persistent, structured logging of security decisions.
    Outputs JSON designed to be ingested by Google Cloud Logging or SIEMs.
    """
    
    @staticmethod
    def log_decision(audit_record: AuditRecord) -> None:
        """
        Write an audit record to the security log.
        """
        # Convert the Pydantic model to a dict, handling datetimes
        log_data = audit_record.model_dump(mode="json")
        
        # Add a special label for GCP log routing
        log_data["log_type"] = "EASF_SECURITY_AUDIT"
        
        # Log as a single JSON string
        audit_logger_instance.info(json.dumps(log_data))

        # Also append to the queryable audit trail (no-op unless AUDIT_TRAIL_ENABLED).
        record_audit(
            "easf.decision",
            user_id=audit_record.user_id,
            actor_type="agent",
            resource_type="action",
            resource_id=audit_record.resource,
            outcome=str(audit_record.decision.value).lower(),
            reason=audit_record.policy_reason,
            metadata={"agent_id": audit_record.agent_id, "requested_action": audit_record.requested_action},
        )

audit_logger = AuditLogger()
