"""Wiki synthesis: uses Claude to build and maintain a structured knowledge wiki.

On every ingest, ``synthesize_wiki_update`` calls Claude to extract entities
and concepts from the ingested content and writes/updates wiki pages under
``WIKI_DIR``.  If ``ANTHROPIC_API_KEY`` is absent or *anthropic* is not
installed, every function degrades gracefully and returns empty results.
"""
from __future__ import annotations

import json
import os
import re
import warnings
from datetime import datetime
from pathlib import Path

from .config import WIKI_DIR, WIKI_MODEL


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_existing_pages() -> dict[str, str]:
    """Return ``{path_relative_to_WIKI_DIR: content}`` for all non-meta pages."""
    pages: dict[str, str] = {}
    if WIKI_DIR.exists():
        for f in sorted(WIKI_DIR.rglob("*.md")):
            if f.name.startswith("_"):
                continue
            rel = str(f.relative_to(WIKI_DIR)).replace("\\", "/")
            try:
                pages[rel] = f.read_text(encoding="utf-8")
            except Exception:
                pass
    return pages


def _index_summary(pages: dict[str, str]) -> str:
    """One-line summary of all existing wiki pages (for Claude prompts)."""
    if not pages:
        return "(no existing wiki pages)"
    lines = []
    for path, content in sorted(pages.items()):
        first_heading = content.split("\n")[0].lstrip("# ").strip()
        lines.append(f"- {path}: {first_heading}")
    return "\n".join(lines)


# ── Index + log maintenance ───────────────────────────────────────────────────

def update_wiki_index() -> Path:
    """Rebuild ``_index.md`` as a catalog of all wiki pages. Returns path."""
    WIKI_DIR.mkdir(parents=True, exist_ok=True)
    index_path = WIKI_DIR / "_index.md"
    pages = _get_existing_pages()

    categories: dict[str, list[tuple[str, str, str]]] = {}
    for path, content in sorted(pages.items()):
        parts = path.split("/")
        category = parts[0] if len(parts) > 1 else "misc"
        first_heading = content.split("\n")[0].lstrip("# ").strip()
        slug = parts[-1].replace(".md", "")
        categories.setdefault(category, []).append((slug, first_heading, path))

    total = sum(len(v) for v in categories.values())
    lines = [
        "# Wiki Index",
        f"*Updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*",
        f"*Total pages: {total}*",
        "",
    ]
    for cat, entries in sorted(categories.items()):
        lines.append(f"## {cat.title()} ({len(entries)})")
        for slug, title, path in entries:
            lines.append(f"- [[{path.replace('.md', '')}]] — {title}")
        lines.append("")

    index_path.write_text("\n".join(lines), encoding="utf-8")
    return index_path


def _append_log(
    action: str,
    doc_title: str,
    summary: str,
    pages: list[dict],
) -> None:
    """Prepend an entry to ``_log.md`` (most recent first)."""
    WIKI_DIR.mkdir(parents=True, exist_ok=True)
    log_path = WIKI_DIR / "_log.md"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    pages_str = (
        ", ".join(p.get("title", p.get("path", "?")) for p in pages) or "—"
    )
    entry = (
        f"## [{timestamp}] {action} | {doc_title}\n"
        f"{summary}\n"
        f"*Pages: {pages_str}*\n\n"
    )
    if log_path.exists():
        existing = log_path.read_text(encoding="utf-8")
        # Insert after the header line if present
        header_end = existing.find("\n\n")
        if existing.startswith("# ") and header_end != -1:
            log_path.write_text(
                existing[: header_end + 2] + entry + existing[header_end + 2 :],
                encoding="utf-8",
            )
            return
        log_path.write_text(entry + existing, encoding="utf-8")
    else:
        log_path.write_text("# Activity Log\n\n" + entry, encoding="utf-8")


# ── Core synthesis ────────────────────────────────────────────────────────────

def synthesize_wiki_update(content: str, metadata: dict) -> list[dict]:
    """Call Claude to extract entities/concepts and write wiki pages.

    Returns a list of ``{"path", "title", "action"}`` dicts for each page
    written.  Returns ``[]`` silently when:
    - ``ANTHROPIC_API_KEY`` is not set, or
    - the *anthropic* package is not installed, or
    - Claude returns unparseable output.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return []

    try:
        from anthropic import Anthropic  # noqa: PLC0415
    except ImportError:
        return []

    WIKI_DIR.mkdir(parents=True, exist_ok=True)

    existing = _get_existing_pages()
    content_excerpt = content[:4000] + ("\n\n[... content truncated ...]" if len(content) > 4000 else "")

    prompt = f"""You are maintaining a personal knowledge base wiki. A new document has been ingested.

DOCUMENT:
- Title: {metadata.get("title", "Unknown")}
- Type:  {metadata.get("type", "unknown")}
- Source: {metadata.get("source", "unknown")}

CONTENT:
{content_excerpt}

EXISTING WIKI PAGES:
{_index_summary(existing)}

TASK:
Extract 2-4 key entities (people, organisations, tools, products, places) and 1-2 key concepts/topics from this document. For each, write a concise wiki page.

RULES:
- Entity pages  → path "entities/<kebab-case>.md"
- Concept pages → path "concepts/<kebab-case>.md"
- Each page: 100-250 words, encyclopedic tone, present tense
- Use [[path/without-extension]] syntax for internal cross-references
- If a page already exists in the list above → set action "update" and merge the new information; otherwise → "create"
- SKIP pages for trivially generic topics (e.g. "document", "file", "text")

Return ONLY valid JSON — no markdown fences, no extra text:
{{
  "summary": "One-sentence summary of this document.",
  "pages": [
    {{
      "path": "entities/example.md",
      "title": "Example",
      "category": "entity",
      "action": "create",
      "content": "# Example\\n\\nContent here..."
    }}
  ]
}}"""

    try:
        client = Anthropic(api_key=api_key)
        response = client.messages.create(
            model=WIKI_MODEL,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()

        # Strip markdown fences if Claude added them despite instructions
        fence_match = re.search(r"```(?:json)?\n?(.*?)```", raw, re.DOTALL)
        if fence_match:
            raw = fence_match.group(1).strip()

        data = json.loads(raw)

        results: list[dict] = []
        for page in data.get("pages", []):
            path_rel: str = page["path"].replace("\\", "/")
            page_path = WIKI_DIR / path_rel
            page_path.parent.mkdir(parents=True, exist_ok=True)
            page_path.write_text(page["content"], encoding="utf-8")
            results.append(
                {
                    "path": path_rel,
                    "title": page.get("title", page_path.stem),
                    "action": page.get("action", "create"),
                }
            )

        update_wiki_index()
        _append_log(
            action="ingest",
            doc_title=metadata.get("title", "Unknown"),
            summary=data.get("summary", ""),
            pages=results,
        )
        return results

    except Exception as exc:
        warnings.warn(f"Wiki synthesis failed ({exc}); skipping wiki update.")
        return []


# ── Wiki query ────────────────────────────────────────────────────────────────

def query_wiki(question: str) -> dict:
    """Answer *question* using the wiki content via Claude.

    Returns ``{"answer": markdown_str, "pages_consulted": [path, ...]}``.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {
            "answer": "ANTHROPIC_API_KEY not configured.",
            "pages_consulted": [],
        }

    try:
        from anthropic import Anthropic  # noqa: PLC0415
    except ImportError:
        return {
            "answer": "The *anthropic* package is not installed.",
            "pages_consulted": [],
        }

    pages = _get_existing_pages()
    if not pages:
        return {
            "answer": (
                "The wiki is empty. "
                "Ingest some documents first to build the knowledge base."
            ),
            "pages_consulted": [],
        }

    # Include all pages up to ~25 K chars of context
    context_parts: list[str] = []
    total_chars = 0
    consulted: list[str] = []
    for path, page_content in sorted(pages.items()):
        if total_chars + len(page_content) > 25_000:
            break
        context_parts.append(f"### {path}\n{page_content}")
        total_chars += len(page_content)
        consulted.append(path)

    wiki_context = "\n\n---\n\n".join(context_parts)

    prompt = f"""You are a personal knowledge base assistant. Answer the question below using ONLY the wiki content provided.

WIKI CONTENT:
{wiki_context}

QUESTION: {question}

Instructions:
- Answer based only on the wiki content above
- If the answer is not in the wiki, say so clearly
- Use markdown formatting (headers, bullets, bold as appropriate)
- Cite sources in parentheses, e.g. (entities/openai)
- Be concise and direct"""

    try:
        client = Anthropic(api_key=api_key)
        response = client.messages.create(
            model=WIKI_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        answer = response.content[0].text.strip()

        _append_log(
            action="query",
            doc_title=question[:60],
            summary=f"Q: {question[:100]}",
            pages=[],
        )
        return {"answer": answer, "pages_consulted": consulted}

    except Exception as exc:
        return {"answer": f"Error calling Claude: {exc}", "pages_consulted": []}
