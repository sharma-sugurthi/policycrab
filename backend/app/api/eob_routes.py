"""
EOB API Routes — parse Explanation of Benefits documents via Gemini Multimodal.

UPGRADE (Phase 2): The extraction pipeline now routes ALL uploads (PDFs and
images) through Gemini Multimodal as the primary extraction engine.

Why: pytesseract flattened multi-column EOB tables into incorrect linear text.
     Gemini reads documents visually, understanding table structure natively.

Extraction flow:
  PDF upload   → Gemini Multimodal (mime: application/pdf)  [PRIMARY]
               → PyMuPDF text layer + LLM re-parse          [FALLBACK]
  Image upload → Gemini Multimodal (mime: image/*)          [PRIMARY]
               → (no image OCR fallback — Gemini handles all image types)

Returns structured EOB fields with per-field confidence levels,
all service lines, and NSA-critical fields (facility_network_status,
ancillary_service_type) for automatic NSA violation detection.

Accepts: PDF or image (JPG, PNG, TIFF, WEBP, BMP), max 10 MB.
"""

import logging
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File

from app.api.auth import get_current_user
from app.security.rate_limit import rate_limit_user
from app.services.pdf_extractor import extract_eob_safely, extract_text_from_pdf
from app.agents.eob_extractor import extract_eob_fields
from app.services.llm_router import get_llm, TaskType

logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

ACCEPTED_PDF_TYPES = {"application/pdf", "pdf"}
ACCEPTED_IMAGE_TYPES = {
    "image/jpeg", "image/jpg", "image/png",
    "image/tiff", "image/webp", "image/bmp",
}

# Mime types that Gemini Multimodal natively supports for document understanding
GEMINI_SUPPORTED_MIMES = {
    "application/pdf",
    "image/jpeg", "image/jpg", "image/png",
    "image/tiff", "image/webp", "image/bmp",
    "image/gif",
}

# Per-user: 10 EOB parses per hour
EOB_PARSE_RATE_LIMIT = rate_limit_user("eob:parse", max_requests=10, window_seconds=3600)

router = APIRouter(prefix="/api/eob", tags=["EOB"])


def _is_pdf(content_type: str | None, filename: str | None) -> bool:
    ct = (content_type or "").lower()
    fn = (filename or "").lower()
    return "pdf" in ct or fn.endswith(".pdf")


def _is_image(content_type: str | None, filename: str | None) -> bool:
    ct = (content_type or "").lower()
    fn = (filename or "").lower()
    if any(t in ct for t in ("jpeg", "jpg", "png", "tiff", "webp", "bmp")):
        return True
    if any(fn.endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".tiff", ".tif", ".webp", ".bmp")):
        return True
    return False


def _resolve_mime_type(content_type: str | None, filename: str | None) -> str:
    """Resolve a reliable MIME type for the Gemini API call."""
    ct = (content_type or "").lower()
    fn = (filename or "").lower()

    if "pdf" in ct or fn.endswith(".pdf"):
        return "application/pdf"
    if "jpeg" in ct or "jpg" in ct or fn.endswith((".jpg", ".jpeg")):
        return "image/jpeg"
    if "png" in ct or fn.endswith(".png"):
        return "image/png"
    if "tiff" in ct or fn.endswith((".tiff", ".tif")):
        return "image/tiff"
    if "webp" in ct or fn.endswith(".webp"):
        return "image/webp"
    if "bmp" in ct or fn.endswith(".bmp"):
        return "image/bmp"
    # Default fallback
    return content_type or "application/octet-stream"


@router.post("/parse")
async def parse_eob(
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
    _: None = Depends(EOB_PARSE_RATE_LIMIT),
):
    """
    Upload an EOB, medical bill, or policy document (PDF or image) and
    extract structured claim fields with per-field confidence scores.

    UPGRADE (Phase 2): All uploads now route through Gemini Multimodal as the
    primary extraction engine for maximum accuracy on medical billing tables.

    The response includes:
    - All service lines (not just the primary line)
    - NSA-critical fields: facility_network_status, ancillary_service_type
    - Per-field confidence scores
    - extraction_method: "gemini_multimodal" | "pymupdf+llm" for transparency

    The frontend uses this to pre-fill the Claim Evaluator form via
    sessionStorage ("Fill Claim Form" action in the Document Vault).

    Accepts: PDF (max 10 MB) or image (JPG, PNG, TIFF, WEBP, BMP, max 10 MB).
    """
    content_type = (file.content_type or "").lower()
    filename = file.filename or ""

    is_pdf = _is_pdf(content_type, filename)
    is_img = _is_image(content_type, filename)

    if not is_pdf and not is_img:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file type: '{file.content_type}'. "
                "Please upload a PDF or an image (JPG, PNG, TIFF, WEBP)."
            ),
        )
    if is_img:
        raise HTTPException(
            status_code=400,
            detail=(
                "Image uploads are unavailable because they cannot be scrubbed "
                "locally before processing. Upload a text-based PDF instead."
            ),
        )

    # ── Read and validate size ────────────────────────────────────
    file_bytes = await file.read()

    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large ({len(file_bytes) / 1024 / 1024:.1f} MB). Maximum is 10 MB.",
        )

    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    # ── PRIMARY: Gemini Multimodal Extraction ─────────────────────
    # Gemini reads the document visually — understanding table layouts,
    # column headers, and multi-line EOB service entries natively.
    # This returns a fully structured dict directly (no intermediate text).
    mime_type = _resolve_mime_type(content_type, filename)
    extraction_method = "gemini_multimodal"
    result = None

    logger.info(
        f"EOB parse: '{filename}' ({mime_type}), "
        f"{len(file_bytes) / 1024:.1f} KB → routing to Gemini Multimodal"
    )

    try:
        result = extract_eob_safely(file_bytes, mime_type=mime_type)

        if "error" in result:
            raise ValueError(result["error"])

    except Exception as gemini_error:
        # ── FALLBACK: PyMuPDF text extraction + LLM re-parse ─────
        # Only applicable for PDFs with a digital text layer.
        # Images without a Gemini path have no fallback.
        if is_pdf:
            logger.warning(
                f"Gemini Multimodal failed for '{filename}': {gemini_error}. "
                f"Attempting PyMuPDF text fallback."
            )
            try:
                doc_text = extract_text_from_pdf(file_bytes)

                if len(doc_text.strip()) < 30:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            "Document produced too little text after fallback extraction. "
                            "It may be a scanned/image-only PDF with no text layer. "
                            "Gemini Multimodal also failed — please try a higher-resolution scan."
                        ),
                    )

                llm = get_llm(TaskType.FAST)
                result = extract_eob_fields(doc_text, llm)
                extraction_method = "pymupdf+llm_fallback"

                logger.info(
                    f"EOB parse fallback: '{filename}' extracted via PyMuPDF + LLM. "
                    f"{len(doc_text)} chars → LLM extraction"
                )

                if "error" in result:
                    raise HTTPException(
                        status_code=422,
                        detail=f"Fallback field extraction failed: {result['error']}",
                    )

            except HTTPException:
                raise
            except Exception as fallback_error:
                logger.error(
                    f"EOB parse: Both Gemini and PyMuPDF fallback failed "
                    f"for '{filename}': {fallback_error}"
                )
                raise HTTPException(
                    status_code=500,
                    detail=(
                        f"EOB extraction failed. Gemini error: {gemini_error}. "
                        f"Fallback error: {fallback_error}"
                    ),
                )
        else:
            # Image file — Gemini is the only path; no OCR fallback
            logger.error(
                f"Gemini Multimodal failed for image '{filename}': {gemini_error}"
            )
            raise HTTPException(
                status_code=500,
                detail=(
                    f"Image extraction failed: {gemini_error}. "
                    "Please ensure the image is clear, well-lit, and at least 300 DPI."
                ),
            )

    # ── Build the response ────────────────────────────────────────
    # Annotate with extraction metadata for the AI Transparency UI
    return {
        "success": True,
        "extracted": result,
        "extraction_method": extraction_method,
        "filename": filename,
        "file_size_kb": round(len(file_bytes) / 1024, 1),
        # Surface NSA-critical fields at top level for frontend awareness
        "nsa_signals": {
            "facility_network_status": result.get("facility_network_status"),
            "ancillary_service_type": result.get("ancillary_service_type"),
            "service_line_count": len(result.get("service_lines") or []),
            "nsa_risk": (
                result.get("facility_network_status") == "IN_NETWORK"
                and result.get("ancillary_service_type") is not None
            ),
        },
    }
