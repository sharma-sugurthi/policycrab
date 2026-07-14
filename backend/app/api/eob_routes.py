"""
EOB API Routes — parse Explanation of Benefits documents.

Accepts:
  - PDF files  → text extracted via PyMuPDF
  - Image files (JPG, PNG, TIFF, WEBP) → text extracted via pytesseract OCR
  - Max 10 MB per file

Returns structured EOB fields with per-field confidence levels and
a document_type classification (eob | bill | policy | unknown).
"""

import logging
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File

from app.api.auth import get_current_user
from app.security.rate_limit import rate_limit_user
from app.services.llm_router import get_llm, TaskType
from app.agents.eob_extractor import extract_eob_fields

logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

ACCEPTED_PDF_TYPES = {"application/pdf", "pdf"}
ACCEPTED_IMAGE_TYPES = {
    "image/jpeg", "image/jpg", "image/png",
    "image/tiff", "image/webp", "image/bmp",
}

# Per-user: 10 EOB parses per hour
EOB_PARSE_RATE_LIMIT = rate_limit_user("eob:parse", max_requests=10, window_seconds=3600)

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


def extract_text_from_image(image_bytes: bytes) -> str:
    """Extract text from an image using pytesseract OCR."""
    try:
        import pytesseract
        from PIL import Image
        import io

        image = Image.open(io.BytesIO(image_bytes))

        # Convert to RGB if needed (handles RGBA, palette modes, etc.)
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")

        # Use english + a config tuned for documents
        text = pytesseract.image_to_string(
            image,
            lang="eng",
            config="--psm 6 --oem 3",
        )
        return text
    except Exception as e:
        raise ValueError(f"Failed to extract text from image via OCR: {e}")


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


@router.post("/parse")
async def parse_eob(
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
    _: None = Depends(EOB_PARSE_RATE_LIMIT),
):
    """
    Upload an EOB, medical bill, or policy document (PDF or image) and
    extract structured claim fields with per-field confidence scores.

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

    # ── Read and validate size ────────────────────────────────
    file_bytes = await file.read()

    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large ({len(file_bytes) / 1024 / 1024:.1f} MB). Maximum is 10 MB.",
        )

    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    # ── Extract text ──────────────────────────────────────────
    try:
        if is_pdf:
            doc_text = extract_text_from_pdf(file_bytes)
            extraction_method = "pymupdf"
        else:
            doc_text = extract_text_from_image(file_bytes)
            extraction_method = "pytesseract_ocr"
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if len(doc_text.strip()) < 30:
        raise HTTPException(
            status_code=400,
            detail=(
                "Document produced too little text. "
                + ("It may be a scanned/image-only PDF — try uploading the image file directly." if is_pdf else
                   "The image may be too blurry or low-resolution for OCR. Try a clearer scan.")
            ),
        )

    logger.info(
        f"EOB parse: '{filename}' ({extraction_method}), "
        f"{len(file_bytes)} bytes → {len(doc_text)} chars extracted"
    )

    # ── Run LLM extraction ────────────────────────────────────
    try:
        llm = get_llm(TaskType.FAST)
        result = extract_eob_fields(doc_text, llm)

        if "error" in result:
            raise HTTPException(
                status_code=422,
                detail=f"Field extraction failed: {result['error']}",
            )

        return {
            "success": True,
            "extracted": result,
            "char_count": len(doc_text),
            "extraction_method": extraction_method,
            "filename": filename,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"EOB parse endpoint error: {e}")
        raise HTTPException(status_code=500, detail=f"EOB parsing failed: {str(e)}")
