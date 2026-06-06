"""Tests for doc2kb.config — constants and paths."""
from __future__ import annotations

from pathlib import Path

import pytest


class TestConfig:
    def test_vault_dir_is_path(self):
        from doc2kb.config import VAULT_DIR
        assert isinstance(VAULT_DIR, Path)

    def test_chroma_dir_is_path(self):
        from doc2kb.config import CHROMA_DIR
        assert isinstance(CHROMA_DIR, Path)

    def test_output_dir_is_path(self):
        from doc2kb.config import OUTPUT_DIR
        assert isinstance(OUTPUT_DIR, Path)

    def test_vault_dir_under_output(self):
        from doc2kb.config import VAULT_DIR, OUTPUT_DIR
        assert str(VAULT_DIR).startswith(str(OUTPUT_DIR))

    def test_chroma_dir_under_output(self):
        from doc2kb.config import CHROMA_DIR, OUTPUT_DIR
        assert str(CHROMA_DIR).startswith(str(OUTPUT_DIR))

    def test_chunk_size_positive(self):
        from doc2kb.config import CHUNK_SIZE
        assert CHUNK_SIZE > 0

    def test_chunk_overlap_less_than_chunk_size(self):
        from doc2kb.config import CHUNK_SIZE, CHUNK_OVERLAP
        assert CHUNK_OVERLAP < CHUNK_SIZE

    def test_pdf_scanned_threshold_positive(self):
        from doc2kb.config import PDF_SCANNED_THRESHOLD
        assert PDF_SCANNED_THRESHOLD > 0

    def test_embed_model_is_string(self):
        from doc2kb.config import EMBED_MODEL
        assert isinstance(EMBED_MODEL, str)
        assert len(EMBED_MODEL) > 0

    def test_collection_name_is_string(self):
        from doc2kb.config import COLLECTION_NAME
        assert isinstance(COLLECTION_NAME, str)

    def test_image_extensions_is_set(self):
        from doc2kb.config import IMAGE_EXTENSIONS
        assert isinstance(IMAGE_EXTENSIONS, set)
        assert ".jpg" in IMAGE_EXTENSIONS
        assert ".png" in IMAGE_EXTENSIONS

    def test_supported_extensions_includes_common_types(self):
        from doc2kb.config import SUPPORTED_EXTENSIONS
        for ext in (".pdf", ".docx", ".txt", ".html", ".pptx"):
            assert ext in SUPPORTED_EXTENSIONS

    def test_supported_extensions_includes_images(self):
        from doc2kb.config import SUPPORTED_EXTENSIONS, IMAGE_EXTENSIONS
        assert IMAGE_EXTENSIONS.issubset(SUPPORTED_EXTENSIONS)

    def test_ocr_confidence_threshold_in_range(self):
        from doc2kb.config import OCR_CONFIDENCE_THRESHOLD
        assert 0.0 < OCR_CONFIDENCE_THRESHOLD < 1.0

    def test_ocr_default_langs_is_list(self):
        from doc2kb.config import OCR_DEFAULT_LANGS
        assert isinstance(OCR_DEFAULT_LANGS, list)
        assert len(OCR_DEFAULT_LANGS) > 0
