"""Convert a DOCX file to markdown via mammoth."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import mammoth
from markdownify import markdownify

from ..utils import content_doc_id


def ingest_docx(path: Path) -> tuple[str, dict]:
    with path.open("rb") as fh:
        result = mammoth.convert_to_html(fh)
    md_text = markdownify(result.value, heading_style="ATX")

    doc_id = content_doc_id(path)

    metadata = {
        "title": path.stem,
        "source": str(path.resolve()),
        "type": "docx",
        "date_ingested": datetime.now().isoformat(timespec="seconds"),
        "tags": [],
        "doc_id": doc_id,
    }
    return md_text, metadata
