"""PDF text extraction with page-level metadata."""

from __future__ import annotations

import logging
from pathlib import Path

import pymupdf as fitz

from app.schemas.documents import PageDocument

logger = logging.getLogger(__name__)


def _ocr_page(page: "fitz.Page") -> str:
    """OCR one page with PyMuPDF's Tesseract integration. Empty string on any failure."""
    try:
        textpage = page.get_textpage_ocr(language="eng", dpi=200, full=True)
        return page.get_text("text", textpage=textpage) or ""
    except Exception as exc:  # tesseract missing, language data missing, etc.
        logger.warning("OCR unavailable (%s)", exc)
        return ""


def load_pdf(
    path: Path,
    *,
    source: str,
    source_id: str,
    session_id: str,
    ocr: bool = False,
) -> list[PageDocument]:
    """Extract text from each PDF page, preserving page numbers.

    Args:
        path: Path to a PDF file.
        source: Display name (usually the original filename).
        source_id: Stable id for this uploaded document.
        session_id: Collection / session this document belongs to.

    Returns:
        One PageDocument per page, including blank pages (empty text).
        With ``ocr=True``, pages without a text layer are OCR'd when Tesseract is installed.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file is not a readable PDF.
    """
    if not path.is_file():
        raise FileNotFoundError(f"PDF not found: {path}")

    try:
        document = fitz.open(path)
    except Exception as exc:  # pymupdf raises mixed exception types
        raise ValueError(f"Unable to open PDF '{path.name}': {exc}") from exc

    pages: list[PageDocument] = []
    try:
        if document.page_count == 0:
            raise ValueError(f"PDF '{path.name}' has no pages")
        for index, page in enumerate(document):
            text = page.get_text("text") or ""
            if ocr and not text.strip():
                text = _ocr_page(page)
            pages.append(
                PageDocument(
                    source=source,
                    page=index + 1,
                    text=text,
                    source_id=source_id,
                    session_id=session_id,
                )
            )
    finally:
        document.close()

    nonempty = sum(1 for page in pages if page.text.strip())
    logger.info(
        "Extracted %s page(s) from %s (%s with text)",
        len(pages),
        source,
        nonempty,
    )
    return pages
