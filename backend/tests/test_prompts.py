"""Prompt assembly: labels, separate document/web sections."""

from app.llm.prompts import build_user_prompt, format_timestamp
from app.retrieval.web_search import WebResult
from app.schemas.documents import RetrievedChunk


def chunk(text: str, **meta) -> RetrievedChunk:
    return RetrievedChunk(id="c1", text=text, metadata=meta, score=0.9)


def test_format_timestamp() -> None:
    assert format_timestamp(0) == "0:00"
    assert format_timestamp(754) == "12:34"
    assert format_timestamp(3725) == "1:02:05"


def test_pdf_and_video_labels() -> None:
    prompt = build_user_prompt(
        "q?",
        [
            chunk("pdf text", source="a.pdf", page=3, source_type="pdf"),
            chunk("video text", source="My Talk", source_type="youtube", start_seconds=754.0),
        ],
    )
    assert "file=a.pdf page=3" in prompt
    assert "video=My Talk @ 12:34" in prompt
    assert "None" not in prompt
    assert "WEB CONTEXT" not in prompt


def test_web_section_is_separate_and_optional() -> None:
    with_web = build_user_prompt("q?", [], [WebResult("Site", "https://x.test", "web body")])
    assert "DOCUMENT CONTEXT:\n\n(no matching passages)" in with_web
    assert "WEB CONTEXT:" in with_web and "web: Site" in with_web
    empty_web = build_user_prompt("q?", [], [])
    assert "(web search returned nothing)" in empty_web
