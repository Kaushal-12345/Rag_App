"""RagService behaviour with fake embedder / LLM / web search (no network, no models)."""

import pytest

from app.retrieval.web_search import WebResult
from app.schemas.api import HistoryMessage
from tests.fakes import FakeLLM, FakeWebSearcher, make_pdf
from tests.helpers import make_services


@pytest.fixture()
def indexed(tmp_path):
    pdf = make_pdf(tmp_path / "doc.pdf", ["Cats enjoy sleeping on warm windowsills.", "Bread needs flour and yeast."])
    services = make_services(tmp_path)
    _, pipeline, *_ = services
    pipeline.ingest_pdf(pdf, filename="doc.pdf", session_id="s1")
    return services


async def test_chat_returns_answer_and_page_citations(indexed) -> None:
    _, _, rag, *_ = indexed
    response = await rag.chat(session_id="s1", question="What do cats enjoy?")
    assert response.answer == "answer from model-a"
    assert response.model == "model-a"
    assert response.web_used is False
    assert response.sources and all(s.source == "doc.pdf" for s in response.sources)
    assert {s.page for s in response.sources} <= {1, 2}


async def test_unknown_model_falls_back_to_default(indexed) -> None:
    _, _, rag, *_ = indexed
    response = await rag.chat(session_id="s1", question="cats?", model="not-configured")
    assert response.model == "model-a"


async def test_missing_session_raises(indexed) -> None:
    _, _, rag, *_ = indexed
    with pytest.raises(FileNotFoundError):
        await rag.chat(session_id="nope", question="hi")


async def test_web_search_adds_labelled_section_and_web_citations(tmp_path) -> None:
    web = FakeWebSearcher([WebResult("Example", "https://example.test/a", "fresh fact")])
    _, pipeline, rag, _, llm, _ = make_services(tmp_path, web=web)
    pipeline.ingest_pdf(make_pdf(tmp_path / "d.pdf", ["alpha beta"]), filename="d.pdf", session_id="s1")

    response = await rag.chat(session_id="s1", question="alpha?", web_search=True)

    assert web.queries == ["alpha?"]
    assert response.web_used is True
    assert [s.source_type for s in response.sources].count("web") == 1
    assert "WEB CONTEXT:" in llm.calls[0]["user"]
    # and when the toggle is off, web search is never called
    await rag.chat(session_id="s1", question="alpha?", web_search=False)
    assert web.queries == ["alpha?"]
    assert "WEB CONTEXT:" not in llm.calls[1]["user"]


async def test_history_is_trimmed_and_forwarded(tmp_path) -> None:
    _, pipeline, rag, _, llm, _ = make_services(tmp_path, max_history_messages=2)
    pipeline.ingest_pdf(make_pdf(tmp_path / "d.pdf", ["alpha"]), filename="d.pdf", session_id="s1")
    history = [HistoryMessage(role="user" if i % 2 == 0 else "assistant", content=f"m{i}") for i in range(6)]
    await rag.chat(session_id="s1", question="alpha?", history=history)
    assert [h["content"] for h in llm.calls[0]["history"]] == ["m4", "m5"]


async def test_stream_events_order(indexed) -> None:
    _, _, rag, *_ = indexed
    events = [e async for e in rag.stream_events(session_id="s1", question="cats?", model="model-b")]
    types = [e["type"] for e in events]
    assert types[0] == "meta" and types[-1] == "done"
    assert set(types[1:-1]) == {"token"}
    assert "".join(e["text"] for e in events if e["type"] == "token").strip() == "answer from model-b"
    assert events[-1]["latency_ms"] >= 0


async def test_compare_streams_all_three_models(indexed) -> None:
    _, _, rag, *_ = indexed
    events = [e async for e in rag.compare_events(session_id="s1", question="cats?")]
    assert events[0]["type"] == "meta" and events[0]["models"] == ["model-a", "model-b", "model-c"]
    done = {e["model"] for e in events if e["type"] == "done"}
    assert done == {"model-a", "model-b", "model-c"}
    for model in done:
        text = "".join(e["text"] for e in events if e["type"] == "token" and e["model"] == model)
        assert text.strip() == f"answer from {model}"


async def test_compare_isolates_a_failing_model(tmp_path) -> None:
    _, pipeline, rag, *_ = make_services(tmp_path, llm=FakeLLM(fail_models={"model-b"}))
    pipeline.ingest_pdf(make_pdf(tmp_path / "d.pdf", ["alpha"]), filename="d.pdf", session_id="s1")
    events = [e async for e in rag.compare_events(session_id="s1", question="alpha?")]
    assert [e["model"] for e in events if e["type"] == "error"] == ["model-b"]
    assert {e["model"] for e in events if e["type"] == "done"} == {"model-a", "model-c"}
