"""Embedding helper — delegates to ChromaDB's built-in ONNX model.

Kept for potential direct use; primary path is through store.py.
"""
from __future__ import annotations

from functools import lru_cache

from chromadb.utils.embedding_functions import DefaultEmbeddingFunction


@lru_cache(maxsize=1)
def _fn() -> DefaultEmbeddingFunction:
    return DefaultEmbeddingFunction()


def embed(texts: list[str]) -> list[list[float]]:
    return _fn()(texts)
