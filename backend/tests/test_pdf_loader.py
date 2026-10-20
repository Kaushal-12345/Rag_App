"""Unit tests for PDF page extraction."""

from pathlib import Path

import pytest

from app.ingestion.pdf_loader import load_pdf
from tests.fakes import make_pdf


def test_load_pdf_keeps_page_numbers(tmp_path: Path) -> None:
    path = make_pdf(
        tmp_path / "sample.pdf",
        ["First page talks about apples.", "Second page talks about oranges."],
    )
    pages = load_pdf(path, source="sample.pdf", source_id="abc", session_id="sess")
    assert len(pages) == 2
    assert pages[0].page == 1
    assert pages[1].page == 2
    assert "apples" in pages[0].text
    assert "oranges" in pages[1].text
    assert pages[0].source == "sample.pdf"
    assert pages[0].source_id == "abc"


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_pdf(tmp_path / "nope.pdf", source="nope.pdf", source_id="x", session_id="s")
