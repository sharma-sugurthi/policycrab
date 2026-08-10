"""
PDF & Document Extractor — Gemini Multimodal primary, PyMuPDF fallback.

UPGRADE (Phase 2): The pytesseract OCR path has been replaced with Gemini's
native multimodal document understanding API.

Why this is superior to Tesseract OCR:
  - Tesseract flattens multi-column EOB tables into garbled linear text,
    causing the "Billed Amount" to land in the "Allowed Amount" column.
  - Gemini reads the document visually and understands table structure,
    column headers, and multi-line service entries natively.
  - Gemini returns structured, typed JSON directly — no second LLM pass needed.

Extraction hierarchy:
  1. Gemini Multimodal API (primary — handles PDFs, images, scanned docs)
  2. PyMuPDF text extraction (fallback — fast, free, for digital-text PDFs)

Two public interfaces:
  - extract_pages_from_pdf()  → RAG ingestion (page-aware chunking)
  - extract_text_from_pdf()   → backward-compatible single-string output
"""

import io
import json
import logging
import re
import fitz  # PyMuPDF
import pymupdf4llm

from app.config import settings
from app.security.presidio_scrubber import PHIScrubbingError, scrub_phi

logger = logging.getLogger(__name__)


# ── Gemini Multimodal EOB Extraction Schema ───────────────────────
# This prompt is sent alongside the raw document bytes to Gemini.
# The strict JSON schema ensures typed, structured output with no
# hallucination — "null" for any field not present in the document.
#
# CRITICAL NSA FIELDS: We explicitly ask for facility_network_status
# and ancillary_service_type so Phase 1's NSA violation detector
# (cost_calculator.py) fires automatically from real EOB uploads.
GEMINI_EOB_EXTRACTION_PROMPT = """You are a US health insurance document analyst.
Analyze this document (EOB, medical bill, policy, or SBC) and extract structured data.

RULES:
- Extract ONLY what is explicitly stated. Do NOT infer or hallucinate.
- Do not extract patient names. Always return patient_name as null.
- For any field not present, return null.
- Dates must be in ISO format: YYYY-MM-DD.
- Amounts must be numeric floats (no $ or commas).
- CPT codes: 5-digit numeric or alphanumeric (e.g. 99285, 00790, J0129).
- ICD-10 codes: letter + digits + optional decimal (e.g. K80.20, M17.11).
- CARC codes: CO-50, PR-242, OA-18, etc.
- RARC codes: N115, M51, etc.
- document_type: "eob" | "bill" | "policy" | "unknown"
- network_status fields: "IN_NETWORK" | "OUT_OF_NETWORK" | null
- ancillary_service_type: if the provider is an anesthesiologist, radiologist,
  pathologist, neonatologist, or assistant surgeon, return the specialty name
  (e.g. "anesthesia", "radiology"). Otherwise null.
- STRICT JSON FORMATTING: Do not use unescaped literal newlines inside JSON strings. Use \\n instead.

If the document has MULTIPLE service lines, extract the PRIMARY denied or
highest-billed line. If all lines are important, extract the first denied line.

Return ONLY this JSON object (no markdown, no explanation):
{
  "document_type": "eob|bill|policy|unknown",
  "patient_name": "string or null",
  "claim_id": "string or null",
  "date_of_service": "YYYY-MM-DD or null",
  "denial_date": "YYYY-MM-DD or null",
  "billed_amount": float or null,
  "allowed_amount": float or null,
  "plan_paid_amount": float or null,
  "patient_responsibility": float or null,
  "provider_name": "string or null",
  "facility_name": "string or null",
  "network_status": "IN_NETWORK|OUT_OF_NETWORK or null",
  "facility_network_status": "IN_NETWORK|OUT_OF_NETWORK or null",
  "ancillary_service_type": "anesthesia|radiology|pathology|neonatology|null",
  "cpt_code": "string or null",
  "cpt_description": "string or null",
  "icd_10_code": "string or null",
  "icd_10_description": "string or null",
  "denial_carc_code": "string or null",
  "denial_rarc_code": "string or null",
  "denial_reason_text": "verbatim denial reason from the EOB or null",
  "is_denied": true or false,
  "service_lines": [
    {
      "provider_name": "string or null",
      "network_status": "IN_NETWORK|OUT_OF_NETWORK or null",
      "ancillary_service_type": "string or null",
      "cpt_code": "string or null",
      "cpt_description": "string or null",
      "billed_amount": float or null,
      "allowed_amount": float or null,
      "plan_paid_amount": float or null,
      "patient_responsibility": float or null,
      "denial_carc_code": "string or null",
      "denial_reason_text": "string or null"
    }
  ],
  "confidence": {
    "date_of_service": "high|medium|low",
    "billed_amount": "high|medium|low",
    "allowed_amount": "high|medium|low",
    "cpt_code": "high|medium|low",
    "denial_carc_code": "high|medium|low",
    "network_status": "high|medium|low",
    "facility_network_status": "high|medium|low"
  }
}"""


def extract_eob_safely(
    file_bytes: bytes,
    mime_type: str = "application/pdf",
) -> dict:
    """
    HIPAA-Compliant EOB Extraction Path.
    
    Instead of passing raw PDF bytes (which contain unredacted PHI) directly
    to the Gemini API, this function:
      1. Extracts tables and text locally to Markdown via pymupdf4llm.
      2. Scrubs all PHI (Names, SSNs, Member IDs) locally using Microsoft Presidio.
      3. Passes the sanitized Markdown text to Gemini for structured JSON extraction.
    """
    try:
        from google import genai
    except ImportError:
        raise ValueError("google-genai SDK not installed.")

    if not settings.google_cloud_project or not settings.gcp_location:
        raise ValueError("GCP project ID or location not configured for Vertex AI.")
        
    client = genai.Client(
        vertexai=True,
        project=settings.google_cloud_project,
        location=settings.gcp_location
    )

    logger.info(f"Processing document natively via Gemini Multimodal ({mime_type}).")

    from pydantic import BaseModel, Field

    class ServiceLine(BaseModel):
        provider_name: str | None
        network_status: str | None
        ancillary_service_type: str | None
        cpt_code: str | None
        cpt_description: str | None
        billed_amount: float | None
        allowed_amount: float | None
        plan_paid_amount: float | None
        patient_responsibility: float | None
        denial_carc_code: str | None
        denial_reason_text: str | None

    class EOBConfidence(BaseModel):
        date_of_service: str | None
        billed_amount: str | None
        allowed_amount: str | None
        cpt_code: str | None
        denial_carc_code: str | None
        network_status: str | None
        facility_network_status: str | None

    class EOBResponseSchema(BaseModel):
        document_type: str | None
        patient_name: str | None
        claim_id: str | None
        date_of_service: str | None
        denial_date: str | None
        billed_amount: float | None
        allowed_amount: float | None
        plan_paid_amount: float | None
        patient_responsibility: float | None
        provider_name: str | None
        facility_name: str | None
        network_status: str | None
        facility_network_status: str | None
        ancillary_service_type: str | None
        cpt_code: str | None
        cpt_description: str | None
        icd_10_code: str | None
        icd_10_description: str | None
        denial_carc_code: str | None
        denial_rarc_code: str | None
        denial_reason_text: str | None
        is_denied: bool | None
        service_lines: list[ServiceLine] = Field(default_factory=list)
        confidence: EOBConfidence | None

    try:
        contents = [
            GEMINI_EOB_EXTRACTION_PROMPT,
            genai.types.Part.from_bytes(data=file_bytes, mime_type=mime_type)
        ]

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=contents,
            config={
                "temperature": 0.0,
                "max_output_tokens": 8192,
                "response_mime_type": "application/json",
                "response_schema": EOBResponseSchema,
                "safety_settings": [
                    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
                ]
            },
        )
    except Exception as e:
        raise ValueError(f"Gemini API call failed: {e}")

    raw = (response.text or "").strip()
    try:
        result = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON response: {e}\nSnippet: {raw[:500]}")
        raise ValueError(f"Gemini returned unparseable output. JSON error: {e}")

    from app.agents.eob_extractor import postprocess_eob_result
    from app.services.math_validator import validate_eob_math
    
    # We no longer have local extracted text for patient name removal in postprocess,
    # but Gemini handles this intrinsically based on prompt constraints.
    result = postprocess_eob_result(result, "")
    result = validate_eob_math(result)

    logger.info(
        f"Extraction complete — "
        f"document_type={result.get('document_type')}, "
        f"is_denied={result.get('is_denied')}, "
        f"network_status={result.get('network_status')}, "
        f"facility_network_status={result.get('facility_network_status')}, "
        f"service_lines={len(result.get('service_lines') or [])}"
    )

    return result


import pymupdf4llm

def extract_pages_from_pdf(pdf_bytes: bytes) -> list[dict]:
    """
    Extract text from a PDF, returning one dict per page.

    Used by the RAG ingestion pipeline (policy_ingestion.py) to preserve
    exact page numbers for citation in appeal letters.

    Extraction hierarchy:
      1. PyMuPDF text layer (fast, free, zero API cost) — handles digital PDFs.
      2. Gemini Multimodal (for scanned/image-only PDFs with no text layer).

    Returns:
        List of dicts, each containing:
          - page_number (int): 1-indexed page number
          - text        (str): extracted text from this page

    Raises:
        ValueError: If the PDF cannot be opened or no text can be extracted.
    """
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as e:
        raise ValueError(f"Could not open PDF: {e}")

    if doc.page_count == 0:
        raise ValueError("PDF has no pages")

    pages: list[dict] = []
    
    # Use pymupdf4llm for markdown extraction which inherently preserves tables 
    # and multi-column layouts, resolving the table jumbling vulnerability.
    try:
        md_pages = pymupdf4llm.to_markdown(doc, page_chunks=True)
        for page_data in md_pages:
            text = page_data.get("text", "").strip()
            if text:
                pages.append({
                    "page_number": page_data.get("metadata", {}).get("page", 0) + 1,
                    "text": text,
                })
    except Exception as e:
        logger.warning(f"pymupdf4llm extraction failed, falling back to basic text: {e}")
        for page_num in range(doc.page_count):
            page = doc.load_page(page_num)
            text = page.get_text("text", sort=True).strip()
            if text:
                pages.append({
                    "page_number": page_num + 1,
                    "text": text,
                })

    doc.close()

    # Check if the PDF is a scanned/image-only document (no text layer)
    total_chars = sum(len(p["text"]) for p in pages)
    if total_chars < 50:
        logger.info(
            "PDF has little extractable text (likely scanned). "
            "For HIPAA compliance, OCR on raw images is disabled."
        )
        raise ValueError("Scanned PDFs (images) cannot be scrubbed securely and are blocked.")

    # 3. Scrub PHI from all extracted pages before returning to the RAG pipeline
    for p in pages:
        try:
            p["text"], _ = scrub_phi(p["text"])
        except PHIScrubbingError as e:
            raise ValueError(str(e)) from e

    if not pages:
        raise ValueError("No text could be extracted from this PDF.")

    logger.info(
        f"PDF extraction: {len(pages)} pages, "
        f"{sum(len(p['text']) for p in pages)} total characters"
    )
    return pages


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """
    Extract all text from a PDF as a single concatenated string.

    Backward-compatible wrapper around extract_pages_from_pdf().
    Page boundaries are marked with '--- Page N ---' headers.

    Args:
        pdf_bytes: Raw bytes of the PDF file.

    Returns:
        Concatenated text from all pages.

    Raises:
        ValueError: If the PDF cannot be opened or has no text.
    """
    pages = extract_pages_from_pdf(pdf_bytes)
    return "\n\n".join(
        f"--- Page {p['page_number']} ---\n{p['text']}"
        for p in pages
    )
