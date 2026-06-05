"""Ingest plain-text or HTML files as markdown."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from markdownify import markdownify

from ..utils import content_doc_id


def ingest_text(path: Path) -> tuple[str, dict]:
    raw = path.read_text(encoding="utf-8", errors="replace")

    suffix = path.suffix.lower()
    if suffix in (".html", ".htm"):
        md_text = markdownify(raw, heading_style="ATX")
    else:
        md_text = raw

    doc_id = content_doc_id(path)

    metadata = {
        "title": path.stem,
        "source": str(path.resolve()),
        "type": "text",
        "date_ingested": datetime.now().isoformat(timespec="seconds"),
        "tags": [],
        "doc_id": doc_id,
    }
    return md_text, metadata
