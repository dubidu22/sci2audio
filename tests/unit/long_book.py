"""A generated book of 1,000 pages and its read-along data, for the Listen page's speed
(#392): ten chapters, three paragraphs of ten sentences on every page, one chunk per
sentence, a second each. Made in the test; no text of it is in the repository."""

from __future__ import annotations

from sci2audio.core import Document, Section, Span
from sci2audio.output import ReadAlong
from sci2audio.output.readalong import ChapterTimes, ChunkTimes
from sci2audio.testing.documents import make_document

PAGES = 1000
CHAPTERS = 10
PARAGRAPHS = 3  # per page
SENTENCES = 10  # per paragraph


def long_book(m4b: str = "Book.m4b") -> tuple[Document, ReadAlong]:
    """The book and a read-along of it in M4B form (one file, no MP3s)."""
    blocks: list[tuple[str, str]] = []
    pages: dict[int, int] = {}
    sections: list[Section] = []
    spans: list[tuple[int, int, int]] = []
    owners: list[int] = []
    firsts: list[int] = []
    per_chapter = PAGES // CHAPTERS
    for chapter in range(CHAPTERS):
        start = len(blocks)
        firsts.append(len(spans))
        title = f"Chapter {chapter + 1}"
        pages[len(blocks)] = chapter * per_chapter + 1
        spans.append((len(blocks), 0, len(title)))
        owners.append(chapter)
        blocks.append(("heading", title))
        for page in range(chapter * per_chapter + 1, (chapter + 1) * per_chapter + 1):
            for paragraph in range(PARAGRAPHS):
                said = [
                    f"Sentence {k + 1} of paragraph {paragraph + 1} on page {page} goes on."
                    for k in range(SENTENCES)
                ]
                at = 0
                for sentence in said:
                    spans.append((len(blocks), at, at + len(sentence)))
                    owners.append(chapter)
                    at += len(sentence) + 1
                pages[len(blocks)] = page
                blocks.append(("paragraph", " ".join(said)))
        sections.append(Section(title, 1, start, len(blocks)))
    document = make_document(blocks, sections=sections, pages=pages)
    chunks = tuple(
        ChunkTimes(owners[n], float(n), n + 0.9, Span(*span)) for n, span in enumerate(spans)
    )
    ends = [*firsts[1:], len(spans)]
    times = tuple(
        ChapterTimes(f"Chapter {c + 1}", None, float(first), float(end), first)
        for c, (first, end) in enumerate(zip(firsts, ends, strict=True))
    )
    return document, ReadAlong(24000, float(len(spans)), m4b, times, chunks)
