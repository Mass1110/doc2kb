"""FastAPI web application for doc2kb."""
from __future__ import annotations

import hashlib
import shutil
import tempfile
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from ..chunker import chunk_markdown
from ..config import CHUNK_OVERLAP, CHUNK_SIZE
from ..ingestion import ingest
from ..markdown_writer import delete_note, regenerate_index, save_note
from ..store import add_chunks, delete_doc, doc_exists, list_documents
from ..store import query as kb_query

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="doc2kb", version="0.1.0")


def _doc_id_for(source: str) -> str:
    key = source if source.startswith("http") else str(Path(source).resolve())
    return "sha256-" + hashlib.sha256(key.encode()).hexdigest()[:16]


def _do_ingest(source: str, force: bool, langs: list[str]) -> dict:
    doc_id = _doc_id_for(source)
    if not force and doc_exists(doc_id):
        return {"status": "skipped", "doc_id": doc_id, "message": "Already indexed"}

    content, metadata = ingest(source, langs=langs if langs else None)
    save_note(content, metadata)
    chunks = chunk_markdown(content, CHUNK_SIZE, CHUNK_OVERLAP)
    if chunks:
        add_chunks(chunks, metadata)
    regenerate_index()
    return {
        "status": "ok",
        "doc_id": metadata["doc_id"],
        "title": metadata["title"],
        "type": metadata["type"],
        "chunks": len(chunks),
    }


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
        return _do_ingest(tmp_path, force, lang_list)
    except Exception as exc:
        raise HTTPException(500, str(exc)) from exc
    finally:
        Path(tmp_path).unlink(missing_ok=True)


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


# Serve static files and SPA root
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def root() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
