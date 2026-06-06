"""Tests for doc2kb.ingestion.web — URL ingestion with trafilatura."""
from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest

from doc2kb.ingestion.web import ingest_web


class TestIngestWeb:
    def _make_meta(self, title="Page Title"):
        m = MagicMock()
        m.title = title
        return m

    def test_raises_on_fetch_failure(self):
        with patch("doc2kb.ingestion.web.trafilatura.fetch_url", return_value=None):
            with pytest.raises(ValueError, match="Could not fetch"):
                ingest_web("https://example.com")

    def test_raises_on_extract_failure(self):
        with patch("doc2kb.ingestion.web.trafilatura.fetch_url", return_value="<html>"):
            with patch("doc2kb.ingestion.web.trafilatura.extract", return_value=None):
                with pytest.raises(ValueError, match="Could not extract"):
                    ingest_web("https://example.com")

    def test_returns_tuple(self):
        with patch("doc2kb.ingestion.web.trafilatura.fetch_url", return_value="<html>"):
            with patch("doc2kb.ingestion.web.trafilatura.extract", return_value="Content"):
                with patch("doc2kb.ingestion.web.trafilatura.extract_metadata", return_value=self._make_meta()):
                    result = ingest_web("https://example.com")
                    assert isinstance(result, tuple)
                    assert len(result) == 2

    def test_metadata_type_is_web(self):
        with patch("doc2kb.ingestion.web.trafilatura.fetch_url", return_value="<html>"):
            with patch("doc2kb.ingestion.web.trafilatura.extract", return_value="Content"):
                with patch("doc2kb.ingestion.web.trafilatura.extract_metadata", return_value=self._make_meta()):
                    _, meta = ingest_web("https://example.com")
                    assert meta["type"] == "web"

    def test_metadata_source_is_url(self):
        url = "https://example.com/article"
        with patch("doc2kb.ingestion.web.trafilatura.fetch_url", return_value="<html>"):
            with patch("doc2kb.ingestion.web.trafilatura.extract", return_value="Content"):
                with patch("doc2kb.ingestion.web.trafilatura.extract_metadata", return_value=self._make_meta()):
                    _, meta = ingest_web(url)
                    assert meta["source"] == url

    def test_metadata_title_from_trafilatura(self):
        with patch("doc2kb.ingestion.web.trafilatura.fetch_url", return_value="<html>"):
            with patch("doc2kb.ingestion.web.trafilatura.extract", return_value="Content"):
                with patch("doc2kb.ingestion.web.trafilatura.extract_metadata", return_value=self._make_meta("My Article")):
                    _, meta = ingest_web("https://example.com")
                    assert meta["title"] == "My Article"

    def test_metadata_title_falls_back_to_netloc(self):
        with patch("doc2kb.ingestion.web.trafilatura.fetch_url", return_value="<html>"):
            with patch("doc2kb.ingestion.web.trafilatura.extract", return_value="Content"):
                with patch("doc2kb.ingestion.web.trafilatura.extract_metadata", return_value=None):
                    _, meta = ingest_web("https://example.com/page")
                    assert "example.com" in meta["title"]

    def test_doc_id_starts_with_sha256(self):
        with patch("doc2kb.ingestion.web.trafilatura.fetch_url", return_value="<html>"):
            with patch("doc2kb.ingestion.web.trafilatura.extract", return_value="Content"):
                with patch("doc2kb.ingestion.web.trafilatura.extract_metadata", return_value=self._make_meta()):
                    _, meta = ingest_web("https://example.com")
                    assert meta["doc_id"].startswith("sha256-")

    def test_same_url_same_doc_id(self):
        url = "https://example.com/stable"
        with patch("doc2kb.ingestion.web.trafilatura.fetch_url", return_value="<html>"):
            with patch("doc2kb.ingestion.web.trafilatura.extract", return_value="Content"):
                with patch("doc2kb.ingestion.web.trafilatura.extract_metadata", return_value=self._make_meta()):
                    _, meta1 = ingest_web(url)
                    _, meta2 = ingest_web(url)
                    assert meta1["doc_id"] == meta2["doc_id"]

    def test_content_returned(self):
        with patch("doc2kb.ingestion.web.trafilatura.fetch_url", return_value="<html>"):
            with patch("doc2kb.ingestion.web.trafilatura.extract", return_value="Article content here"):
                with patch("doc2kb.ingestion.web.trafilatura.extract_metadata", return_value=self._make_meta()):
                    text, _ = ingest_web("https://example.com")
                    assert "Article content here" == text

    def test_tags_empty_list(self):
        with patch("doc2kb.ingestion.web.trafilatura.fetch_url", return_value="<html>"):
            with patch("doc2kb.ingestion.web.trafilatura.extract", return_value="Content"):
                with patch("doc2kb.ingestion.web.trafilatura.extract_metadata", return_value=self._make_meta()):
                    _, meta = ingest_web("https://example.com")
                    assert meta["tags"] == []
