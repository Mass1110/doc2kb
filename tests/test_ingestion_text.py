"""Tests for doc2kb.ingestion.text — plain text and HTML ingestion."""
from __future__ import annotations

import pytest

from doc2kb.ingestion.text import ingest_text


class TestIngestText:
    def test_plain_text_returns_raw_content(self, tmp_path):
        f = tmp_path / "note.txt"
        f.write_text("Hello, world!", encoding="utf-8")
        md, meta = ingest_text(f)
        assert "Hello, world!" in md

    def test_metadata_keys_present(self, tmp_path):
        f = tmp_path / "doc.txt"
        f.write_text("content", encoding="utf-8")
        _, meta = ingest_text(f)
        for key in ("title", "source", "type", "date_ingested", "tags", "doc_id"):
            assert key in meta

    def test_metadata_type_is_text(self, tmp_path):
        f = tmp_path / "doc.txt"
        f.write_text("x", encoding="utf-8")
        _, meta = ingest_text(f)
        assert meta["type"] == "text"

    def test_metadata_title_is_stem(self, tmp_path):
        f = tmp_path / "my_document.txt"
        f.write_text("x", encoding="utf-8")
        _, meta = ingest_text(f)
        assert meta["title"] == "my_document"

    def test_metadata_source_is_absolute(self, tmp_path):
        f = tmp_path / "file.txt"
        f.write_text("x", encoding="utf-8")
        _, meta = ingest_text(f)
        assert meta["source"].startswith("/")

    def test_html_file_converted_to_markdown(self, tmp_path):
        f = tmp_path / "page.html"
        f.write_text(
            "<html><body><h1>My Title</h1><p>Body text.</p></body></html>",
            encoding="utf-8",
        )
        md, _ = ingest_text(f)
        assert "My Title" in md
        assert "Body text" in md

    def test_html_headings_use_atx_style(self, tmp_path):
        f = tmp_path / "page.html"
        f.write_text("<h1>Heading</h1>", encoding="utf-8")
        md, _ = ingest_text(f)
        assert "#" in md

    def test_htm_extension_also_converted(self, tmp_path):
        f = tmp_path / "page.htm"
        f.write_text("<p>Paragraph</p>", encoding="utf-8")
        md, _ = ingest_text(f)
        assert "Paragraph" in md

    def test_doc_id_stable(self, tmp_path):
        f = tmp_path / "stable.txt"
        f.write_text("stable content", encoding="utf-8")
        _, meta1 = ingest_text(f)
        _, meta2 = ingest_text(f)
        assert meta1["doc_id"] == meta2["doc_id"]

    def test_tags_empty_list(self, tmp_path):
        f = tmp_path / "file.txt"
        f.write_text("x", encoding="utf-8")
        _, meta = ingest_text(f)
        assert meta["tags"] == []

    def test_markdown_file_not_converted(self, tmp_path):
        content = "# Heading\n\nBody text."
        f = tmp_path / "note.md"
        f.write_text(content, encoding="utf-8")
        md, _ = ingest_text(f)
        # .md should be treated as plain text, not converted
        assert "# Heading" in md
