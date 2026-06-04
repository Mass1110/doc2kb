"""Convert a PDF to markdown via pymupdf4llm."""
from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path

import pymupdf4llm


def ingest_pdf(path: Path) -> tuple[str, dict]:
    md_text = pymupdf4llm.to_markdown(str(path))

    doc_id = "sha256-" + hashlib.sha256(path.resolve().as_posix().encode()).hexdigest()[:16]

    metadata = {
        "title": path.stem,
        "source": str(path.resolve()),
        "type": "pdf",
        "date_ingested": datetime.now().isoformat(timespec="seconds"),
        "tags": [],
        "doc_id": doc_id,
    }
    return md_text, metadata
