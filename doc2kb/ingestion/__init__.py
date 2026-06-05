"""Route a source (URL or file path) to the correct ingestion handler."""
from __future__ import annotations

from pathlib import Path

from .web import ingest_web
from .pdf import ingest_pdf
from .docx import ingest_docx
from .pptx import ingest_pptx
from .text import ingest_text
from .handwriting import ingest_handwriting
from ..config import IMAGE_EXTENSIONS, SUPPORTED_EXTENSIONS


def collect_files(directory: Path) -> list[Path]:
    """Return all supported files under *directory*, recursively, sorted by path."""
    return sorted(
        p for p in directory.rglob("*")
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
    )


def ingest(source: str, langs: list[str] | None = None) -> tuple[str, dict]:
    """Return (markdown_content, metadata) for *source*.

    *langs* is only used for image/handwriting sources (EasyOCR language codes).
    """
    if source.startswith("http://") or source.startswith("https://"):
        return ingest_web(source)

    path = Path(source)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {source}")

    suffix = path.suffix.lower()

    if suffix == ".pdf":
        return ingest_pdf(path)
    if suffix in (".docx", ".doc"):
        return ingest_docx(path)
    if suffix in (".pptx", ".ppt"):
        return ingest_pptx(path)
    if suffix in IMAGE_EXTENSIONS:
        return ingest_handwriting(path, langs=langs)
    # fallback: plain text / HTML
    return ingest_text(path)
