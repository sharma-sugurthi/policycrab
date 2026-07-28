import asyncio
from app.api.audit_routes import scan_bill, AuditScanRequest
from app.models.bill_audit_models import ServiceLineInput
import json

async def run():
    req = AuditScanRequest(
        service_lines=[
            ServiceLineInput(
                line_number=1,
                cpt_code="99285", # Level 5 ER
                icd_10_code="J00", # Simple cold (Upcoding!)
                billed_amount=4500.0, # Excessive charge!
            )
        ]
    )
    res = await scan_bill(req, user={"id": "test_user"})
    print(json.dumps(res, indent=2))

if __name__ == "__main__":
    asyncio.run(run())
