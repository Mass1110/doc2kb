"""Tests for doc2kb.store — ChromaDB persistence layer."""
from __future__ import annotations

import pytest


META = {
    "doc_id": "sha256-testdoc12345678",
    "source": "https://example.com",
    "title": "Test Document",
    "type": "web",
}


class TestDocExists:
    def test_returns_false_when_absent(self, tmp_vault):
        from doc2kb import store
        assert store.doc_exists("sha256-doesnotexist") is False

    def test_returns_true_after_add(self, tmp_vault):
        from doc2kb import store
        store.add_chunks(["chunk one", "chunk two"], META)
        assert store.doc_exists(META["doc_id"]) is True


class TestAddChunks:
    def test_add_single_chunk(self, tmp_vault):
        from doc2kb import store
        store.add_chunks(["single chunk text"], META)
        docs = store.list_documents()
        assert any(d["doc_id"] == META["doc_id"] for d in docs)

    def test_add_multiple_chunks(self, tmp_vault):
        from doc2kb import store
        store.add_chunks(["chunk one", "chunk two", "chunk three"], META)
        docs = store.list_documents()
        assert len(docs) == 1

    def test_metadata_stored(self, tmp_vault):
        from doc2kb import store
        store.add_chunks(["content"], META)
        docs = store.list_documents()
        doc = next(d for d in docs if d["doc_id"] == META["doc_id"])
        assert doc["title"] == "Test Document"
        assert doc["source"] == "https://example.com"
        assert doc["type"] == "web"


class TestQuery:
    def test_query_returns_results(self, tmp_vault):
        from doc2kb import store
        store.add_chunks(["The quick brown fox jumps over the lazy dog"], META)
        results = store.query("fox", n_results=1)
        assert len(results) >= 1

    def test_query_result_has_required_keys(self, tmp_vault):
        from doc2kb import store
        store.add_chunks(["Sample document content for testing"], META)
        results = store.query("sample content", n_results=1)
        assert len(results) >= 1
        for key in ("text", "score", "doc_id", "source", "title", "type"):
            assert key in results[0]

    def test_query_score_is_float(self, tmp_vault):
        from doc2kb import store
        store.add_chunks(["Python programming language"], META)
        results = store.query("Python", n_results=1)
        # ChromaDB cosine distance is in [0, 2] → score = 1 - dist, range [-1, 1]
        assert isinstance(results[0]["score"], float)
        assert -1.0 <= results[0]["score"] <= 1.0

    def test_query_n_results_respected(self, tmp_vault):
        from doc2kb import store
        chunks = [f"chunk number {i} with unique content" for i in range(5)]
        store.add_chunks(chunks, META)
        results = store.query("chunk", n_results=3)
        assert len(results) <= 3


class TestDeleteDoc:
    def test_delete_removes_document(self, tmp_vault):
        from doc2kb import store
        store.add_chunks(["content to delete"], META)
        store.delete_doc(META["doc_id"])
        assert not store.doc_exists(META["doc_id"])

    def test_delete_returns_chunk_count(self, tmp_vault):
        from doc2kb import store
        store.add_chunks(["chunk A", "chunk B", "chunk C"], META)
        count = store.delete_doc(META["doc_id"])
        assert count == 3

    def test_delete_nonexistent_returns_zero(self, tmp_vault):
        from doc2kb import store
        count = store.delete_doc("sha256-doesnotexist1")
        assert count == 0

    def test_delete_does_not_affect_other_docs(self, tmp_vault):
        from doc2kb import store
        meta2 = {**META, "doc_id": "sha256-otherdoc12345"}
        store.add_chunks(["doc 1 content"], META)
        store.add_chunks(["doc 2 content"], meta2)
        store.delete_doc(META["doc_id"])
        docs = store.list_documents()
        assert any(d["doc_id"] == meta2["doc_id"] for d in docs)


class TestListDocuments:
    def test_empty_store_returns_empty_list(self, tmp_vault):
        from doc2kb import store
        assert store.list_documents() == []

    def test_lists_added_documents(self, tmp_vault):
        from doc2kb import store
        store.add_chunks(["content"], META)
        docs = store.list_documents()
        assert len(docs) == 1

    def test_deduplicates_chunks(self, tmp_vault):
        from doc2kb import store
        store.add_chunks(["chunk 1", "chunk 2", "chunk 3"], META)
        docs = store.list_documents()
        assert len(docs) == 1

    def test_multiple_documents(self, tmp_vault):
        from doc2kb import store
        meta2 = {**META, "doc_id": "sha256-second12345678", "title": "Second"}
        store.add_chunks(["content 1"], META)
        store.add_chunks(["content 2"], meta2)
        docs = store.list_documents()
        assert len(docs) == 2

    def test_document_fields_present(self, tmp_vault):
        from doc2kb import store
        store.add_chunks(["content"], META)
        doc = store.list_documents()[0]
        for field in ("doc_id", "title", "source", "type"):
            assert field in doc
