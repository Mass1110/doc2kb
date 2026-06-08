"""FastAPI web application for doc2kb."""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from ..chunker import chunk_markdown
from ..config import CHUNK_OVERLAP, CHUNK_SIZE, WIKI_DIR
from ..ingestion import ingest, collect_files
from ..markdown_writer import delete_note, regenerate_index, save_note
from ..store import add_chunks, delete_doc, doc_exists, list_documents
from ..store import query as kb_query
from ..utils import content_doc_id, url_doc_id

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="doc2kb", version="0.3.0")


def _doc_id_for(source: str) -> str:
    if source.startswith("http://") or source.startswith("https://"):
        return url_doc_id(source)
    return content_doc_id(Path(source))


def _do_ingest(
    source: str,
    force: bool,
    langs: list[str],
    display_name: str | None = None,
) -> dict:
    doc_id = _doc_id_for(source)
    if not force and doc_exists(doc_id):
        return {"status": "skipped", "doc_id": doc_id, "message": "Already indexed"}

    content, metadata = ingest(source, langs=langs if langs else None)

    # For file uploads the source is a temp path — replace title and source
    # with the original filename so vault notes get friendly names.
    if display_name:
        metadata["title"] = Path(display_name).stem
        metadata["source"] = display_name

    save_note(content, metadata)
    chunks = chunk_markdown(content, CHUNK_SIZE, CHUNK_OVERLAP)
    if chunks:
        add_chunks(chunks, metadata)
    regenerate_index()

    # Wiki synthesis (optional — requires ANTHROPIC_API_KEY + anthropic package)
    wiki_pages: list[dict] = []
    try:
        from ..wiki_writer import synthesize_wiki_update  # noqa: PLC0415
        wiki_pages = synthesize_wiki_update(content, metadata)
    except Exception:
        pass

    return {
        "status": "ok",
        "doc_id": metadata["doc_id"],
        "title": metadata["title"],
        "type": metadata["type"],
        "chunks": len(chunks),
        "wiki_pages": len(wiki_pages),
    }


# ── Ingest endpoints ──────────────────────────────────────────────────────────

@app.post("/api/ingest/url")
async def ingest_url_endpoint(body: dict) -> dict:
    url: str = body.get("url", "").strip()
    if not url:
        raise HTTPException(400, "Missing 'url' field")
    force: bool = body.get("force", False)
    langs: list[str] = body.get("langs", ["en"])
    try:
        return _do_ingest(url, force, langs)
    except Exception as exc:
        raise HTTPException(500, str(exc)) from exc


@app.post("/api/ingest/file")
async def ingest_file_endpoint(
    file: Annotated[UploadFile, File()],
    force: Annotated[bool, Form()] = False,
    langs: Annotated[str, Form()] = "en",
) -> dict:
    lang_list = [l.strip() for l in langs.split(",") if l.strip()]
    suffix = Path(file.filename or "upload").suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name
    try:
        return _do_ingest(tmp_path, force, lang_list, display_name=file.filename)
    except Exception as exc:
        raise HTTPException(500, str(exc)) from exc
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@app.post("/api/ingest/dir")
async def ingest_dir_endpoint(body: dict) -> dict:
    directory: str = body.get("directory", "").strip()
    if not directory:
        raise HTTPException(400, "Missing 'directory' field")
    dir_path = Path(directory)
    if not dir_path.is_dir():
        raise HTTPException(400, f"Not a directory: {directory}")
    force: bool = body.get("force", False)
    langs: list[str] = body.get("langs", ["en"])

    files = collect_files(dir_path)
    if not files:
        return {"status": "empty", "message": "No supported files found", "files": 0}

    results = []
    for f in files:
        try:
            result = _do_ingest(str(f), force, langs)
            results.append({"file": str(f), **result})
        except Exception as exc:
            results.append({"file": str(f), "status": "error", "message": str(exc)})

    ok = sum(1 for r in results if r.get("status") == "ok")
    skipped = sum(1 for r in results if r.get("status") == "skipped")
    errors = sum(1 for r in results if r.get("status") == "error")
    return {
        "status": "ok",
        "total": len(files),
        "indexed": ok,
        "skipped": skipped,
        "errors": errors,
        "details": results,
    }


# ── Query / document endpoints ────────────────────────────────────────────────

@app.get("/api/query")
async def query_endpoint(
    q: str = Query(..., description="Search query"),
    n: int = Query(5, ge=1, le=20, description="Number of results"),
) -> list[dict]:
    try:
        return kb_query(q, n_results=n)
    except Exception as exc:
        raise HTTPException(500, str(exc)) from exc


@app.get("/api/documents")
async def documents_endpoint() -> list[dict]:
    return list_documents()


@app.delete("/api/documents/{doc_id}")
async def delete_document_endpoint(doc_id: str) -> dict:
    chunks = delete_doc(doc_id)
    note = delete_note(doc_id)
    regenerate_index()
    return {
        "doc_id": doc_id,
        "chunks_removed": chunks,
        "note_deleted": note is not None,
    }


@app.post("/api/index")
async def rebuild_index_endpoint() -> dict:
    path = regenerate_index()
    return {"path": str(path)}


# ── Wiki endpoints ────────────────────────────────────────────────────────────

@app.get("/api/wiki/pages")
async def wiki_pages_endpoint() -> dict:
    """Return a flat list of all wiki pages, annotated with category and meta flag."""
    pages: list[dict] = []
    if WIKI_DIR.exists():
        for f in sorted(WIKI_DIR.rglob("*.md")):
            rel = str(f.relative_to(WIKI_DIR)).replace("\\", "/")
            parts = rel.split("/")
            pages.append(
                {
                    "path": rel,
                    "name": f.stem,
                    "category": parts[0] if len(parts) > 1 else "_root",
                    "is_meta": f.name.startswith("_"),
                }
            )
    return {"pages": pages}


@app.get("/api/wiki/page")
async def wiki_page_endpoint(path: str = Query(...)) -> dict:
    """Return the markdown content of a single wiki page."""
    # Security: prevent path traversal
    try:
        target = (WIKI_DIR / path).resolve()
        if not str(target).startswith(str(WIKI_DIR.resolve())):
            raise HTTPException(403, "Invalid path")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(403, "Invalid path")
    if not target.exists():
        raise HTTPException(404, "Page not found")
    return {"path": path, "content": target.read_text(encoding="utf-8")}


@app.post("/api/wiki/query")
async def wiki_query_endpoint(body: dict) -> dict:
    """Answer a question using wiki content via Claude."""
    question = body.get("question", "").strip()
    if not question:
        raise HTTPException(400, "Missing 'question' field")
    try:
        from ..wiki_writer import query_wiki  # noqa: PLC0415
        return query_wiki(question)
    except Exception as exc:
        raise HTTPException(500, str(exc)) from exc


@app.get("/api/wiki/log")
async def wiki_log_endpoint() -> dict:
    """Return the 25 most recent activity log entries."""
    log_path = WIKI_DIR / "_log.md"
    if not log_path.exists():
        return {"entries": []}

    content = log_path.read_text(encoding="utf-8")
    entries: list[dict] = []
    for block in content.split("## [")[1:]:
        lines = block.strip().split("\n")
        if not lines:
            continue
        header = lines[0]
        try:
            ts_part, rest = header.split("] ", 1)
            action, title = rest.split(" | ", 1) if " | " in rest else (rest, "")
        except Exception:
            continue
        summary = lines[1].strip() if len(lines) > 1 else ""
        entries.append(
            {
                "timestamp": ts_part.strip(),
                "action": action.strip(),
                "title": title.strip(),
                "summary": summary,
            }
        )
    return {"entries": entries[:25]}


# ── Stats endpoint ────────────────────────────────────────────────────────────

@app.get("/api/stats")
async def stats_endpoint() -> dict:
    """Return dashboard summary statistics."""
    docs = list_documents()
    wiki_pages = 0
    wiki_categories: set[str] = set()
    if WIKI_DIR.exists():
        for f in WIKI_DIR.rglob("*.md"):
            if not f.name.startswith("_"):
                wiki_pages += 1
                parts = str(f.relative_to(WIKI_DIR)).replace("\\", "/").split("/")
                if len(parts) > 1:
                    wiki_categories.add(parts[0])
    return {
        "total_docs": len(docs),
        "wiki_pages": wiki_pages,
        "wiki_categories": len(wiki_categories),
    }


# ── Static files / SPA ───────────────────────────────────────────────────────

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def root() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
