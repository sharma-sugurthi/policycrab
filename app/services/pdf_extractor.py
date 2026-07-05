"""
PDF Text Extractor — uses PyMuPDF (fitz) to extract text
from uploaded SBC/EOB PDF documents.

Handles multi-page documents and attempts to preserve
table structures common in insurance policy documents.
"""

import io
import logging

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """
    Extract all text from a PDF file's bytes.

    Uses PyMuPDF's text extraction which handles:
    - Multi-column layouts common in SBC documents
    - Tables with cost-sharing information
    - Headers, footers, and page numbers

    Args:
        pdf_bytes: Raw bytes of the PDF file.

    Returns:
        Concatenated text from all pages.

    Raises:
        ValueError: If the PDF cannot be opened or has no text.
    """
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as e:
        raise ValueError(f"Could not open PDF: {e}")

    if doc.page_count == 0:
        raise ValueError("PDF has no pages")

    all_text = []

    for page_num in range(doc.page_count):
        page = doc.load_page(page_num)
        text = page.get_text("text")
        if text.strip():
            all_text.append(f"--- Page {page_num + 1} ---\n{text.strip()}")

    doc.close()

    if not all_text:
        raise ValueError("PDF contains no extractable text (may be scanned/image-only)")

    full_text = "\n\n".join(all_text)

    logger.info(
        f"PDF extraction: {doc.page_count} pages, "
        f"{len(full_text)} characters extracted"
    )

    return full_text
