"""Tests for doc2kb.utils — doc_id helpers."""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from doc2kb.utils import content_doc_id, url_doc_id


class TestContentDocId:
    def test_returns_sha256_prefix(self, tmp_path):
        f = tmp_path / "file.txt"
        f.write_bytes(b"hello")
        doc_id = content_doc_id(f)
        assert doc_id.startswith("sha256-")

    def test_length(self, tmp_path):
        f = tmp_path / "file.txt"
        f.write_bytes(b"data")
        doc_id = content_doc_id(f)
        # "sha256-" (7) + 16 hex chars
        assert len(doc_id) == 23

    def test_same_content_same_id(self, tmp_path):
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_bytes(b"same content")
        f2.write_bytes(b"same content")
        assert content_doc_id(f1) == content_doc_id(f2)

    def test_different_content_different_id(self, tmp_path):
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_bytes(b"content A")
        f2.write_bytes(b"content B")
        assert content_doc_id(f1) != content_doc_id(f2)

    def test_empty_file(self, tmp_path):
        f = tmp_path / "empty.txt"
        f.write_bytes(b"")
        doc_id = content_doc_id(f)
        assert doc_id.startswith("sha256-")

    def test_path_invariant(self, tmp_path):
        """Same bytes at different paths → same id."""
        subdir = tmp_path / "sub"
        subdir.mkdir()
        f1 = tmp_path / "x.bin"
        f2 = subdir / "x.bin"
        data = b"\x00\x01\x02" * 100
        f1.write_bytes(data)
        f2.write_bytes(data)
        assert content_doc_id(f1) == content_doc_id(f2)

    def test_expected_value(self, tmp_path):
        f = tmp_path / "f.txt"
        content = b"test"
        f.write_bytes(content)
        expected = "sha256-" + hashlib.sha256(content).hexdigest()[:16]
        assert content_doc_id(f) == expected


class TestUrlDocId:
    def test_returns_sha256_prefix(self):
        doc_id = url_doc_id("https://example.com")
        assert doc_id.startswith("sha256-")

    def test_length(self):
        doc_id = url_doc_id("https://example.com/page")
        assert len(doc_id) == 23

    def test_same_url_same_id(self):
        url = "https://example.com/article"
        assert url_doc_id(url) == url_doc_id(url)

    def test_different_urls_different_ids(self):
        assert url_doc_id("https://a.com") != url_doc_id("https://b.com")

    def test_expected_value(self):
        url = "https://example.com"
        expected = "sha256-" + hashlib.sha256(url.encode()).hexdigest()[:16]
        assert url_doc_id(url) == expected
