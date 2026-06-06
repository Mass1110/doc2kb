"""Tests for doc2kb.ingestion.pdf — PDF text extraction logic."""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch, MagicMock, call

import pytest

from doc2kb.ingestion.pdf import _is_scanned, ingest_pdf
from doc2kb.config import PDF_SCANNED_THRESHOLD


def _mock_doc(pages_chars: list[int]) -> MagicMock:
    """Build a fake pymupdf.Document with pages returning given char counts."""
    doc = MagicMock()
    doc.__len__ = MagicMock(return_value=len(pages_chars))
    pages = []
    for n in pages_chars:
        p = MagicMock()
        p.get_text.return_value = "x" * n
        pages.append(p)
    doc.__getitem__ = MagicMock(side_effect=lambda i: pages[i])
    return doc


class TestIsScanned:
    def test_digital_pdf_returns_false(self):
        doc = _mock_doc([500, 600, 700])
        assert _is_scanned(doc) is False

    def test_scanned_pdf_returns_true(self):
        doc = _mock_doc([20, 10, 5])
        assert _is_scanned(doc) is True

    def test_empty_doc_returns_false(self):
        doc = MagicMock()
        doc.__len__ = MagicMock(return_value=0)
        assert _is_scanned(doc) is False

    def test_exactly_at_threshold(self):
        doc = _mock_doc([PDF_SCANNED_THRESHOLD])
        assert _is_scanned(doc) is False

    def test_one_below_threshold(self):
        doc = _mock_doc([PDF_SCANNED_THRESHOLD - 1])
        assert _is_scanned(doc) is True

    def test_mixed_pages_uses_average(self):
        # avg = (900 + 0) / 2 = 450 → not scanned
        doc = _mock_doc([900, 0])
        assert _is_scanned(doc) is False


class TestIngestPdf:
    def _setup_mocks(self, tmp_path, chars_per_page=500):
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4")

        mock_doc = _mock_doc([chars_per_page])
        return pdf_path, mock_doc

    def test_returns_tuple(self, tmp_path):
        pdf_path, mock_doc = self._setup_mocks(tmp_path)
        with patch("doc2kb.ingestion.pdf.pymupdf.open", return_value=mock_doc):
            with patch("doc2kb.ingestion.pdf.pymupdf4llm.to_markdown", return_value="## Markdown"):
                result = ingest_pdf(pdf_path)
                assert isinstance(result, tuple)
                assert len(result) == 2

    def test_metadata_type_is_pdf(self, tmp_path):
        pdf_path, mock_doc = self._setup_mocks(tmp_path)
        with patch("doc2kb.ingestion.pdf.pymupdf.open", return_value=mock_doc):
            with patch("doc2kb.ingestion.pdf.pymupdf4llm.to_markdown", return_value="content"):
                _, meta = ingest_pdf(pdf_path)
                assert meta["type"] == "pdf"

    def test_metadata_title_is_stem(self, tmp_path):
        pdf_path = tmp_path / "my_report.pdf"
        pdf_path.write_bytes(b"%PDF-1.4")
        mock_doc = _mock_doc([500])
        with patch("doc2kb.ingestion.pdf.pymupdf.open", return_value=mock_doc):
            with patch("doc2kb.ingestion.pdf.pymupdf4llm.to_markdown", return_value="content"):
                _, meta = ingest_pdf(pdf_path)
                assert meta["title"] == "my_report"

    def test_uses_pymupdf4llm_for_digital_pdf(self, tmp_path):
        pdf_path, mock_doc = self._setup_mocks(tmp_path, chars_per_page=500)
        with patch("doc2kb.ingestion.pdf.pymupdf.open", return_value=mock_doc):
            with patch("doc2kb.ingestion.pdf.pymupdf4llm.to_markdown", return_value="## Digital") as mock_md:
                text, _ = ingest_pdf(pdf_path)
                mock_md.assert_called_once()
                assert "## Digital" in text

    def test_uses_claude_vision_for_scanned_pdf_with_key(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")
        pdf_path, mock_doc = self._setup_mocks(tmp_path, chars_per_page=5)
        with patch("doc2kb.ingestion.pdf.pymupdf.open", return_value=mock_doc):
            with patch("doc2kb.ingestion.pdf._claude_vision_pdf", return_value="OCR text") as mock_cv:
                text, _ = ingest_pdf(pdf_path)
                mock_cv.assert_called_once()
                assert "OCR text" in text

    def test_no_claude_vision_without_api_key(self, tmp_path, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        pdf_path, mock_doc = self._setup_mocks(tmp_path, chars_per_page=5)
        with patch("doc2kb.ingestion.pdf.pymupdf.open", return_value=mock_doc):
            with patch("doc2kb.ingestion.pdf.pymupdf4llm.to_markdown", return_value="fallback") as mock_md:
                with patch("doc2kb.ingestion.pdf._claude_vision_pdf") as mock_cv:
                    ingest_pdf(pdf_path)
                    mock_cv.assert_not_called()
                    mock_md.assert_called_once()

    def test_ocr_note_prepended_when_claude_used(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")
        pdf_path, mock_doc = self._setup_mocks(tmp_path, chars_per_page=5)
        with patch("doc2kb.ingestion.pdf.pymupdf.open", return_value=mock_doc):
            with patch("doc2kb.ingestion.pdf._claude_vision_pdf", return_value="OCR text"):
                text, _ = ingest_pdf(pdf_path)
                assert text.startswith("*OCR via")

    def test_doc_id_starts_with_sha256(self, tmp_path):
        pdf_path, mock_doc = self._setup_mocks(tmp_path)
        with patch("doc2kb.ingestion.pdf.pymupdf.open", return_value=mock_doc):
            with patch("doc2kb.ingestion.pdf.pymupdf4llm.to_markdown", return_value="content"):
                _, meta = ingest_pdf(pdf_path)
                assert meta["doc_id"].startswith("sha256-")

    def test_doc_closes_after_ingest(self, tmp_path):
        pdf_path, mock_doc = self._setup_mocks(tmp_path)
        with patch("doc2kb.ingestion.pdf.pymupdf.open", return_value=mock_doc):
            with patch("doc2kb.ingestion.pdf.pymupdf4llm.to_markdown", return_value="content"):
                ingest_pdf(pdf_path)
                mock_doc.close.assert_called_once()
