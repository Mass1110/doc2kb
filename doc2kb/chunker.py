"""Split markdown text into overlapping word-count chunks."""
from __future__ import annotations

import re


_HEADING_RE = re.compile(r"^#{1,3} .+", re.MULTILINE)


def _word_count(text: str) -> int:
    return len(text.split())


def _sliding_window(text: str, size: int, overlap: int) -> list[str]:
    words = text.split()
    chunks = []
    step = size - overlap
    for i in range(0, len(words), step):
        chunk = " ".join(words[i : i + size])
        if chunk:
            chunks.append(chunk)
        if i + size >= len(words):
            break
    return chunks


def chunk_markdown(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Split *text* on headings first, then apply sliding window if needed."""
    # Split on heading boundaries, keeping the heading with its section
    parts = _HEADING_RE.split(text)
    headings = _HEADING_RE.findall(text)

    sections: list[str] = []
    if parts and parts[0].strip():
        sections.append(parts[0].strip())
    for heading, body in zip(headings, parts[1:]):
        section = f"{heading}\n{body}".strip()
        if section:
            sections.append(section)

    chunks: list[str] = []
    for section in sections:
        if _word_count(section) <= chunk_size:
            chunks.append(section)
        else:
            chunks.extend(_sliding_window(section, chunk_size, overlap))

    return [c for c in chunks if c.strip()]
