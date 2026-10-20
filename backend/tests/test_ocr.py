"""OCR fallback for scanned PDFs (skipped when Tesseract isn't installed)."""

import shutil
from pathlib import Path

import pymupdf as fitz
import pytest

from app.ingestion.pdf_loader import load_pdf

pytestmark = pytest.mark.skipif(shutil.which("tesseract") is None, reason="tesseract not installed")


def make_scanned_pdf(path: Path, text: str) -> Path:
    """A PDF whose only content is an image of text (no text layer)."""
    source = fitz.open()
    page = source.new_page()
    page.insert_text((72, 100), text, fontsize=24)
    pixmap = page.get_pixmap(dpi=150)
    scan = fitz.open()
    scan.new_page().insert_image(scan[0].rect, pixmap=pixmap)
    scan.save(path)
    return path


def test_scanned_page_is_empty_without_ocr_and_readable_with_it(tmp_path: Path) -> None:
    pdf = make_scanned_pdf(tmp_path / "scan.pdf", "Scanned invoice total 1845 dollars")
    plain = load_pdf(pdf, source="scan.pdf", source_id="x", session_id="s", ocr=False)
    assert plain[0].text.strip() == ""
    with_ocr = load_pdf(pdf, source="scan.pdf", source_id="x", session_id="s", ocr=True)
    assert "1845" in with_ocr[0].text
