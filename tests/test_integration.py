"""Integration tests — full pipeline with real files."""
from __future__ import annotations

from pathlib import Path

import pytest

from doc2kb.ingestion.text import ingest_text
from doc2kb.chunker import chunk_markdown
from doc2kb.markdown_writer import save_note, regenerate_index
from doc2kb.config import CHUNK_SIZE, CHUNK_OVERLAP


class TestFullPipeline:
    """Exercise the ingest → chunk → save → index flow end-to-end."""

    def test_text_file_full_pipeline(self, tmp_vault, tmp_path):
        # 1. Create a sample text file
        content = "\n\n".join(
            [f"# Section {i}\n\n" + " ".join(["word"] * 50) for i in range(5)]
        )
        doc = tmp_path / "sample.txt"
        doc.write_text(content, encoding="utf-8")

        # 2. Ingest
        md_text, metadata = ingest_text(doc)
        assert md_text

        # 3. Chunk
        chunks = chunk_markdown(md_text, CHUNK_SIZE, CHUNK_OVERLAP)
        assert len(chunks) >= 1

        # 4. Save note
        path = save_note(md_text, metadata)
        assert path.exists()

        # 5. Regenerate index
        index_path = regenerate_index()
        index_content = index_path.read_text(encoding="utf-8")
        assert "Knowledge Base Index" in index_content

    def test_html_file_full_pipeline(self, tmp_vault, tmp_path):
        html = """
        <html><body>
          <h1>Article Title</h1>
          <p>First paragraph with content.</p>
          <h2>Sub Section</h2>
          <p>Second paragraph with more content here.</p>
        </body></html>
        """
        doc = tmp_path / "article.html"
        doc.write_text(html, encoding="utf-8")

        md_text, metadata = ingest_text(doc)
        assert "Article Title" in md_text

        chunks = chunk_markdown(md_text, CHUNK_SIZE, CHUNK_OVERLAP)
        assert len(chunks) >= 1

        path = save_note(md_text, metadata)
        assert path.exists()

    def test_multiple_docs_indexed_separately(self, tmp_vault, tmp_path):
        for i in range(3):
            doc = tmp_path / f"doc{i}.txt"
            doc.write_text(f"Document {i} content.", encoding="utf-8")
            md_text, meta = ingest_text(doc)
            save_note(md_text, meta)

        index_path = regenerate_index()
        content = index_path.read_text(encoding="utf-8")
        # All 3 docs should appear as links
        assert content.count("[[") == 3

    def test_doc_id_deduplication(self, tmp_path):
        """Same file ingested twice → same doc_id."""
        doc = tmp_path / "file.txt"
        doc.write_text("Stable content.", encoding="utf-8")
        _, meta1 = ingest_text(doc)
        _, meta2 = ingest_text(doc)
        assert meta1["doc_id"] == meta2["doc_id"]

    def test_chunk_size_respected(self, tmp_path):
        long_text = " ".join(["word"] * 1200)
        doc = tmp_path / "long.txt"
        doc.write_text(long_text, encoding="utf-8")
        md_text, _ = ingest_text(doc)
        chunks = chunk_markdown(md_text, chunk_size=200, overlap=20)
        for chunk in chunks:
            word_count = len(chunk.split())
            # Allow one step of overlap beyond chunk_size
            assert word_count <= 200 + 20

    def test_real_pdf_file(self, tmp_vault):
        """Smoke test against the sample PDF shipped with the repo."""
        pdf_path = Path(__file__).parent.parent / "repubblica2404.pdf"
        if not pdf_path.exists():
            pytest.skip("Sample PDF not found")

        import pymupdf
        import pymupdf4llm
        from doc2kb.ingestion.pdf import ingest_pdf

        with pytest.MonkeyPatch().context() as m:
            m.delenv("ANTHROPIC_API_KEY", raising=False)
            md_text, meta = ingest_pdf(pdf_path)

        assert md_text
        assert meta["type"] == "pdf"
        assert meta["doc_id"].startswith("sha256-")
        chunks = chunk_markdown(md_text, CHUNK_SIZE, CHUNK_OVERLAP)
        assert len(chunks) >= 1
