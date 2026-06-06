"""Tests for doc2kb.markdown_writer — Obsidian vault note management."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import frontmatter
import pytest

from doc2kb.markdown_writer import save_note, delete_note, regenerate_index


SAMPLE_META = {
    "title": "Test Note",
    "source": "https://example.com",
    "type": "web",
    "date_ingested": "2024-01-01T12:00:00",
    "tags": ["tag1", "tag2"],
    "doc_id": "sha256-abc123def456",
}


class TestSaveNote:
    def test_creates_markdown_file(self, tmp_vault):
        from doc2kb import markdown_writer as mw
        path = save_note("# Hello\n\nContent.", SAMPLE_META)
        assert path.exists()
        assert path.suffix == ".md"

    def test_file_is_in_vault_dir(self, tmp_vault):
        from doc2kb import markdown_writer as mw
        path = save_note("Content.", SAMPLE_META)
        assert path.parent == mw.VAULT_DIR

    def test_frontmatter_contains_metadata(self, tmp_vault):
        path = save_note("Body content.", SAMPLE_META)
        post = frontmatter.load(str(path))
        assert post.metadata["title"] == "Test Note"
        assert post.metadata["source"] == "https://example.com"
        assert post.metadata["type"] == "web"
        assert post.metadata["doc_id"] == "sha256-abc123def456"

    def test_frontmatter_tags(self, tmp_vault):
        path = save_note("Body.", SAMPLE_META)
        post = frontmatter.load(str(path))
        assert post.metadata["tags"] == ["tag1", "tag2"]

    def test_body_content_preserved(self, tmp_vault):
        path = save_note("# My Heading\n\nParagraph text.", SAMPLE_META)
        post = frontmatter.load(str(path))
        assert "My Heading" in post.content
        assert "Paragraph text" in post.content

    def test_slug_from_title(self, tmp_vault):
        meta = {**SAMPLE_META, "title": "My Great Article"}
        path = save_note("Content.", meta)
        assert "my-great-article" in path.name

    def test_slug_from_source_when_no_title(self, tmp_vault):
        meta = {**SAMPLE_META, "title": "", "source": "https://example.com/page"}
        path = save_note("Content.", meta)
        assert path.exists()

    def test_overwrite_existing(self, tmp_vault):
        save_note("Version 1.", SAMPLE_META)
        path = save_note("Version 2.", SAMPLE_META)
        post = frontmatter.load(str(path))
        assert "Version 2" in post.content

    def test_returns_path_object(self, tmp_vault):
        result = save_note("Content.", SAMPLE_META)
        assert isinstance(result, Path)

    def test_date_ingested_auto_filled_if_missing(self, tmp_vault):
        meta = {k: v for k, v in SAMPLE_META.items() if k != "date_ingested"}
        path = save_note("Content.", meta)
        post = frontmatter.load(str(path))
        assert "date_ingested" in post.metadata


class TestDeleteNote:
    def test_deletes_note_by_doc_id(self, tmp_vault):
        path = save_note("Content.", SAMPLE_META)
        assert path.exists()
        deleted = delete_note(SAMPLE_META["doc_id"])
        assert deleted == path
        assert not path.exists()

    def test_returns_none_when_not_found(self, tmp_vault):
        result = delete_note("sha256-nonexistent1234")
        assert result is None

    def test_skips_index_file(self, tmp_vault):
        from doc2kb import markdown_writer as mw
        index = mw.VAULT_DIR / "_INDEX.md"
        index.write_text("---\ndoc_id: sha256-abc123def456\n---\n# Index", encoding="utf-8")
        # Should NOT delete _INDEX.md even if doc_id matches
        result = delete_note(SAMPLE_META["doc_id"])
        assert result is None
        assert index.exists()


class TestRegenerateIndex:
    def test_creates_index_file(self, tmp_vault):
        from doc2kb import markdown_writer as mw
        regenerate_index()
        index = mw.VAULT_DIR / "_INDEX.md"
        assert index.exists()

    def test_index_contains_heading(self, tmp_vault):
        from doc2kb import markdown_writer as mw
        index_path = regenerate_index()
        content = index_path.read_text(encoding="utf-8")
        assert "# Knowledge Base Index" in content

    def test_index_lists_notes_by_type(self, tmp_vault):
        save_note("Web content.", {**SAMPLE_META, "type": "web", "slug": "a"})
        pdf_meta = {**SAMPLE_META, "doc_id": "sha256-pdf111", "type": "pdf", "title": "PDF Doc"}
        save_note("PDF content.", pdf_meta)
        index_path = regenerate_index()
        content = index_path.read_text(encoding="utf-8")
        assert "## Web" in content
        assert "## PDF" in content

    def test_index_links_to_notes(self, tmp_vault):
        save_note("Content.", SAMPLE_META)
        index_path = regenerate_index()
        content = index_path.read_text(encoding="utf-8")
        assert "[[" in content

    def test_returns_path_object(self, tmp_vault):
        result = regenerate_index()
        assert isinstance(result, Path)

    def test_empty_vault_creates_index(self, tmp_vault):
        index_path = regenerate_index()
        assert index_path.exists()
        content = index_path.read_text(encoding="utf-8")
        assert "# Knowledge Base Index" in content
