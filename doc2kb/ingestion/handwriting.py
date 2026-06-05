"""OCR for handwritten images.

Engine priority (first available wins):
  1. Claude Vision  — if ANTHROPIC_API_KEY is set
  2. Google Vision  — if GOOGLE_APPLICATION_CREDENTIALS is set
  3. EasyOCR        — local fallback (always available)
"""
from __future__ import annotations

import base64
import os
import shutil
import warnings
from datetime import datetime
from pathlib import Path

from ..config import (
    ATTACHMENTS_DIR,
    OCR_CONFIDENCE_THRESHOLD,
    OCR_DEFAULT_LANGS,
    ANTHROPIC_OCR_MODEL,
)
from ..utils import content_doc_id


# ── Engine implementations ────────────────────────────────────────────────────

def _claude_vision(path: Path) -> str:
    """Transcribe handwritten text via Claude Vision."""
    import anthropic

    image_data = base64.standard_b64encode(path.read_bytes()).decode()
    suffix = path.suffix.lower().lstrip(".")
    media_type_map = {
        "jpg": "image/jpeg", "jpeg": "image/jpeg",
        "png": "image/png", "gif": "image/gif",
        "webp": "image/webp",
    }
    media_type = media_type_map.get(suffix, "image/jpeg")

    client = anthropic.Anthropic()
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
                            "media_type": media_type,
                            "data": image_data,
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            "Please transcribe all the handwritten text in this image. "
                            "Preserve the original structure (paragraphs, lists, headings) as much as possible. "
                            "Output only the transcribed text, with no commentary."
                        ),
                    },
                ],
            }
        ],
    )
    return message.content[0].text


def _google_vision(path: Path) -> str:
    """Transcribe text via Google Cloud Vision API."""
    from google.cloud import vision  # type: ignore[import]

    client = vision.ImageAnnotatorClient()
    with path.open("rb") as fh:
        content = fh.read()
    image = vision.Image(content=content)
    response = client.document_text_detection(image=image)
    if response.error.message:
        raise RuntimeError(f"Google Vision error: {response.error.message}")
    return response.full_text_annotation.text


def _easyocr(path: Path, langs: list[str]) -> tuple[str, float]:
    """Transcribe text via EasyOCR (local)."""
    import easyocr

    reader = easyocr.Reader(langs, gpu=False, verbose=False)
    results = reader.readtext(str(path))
    if not results:
        return "", 0.0
    text = "\n".join(r[1] for r in results)
    confidence = sum(r[2] for r in results) / len(results)
    return text, confidence


# ── Main entry point ──────────────────────────────────────────────────────────

def ingest_handwriting(path: Path, langs: list[str] | None = None) -> tuple[str, dict]:
    langs = list(langs) if langs else list(OCR_DEFAULT_LANGS)

    engine_used = "EasyOCR local"
    text = ""

    # 1 — Claude Vision (best quality)
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            text = _claude_vision(path)
            engine_used = f"Claude Vision ({ANTHROPIC_OCR_MODEL})"
        except Exception as exc:
            warnings.warn(
                f"Claude Vision failed ({exc}); trying next engine.",
                stacklevel=2,
            )

    # 2 — Google Vision
    if not text and os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        try:
            text = _google_vision(path)
            engine_used = "Google Vision"
        except Exception as exc:
            warnings.warn(
                f"Google Vision failed ({exc}); falling back to EasyOCR.",
                stacklevel=2,
            )

    # 3 — EasyOCR (local fallback)
    if not text:
        text, confidence = _easyocr(path, langs)
        engine_used = f"EasyOCR local (langs={langs}, confidence={confidence:.2f})"
        if confidence < OCR_CONFIDENCE_THRESHOLD:
            warnings.warn(
                f"EasyOCR confidence {confidence:.2f} is below threshold "
                f"({OCR_CONFIDENCE_THRESHOLD}). Consider setting ANTHROPIC_API_KEY "
                "or GOOGLE_APPLICATION_CREDENTIALS for better results.",
                stacklevel=2,
            )

    # Copy image to vault attachments for Obsidian display
    ATTACHMENTS_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, ATTACHMENTS_DIR / path.name)

    md_text = (
        f"![[attachments/{path.name}]]\n\n"
        f"*OCR via {engine_used}*\n\n"
        f"{text}"
    )

    metadata = {
        "title": path.stem,
        "source": str(path.resolve()),
        "type": "handwriting",
        "date_ingested": datetime.now().isoformat(timespec="seconds"),
        "tags": ["handwriting"],
        "doc_id": content_doc_id(path),
    }
    return md_text, metadata
