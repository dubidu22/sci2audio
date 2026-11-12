"""The reading document the layout stage builds from the extracted content (D-63).

Layout decides the reading order, groups the extracted items into `Block`s, gives each a
kind and builds the `Section` tree. Every extracted item ends up in exactly one block, so
nothing is lost silently; page furniture is a block kind that a text step removes with a
marked edit (TP-01). After layout nothing changes the document: text steps point into it
with `Span`s, so the original stays available for read-along and the "what changed" report.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import StrEnum

from sci2audio.core.content import Content


class SpanError(ValueError):
    """A span that does not lie inside the text of its block."""


class BlockKind(StrEnum):
    """What a block is. Tables, formulas and figures are placeholders in v1.0 (D-55)."""

    PARAGRAPH = "paragraph"
    HEADING = "heading"
    FOOTNOTE = "footnote"
    CAPTION = "caption"
    LIST_ITEM = "list_item"
    FURNITURE = "furniture"  # running heads, page and line numbers, side stamps
    TABLE = "table"
    FORMULA = "formula"
    FIGURE = "figure"  # images, charts, diagrams


PLACEHOLDER_KINDS = frozenset({BlockKind.TABLE, BlockKind.FORMULA, BlockKind.FIGURE})


class FurnitureRole(StrEnum):
    """What a furniture block is (#31), named as in the corpus truth files."""

    PAGE_NUMBER = "page-number"
    RUNNING_HEAD = "running-head"  # a line repeated at the top or foot of pages
    FOOTER = "footer"  # a one-off venue or licence line
    SIDE_STAMP = "side-stamp"  # e.g. the arXiv id along the margin
    LINE_NUMBER = "line-number"
    CONTENTS = "contents"  # a printed table of contents
    SIDEBAR = "sidebar"  # e.g. the JOSS metadata column


@dataclass(frozen=True)
class Part:
    """An extracted item a block is made of, and where its text starts in the block's text."""

    item: str  # id of a TextLine, Picture or Drawing in the content
    start: int = 0


@dataclass(frozen=True)
class Block:
    """One unit of the reading order: its kind, its text and the items it came from.

    The text is the block's lines joined by line breaks, as layout found them; joining
    hyphenated words is a text step (TP-02). A placeholder's text is whatever text its items
    hold, possibly none; a text step proposes the spoken notice that replaces it (D-55).
    """

    kind: BlockKind
    text: str
    parts: tuple[Part, ...] = ()  # in reading order, starts not decreasing
    describes: int | None = None  # a caption: index of the table, formula or figure block
    role: FurnitureRole | None = None  # furniture: what it is, if known

    def __post_init__(self) -> None:
        starts = [part.start for part in self.parts]
        if starts != sorted(starts) or (
            starts and not 0 <= starts[0] <= starts[-1] <= len(self.text)
        ):
            raise ValueError(f"part starts must increase within the text, got {starts}")
        if self.describes is not None and self.kind is not BlockKind.CAPTION:
            raise ValueError(f"only a caption describes another block, not a {self.kind}")
        if self.role is not None and self.kind is not BlockKind.FURNITURE:
            raise ValueError(f"only furniture has a furniture role, not a {self.kind}")

    @property
    def is_placeholder(self) -> bool:
        """True for tables, formulas and figures, which are not read out in v1.0."""
        return self.kind in PLACEHOLDER_KINDS

    def part_at(self, offset: int) -> Part | None:
        """The part whose text holds the character at `offset` (read-along), if any."""
        found = None
        for part in self.parts:
            if part.start <= offset:
                found = part
        return found


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
    """The extracted content in reading order: blocks, sections, and the content itself."""

    content: Content
    language: str  # BCP 47 tag, e.g. "en" or "en-GB"
    blocks: tuple[Block, ...]
    sections: tuple[Section, ...] = ()
    # the page label each page prints ("39", "xii"; "" where it prints none), page by
    # page; empty when not known
    page_labels: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.language:
            raise ValueError("document language must be set, e.g. 'en'")
        used = Counter(part.item for block in self.blocks for part in block.parts)
        known = self.content.items().keys()
        if unknown := sorted(used.keys() - known):
            raise ValueError(f"blocks point at items the content doesn't have: {unknown}")
        if missing := sorted(known - used.keys()):
            raise ValueError(f"items in no block (nothing may be lost): {missing}")
        if doubled := sorted(item for item, n in used.items() if n > 1):
            raise ValueError(f"items in more than one block: {doubled}")
        for index, block in enumerate(self.blocks):
            target = block.describes
            if target is not None and not (
                0 <= target < len(self.blocks) and self.blocks[target].is_placeholder
            ):
                raise ValueError(f"caption {index} must describe a table, formula or figure")
        _check_ranges(self.sections, 0, len(self.blocks), "document")
        pages = len(self.content.pages)
        if self.page_labels and len(self.page_labels) != pages:
            raise ValueError(f"{len(self.page_labels)} page labels for {pages} pages")

    def page_label(self, number: int) -> str:
        """The label printed on page `number` (counted from 1), or "" if none is known.

        Raise ValueError for a page the document doesn't have.
        """
        if not 1 <= number <= len(self.content.pages):
            raise ValueError(f"page {number} is not in 1..{len(self.content.pages)}")
        return self.page_labels[number - 1] if self.page_labels else ""

    def check_span(self, span: Span) -> None:
        """Raise SpanError unless the span lies inside the text of its block."""
        if span.block >= len(self.blocks):
            raise SpanError(f"{span} points at block {span.block}; there are {len(self.blocks)}")
        if span.end > len(self.blocks[span.block].text):
            length = len(self.blocks[span.block].text)
            raise SpanError(f"{span} ends after the block's text ({length} characters)")

    def text_of(self, span: Span) -> str:
        """The original text a span covers."""
        self.check_span(span)
        return self.blocks[span.block].text[span.start : span.end]
