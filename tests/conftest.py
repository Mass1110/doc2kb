"""Shared fixtures for the doc2kb test suite."""
from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path
from typing import List
from unittest.mock import patch

import pytest


class _HashEmbeddingFunction:
    """Offline embedding function using deterministic hash vectors (384 dims)."""

    def __call__(self, input: List[str]) -> List[List[float]]:
        embeddings = []
        for text in input:
            digest = hashlib.sha256(text.encode()).digest()
            vec = [((b / 255.0) * 2 - 1) for b in digest]
            while len(vec) < 384:
                vec.extend(vec)
            embeddings.append(vec[:384])
        return embeddings

    def embed_query(self, input: List[str]) -> List[List[float]]:
        return self.__call__(input)

    def name(self) -> str:
        return "hash-embedding"

    def get_config(self) -> dict:
        return {}

    @classmethod
    def build_from_config(cls, config: dict) -> "_HashEmbeddingFunction":
        return cls()

    def is_legacy(self) -> bool:
        return False

    def supported_spaces(self) -> List[str]:
        return ["cosine", "l2", "ip"]


@pytest.fixture
def tmp_vault(tmp_path, monkeypatch):
    """Redirect VAULT_DIR and CHROMA_DIR to a temp directory for isolation.

    Also patches SentenceTransformerEmbeddingFunction so store tests run
    without internet access (no HuggingFace download needed).
    """
    vault = tmp_path / "obsidian_vault"
    chroma = tmp_path / "chroma_db"
    vault.mkdir()

    import doc2kb.config as cfg
    monkeypatch.setattr(cfg, "VAULT_DIR", vault)
    monkeypatch.setattr(cfg, "CHROMA_DIR", chroma)
    monkeypatch.setattr(cfg, "OUTPUT_DIR", tmp_path)

    import doc2kb.markdown_writer as mw
    monkeypatch.setattr(mw, "VAULT_DIR", vault)

    import doc2kb.store as st
    monkeypatch.setattr(st, "CHROMA_DIR", chroma)
    # Reset singletons so each test gets a fresh client
    monkeypatch.setattr(st, "_client", None)
    monkeypatch.setattr(st, "_col", None)

    # Replace the sentence-transformer EF with an offline hash-based one
    monkeypatch.setattr(
        "chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction",
        lambda **kwargs: _HashEmbeddingFunction(),
    )

    return tmp_path


@pytest.fixture
def sample_text_file(tmp_path):
    f = tmp_path / "hello.txt"
    f.write_text("Hello world\nThis is a test file.", encoding="utf-8")
    return f


@pytest.fixture
def sample_html_file(tmp_path):
    f = tmp_path / "page.html"
    f.write_text(
        "<html><body><h1>Title</h1><p>Paragraph content.</p></body></html>",
        encoding="utf-8",
    )
    return f
