"""Save ingested content as Obsidian-compatible markdown notes."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import frontmatter
from slugify import slugify

from .config import VAULT_DIR


def _slug(source: str, title: str) -> str:
    base = title if title else source
    return slugify(base, max_length=80, word_boundary=True)


def save_note(
    content: str,
    metadata: dict,
) -> Path:
    """Write a markdown note with YAML frontmatter into the Obsidian vault.

    Returns the path of the written file.
    """
    VAULT_DIR.mkdir(parents=True, exist_ok=True)

    slug = _slug(metadata.get("source", ""), metadata.get("title", ""))
    note_path = VAULT_DIR / f"{slug}.md"

    post = frontmatter.Post(
        content,
        title=metadata.get("title", slug),
        source=metadata.get("source", ""),
        type=metadata.get("type", "text"),
        date_ingested=metadata.get(
            "date_ingested", datetime.now().isoformat(timespec="seconds")
        ),
        tags=metadata.get("tags", []),
        doc_id=metadata.get("doc_id", ""),
    )

    note_path.write_text(frontmatter.dumps(post), encoding="utf-8")
    return note_path


def delete_note(doc_id: str) -> Path | None:
    """Find and delete the Obsidian note with the given doc_id. Returns path or None."""
    for note_path in VAULT_DIR.glob("*.md"):
        if note_path.name == "_INDEX.md":
            continue
        try:
            post = frontmatter.load(str(note_path))
        except Exception:
            continue
        if post.metadata.get("doc_id") == doc_id:
            note_path.unlink()
            return note_path
    return None


def regenerate_index() -> Path:
    """Rebuild _INDEX.md in the vault with links to all notes, grouped by type."""
    VAULT_DIR.mkdir(parents=True, exist_ok=True)
    index_path = VAULT_DIR / "_INDEX.md"

    groups: dict[str, list[tuple[str, str]]] = {}

    for md_file in sorted(VAULT_DIR.glob("*.md")):
        if md_file.name == "_INDEX.md":
            continue
        try:
            post = frontmatter.load(str(md_file))
        except Exception:
            continue
        doc_type = post.metadata.get("type", "text")
        title = post.metadata.get("title", md_file.stem)
        slug = md_file.stem
        groups.setdefault(doc_type, []).append((slug, title))

    lines = [
        "# Knowledge Base Index",
        f"*Aggiornato: {datetime.now().strftime('%Y-%m-%d %H:%M')}*",
        "",
    ]

    type_labels = {
        "web": "Web",
        "pdf": "PDF",
        "docx": "DOCX",
        "pptx": "PPTX",
        "handwriting": "Manoscritti",
        "text": "Testo",
    }

    for doc_type, entries in sorted(groups.items()):
        label = type_labels.get(doc_type, doc_type.upper())
        lines.append(f"## {label} ({len(entries)})")
        for slug, title in entries:
            lines.append(f"- [[{slug}]] — {title}")
        lines.append("")

    index_path.write_text("\n".join(lines), encoding="utf-8")
    return index_path
