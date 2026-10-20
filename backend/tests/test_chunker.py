"""Unit tests for token chunking and metadata preservation."""

from app.ingestion.chunker import chunk_pages, count_tokens
from app.schemas.documents import PageDocument


def _page(text: str, page: int = 1) -> PageDocument:
    return PageDocument(
        source="guide.pdf",
        page=page,
        text=text,
        source_id="src1",
        session_id="sess1",
    )


def test_count_tokens_splits_on_whitespace() -> None:
    assert count_tokens("one two three") == 3
    assert count_tokens("  ") == 0


def test_empty_pages_produce_no_chunks() -> None:
    assert chunk_pages([_page("   ")], chunk_size=10, overlap=2) == []


def test_short_page_is_single_chunk() -> None:
    chunks = chunk_pages([_page("Hello world.")], chunk_size=50, overlap=5)
    assert len(chunks) == 1
    assert chunks[0].text == "Hello world."
    assert chunks[0].metadata["source"] == "guide.pdf"
    assert chunks[0].metadata["page"] == 1
    assert chunks[0].metadata["source_id"] == "src1"


def test_long_page_splits_and_keeps_page_metadata() -> None:
    words = [f"word{i}" for i in range(25)]
    chunks = chunk_pages([_page(" ".join(words))], chunk_size=10, overlap=2)
    assert len(chunks) > 1
    assert all(chunk.metadata["page"] == 1 for chunk in chunks)
    joined = " ".join(chunk.text for chunk in chunks)
    assert "word0" in joined
    assert "word24" in joined


def test_overlap_repeats_trailing_tokens() -> None:
    words = [f"t{i}" for i in range(18)]
    chunks = chunk_pages([_page(" ".join(words))], chunk_size=8, overlap=3)
    assert len(chunks) >= 2
    first_tail = chunks[0].text.split()[-3:]
    second_head = chunks[1].text.split()[:3]
    assert first_tail == second_head


def test_pages_are_not_merged() -> None:
    pages = [
        _page("Alpha content on page one.", page=1),
        _page("Beta content on page two.", page=2),
    ]
    chunks = chunk_pages(pages, chunk_size=50, overlap=5)
    assert {chunk.metadata["page"] for chunk in chunks} == {1, 2}
    page_one = next(chunk for chunk in chunks if chunk.metadata["page"] == 1)
    assert "Alpha" in page_one.text
    assert "Beta" not in page_one.text


def test_invalid_sizes_raise() -> None:
    page = _page("hello")
    try:
        chunk_pages([page], chunk_size=10, overlap=10)
        assert False, "expected ValueError"
    except ValueError:
        pass
