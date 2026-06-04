"""OCR for handwritten images: TrOCR local model with Google Vision cloud fallback."""
from __future__ import annotations

import hashlib
import os
import shutil
import warnings
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image

from ..config import (
    ATTACHMENTS_DIR,
    HANDWRITING_MODEL,
    OCR_CONFIDENCE_THRESHOLD,
)

if TYPE_CHECKING:
    pass


def _trocr(image: Image.Image) -> tuple[str, float]:
    """Run TrOCR and return (text, mean_confidence)."""
    from transformers import TrOCRProcessor, VisionEncoderDecoderModel
    import torch

    processor = TrOCRProcessor.from_pretrained(HANDWRITING_MODEL)
    model = VisionEncoderDecoderModel.from_pretrained(HANDWRITING_MODEL)
    model.eval()

    pixel_values = processor(images=image.convert("RGB"), return_tensors="pt").pixel_values

    with torch.no_grad():
        outputs = model.generate(
            pixel_values,
            output_scores=True,
            return_dict_in_generate=True,
        )

    generated_ids = outputs.sequences
    text = processor.batch_decode(generated_ids, skip_special_tokens=True)[0]

    # Compute mean token probability as confidence proxy
    if outputs.scores:
        import torch.nn.functional as F

        probs = [F.softmax(s, dim=-1).max(dim=-1).values for s in outputs.scores]
        confidence = float(sum(p.mean().item() for p in probs) / len(probs))
    else:
        confidence = 1.0

    return text, confidence


def _google_vision(path: Path) -> str:
    """Call Google Vision API for handwriting recognition."""
    from google.cloud import vision  # type: ignore[import]

    client = vision.ImageAnnotatorClient()
    with path.open("rb") as fh:
        content = fh.read()
    image = vision.Image(content=content)
    response = client.document_text_detection(image=image)
    if response.error.message:
        raise RuntimeError(f"Google Vision error: {response.error.message}")
    return response.full_text_annotation.text


def ingest_handwriting(path: Path) -> tuple[str, dict]:
    image = Image.open(path)

    text, confidence = _trocr(image)

    used_cloud = False
    creds_set = bool(os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"))

    if confidence < OCR_CONFIDENCE_THRESHOLD:
        if creds_set:
            try:
                text = _google_vision(path)
                used_cloud = True
            except Exception as exc:
                warnings.warn(
                    f"Google Vision fallback failed ({exc}); using local TrOCR result.",
                    stacklevel=2,
                )
        else:
            warnings.warn(
                f"OCR confidence {confidence:.2f} below threshold "
                f"({OCR_CONFIDENCE_THRESHOLD}). "
                "Set GOOGLE_APPLICATION_CREDENTIALS for cloud fallback.",
                stacklevel=2,
            )

    # Copy image to vault attachments so Obsidian can display it
    ATTACHMENTS_DIR.mkdir(parents=True, exist_ok=True)
    dest = ATTACHMENTS_DIR / path.name
    shutil.copy2(path, dest)

    ocr_note = "Google Vision (cloud)" if used_cloud else f"TrOCR local (confidence {confidence:.2f})"
    md_text = (
        f"![[attachments/{path.name}]]\n\n"
        f"*OCR via {ocr_note}*\n\n"
        f"{text}"
    )

    doc_id = "sha256-" + hashlib.sha256(path.resolve().as_posix().encode()).hexdigest()[:16]

    metadata = {
        "title": path.stem,
        "source": str(path.resolve()),
        "type": "handwriting",
        "date_ingested": datetime.now().isoformat(timespec="seconds"),
        "tags": ["handwriting"],
        "doc_id": doc_id,
    }
    return md_text, metadata
