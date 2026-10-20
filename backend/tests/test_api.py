"""HTTP-level tests with the real routers and fake embedder/LLM/web search."""

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes_chat import router as chat_router
from app.api.routes_ingest import router as ingest_router
from app.api.routes_sources import router as sources_router
from app.utils.rate_limit import RateLimitMiddleware
from tests.fakes import make_pdf
from tests.helpers import make_services


def build_client(tmp_path, *, rate_limit: int | None = None, **settings) -> tuple[TestClient, object]:
    settings_obj, pipeline, rag, store, llm, web = make_services(tmp_path, **settings)
    app = FastAPI()
    if rate_limit:
        app.add_middleware(RateLimitMiddleware, per_minute=rate_limit)
    app.include_router(ingest_router)
    app.include_router(chat_router)
    app.include_router(sources_router)
    app.state.settings = settings_obj
    app.state.pipeline = pipeline
    app.state.rag_service = rag
    app.state.vector_store = store
    return TestClient(app), settings_obj


def sse_events(response) -> list[dict]:
    events = []
    for block in response.text.split("\n\n"):
        block = block.strip()
        if block.startswith("data:"):
            events.append(json.loads(block[5:].strip()))
    return events


@pytest.fixture()
def client(tmp_path):
    test_client, _ = build_client(tmp_path)
    return test_client


@pytest.fixture()
def pdf_bytes(tmp_path) -> bytes:
    return make_pdf(tmp_path / "x.pdf", ["Cats enjoy sleeping on warm windowsills.", "Bread needs flour."]).read_bytes()


def upload(client, pdf_bytes, session="s1", name="notes.pdf"):
    return client.post("/ingest/pdf", files={"file": (name, pdf_bytes, "application/pdf")}, data={"session_id": session})


def test_models_endpoint(client) -> None:
    body = client.get("/models").json()
    assert body["models"] == ["model-a", "model-b", "model-c"]
    assert body["default"] == "model-a"


def test_ingest_then_chat_flow(client, pdf_bytes) -> None:
    ingested = upload(client, pdf_bytes)
    assert ingested.status_code == 200
    assert ingested.json()["pages"] == 2 and ingested.json()["source_type"] == "pdf"

    chat = client.post("/chat", json={"session_id": "s1", "question": "What do cats enjoy?"})
    assert chat.status_code == 200
    assert chat.json()["answer"] == "answer from model-a"
    assert chat.json()["sources"][0]["source"] == "notes.pdf"


def test_chat_unknown_session_is_404(client) -> None:
    response = client.post("/chat", json={"session_id": "ghost", "question": "hi"})
    assert response.status_code == 404


def test_chat_stream_sse(client, pdf_bytes) -> None:
    upload(client, pdf_bytes)
    response = client.post("/chat/stream", json={"session_id": "s1", "question": "cats?", "model": "model-c"})
    assert response.headers["content-type"].startswith("text/event-stream")
    events = sse_events(response)
    assert events[0]["type"] == "meta" and events[0]["model"] == "model-c"
    assert events[-1] == {"type": "end"}
    assert any(e["type"] == "done" for e in events)


def test_chat_stream_reports_missing_session_as_event(client) -> None:
    events = sse_events(client.post("/chat/stream", json={"session_id": "ghost", "question": "hi"}))
    assert events[0]["type"] == "error" and "No indexed documents" in events[0]["message"]


def test_compare_sse(client, pdf_bytes) -> None:
    upload(client, pdf_bytes)
    events = sse_events(client.post("/chat/compare", json={"session_id": "s1", "question": "cats?"}))
    assert {e["model"] for e in events if e["type"] == "done"} == {"model-a", "model-b", "model-c"}


def test_sources_listing_and_delete(client, pdf_bytes) -> None:
    source_id = upload(client, pdf_bytes).json()["source_id"]
    listing = client.get("/sources", params={"session_id": "s1"}).json()
    assert [s["source_id"] for s in listing["sources"]] == [source_id]

    assert client.delete(f"/sources/{source_id}", params={"session_id": "s1"}).status_code == 200
    assert client.delete(f"/sources/{source_id}", params={"session_id": "s1"}).status_code == 404
    assert client.get("/sources", params={"session_id": "s1"}).json()["sources"] == []


def test_delete_session_removes_files(client, pdf_bytes, tmp_path) -> None:
    upload(client, pdf_bytes)
    assert (tmp_path / "uploads" / "s1" / "notes.pdf").exists()
    assert client.delete("/sessions/s1").status_code == 200
    assert not (tmp_path / "uploads" / "s1").exists()
    assert client.post("/chat", json={"session_id": "s1", "question": "hi"}).status_code == 404


def test_swagger_placeholder_session_gets_a_fresh_id(client, pdf_bytes) -> None:
    body = upload(client, pdf_bytes, session="string").json()
    assert body["session_id"] != "string" and len(body["session_id"]) >= 16


def test_path_traversal_in_session_id_is_neutralised(client, pdf_bytes, tmp_path) -> None:
    response = upload(client, pdf_bytes, session="../../evil")
    assert response.status_code == 200
    assert response.json()["session_id"] == "evil"  # slashes stripped
    assert not (tmp_path.parent / "evil").exists()
    assert (tmp_path / "uploads" / "evil" / "notes.pdf").exists()


def test_rejects_non_pdf_and_fake_pdf(client) -> None:
    assert upload(client, b"hello", name="a.txt").status_code == 400
    assert upload(client, b"not really a pdf", name="a.pdf").status_code == 400
    assert upload(client, b"", name="a.pdf").status_code == 400


def test_upload_size_limit(tmp_path, pdf_bytes) -> None:
    small, _ = build_client(tmp_path, max_upload_mb=1)
    big = b"%PDF-1.4\n" + b"0" * (1024 * 1024 + 10)
    assert upload(small, big).status_code == 413


def test_ingest_youtube_errors_become_400(client) -> None:
    response = client.post("/ingest/youtube", json={"url": "https://example.com/video"})
    assert response.status_code == 400
    assert "valid YouTube" in response.json()["detail"]


def test_ingest_youtube_happy_path(tmp_path, monkeypatch) -> None:
    from app.ingestion import pipeline as pipeline_module
    from app.ingestion.youtube_loader import TranscriptWindow

    monkeypatch.setattr(
        pipeline_module,
        "fetch_windows",
        lambda url, **kwargs: ("dQw4w9WgXcQ", [TranscriptWindow("welcome to the cat video", 0.0, 30.0), TranscriptWindow("bread recipe", 30.0, 60.0)]),
    )
    monkeypatch.setattr(pipeline_module, "fetch_title", lambda video_id: "Cat Video")
    test_client, _ = build_client(tmp_path)

    ingested = test_client.post("/ingest/youtube", json={"url": "https://youtu.be/dQw4w9WgXcQ", "session_id": "yt1"}).json()
    assert ingested["source_type"] == "youtube" and ingested["filename"] == "Cat Video" and ingested["chunks"] == 2

    chat = test_client.post("/chat", json={"session_id": "yt1", "question": "cat video"}).json()
    youtube_sources = [s for s in chat["sources"] if s["source_type"] == "youtube"]
    assert youtube_sources and youtube_sources[0]["url"].startswith("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=")
    assert youtube_sources[0]["start_seconds"] in (0.0, 30.0)


def test_rate_limit_returns_429(tmp_path) -> None:
    limited, _ = build_client(tmp_path, rate_limit=2)
    body = {"session_id": "ghost", "question": "hi"}
    assert limited.post("/chat", json=body).status_code == 404
    assert limited.post("/chat", json=body).status_code == 404
    third = limited.post("/chat", json=body)
    assert third.status_code == 429 and third.headers["retry-after"] == "60"
    assert limited.get("/models").status_code == 200  # GETs are not limited
