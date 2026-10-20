"""Unit tests for vector upsert and nearest-neighbor retrieval."""

from pathlib import Path

from app.retrieval.vector_store import ChromaVectorStore


def test_query_returns_nearest_document(tmp_path: Path) -> None:
    store = ChromaVectorStore(tmp_path / "chroma")
    docs = [
        "Cats enjoy sleeping on warm windowsills.",
        "Quantum physics describes subatomic particles.",
        "Baking bread needs flour, water, yeast, and salt.",
    ]
    store.upsert(
        collection="sess_testcollection",
        ids=["a", "b", "c"],
        documents=docs,
        embeddings=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        metadatas=[
            {"source": "pets.pdf", "page": 1},
            {"source": "science.pdf", "page": 2},
            {"source": "food.pdf", "page": 3},
        ],
    )

    results = store.query(
        collection="sess_testcollection",
        query_embedding=[1.0, 0.0, 0.0],
        top_k=2,
    )
    assert results
    assert "Cats" in results[0].text
    assert results[0].metadata["source"] == "pets.pdf"
    assert results[0].metadata["page"] == 1
    assert results[0].score >= results[1].score


def test_missing_collection_returns_empty(tmp_path: Path) -> None:
    store = ChromaVectorStore(tmp_path / "chroma")
    results = store.query(
        collection="sess_missing",
        query_embedding=[0.1, 0.2, 0.3],
        top_k=3,
    )
    assert results == []


def test_upsert_length_mismatch_raises(tmp_path: Path) -> None:
    store = ChromaVectorStore(tmp_path / "chroma")
    try:
        store.upsert(
            collection="sess_bad",
            ids=["a"],
            documents=["one", "two"],
            embeddings=[[0.0, 1.0]],
            metadatas=[{"page": 1}],
        )
        assert False, "expected ValueError"
    except ValueError:
        pass
