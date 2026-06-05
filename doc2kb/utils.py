"""Shared utilities for doc2kb."""
from __future__ import annotations

import hashlib
from pathlib import Path


def content_doc_id(path: Path) -> str:
    """Return a stable doc_id based on the SHA-256 of the file's content.

    Unlike a path-based hash, this is invariant to where the file lives on
    disk — so uploading the same file twice (e.g. via the webapp temp dir)
    always yields the same doc_id and deduplication works correctly.
    """
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(65536), b""):
            h.update(block)
    return "sha256-" + h.hexdigest()[:16]


def url_doc_id(url: str) -> str:
    """Return a stable doc_id for a URL."""
    return "sha256-" + hashlib.sha256(url.encode()).hexdigest()[:16]
