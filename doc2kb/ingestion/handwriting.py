"""OCR for handwritten images: EasyOCR local engine with Google Vision cloud fallback."""
from __future__ import annotations

import os
import shutil
import warnings
from datetime import datetime
from pathlib import Path

from ..config import (
    ATTACHMENTS_DIR,
    OCR_CONFIDENCE_THRESHOLD,
    OCR_DEFAULT_LANGS,
)
from ..utils import content_doc_id


def _easyocr(path: Path, langs: list[str]) -> tuple[str, float]:
    import easyocr

    reader = easyocr.Reader(langs, gpu=False, verbose=False)
    results = reader.readtext(str(path))
    if not results:
        return "", 0.0
    text = "\n".join(r[1] for r in results)
    confidence = sum(r[2] for r in results) / len(results)
    return text, confidence


def _google_vision(path: Path) -> str:
    from google.cloud import vision  # type: ignore[import]

    client = vision.ImageAnnotatorClient()
    with path.open("rb") as fh:
        content = fh.read()
    image = vision.Image(content=content)
    response = client.document_text_detection(image=image)
    if response.error.message:
        raise RuntimeError(f"Google Vision error: {response.error.message}")
    return response.full_text_annotation.text


def ingest_handwriting(path: Path, langs: list[str] | None = None) -> tuple[str, dict]:
    langs = list(langs) if langs else list(OCR_DEFAULT_LANGS)

    text, confidence = _easyocr(path, langs)

    used_cloud = False
    creds_set = bool(os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"))

    if confidence < OCR_CONFIDENCE_THRESHOLD:
        if creds_set:
            try:
                text = _google_vision(path)
                used_cloud = True
            except Exception as exc:
                warnings.warn(
                    f"Google Vision fallback failed ({exc}); using local EasyOCR result.",
                    stacklevel=2,
                )
        else:
            warnings.warn(
                f"OCR confidence {confidence:.2f} below threshold "
                f"({OCR_CONFIDENCE_THRESHOLD}). "
                "Set GOOGLE_APPLICATION_CREDENTIALS for cloud fallback.",
                stacklevel=2,
            )

    ATTACHMENTS_DIR.mkdir(parents=True, exist_ok=True)
    dest = ATTACHMENTS_DIR / path.name
    shutil.copy2(path, dest)

    if used_cloud:
        ocr_note = "Google Vision (cloud)"
    else:
        ocr_note = f"EasyOCR local, langs={langs}, confidence={confidence:.2f}"

    md_text = (
        f"![[attachments/{path.name}]]\n\n"
        f"*OCR via {ocr_note}*\n\n"
        f"{text}"
    )

    doc_id = content_doc_id(path)

    metadata = {
        "title": path.stem,
        "source": str(path.resolve()),
        "type": "handwriting",
        "date_ingested": datetime.now().isoformat(timespec="seconds"),
        "tags": ["handwriting"],
        "doc_id": doc_id,
    }
    return md_text, metadata
