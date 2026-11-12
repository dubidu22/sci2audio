"""What extraction records: everything a file holds, with positions and styles, undecided.

Extraction reads a file into `Content` and decides nothing about it (D-63): no reading order,
no headings, nothing left out. Each page keeps its text lines (made of styled runs), pictures
and drawings with their boxes, in the order the file stores them, which is only a hint. The
layout stage turns this into a `Document`; every item has an id the document points back to.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field
from enum import StrEnum


class SourceFormat(StrEnum):
    """The kind of file the content was read from."""

    PDF = "pdf"
    EPUB = "epub"
    MARKDOWN = "markdown"
    TEXT = "text"


@dataclass(frozen=True)
class Source:
    """Where the content came from: the file name (never a full path), its format and hash."""

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
    language: str = ""  # as the file declares it, e.g. "en"; may be missing or wrong


@dataclass(frozen=True)
class Box:
    """A rectangle on a page in points, (x0, y0) top left and (x1, y1) bottom right."""

    x0: float
    y0: float
    x1: float
    y1: float

    def __post_init__(self) -> None:
        for name in ("x0", "y0", "x1", "y1"):  # 72 and 72.0 export the same
            object.__setattr__(self, name, float(getattr(self, name)))
        coords = (self.x0, self.y0, self.x1, self.y1)
        if not all(math.isfinite(c) for c in coords) or self.x0 > self.x1 or self.y0 > self.y1:
            raise ValueError(f"box needs finite x0 <= x1 and y0 <= y1, got {coords}")


@dataclass(frozen=True)
class TextRun:
    """A piece of a line in one style. Fields the source doesn't give stay at their default.

    `tags` are the source's own markup around the run, e.g. ("h2",) in an EPUB or ("li", "em")
    in Markdown: hints for the layout stage, not decisions.
    """

    text: str
    font: str = ""
    size: float = 0.0  # points; 0 when the source has no sizes
    bold: bool = False
    italic: bool = False
    box: Box | None = None
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "size", float(self.size))
        if not self.text:
            raise ValueError("a text run needs text")
        if not math.isfinite(self.size) or self.size < 0:
            raise ValueError(f"font size must be a finite number >= 0, got {self.size}")


@dataclass(frozen=True)
class TextLine:
    """One line of text as the file has it, made of runs."""

    id: str
    runs: tuple[TextRun, ...]
    box: Box | None = None  # None where the source has no positions (EPUB, text)

    def __post_init__(self) -> None:
        if not self.runs:
            raise ValueError(f"text line {self.id!r} needs at least one run")

    @property
    def text(self) -> str:
        """The line's text, all runs joined."""
        return "".join(run.text for run in self.runs)


@dataclass(frozen=True)
class Picture:
    """An image in the file. The image itself is not kept; its box is enough to find it again."""

    id: str
    box: Box | None = None
    alt: str = ""  # alternative text, where the source gives one


@dataclass(frozen=True)
class Drawing:
    """A vector graphic: a line, rectangle or curve, as in charts and table rules."""

    id: str
    box: Box


@dataclass(frozen=True)
class Page:
    """One page of a PDF, one spine document of an EPUB, or the whole of a text file.

    Each kind of item keeps the order the file stores it in.
    """

    number: int  # 1 = first page
    lines: tuple[TextLine, ...] = ()
    pictures: tuple[Picture, ...] = ()
    drawings: tuple[Drawing, ...] = ()
    width: float | None = None  # points; None where pages have no fixed size
    height: float | None = None

    def __post_init__(self) -> None:
        if self.number < 1:
            raise ValueError(f"page number must be >= 1, got {self.number}")
        if (self.width is None) != (self.height is None):
            raise ValueError(f"page {self.number} needs both width and height, or neither")
        for name in ("width", "height"):
            value = getattr(self, name)
            if value is not None:
                if not math.isfinite(value) or value <= 0:
                    raise ValueError(f"page {self.number} {name} must be > 0, got {value}")
                object.__setattr__(self, name, float(value))


Item = TextLine | Picture | Drawing


@dataclass(frozen=True)
class Content:
    """Everything extraction recorded from one file, page by page."""

    source: Source
    pages: tuple[Page, ...]
    metadata: Metadata = field(default_factory=Metadata)

    def __post_init__(self) -> None:
        numbers = [page.number for page in self.pages]
        if numbers != list(range(1, len(numbers) + 1)):
            raise ValueError(f"pages must be numbered 1, 2, 3, ... in order, got {numbers}")
        counts = Counter(item.id for page in self.pages for item in _items(page))
        doubled = sorted(i for i, n in counts.items() if n > 1)
        if doubled or "" in counts:
            raise ValueError(f"item ids must be unique and non-empty, repeated: {doubled}")

    def items(self) -> dict[str, tuple[Page, Item]]:
        """Every item by its id, with the page it stands on."""
        return {item.id: (page, item) for page in self.pages for item in _items(page)}


def _items(page: Page) -> tuple[Item, ...]:
    return (*page.lines, *page.pictures, *page.drawings)
