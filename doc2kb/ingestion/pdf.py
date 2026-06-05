"""Ingest PDF files.

Strategy:
  1. Extract text with pymupdf4llm (fast, zero cost).
  2. If extracted text is sparse (likely a scanned PDF) AND
     ANTHROPIC_API_KEY is set, fall back to Claude Vision page-by-page.
"""
from __future__ import annotations

import base64
import os
from datetime import datetime
from pathlib import Path

import pymupdf
import pymupdf4llm

from ..config import ANTHROPIC_OCR_MODEL, PDF_SCANNED_THRESHOLD
from ..utils import content_doc_id


def _is_scanned(doc: pymupdf.Document) -> bool:
    """Return True if the PDF has too little selectable text to be digital."""
    n_pages = len(doc)
    if n_pages == 0:
        return False
    total_chars = sum(len(doc[i].get_text()) for i in range(n_pages))
    avg_chars = total_chars / n_pages
    return avg_chars < PDF_SCANNED_THRESHOLD


def _claude_vision_pdf(doc: pymupdf.Document) -> str:
    """Render each page as an image and transcribe with Claude Vision."""
    import anthropic

    client = anthropic.Anthropic()
    pages_text: list[str] = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        # Render at 150 DPI (good balance of quality vs token cost)
        pix = page.get_pixmap(dpi=150)
        img_data = base64.standard_b64encode(pix.tobytes("png")).decode()

        message = client.messages.create(
            model=ANTHROPIC_OCR_MODEL,
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": img_data,
                            },
                        },
                        {
                            "type": "text",
                            "text": (
                                "Transcribe all the text in this PDF page. "
                                "Preserve headings, paragraphs, lists and tables as markdown. "
                                "Output only the transcribed text, no commentary."
                            ),
                        },
                    ],
                }
            ],
        )
        page_text = message.content[0].text.strip()
        if page_text:
            pages_text.append(f"## Page {page_num + 1}\n\n{page_text}")

    return "\n\n---\n\n".join(pages_text)


def ingest_pdf(path: Path) -> tuple[str, dict]:
    doc = pymupdf.open(str(path))

    ocr_engine = "pymupdf4llm"

    if _is_scanned(doc) and os.environ.get("ANTHROPIC_API_KEY"):
        md_text = _claude_vision_pdf(doc)
        ocr_engine = f"Claude Vision ({ANTHROPIC_OCR_MODEL})"
    else:
        md_text = pymupdf4llm.to_markdown(doc)

    doc.close()

    # Prepend engine note only when Claude Vision was used
    if ocr_engine != "pymupdf4llm":
        md_text = f"*OCR via {ocr_engine}*\n\n{md_text}"

    metadata = {
        "title": path.stem,
        "source": str(path.resolve()),
        "type": "pdf",
        "date_ingested": datetime.now().isoformat(timespec="seconds"),
        "tags": [],
        "doc_id": content_doc_id(path),
    }
    return md_text, metadata
