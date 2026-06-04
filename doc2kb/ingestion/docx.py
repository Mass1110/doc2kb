"""Convert a DOCX file to markdown via mammoth."""
from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path

import mammoth
from markdownify import markdownify


def ingest_docx(path: Path) -> tuple[str, dict]:
    with path.open("rb") as fh:
        result = mammoth.convert_to_html(fh)
    md_text = markdownify(result.value, heading_style="ATX")

    doc_id = "sha256-" + hashlib.sha256(path.resolve().as_posix().encode()).hexdigest()[:16]

    metadata = {
        "title": path.stem,
        "source": str(path.resolve()),
        "type": "docx",
        "date_ingested": datetime.now().isoformat(timespec="seconds"),
        "tags": [],
        "doc_id": doc_id,
    }
    return md_text, metadata
