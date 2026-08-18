"""
Bill Audit API Routes — handling manual line entry, document upload, and dispute letters.
"""

import logging
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from pydantic import BaseModel

from app.api.auth import get_current_user
from app.security.rate_limit import rate_limit_user
from app.agents.bill_auditor import run_bill_audit, generate_dispute_letter
from app.models.bill_audit_models import ServiceLineInput, BillAuditResult
from app.services.pdf_extractor import extract_eob_safely
from app.api.eob_routes import _resolve_mime_type, _is_pdf, _is_image, MAX_FILE_SIZE
from app.services.user_data import create_user_audit, update_user_audit_letter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/audit", tags=["Audit"])

# ── Rate Limits ───────────────────────────────────────────────────
AUDIT_SCAN_RATE_LIMIT = rate_limit_user("audit:scan", max_requests=20, window_seconds=3600)
AUDIT_UPLOAD_RATE_LIMIT = rate_limit_user("audit:upload", max_requests=10, window_seconds=3600)
AUDIT_LETTER_RATE_LIMIT = rate_limit_user("audit:letter", max_requests=10, window_seconds=3600)


class AuditScanRequest(BaseModel):
    service_lines: list[ServiceLineInput]
    policy_context: str | None = None


class DisputeLetterRequest(BaseModel):
    audit_result: BillAuditResult
    audit_id: str | None = None


@router.post("/scan")
async def scan_bill(
    request: AuditScanRequest,
    user: dict = Depends(get_current_user),
    _: None = Depends(AUDIT_SCAN_RATE_LIMIT)
):
    """
    Audit manually provided service lines for billing errors.
    """
    logger.info(f"Running manual bill audit for user {user.get('id')} with {len(request.service_lines)} lines")
    
    try:
        result = await run_bill_audit(request.service_lines, request.policy_context or "")
        res_dict = result.model_dump()
        audit_id = None
        if user and user.get("id"):
            try:
                saved = create_user_audit(
                    user_id=user["id"],
                    service_lines_json=[sl.model_dump() for sl in request.service_lines],
                    audit_result_json=res_dict,
                    overall_risk=result.overall_risk,
                    total_billed=result.total_billed,
                    potential_savings=result.potential_savings,
                    source="manual",
                )
                if saved:
                    audit_id = saved.get("id")
            except ValueError as limit_err:
                raise HTTPException(status_code=400, detail=str(limit_err))
            except Exception as db_err:
                logger.error(f"Failed to save manual audit to Supabase: {db_err}", exc_info=True)

        return {"success": True, "audit_id": audit_id, "audit_result": res_dict}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Audit scan endpoint error: {e}")
        raise HTTPException(status_code=500, detail="Failed to run bill audit.")


@router.post("/upload")
async def upload_and_scan_bill(
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
    _: None = Depends(AUDIT_UPLOAD_RATE_LIMIT)
):
    """
    Upload a bill (PDF/Image), extract service lines via Gemini Multimodal,
    and automatically run the bill auditor on the extracted lines.
    """
    content_type = (file.content_type or "").lower()
    filename = file.filename or ""

    if not _is_pdf(content_type, filename) and not _is_image(content_type, filename):
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Please upload a PDF or image.",
        )

    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large ({len(file_bytes) / 1024 / 1024:.1f} MB). Maximum is 10 MB.",
        )
    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    logger.info(f"Audit upload: '{filename}' for user {user.get('id')}")

    try:
        # 1. Extract using Gemini Multimodal (re-using the robust pipeline from EOB routes)
        mime_type = _resolve_mime_type(content_type, filename)
        extraction_result = extract_eob_safely(file_bytes, mime_type=mime_type)

        if "error" in extraction_result:
            raise ValueError(extraction_result["error"])
            
        # 1.5 Validate document type (Gemini identified this visually)
        doc_type = (extraction_result.get("document_type") or "").lower()
        if doc_type and doc_type not in ["bill", "eob"]:
            raise ValueError(f"Document visually identified as '{doc_type}'. Please upload a valid medical bill or EOB.")

        # 2. Format extracted service lines into ServiceLineInput models
        raw_lines = extraction_result.get("service_lines", [])
        if not raw_lines:
            # If no service lines found, try to build a single line from the top-level EOB fields
            if extraction_result.get("billed_amount"):
                raw_lines = [extraction_result]
            else:
                raise ValueError("No distinct service lines or billed amounts found in the document.")

        service_lines = []
        for i, line in enumerate(raw_lines):
            try:
                # Safely convert billed amount to float if possible
                billed_amt = None
                if line.get("billed_amount") is not None:
                    try:
                        billed_amt = float(line["billed_amount"])
                    except ValueError:
                        pass
                
                allowed_amt = None
                if line.get("allowed_amount") is not None:
                    try:
                        allowed_amt = float(line["allowed_amount"])
                    except ValueError:
                        pass

                sl = ServiceLineInput(
                    line_number=i + 1,
                    cpt_code=line.get("cpt_code"),
                    cpt_description=line.get("cpt_description"),
                    icd_10_code=line.get("icd_10_code"),
                    billed_amount=billed_amt,
                    allowed_amount=allowed_amt,
                    date_of_service=extraction_result.get("date_of_service") or line.get("date_of_service"), # fallback to doc-level
                    provider_name=line.get("provider_name") or extraction_result.get("provider_name"),
                )
                service_lines.append(sl)
            except Exception as e:
                logger.warning(f"Could not parse extracted line {i}: {e}")
                continue

        if not service_lines:
            raise ValueError("Could not extract valid service lines with billed amounts from the document.")

        # 3. Run Audit
        audit_result = await run_bill_audit(service_lines)
        res_dict = audit_result.model_dump()
        extracted_lines = [sl.model_dump() for sl in service_lines]

        audit_id = None
        if user and user.get("id"):
            try:
                saved = create_user_audit(
                    user_id=user["id"],
                    service_lines_json=extracted_lines,
                    audit_result_json=res_dict,
                    overall_risk=audit_result.overall_risk,
                    total_billed=audit_result.total_billed,
                    potential_savings=audit_result.potential_savings,
                    source="upload",
                )
                if saved:
                    audit_id = saved.get("id")
            except ValueError as limit_err:
                raise HTTPException(status_code=400, detail=str(limit_err))
            except Exception as db_err:
                logger.error(f"Failed to save upload audit to Supabase: {db_err}", exc_info=True)
        
        return {
            "success": True,
            "audit_id": audit_id,
            "audit_result": res_dict,
            "extracted_lines": extracted_lines
        }

    except ValueError as ve:
        logger.error(f"Audit upload validation error: {ve}")
        raise HTTPException(status_code=400, detail=str(ve))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Audit upload endpoint error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process bill: {str(e)}")


@router.post("/dispute-letter")
async def generate_letter(
    request: DisputeLetterRequest,
    user: dict = Depends(get_current_user),
    _: None = Depends(AUDIT_LETTER_RATE_LIMIT)
):
    """
    Generate a formal dispute letter based on the audit findings.
    """
    logger.info(f"Generating dispute letter for user {user.get('id')}")
    
    try:
        letter_text = await generate_dispute_letter(request.audit_result)
        if request.audit_id and user and user.get("id"):
            try:
                update_user_audit_letter(user_id=user["id"], audit_id=request.audit_id, letter_text=letter_text)
            except Exception as db_err:
                logger.warning(f"Failed to update dispute letter in Supabase: {db_err}")
        return {"success": True, "letter_text": letter_text}
    except Exception as e:
        logger.error(f"Dispute letter endpoint error: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate dispute letter.")
