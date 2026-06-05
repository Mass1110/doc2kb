"""doc2kb CLI — ingest, query, list, index, delete, serve."""
from __future__ import annotations

from pathlib import Path

import click

from .config import CHUNK_SIZE, CHUNK_OVERLAP
from .ingestion import ingest
from .markdown_writer import save_note, regenerate_index, delete_note
from .chunker import chunk_markdown
from .store import add_chunks, doc_exists, query as kb_query, list_documents, delete_doc
from .config import VAULT_DIR, CHROMA_DIR
from .utils import content_doc_id, url_doc_id


@click.group()
def cli() -> None:
    """doc2kb: ingest documents into an Obsidian vault + ChromaDB knowledge base."""


@cli.command("ingest")
@click.argument("source")
@click.option("--force", is_flag=True, help="Re-ingest even if already indexed.")
@click.option("--batch", is_flag=True, help="Treat SOURCE as a file of sources (one per line).")
@click.option(
    "--lang",
    multiple=True,
    default=["en"],
    show_default=True,
    help="OCR language code(s) for image files (EasyOCR). E.g. --lang it --lang en",
)
def ingest_cmd(source: str, force: bool, batch: bool, lang: tuple[str, ...]) -> None:
    """Ingest a URL, local file, or batch file into the knowledge base."""
    langs = list(lang)
    if batch:
        sources = [
            line.strip()
            for line in Path(source).read_text().splitlines()
            if line.strip() and not line.startswith("#")
        ]
    else:
        sources = [source]

    for src in sources:
        _do_ingest(src, force, langs)


def _doc_id_for(source: str) -> str:
    if source.startswith("http://") or source.startswith("https://"):
        return url_doc_id(source)
    return content_doc_id(Path(source))


def _do_ingest(source: str, force: bool, langs: list[str] | None = None) -> None:
    doc_id = _doc_id_for(source)

    if not force and doc_exists(doc_id):
        click.echo(f"[skip] Already indexed: {source}  (use --force to re-ingest)")
        return

    click.echo(f"[ingest] {source}")
    try:
        content, metadata = ingest(source, langs=langs)
    except Exception as exc:
        click.echo(f"[error] {exc}", err=True)
        return

    note_path = save_note(content, metadata)
    click.echo(f"  → note saved: {note_path}")

    chunks = chunk_markdown(content, CHUNK_SIZE, CHUNK_OVERLAP)
    if not chunks:
        click.echo("  [warn] No chunks produced — skipping vector store.")
        return

    add_chunks(chunks, metadata)
    click.echo(f"  → {len(chunks)} chunk(s) indexed in ChromaDB")


@cli.command("query")
@click.argument("text")
@click.option("-n", "--results", default=5, show_default=True, help="Number of results.")
def query_cmd(text: str, results: int) -> None:
    """Semantic search across the knowledge base."""
    hits = kb_query(text, n_results=results)
    if not hits:
        click.echo("No results found.")
        return
    for i, hit in enumerate(hits, start=1):
        click.echo(
            f"\n[{i}] score={hit['score']}  type={hit['type']}\n"
            f"    source: {hit['source']}\n"
            f"    title:  {hit['title']}\n"
            f"    ---\n"
            f"    {hit['text'][:300].replace(chr(10), ' ')}"
        )


@cli.command("list")
def list_cmd() -> None:
    """List all indexed documents."""
    docs = list_documents()
    if not docs:
        click.echo("Knowledge base is empty.")
        return
    click.echo(f"{'TYPE':<12} {'DOC_ID':<22} {'TITLE':<36} SOURCE")
    click.echo("-" * 100)
    for doc in sorted(docs, key=lambda d: d["type"]):
        click.echo(
            f"{doc['type']:<12} {doc['doc_id']:<22} "
            f"{doc['title'][:34]:<36} {doc['source'][:50]}"
        )


@cli.command("delete")
@click.argument("source", required=False)
@click.option("--doc-id", "doc_id", default=None, help="Delete by explicit doc_id.")
def delete_cmd(source: str | None, doc_id: str | None) -> None:
    """Remove a document from the knowledge base (ChromaDB + Obsidian vault).

    Pass the same SOURCE used during ingestion, or use --doc-id.
    """
    if not source and not doc_id:
        raise click.UsageError("Provide SOURCE or --doc-id.")

    target_id = doc_id if doc_id else _doc_id_for(source)

    chunks_removed = delete_doc(target_id)
    if chunks_removed == 0:
        click.echo(f"[warn] No chunks found for doc_id={target_id}")
    else:
        click.echo(f"  → {chunks_removed} chunk(s) removed from ChromaDB")

    note_path = delete_note(target_id)
    if note_path:
        click.echo(f"  → note deleted: {note_path}")
    else:
        click.echo("  [warn] No vault note found for this document.")

    regenerate_index()
    click.echo("  → _INDEX.md regenerated")


@cli.command("reset")
@click.option("--yes", is_flag=True, help="Skip confirmation prompt.")
def reset_cmd(yes: bool) -> None:
    """Delete all data: ChromaDB collection + Obsidian vault notes."""
    import shutil

    if not yes:
        click.confirm(
            "Questo cancellerà tutto il database e tutte le note del vault. Continuare?",
            abort=True,
        )

    # Remove ChromaDB
    if CHROMA_DIR.exists():
        shutil.rmtree(CHROMA_DIR)
        click.echo(f"  → ChromaDB eliminato: {CHROMA_DIR}")
    else:
        click.echo("  [skip] ChromaDB non trovato.")

    # Remove all vault notes except _INDEX.md and .obsidian settings
    removed = 0
    if VAULT_DIR.exists():
        for f in VAULT_DIR.glob("*.md"):
            if f.name != "_INDEX.md":
                f.unlink()
                removed += 1
        click.echo(f"  → {removed} nota/e eliminate dal vault.")
        regenerate_index()
        click.echo("  → _INDEX.md rigenerato.")
    else:
        click.echo("  [skip] Vault non trovato.")

    click.echo("Reset completato.")


@cli.command("index")
def index_cmd() -> None:
    """Regenerate the _INDEX.md file in the Obsidian vault."""
    path = regenerate_index()
    click.echo(f"Index written: {path}")


@cli.command("serve")
@click.option("--host", default="127.0.0.1", show_default=True, help="Bind host.")
@click.option("--port", default=8000, show_default=True, type=int, help="Bind port.")
def serve_cmd(host: str, port: int) -> None:
    """Start the doc2kb web frontend."""
    try:
        import uvicorn
    except ImportError:
        raise click.ClickException(
            "Web dependencies not installed. Run: pip install -e \".[web]\""
        )
    from .webapp.app import app

    click.echo(f"Starting doc2kb web UI at http://{host}:{port}")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    cli()
