"""Fetch a URL and extract clean markdown via trafilatura."""
from __future__ import annotations

import hashlib
from datetime import datetime
from urllib.parse import urlparse

import trafilatura


def ingest_web(url: str) -> tuple[str, dict]:
    downloaded = trafilatura.fetch_url(url)
    if not downloaded:
        raise ValueError(f"Could not fetch URL: {url}")

    text = trafilatura.extract(
        downloaded,
        include_tables=True,
        include_images=False,
        output_format="markdown",
    )
    if not text:
        raise ValueError(f"Could not extract content from: {url}")

    meta_raw = trafilatura.extract_metadata(downloaded)
    title = (meta_raw.title if meta_raw and meta_raw.title else "") or urlparse(url).netloc

    doc_id = "sha256-" + hashlib.sha256(url.encode()).hexdigest()[:16]

    metadata = {
        "title": title,
        "source": url,
        "type": "web",
        "date_ingested": datetime.now().isoformat(timespec="seconds"),
        "tags": [],
        "doc_id": doc_id,
    }
    return text, metadata
