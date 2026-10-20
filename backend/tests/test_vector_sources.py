"""Listing and deleting sources inside a collection."""

from pathlib import Path

from app.retrieval.vector_store import ChromaVectorStore


def _store_with_two_sources(tmp_path: Path) -> ChromaVectorStore:
    store = ChromaVectorStore(tmp_path / "chroma")
    store.upsert(
        collection="sess_demo",
        ids=["a_0", "a_1", "b_0"],
        documents=["pdf one", "pdf two", "video one"],
        embeddings=[[1.0, 0.0], [0.9, 0.1], [0.0, 1.0]],
        metadatas=[
            {"source": "notes.pdf", "source_id": "a", "source_type": "pdf", "page": 1},
            {"source": "notes.pdf", "source_id": "a", "source_type": "pdf", "page": 2},
            {"source": "Talk", "source_id": "b", "source_type": "youtube", "video_id": "dQw4w9WgXcQ"},
        ],
    )
    return store


def test_list_sources_groups_by_source(tmp_path: Path) -> None:
    sources = _store_with_two_sources(tmp_path).list_sources("sess_demo")
    by_id = {item["source_id"]: item for item in sources}
    assert by_id["a"]["chunks"] == 2 and by_id["a"]["source_type"] == "pdf"
    assert by_id["b"]["source_type"] == "youtube"
    assert by_id["b"]["url"] == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


def test_delete_source_removes_only_that_source(tmp_path: Path) -> None:
    store = _store_with_two_sources(tmp_path)
    assert store.delete_source("sess_demo", "a") == 2
    remaining = store.list_sources("sess_demo")
    assert [item["source_id"] for item in remaining] == ["b"]
    assert store.delete_source("sess_demo", "a") == 0


def test_missing_collection_is_empty(tmp_path: Path) -> None:
    store = ChromaVectorStore(tmp_path / "chroma")
    assert store.list_sources("sess_none") == []
    assert store.delete_source("sess_none", "x") == 0
