"""Convert a PDF to markdown via pymupdf4llm."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pymupdf
import pymupdf4llm

from ..utils import content_doc_id


def ingest_pdf(path: Path) -> tuple[str, dict]:
    doc = pymupdf.open(str(path))
    md_text = pymupdf4llm.to_markdown(doc)
    doc.close()

    doc_id = content_doc_id(path)

    metadata = {
        "title": path.stem,
        "source": str(path.resolve()),
        "type": "pdf",
        "date_ingested": datetime.now().isoformat(timespec="seconds"),
        "tags": [],
        "doc_id": doc_id,
    }
    return md_text, metadata
