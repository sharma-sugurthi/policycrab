"""
Policy API Routes — upload and retrieve insurance policy profiles.
Supports both raw text paste and PDF file upload.
"""

import logging
from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from pydantic import BaseModel, Field

from app.agents.graph import get_policy_ingestion_graph
from app.services.pdf_extractor import extract_text_from_pdf
from app.api.auth import get_current_user
from app.security.rate_limit import rate_limit
from app.services.user_data import create_user_policy

logger = logging.getLogger(__name__)
POLICY_UPLOAD_RATE_LIMIT = rate_limit("policy:upload", max_requests=5, window_seconds=60)

router = APIRouter(prefix="/api/policy", tags=["Policy"])

# ── Max PDF size: 10 MB ──────────────────────────────────────
MAX_PDF_SIZE = 10 * 1024 * 1024


class PolicyUploadRequest(BaseModel):
    """Request body for policy text upload."""
    policy_text: str = Field(
        ...,
        min_length=50,
        description="Raw text from an SBC, EOB, or policy summary document"
    )


class PolicyUploadResponse(BaseModel):
    """Response after policy ingestion."""
    success: bool
    policy_profile: dict | None = None
    explanation: str | None = None
    extracted_text: str | None = None
    extraction_warnings: list[str] = []
    extraction_confidence: str | None = None
    errors: list[str] = []
    session_id: str | None = None       # The Supabase session used for RAG indexing
    policy_indexed: bool = False         # True if the full doc was chunked/embedded for RAG
    policy_page_count: int | None = None # Number of pages processed


async def _run_ingestion(policy_text: str) -> PolicyUploadResponse:
    """Shared logic: run the policy ingestion graph on extracted text."""
    graph = get_policy_ingestion_graph()

    initial_state = {
        "messages": [],
        "raw_policy_text": policy_text,
        "raw_claim_text": "",
        "policy_profile": None,
        "claim_case": None,
        "allowed_amount": None,
        "cost_breakdown": None,
        "appeal_output": None,
        "current_phase": "ingestion",
        "route_decision": "",
        "errors": [],
        "extraction_warnings": [],
        "extraction_confidence": None,
        "explanations": {},
    }

    result = await graph.ainvoke(initial_state)

    if result.get("policy_profile"):
        return PolicyUploadResponse(
            success=True,
            policy_profile=result["policy_profile"],
            explanation=result.get("explanations", {}).get("ingestion"),
            extraction_warnings=result.get("extraction_warnings", []),
            extraction_confidence=result.get("extraction_confidence"),
            errors=result.get("errors", []),
            session_id=result.get("session_id"),
            policy_indexed=result.get("policy_indexed", False),
            policy_page_count=result.get("policy_page_count"),
        )
    else:
        # Phase 1 (RAG indexing) may have succeeded even if Phase 2 (extraction) failed.
        # Surface the session_id so the frontend can still use RAG if available.
        return PolicyUploadResponse(
            success=False,
            errors=result.get("errors", ["Policy extraction returned no data"]),
            session_id=result.get("session_id"),
            policy_indexed=result.get("policy_indexed", False),
            policy_page_count=result.get("policy_page_count"),
        )


@router.post("/upload", response_model=PolicyUploadResponse)
async def upload_policy_text(
    request: PolicyUploadRequest, 
    user: dict = Depends(get_current_user),
    _: None = Depends(POLICY_UPLOAD_RATE_LIMIT)
):
    """
    Upload raw SBC/EOB text for AI-powered policy extraction.
    """
    try:
        response = await _run_ingestion(request.policy_text)
        if response.success and response.policy_profile:
            try:
                create_user_policy(user["id"], response.policy_profile)
            except ValueError as limit_error:
                # Policy limit reached — still return the profile but warn the user
                response.errors = response.errors + [str(limit_error)]
            except Exception as db_error:
                logger.warning(f"Failed to save policy to database (continuing anyway): {db_error}")
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Policy ingestion failed: {str(e)}")


@router.post("/upload-pdf", response_model=PolicyUploadResponse)
async def upload_policy_pdf(
    file: UploadFile = File(...), 
    user: dict = Depends(get_current_user),
    _: None = Depends(POLICY_UPLOAD_RATE_LIMIT)
):
    """
    Upload a PDF file (SBC, EOB, or policy summary) for AI-powered extraction.

    Phase 4 upgrade: The full document is chunked page-by-page and embedded
    into Supabase for semantic RAG search by the Policy Analyzer Agent.
    This enables exact page-number citations in appeal letters.

    Accepts: application/pdf, max 10 MB. Supports 150+ page policy documents.
    Processing time scales with document length (allow up to 2 minutes for
    very large documents).
    """
    # ── Validate file type (loosened — some browsers send octet-stream) ──
    ct = (file.content_type or "").lower()
    fn = (file.filename or "").lower()
    if "pdf" not in ct and not fn.endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type: {file.content_type}. Please upload a PDF file."
        )

    # ── Read and validate size ────────────────────────────────
    pdf_bytes = await file.read()

    if len(pdf_bytes) > MAX_PDF_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large ({len(pdf_bytes) / 1024 / 1024:.1f} MB). Maximum is 10 MB."
        )

    if len(pdf_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    # ── Extract text from PDF (page-aware) ───────────────────
    try:
        extracted_text = extract_text_from_pdf(pdf_bytes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if len(extracted_text.strip()) < 50:
        raise HTTPException(
            status_code=400,
            detail="PDF produced too little text. It may be a scanned document — try pasting the text manually."
        )

    # Estimate page count from "--- Page N ---" markers
    import re
    page_markers = re.findall(r"--- Page (\d+) ---", extracted_text)
    page_count = int(page_markers[-1]) if page_markers else 1

    logger.info(
        f"PDF upload: '{file.filename}', {len(pdf_bytes) / 1024:.0f} KB, "
        f"~{page_count} pages → {len(extracted_text)} chars extracted. "
        f"User: {user.get('id', 'unknown')}"
    )

    # ── Build session_id from user id (stable across uploads) ──
    # This ensures the Policy Analyzer always queries the correct user's chunks.
    import hashlib
    user_session_id = hashlib.sha256(
        f"{user['id']}:{file.filename}:{len(pdf_bytes)}".encode()
    ).hexdigest()[:16]

    try:
        from app.agents.graph import get_policy_ingestion_graph
        graph = get_policy_ingestion_graph()

        initial_state = {
            "messages": [],
            "raw_policy_text": extracted_text,
            "raw_claim_text": "",
            "policy_profile": None,
            "claim_case": None,
            "allowed_amount": None,
            "cost_breakdown": None,
            "appeal_output": None,
            "current_phase": "ingestion",
            "route_decision": "",
            "errors": [],
            "extraction_warnings": [],
            "extraction_confidence": None,
            "explanations": {},
            "session_id": user_session_id,  # Pre-seed session_id
        }

        result = await graph.ainvoke(initial_state)

        # Build response
        base_resp = PolicyUploadResponse(
            success=bool(result.get("policy_profile")),
            policy_profile=result.get("policy_profile"),
            explanation=result.get("explanations", {}).get("ingestion"),
            extraction_warnings=result.get("extraction_warnings", []),
            extraction_confidence=result.get("extraction_confidence"),
            errors=result.get("errors", []),
            session_id=result.get("session_id", user_session_id),
            policy_indexed=result.get("policy_indexed", False),
            policy_page_count=result.get("policy_page_count", page_count),
            extracted_text=extracted_text[:2000],
        )

        if base_resp.success and base_resp.policy_profile:
            try:
                create_user_policy(user["id"], base_resp.policy_profile)
            except ValueError as limit_error:
                base_resp.errors = base_resp.errors + [str(limit_error)]
            except Exception as db_error:
                logger.warning(f"Failed to save policy to database (continuing anyway): {db_error}")

        return base_resp

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Policy ingestion failed: {str(e)}")
