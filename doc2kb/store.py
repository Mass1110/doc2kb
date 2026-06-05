"""ChromaDB persistence layer: add chunks, query, list documents."""
from __future__ import annotations

import chromadb
from chromadb.utils import embedding_functions

from .config import CHROMA_DIR, COLLECTION_NAME, EMBED_MODEL

# Module-level singletons so we can close them explicitly on reset.
_client: chromadb.PersistentClient | None = None
_col: chromadb.Collection | None = None


def _collection() -> chromadb.Collection:
    global _client, _col
    if _col is None:
        CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=EMBED_MODEL
        )
        _col = _client.get_or_create_collection(
            COLLECTION_NAME,
            embedding_function=ef,
            metadata={"hnsw:space": "cosine"},
        )
    return _col


def close() -> None:
    """Release the ChromaDB client and file handles (needed before deleting the dir)."""
    global _client, _col
    _col = None
    if _client is not None:
        # chromadb >=0.5 exposes __del__ / internal teardown; setting to None
        # drops the last reference so GC can close SQLite handles.
        _client = None


def doc_exists(doc_id: str) -> bool:
    results = _collection().get(where={"doc_id": doc_id}, limit=1)
    return bool(results["ids"])


def add_chunks(chunks: list[str], metadata: dict) -> None:
    col = _collection()
    ids = [f"{metadata['doc_id']}_chunk_{i}" for i in range(len(chunks))]
    metas = [
        {
            "doc_id": metadata["doc_id"],
            "source": metadata.get("source", ""),
            "title": metadata.get("title", ""),
            "type": metadata.get("type", "text"),
            "chunk_index": i,
        }
        for i in range(len(chunks))
    ]
    col.add(ids=ids, documents=chunks, metadatas=metas)


def query(text: str, n_results: int = 5) -> list[dict]:
    col = _collection()
    results = col.query(query_texts=[text], n_results=n_results)
    hits = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        hits.append({"text": doc, "score": round(1 - dist, 4), **meta})
    return hits


def delete_doc(doc_id: str) -> int:
    """Remove all chunks for *doc_id*. Returns the number of chunks deleted."""
    col = _collection()
    results = col.get(where={"doc_id": doc_id})
    ids = results["ids"]
    if ids:
        col.delete(ids=ids)
    return len(ids)


def list_documents() -> list[dict]:
    col = _collection()
    all_meta = col.get(include=["metadatas"])["metadatas"]
    seen: dict[str, dict] = {}
    for m in all_meta:
        doc_id = m.get("doc_id", "")
        if doc_id not in seen:
            seen[doc_id] = {
                "doc_id": doc_id,
                "title": m.get("title", ""),
                "source": m.get("source", ""),
                "type": m.get("type", ""),
            }
    return list(seen.values())
