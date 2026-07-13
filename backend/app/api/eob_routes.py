"""
EOB API Routes — parse Explanation of Benefits PDF documents.
"""

import logging
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File

from app.api.auth import get_current_user
from app.security.rate_limit import rate_limit
from app.services.llm_router import get_llm, TaskType
from app.agents.eob_extractor import extract_eob_fields

logger = logging.getLogger(__name__)

MAX_PDF_SIZE = 10 * 1024 * 1024  # 10 MB

EOB_PARSE_RATE_LIMIT = rate_limit("eob:parse", max_requests=10, window_seconds=60)

router = APIRouter(prefix="/api/eob", tags=["EOB"])


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extract text from PDF bytes using PyMuPDF."""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()
        return text
    except Exception as e:
        raise ValueError(f"Failed to extract text from PDF: {e}")


@router.post("/parse")
async def parse_eob(
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
    _: None = Depends(EOB_PARSE_RATE_LIMIT),
):
    """
    Upload an EOB PDF and extract structured claim fields.

    Returns extracted fields with per-field confidence levels.
    The frontend uses this to pre-fill the Claim Evaluator form.

    Accepts: application/pdf, max 10 MB.
    """
    # ── Validate file type ────────────────────────────────────
    if not file.content_type or "pdf" not in file.content_type.lower():
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type: {file.content_type}. Please upload a PDF EOB.",
        )

    # ── Read and validate size ────────────────────────────────
    pdf_bytes = await file.read()

    if len(pdf_bytes) > MAX_PDF_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large ({len(pdf_bytes) / 1024 / 1024:.1f} MB). Maximum is 10 MB.",
        )

    if len(pdf_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    # ── Extract text from PDF ─────────────────────────────────
    try:
        eob_text = extract_text_from_pdf(pdf_bytes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if len(eob_text.strip()) < 30:
        raise HTTPException(
            status_code=400,
            detail=(
                "PDF produced too little text. It may be a scanned document. "
                "Try copying the EOB text and pasting it manually instead."
            ),
        )

    logger.info(
        f"EOB parse: {file.filename}, {len(pdf_bytes)} bytes → {len(eob_text)} chars extracted"
    )

    # ── Run LLM extraction ────────────────────────────────────
    try:
        llm = get_llm(TaskType.FAST)
        result = extract_eob_fields(eob_text, llm)

        if "error" in result:
            raise HTTPException(
                status_code=422,
                detail=f"EOB extraction failed: {result['error']}",
            )

        return {
            "success": True,
            "extracted": result,
            "char_count": len(eob_text),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"EOB parse endpoint error: {e}")
        raise HTTPException(status_code=500, detail=f"EOB parsing failed: {str(e)}")
