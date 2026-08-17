import json
import logging
from typing import Any

from app.models.security import AuditRecord

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

audit_logger = AuditLogger()
