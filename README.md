# doc2kb

Ingest any document or webpage into a searchable knowledge base: an **Obsidian vault** of Markdown notes + a **ChromaDB** vector store for semantic (RAG) queries.

## Supported sources

| Source | Extension / Format |
|---|---|
| Webpage | `http://` / `https://` URL |
| PDF | `.pdf` |
| Word document | `.docx` |
| PowerPoint | `.pptx` |
| Plain text | `.txt`, `.md` |
| HTML file | `.html`, `.htm` |
| Handwritten image | `.jpg`, `.png`, `.tiff`, … |

## Installation

```bash
cd doc2kb
pip install -e .          # core dependencies
pip install -e ".[cloud]" # + Google Vision OCR fallback
```

Requires Python ≥ 3.10.

## Quick start

```bash
# Ingest a webpage
doc2kb ingest https://en.wikipedia.org/wiki/Python_(programming_language)

# Ingest a local PDF
doc2kb ingest ./report.pdf

# Ingest a handwritten image (uses TrOCR locally; Google Vision if confidence is low)
doc2kb ingest ./note.jpg

# Ingest many sources at once (one per line in a text file)
doc2kb ingest --batch sources.txt

# Semantic search
doc2kb query "what is Python used for?"

# List all indexed documents
doc2kb list

# Regenerate the Obsidian index note
doc2kb index
```

## Obsidian vault

After ingestion, open `output/obsidian_vault/` in [Obsidian](https://obsidian.md).  
Every document becomes a note with YAML frontmatter (`title`, `source`, `type`, `date_ingested`).  
`_INDEX.md` is auto-generated with `[[wikilinks]]` to all notes, grouped by type.

## Handwriting OCR

1. **Local (default)** — `microsoft/trocr-base-handwritten` via HuggingFace Transformers.
2. **Cloud fallback** — Google Vision API, used automatically when local confidence < 0.75.

To enable cloud fallback set the environment variable before running:

```bash
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
doc2kb ingest ./handwritten_letter.png
```

## Output layout

```
output/
├── obsidian_vault/       ← open this folder in Obsidian
│   ├── _INDEX.md
│   ├── python-programming-language.md
│   ├── report.md
│   └── attachments/      ← original images for handwriting notes
└── chroma_db/            ← ChromaDB vector store (auto-managed)
```

## Re-ingesting a document

By default, already-indexed documents are skipped (deduplication by SHA-256).  
Use `--force` to re-ingest:

```bash
doc2kb ingest --force ./report.pdf
```
