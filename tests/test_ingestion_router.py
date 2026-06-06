"""Tests for doc2kb.ingestion — routing and file collection."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from doc2kb.ingestion import collect_files, ingest


class TestCollectFiles:
    def test_empty_directory(self, tmp_path):
        assert collect_files(tmp_path) == []

    def test_finds_supported_extensions(self, tmp_path):
        (tmp_path / "a.pdf").touch()
        (tmp_path / "b.txt").touch()
        (tmp_path / "c.docx").touch()
        files = collect_files(tmp_path)
        suffixes = {f.suffix for f in files}
        assert ".pdf" in suffixes
        assert ".txt" in suffixes
        assert ".docx" in suffixes

    def test_skips_unsupported_extensions(self, tmp_path):
        (tmp_path / "file.zip").touch()
        (tmp_path / "file.exe").touch()
        files = collect_files(tmp_path)
        assert files == []

    def test_recursive_search(self, tmp_path):
        sub = tmp_path / "subdir"
        sub.mkdir()
        (sub / "nested.txt").touch()
        files = collect_files(tmp_path)
        assert any(f.name == "nested.txt" for f in files)

    def test_returns_sorted(self, tmp_path):
        (tmp_path / "z.txt").touch()
        (tmp_path / "a.txt").touch()
        files = collect_files(tmp_path)
        names = [f.name for f in files]
        assert names == sorted(names)

    def test_returns_only_files_not_dirs(self, tmp_path):
        sub = tmp_path / "subdir"
        sub.mkdir()
        (tmp_path / "file.txt").touch()
        files = collect_files(tmp_path)
        assert all(f.is_file() for f in files)

    def test_image_extensions_included(self, tmp_path):
        for ext in [".jpg", ".png", ".tiff"]:
            (tmp_path / f"img{ext}").touch()
        files = collect_files(tmp_path)
        assert len(files) == 3


class TestIngestRouting:
    def test_file_not_found_raises(self):
        with pytest.raises(FileNotFoundError):
            ingest("/nonexistent/file.txt")

    def test_routes_http_url_to_web(self):
        with patch("doc2kb.ingestion.ingest_web") as mock_web:
            mock_web.return_value = ("content", {"doc_id": "x"})
            ingest("http://example.com")
            mock_web.assert_called_once_with("http://example.com")

    def test_routes_https_url_to_web(self):
        with patch("doc2kb.ingestion.ingest_web") as mock_web:
            mock_web.return_value = ("content", {"doc_id": "x"})
            ingest("https://example.com/page")
            mock_web.assert_called_once()

    def test_routes_pdf_to_pdf_handler(self, tmp_path):
        f = tmp_path / "doc.pdf"
        f.write_bytes(b"%PDF-1.4 test")
        with patch("doc2kb.ingestion.ingest_pdf") as mock_pdf:
            mock_pdf.return_value = ("content", {"doc_id": "x"})
            ingest(str(f))
            mock_pdf.assert_called_once_with(f)

    def test_routes_docx_to_docx_handler(self, tmp_path):
        f = tmp_path / "doc.docx"
        f.write_bytes(b"PK\x03\x04")  # minimal ZIP header (DOCX is a ZIP)
        with patch("doc2kb.ingestion.ingest_docx") as mock_docx:
            mock_docx.return_value = ("content", {"doc_id": "x"})
            ingest(str(f))
            mock_docx.assert_called_once_with(f)

    def test_routes_pptx_to_pptx_handler(self, tmp_path):
        f = tmp_path / "deck.pptx"
        f.write_bytes(b"PK\x03\x04")
        with patch("doc2kb.ingestion.ingest_pptx") as mock_pptx:
            mock_pptx.return_value = ("content", {"doc_id": "x"})
            ingest(str(f))
            mock_pptx.assert_called_once_with(f)

    def test_routes_txt_to_text_handler(self, tmp_path):
        f = tmp_path / "note.txt"
        f.write_text("hello", encoding="utf-8")
        with patch("doc2kb.ingestion.ingest_text") as mock_text:
            mock_text.return_value = ("content", {"doc_id": "x"})
            ingest(str(f))
            mock_text.assert_called_once_with(f)

    def test_routes_image_to_handwriting_handler(self, tmp_path):
        f = tmp_path / "scan.jpg"
        f.write_bytes(b"\xff\xd8\xff")
        with patch("doc2kb.ingestion.ingest_handwriting") as mock_hw:
            mock_hw.return_value = ("content", {"doc_id": "x"})
            ingest(str(f))
            mock_hw.assert_called_once()

    def test_routes_png_to_handwriting_handler(self, tmp_path):
        f = tmp_path / "image.png"
        f.write_bytes(b"\x89PNG\r\n")
        with patch("doc2kb.ingestion.ingest_handwriting") as mock_hw:
            mock_hw.return_value = ("content", {"doc_id": "x"})
            ingest(str(f))
            mock_hw.assert_called_once()

    def test_fallback_html_to_text_handler(self, tmp_path):
        f = tmp_path / "page.html"
        f.write_text("<p>hello</p>", encoding="utf-8")
        with patch("doc2kb.ingestion.ingest_text") as mock_text:
            mock_text.return_value = ("content", {"doc_id": "x"})
            ingest(str(f))
            mock_text.assert_called_once_with(f)

    def test_doc_extension_routed_to_docx(self, tmp_path):
        f = tmp_path / "doc.doc"
        f.write_bytes(b"\xd0\xcf\x11\xe0")
        with patch("doc2kb.ingestion.ingest_docx") as mock_docx:
            mock_docx.return_value = ("content", {"doc_id": "x"})
            ingest(str(f))
            mock_docx.assert_called_once()
