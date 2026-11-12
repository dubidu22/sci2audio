"""The document every stage passes along: blocks of source text, sections and spans.

Extraction builds a `Document`; nothing changes it afterwards. Text steps point into it with
`Span`s, so the original text stays available for read-along and the "what changed" report.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import StrEnum


class SpanError(ValueError):
    """A span that does not lie inside the text of its block."""


class SourceFormat(StrEnum):
    """The kind of file a document was read from."""

    PDF = "pdf"
    EPUB = "epub"
    MARKDOWN = "markdown"
    TEXT = "text"


@dataclass(frozen=True)
class Source:
    """Where a document came from: the file name (never a full path), its format and hash."""

    name: str
    format: SourceFormat
    sha256: str = ""  # hex digest of the file's bytes, to recognise the same file again

    def __post_init__(self) -> None:
        if not self.name or "/" in self.name or "\\" in self.name:
            raise ValueError(f"source name must be a bare file name, got {self.name!r}")


@dataclass(frozen=True)
class Metadata:
    """What the file says about itself; empty where it says nothing."""

    title: str = ""
    authors: tuple[str, ...] = ()
    date: str = ""  # as the file gives it, e.g. "2024" or "2024-03-01"
    identifier: str = ""  # DOI, ISBN or arXiv id


@dataclass(frozen=True)
class Region:
    """A rectangle on a PDF page, in points from the top left, where part of a block stands.

    `start` is the character offset in the block's text where this region's text begins, so a
    paragraph that runs across a column or page break knows which page each sentence is on.
    """

    page: int  # 1 = first page of the file
    x0: float
    y0: float
    x1: float
    y1: float
    start: int = 0

    def __post_init__(self) -> None:
        for name in ("x0", "y0", "x1", "y1"):  # 72 and 72.0 export the same
            object.__setattr__(self, name, float(getattr(self, name)))
        if self.page < 1 or self.start < 0:
            raise ValueError(f"region needs page >= 1 and start >= 0, got {self}")
        coords = (self.x0, self.y0, self.x1, self.y1)
        if not all(math.isfinite(c) for c in coords) or self.x0 > self.x1 or self.y0 > self.y1:
            raise ValueError(f"region needs finite x0 <= x1 and y0 <= y1, got {self}")


@dataclass(frozen=True)
class Origin:
    """Where a block stands in the source: regions for PDF, chapter for EPUB, line for text."""

    regions: tuple[Region, ...] = ()  # in reading order, `start` strictly increasing from 0
    chapter: int | None = None  # 1 = first document in the EPUB spine
    line: int | None = None  # 1 = first line of a Markdown or text file

    def __post_init__(self) -> None:
        starts = [r.start for r in self.regions]
        if starts and (starts[0] != 0 or starts != sorted(set(starts))):
            raise ValueError(f"region starts must begin at 0 and increase, got {starts}")
        for name in ("chapter", "line"):
            value = getattr(self, name)
            if value is not None and value < 1:
                raise ValueError(f"origin {name} must be >= 1, got {value}")

    @property
    def page(self) -> int | None:
        """The page the block starts on, or None outside PDFs."""
        return self.regions[0].page if self.regions else None


class BlockKind(StrEnum):
    """What a block is. Tables and formulas are placeholders in v1.0 (D-55)."""

    PARAGRAPH = "paragraph"
    HEADING = "heading"
    FOOTNOTE = "footnote"
    CAPTION = "caption"
    LIST_ITEM = "list_item"
    TABLE = "table"
    FORMULA = "formula"


PLACEHOLDER_KINDS = frozenset({BlockKind.TABLE, BlockKind.FORMULA})


@dataclass(frozen=True)
class Block:
    """One piece of the source text as extracted, never changed afterwards.

    A table or formula block is a placeholder: its text is what extraction found (may be
    empty), and a text step proposes the spoken notice that replaces it (D-55).
    """

    kind: BlockKind
    text: str
    origin: Origin = field(default_factory=Origin)

    def __post_init__(self) -> None:
        if self.origin.regions and self.origin.regions[-1].start > len(self.text):
            raise ValueError("a region starts beyond the end of the block's text")

    @property
    def is_placeholder(self) -> bool:
        """True for tables and formulas, which are not read out in v1.0."""
        return self.kind in PLACEHOLDER_KINDS


@dataclass(frozen=True)
class Span:
    """Characters `start` up to (not including) `end` of block number `block`.

    An empty span (start == end) marks a position, e.g. where a pause goes.
    """

    block: int  # index into Document.blocks
    start: int
    end: int

    def __post_init__(self) -> None:
        if not 0 <= self.start <= self.end or self.block < 0:
            raise SpanError(f"span needs block >= 0 and 0 <= start <= end, got {self}")


@dataclass(frozen=True)
class Section:
    """A heading and the blocks under it: blocks `start` up to (not including) `end`.

    Children lie inside their parent, in order and without overlap.
    """

    title: str
    level: int  # 1 = top level
    start: int
    end: int
    children: tuple[Section, ...] = ()

    def __post_init__(self) -> None:
        if self.level < 1 or not 0 <= self.start <= self.end:
            raise ValueError(f"section {self.title!r} needs level >= 1 and start <= end")
        _check_ranges(self.children, self.start, self.end, f"section {self.title!r}")
        if any(child.level <= self.level for child in self.children):
            raise ValueError(f"children of section {self.title!r} must have a deeper level")


def _check_ranges(sections: tuple[Section, ...], start: int, end: int, where: str) -> None:
    position = start
    for section in sections:
        if section.start < position or section.end > end:
            raise ValueError(f"{where}: section {section.title!r} overlaps or lies outside")
        position = section.end


@dataclass(frozen=True)
class Document:
    """A whole source file as blocks in reading order, with its section tree."""

    source: Source
    language: str  # BCP 47 tag, e.g. "en" or "en-GB"
    blocks: tuple[Block, ...]
    metadata: Metadata = field(default_factory=Metadata)
    sections: tuple[Section, ...] = ()

    def __post_init__(self) -> None:
        if not self.language:
            raise ValueError("document language must be set, e.g. 'en'")
        _check_ranges(self.sections, 0, len(self.blocks), "document")

    def check_span(self, span: Span) -> None:
        """Raise SpanError unless the span lies inside the text of its block."""
        if span.block >= len(self.blocks):
            raise SpanError(
                f"{span} points at block {span.block}, but there are {len(self.blocks)}"
            )
        if span.end > len(self.blocks[span.block].text):
            length = len(self.blocks[span.block].text)
            raise SpanError(f"{span} ends after the block's text ({length} characters)")

    def text_of(self, span: Span) -> str:
        """The original text a span covers."""
        self.check_span(span)
        return self.blocks[span.block].text[span.start : span.end]
