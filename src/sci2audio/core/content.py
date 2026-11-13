"""What extraction records: everything a file holds, with positions and styles, undecided.

Extraction reads a file into `Content` and decides nothing about it (D-63): no reading order,
no headings, nothing left out. Each page keeps its text lines (made of styled runs), pictures
and drawings with their boxes, in the order the file stores them, which is only a hint. The
file's own outline (PDF bookmarks, an EPUB's table of contents) is kept as it is stored, as a
hint for headings (#24). The layout stage turns this into a `Document`; every item has an id
the document points back to.
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
    """Where the content came from: the file name (never a full path), its format and hash.

    For a text file (Markdown, plain text) `encoding` names how its bytes were read, as the
    WHATWG Encoding Standard names it ("utf-8", "utf-16le", "windows-1252"); it is empty where
    the format brings its own (PDF, EPUB). `encoding_guessed` is true when the file declared
    no encoding and was not valid UTF-8, so the encoding is a guess a person should check
    (D-345, D-346).
    """

    name: str
    format: SourceFormat
    sha256: str = ""  # hex digest of the file's bytes, to recognise the same file again
    encoding: str = ""
    encoding_guessed: bool = False

    def __post_init__(self) -> None:
        if not self.name or "/" in self.name or "\\" in self.name:
            raise ValueError(f"source name must be a bare file name, got {self.name!r}")
        if self.encoding_guessed and not self.encoding:
            raise ValueError(f"source {self.name!r} has a guessed encoding but names none")
        if self.encoding and self.format in (SourceFormat.PDF, SourceFormat.EPUB):
            raise ValueError(
                f"source {self.name!r} is {self.format.value}, which brings its own encoding,"
                f" but names {self.encoding!r}"
            )


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
    """An image in the file. The image itself is not kept: its box finds it again on a PDF
    page, and `ref` where the file stores images apart from the text (D-310)."""

    id: str
    box: Box | None = None
    alt: str = ""  # alternative text, where the source gives one
    # Where the file stores the image, e.g. its path inside an EPUB: the file's own text as
    # stored, so never trusted as a path to read or write outside that file.
    ref: str = ""


@dataclass(frozen=True)
class Drawing:
    """A vector graphic: a line, rectangle or curve, as in charts and table rules."""

    id: str
    box: Box


@dataclass(frozen=True)
class Page:
    """One page of a PDF, one spine document of an EPUB, or the whole of a text file.

    Each kind of item keeps the order the file stores it in. Where items have no position
    (EPUB, Markdown), `order` lists the ids of all of them, lines and pictures alike, in the
    order the file stores them, so a picture's place between two lines is kept (D-309); it is
    empty where the boxes place the items (PDF).
    """

    number: int  # 1 = first page
    lines: tuple[TextLine, ...] = ()
    pictures: tuple[Picture, ...] = ()
    drawings: tuple[Drawing, ...] = ()
    width: float | None = None  # points; None where pages have no fixed size
    height: float | None = None
    order: tuple[str, ...] = ()

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
        if self.order and sorted(self.order) != sorted(item.id for item in _items(self)):
            raise ValueError(
                f"page {self.number} order must list each of its item ids once, got {self.order}"
            )


Item = TextLine | Picture | Drawing


@dataclass(frozen=True)
class OutlineEntry:
    """One entry of the file's own outline (PDF bookmarks, an EPUB's table of contents):
    a hint for the layout stage, not a decision (D-263 to D-266).

    The title is kept exactly as the file stores it, also when it is empty or ends in a space;
    a printed heading number is often left out of it ("Introduction" for "1 Introduction").
    `item` is set where the entry points at a place inside its page, as an EPUB link to an
    anchor in a chapter file does: the id of the first item at or after that place (D-311).
    """

    title: str
    level: int  # 1 = top; an entry under another is one level deeper
    page: int | None = None  # the `Page.number` it points at; None if it points at no page
    item: str = ""  # the id of the item it points at on that page; "" for the whole page

    def __post_init__(self) -> None:
        if self.level < 1:
            raise ValueError(f"outline level must be >= 1, got {self.level}")


@dataclass(frozen=True)
class Content:
    """Everything extraction recorded from one file, page by page.

    `outline` lists the file's outline entries in the order it stores them; their levels keep
    the nesting: the first entry is at level 1 and each entry is at most one level deeper than
    the one before it. Empty when the file has none.
    """

    source: Source
    pages: tuple[Page, ...]
    metadata: Metadata = field(default_factory=Metadata)
    outline: tuple[OutlineEntry, ...] = ()

    def __post_init__(self) -> None:
        numbers = [page.number for page in self.pages]
        if numbers != list(range(1, len(numbers) + 1)):
            raise ValueError(f"pages must be numbered 1, 2, 3, ... in order, got {numbers}")
        _check_outline(self.outline, self.pages)
        counts = Counter(item.id for page in self.pages for item in _items(page))
        doubled = sorted(i for i, n in counts.items() if n > 1)
        if doubled or "" in counts:
            raise ValueError(f"item ids must be unique and non-empty, repeated: {doubled}")

    def items(self) -> dict[str, tuple[Page, Item]]:
        """Every item by its id, with the page it stands on."""
        return {item.id: (page, item) for page in self.pages for item in _items(page)}


def _check_outline(outline: tuple[OutlineEntry, ...], pages: tuple[Page, ...]) -> None:
    level = 0  # the level before the first entry
    ids: dict[int, set[str]] = {}  # item ids by page number, made once per page asked for
    for entry in outline:
        if entry.level > level + 1:
            raise ValueError(
                f"outline entry {entry.title!r} is at level {entry.level}, more than one level"
                f" below the entry before it (level {level})"
            )
        if entry.page is not None and not 1 <= entry.page <= len(pages):
            raise ValueError(
                f"outline entry {entry.title!r} points at page {entry.page}, which the content"
                f" does not have (pages 1 to {len(pages)})"
            )
        if entry.item and entry.page is None:
            raise ValueError(
                f"outline entry {entry.title!r} points at item {entry.item!r} but at no page"
            )
        if entry.item and entry.page is not None:
            if entry.page not in ids:
                ids[entry.page] = {item.id for item in _items(pages[entry.page - 1])}
            if entry.item not in ids[entry.page]:
                raise ValueError(
                    f"outline entry {entry.title!r} points at item {entry.item!r}, which is not"
                    f" on its page ({entry.page})"
                )
        level = entry.level


def _items(page: Page) -> tuple[Item, ...]:
    return (*page.lines, *page.pictures, *page.drawings)
