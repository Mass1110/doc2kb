"""Tests for doc2kb.chunker — heading-aware sliding-window chunking."""
from __future__ import annotations

import pytest

from doc2kb.chunker import chunk_markdown, _word_count, _sliding_window


class TestWordCount:
    def test_empty(self):
        assert _word_count("") == 0

    def test_single_word(self):
        assert _word_count("hello") == 1

    def test_multiple_words(self):
        assert _word_count("one two three") == 3

    def test_extra_whitespace(self):
        assert _word_count("  a   b  ") == 2


class TestSlidingWindow:
    def test_short_text_single_chunk(self):
        words = " ".join(["word"] * 10)
        chunks = _sliding_window(words, size=20, overlap=5)
        assert len(chunks) == 1
        assert chunks[0] == words

    def test_exact_size(self):
        words = " ".join(["w"] * 10)
        chunks = _sliding_window(words, size=10, overlap=0)
        assert len(chunks) == 1

    def test_two_chunks_with_overlap(self):
        words = " ".join([str(i) for i in range(10)])
        chunks = _sliding_window(words, size=6, overlap=2)
        # step = 6 - 2 = 4  → starts at 0, 4 → 2 chunks
        assert len(chunks) == 2

    def test_overlap_content_shared(self):
        words = "a b c d e f g h"
        chunks = _sliding_window(words, size=4, overlap=2)
        # chunk 0: a b c d, chunk 1: c d e f, chunk 2: e f g h
        assert "c" in chunks[0]
        assert "c" in chunks[1]

    def test_empty_input(self):
        assert _sliding_window("", size=5, overlap=1) == []


class TestChunkMarkdown:
    def test_short_text_single_chunk(self):
        text = "Just a short sentence."
        chunks = chunk_markdown(text, chunk_size=100, overlap=10)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_empty_returns_empty(self):
        assert chunk_markdown("", chunk_size=100, overlap=10) == []

    def test_heading_splits_sections(self):
        text = "# Section A\n\nContent A.\n\n# Section B\n\nContent B."
        chunks = chunk_markdown(text, chunk_size=200, overlap=10)
        # Two sections → two chunks (each short)
        assert any("Section A" in c for c in chunks)
        assert any("Section B" in c for c in chunks)

    def test_long_section_gets_windowed(self):
        long_body = " ".join(["word"] * 600)
        text = f"# Big Section\n\n{long_body}"
        chunks = chunk_markdown(text, chunk_size=200, overlap=20)
        assert len(chunks) > 1

    def test_whitespace_only_text(self):
        assert chunk_markdown("   \n\n   ", chunk_size=100, overlap=10) == []

    def test_multiple_heading_levels(self):
        text = "## H2\n\nBody.\n\n### H3\n\nSub-body."
        chunks = chunk_markdown(text, chunk_size=200, overlap=10)
        assert len(chunks) >= 1

    def test_preamble_before_first_heading(self):
        text = "Intro paragraph.\n\n# Heading\n\nSection content."
        chunks = chunk_markdown(text, chunk_size=200, overlap=10)
        assert any("Intro" in c for c in chunks)

    def test_chunks_are_non_empty_strings(self):
        text = "# A\n\nFoo bar.\n\n# B\n\nBaz qux."
        chunks = chunk_markdown(text, chunk_size=200, overlap=10)
        assert all(isinstance(c, str) and c.strip() for c in chunks)
