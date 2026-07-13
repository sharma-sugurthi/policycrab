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
        )
    else:
        return PolicyUploadResponse(
            success=False,
            errors=result.get("errors", ["Policy extraction returned no data"]),
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
            create_user_policy(user["id"], response.policy_profile)
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

    The PDF text is extracted using PyMuPDF, then passed through
    the same Policy Ingestion Agent as the text upload endpoint.

    Accepts: application/pdf, max 10 MB.
    """
    # ── Validate file type ────────────────────────────────────
    if not file.content_type or "pdf" not in file.content_type.lower():
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

    # ── Extract text from PDF ─────────────────────────────────
    try:
        extracted_text = extract_text_from_pdf(pdf_bytes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if len(extracted_text.strip()) < 50:
        raise HTTPException(
            status_code=400,
            detail="PDF produced too little text. It may be a scanned document — try pasting the text manually."
        )

    logger.info(f"PDF upload: {file.filename}, {len(pdf_bytes)} bytes → {len(extracted_text)} chars extracted")

    try:
        response = await _run_ingestion(extracted_text)
        response.extracted_text = extracted_text[:2000]
        if response.success and response.policy_profile:
            create_user_policy(user["id"], response.policy_profile)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Policy ingestion failed: {str(e)}")
