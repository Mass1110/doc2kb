"""doc2kb CLI — ingest, query, list, index."""
from __future__ import annotations

import sys
from pathlib import Path

import click

from .config import CHUNK_SIZE, CHUNK_OVERLAP
from .ingestion import ingest
from .markdown_writer import save_note, regenerate_index
from .chunker import chunk_markdown
from .store import add_chunks, doc_exists, query as kb_query, list_documents


@click.group()
def cli() -> None:
    """doc2kb: ingest documents into an Obsidian vault + ChromaDB knowledge base."""


@cli.command()
@click.argument("source")
@click.option("--force", is_flag=True, help="Re-ingest even if already indexed.")
@click.option("--batch", is_flag=True, help="Treat SOURCE as a file of sources (one per line).")
def ingest_cmd(source: str, force: bool, batch: bool) -> None:
    """Ingest a URL, local file, or batch file into the knowledge base."""
    sources = []
    if batch:
        sources = [
            line.strip()
            for line in Path(source).read_text().splitlines()
            if line.strip() and not line.startswith("#")
        ]
    else:
        sources = [source]

    for src in sources:
        _do_ingest(src, force)


def _do_ingest(source: str, force: bool) -> None:
    import hashlib

    # Compute doc_id upfront to check deduplication
    key = source if source.startswith("http") else str(Path(source).resolve())
    doc_id = "sha256-" + hashlib.sha256(key.encode()).hexdigest()[:16]

    if not force and doc_exists(doc_id):
        click.echo(f"[skip] Already indexed: {source}  (use --force to re-ingest)")
        return

    click.echo(f"[ingest] {source}")
    try:
        content, metadata = ingest(source)
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
    click.echo(f"{'TYPE':<12} {'TITLE':<40} SOURCE")
    click.echo("-" * 90)
    for doc in sorted(docs, key=lambda d: d["type"]):
        click.echo(f"{doc['type']:<12} {doc['title'][:38]:<40} {doc['source'][:60]}")


@cli.command("index")
def index_cmd() -> None:
    """Regenerate the _INDEX.md file in the Obsidian vault."""
    path = regenerate_index()
    click.echo(f"Index written: {path}")


# Allow `doc2kb ingest` as an alias for the ingest subcommand
cli.add_command(ingest_cmd, name="ingest")


if __name__ == "__main__":
    cli()
