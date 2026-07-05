"""
PDF Text Extractor — uses PyMuPDF (fitz) to extract text
from uploaded SBC/EOB PDF documents.

Handles multi-page documents and attempts to preserve
table structures common in insurance policy documents.
"""

import io
import logging
import fitz  # PyMuPDF

try:
    from pdf2image import convert_from_bytes
    import pytesseract
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

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
    
    full_text = "\n\n".join(all_text)

    # ── Fallback to OCR if less than 50 characters were extracted ──
    if len(full_text.strip()) < 50:
        if not OCR_AVAILABLE:
            logger.warning("PDF has very little text and OCR dependencies are not installed.")
            raise ValueError("PDF contains no extractable text (may be scanned). Please install OCR dependencies or paste text manually.")
        
        logger.info("PDF contains very little text. Attempting Tesseract OCR fallback...")
        try:
            images = convert_from_bytes(pdf_bytes, dpi=200)
            ocr_text_list = []
            for i, img in enumerate(images):
                page_text = pytesseract.image_to_string(img)
                ocr_text_list.append(f"--- Page {i + 1} (OCR) ---\n{page_text.strip()}")
            full_text = "\n\n".join(ocr_text_list)
            
            if len(full_text.strip()) < 50:
                 raise ValueError("OCR extraction also yielded no meaningful text.")
        except Exception as e:
            logger.error(f"OCR fallback failed: {e}")
            raise ValueError("PDF contains no extractable text and OCR fallback failed. Please paste text manually.")

    logger.info(f"PDF extraction successful. {len(full_text)} characters extracted")

    return full_text
