"""Chapters: what the person chooses to hear, and what output turns into chapter marks (Q6).

- Each top-level section of the document starts a chapter (a level-1 section; a top-level
  section of a deeper level, with no level-1 heading above it, too). A chapter runs to the
  next chapter's start or the document's end, so every block is in exactly one chapter,
  also where the section tree leaves gaps.
- Text before the first heading is the first chapter, titled with the document title the
  file gives (`Content.metadata.title`), else the file name without its extension. A
  document without headings is one chapter, titled the same way.
- A chapter whose title, without its printed number, is a reference-list name
  (`REFERENCE_NAMES`) is the reference list: deselected by default (TP-06). Appendices stay
  selected.

Titles are kept as printed ("2 Related Work"), white space runs read as one space.
EPUB's top-level navigation entries become level-1 sections in layout (#73, #75).
"""

from __future__ import annotations

import re
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from pathlib import PurePath

from sci2audio.core import Document
from sci2audio.textprep import REFERENCE_NAMES

# The names a reference-list heading has, compared without case and without a printed
# number: the reference-list text step's own table, English and German (#221), so the
# chapter choice and the step agree (D-146). Every language's names count here, since the
# chapter list does not depend on the job's language.
_ALL_REFERENCE_NAMES = frozenset(
    name.casefold() for names in REFERENCE_NAMES.values() for name in names
)
# a printed heading number before the title: "7", "7.", "A", "A.1", "IV."
_NUMBER = re.compile(r"\A(?:\d{1,2}|[A-Z]|[IVX]{1,5})(?:\.\d{1,2})*\.?\s+")
_SPACES = re.compile(r"\s+")
# The source tags (`TextRun.tags`: EPUB's `epub:type` and ARIA's `role` tokens, which the
# heading's runs carry from their section) that mark a publisher's page, not the book's
# text (#190): EPUB 3 Structural Semantics and DPUB-ARIA names for front and back matter
# about the edition, plus navigation lists. The title page stays out of the list: it reads
# the book's title and author, a natural start.
PUBLISHER_TAGS = frozenset(
    {
        "epub:imprint",
        "epub:colophon",
        "epub:copyright-page",
        "epub:seriespage",
        "epub:other-credits",
        "epub:errata",
        "epub:toc",
        "epub:landmarks",
        "epub:loi",
        "epub:lot",
        "epub:page-list",
        "epub:index",
        "role:doc-colophon",
        "role:doc-credits",
        "role:doc-errata",
        "role:doc-toc",
        "role:doc-index",
        "role:doc-pagelist",
    }
)


@dataclass(frozen=True)
class Chapter:
    """Chapter number `index` (from 0): its title and blocks `start` up to `end`."""

    index: int
    title: str
    start: int
    end: int
    references: bool = False  # the reference list: deselected by default
    publisher: bool = False  # a publisher's page (#190): deselected by default

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise ValueError("a chapter needs a title")
        if self.index < 0 or not 0 <= self.start <= self.end:
            raise ValueError(f"chapter {self.title!r} needs index >= 0 and start <= end")

    def holds(self, block: int) -> bool:
        """True if block number `block` belongs to this chapter."""
        return self.start <= block < self.end


def document_title(document: Document) -> str:
    """The title the file gives, else the file name without its extension ("Untitled" if
    neither has a letter to read)."""
    name = document.content.source.name
    candidates = (document.content.metadata.title, PurePath(name).stem, name)
    return next((title for text in candidates if (title := _clean(text))), "Untitled")


def find_chapters(document: Document) -> tuple[Chapter, ...]:
    """The document's chapters in order; together they hold every block exactly once."""
    count = len(document.blocks)
    starts = [(section.start, section.title) for section in document.sections]
    heads: list[tuple[int, str, bool, bool]] = []  # start, title, reference list, publisher
    if not starts or starts[0][0] > 0:
        heads.append((0, document_title(document), False, False))
    tagged = _publisher_starts(document, {start for start, _ in starts})
    for number, (start, title) in enumerate(starts, start=1):
        cleaned = _clean(title) or f"Section {number}"
        heads.append((start, cleaned, is_reference_title(cleaned), start in tagged))
    chapters = []
    for index, (start, title, references, publisher) in enumerate(heads):
        end = heads[index + 1][0] if index + 1 < len(heads) else count
        chapters.append(Chapter(index, title, start, end, references, publisher))
    return tuple(chapters)


def _publisher_starts(document: Document, starts: Collection[int]) -> frozenset[int]:
    """The chapter starts whose first line carries a publisher's page tag (#190)."""
    firsts = {
        number: block.parts[0].item
        for number in starts
        if number < len(document.blocks) and (block := document.blocks[number]).parts
    }
    if not firsts:
        return frozenset()
    wanted = set(firsts.values())
    tags: dict[str, frozenset[str]] = {}
    for page in document.content.pages:
        for line in page.lines:
            if line.id in wanted:
                tags[line.id] = frozenset(tag for run in line.runs for tag in run.tags)
    return frozenset(
        number for number, item in firsts.items() if tags.get(item, frozenset()) & PUBLISHER_TAGS
    )


def is_reference_title(title: str) -> bool:
    """True if the title names a reference list ("References", "7 Bibliography")."""
    name = _NUMBER.sub("", _clean(title), count=1)
    return name.casefold().rstrip(".:") in _ALL_REFERENCE_NAMES


def default_selection(chapters: Collection[Chapter]) -> frozenset[int]:
    """Every chapter but the reference list and the publisher's pages (#190)."""
    return frozenset(
        chapter.index for chapter in chapters if not chapter.references and not chapter.publisher
    )


def selected(
    chapters: Collection[Chapter], chosen: Sequence[int] | None
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """The chosen chapters in the order they are read (the default, in printed order, when
    `chosen` is None; #119), and the chosen indices the document doesn't have, which are
    ignored."""
    if chosen is None:
        return tuple(sorted(default_selection(chapters))), ()
    known = {chapter.index for chapter in chapters}
    order = tuple(dict.fromkeys(n for n in chosen if n in known))
    return order, tuple(sorted(set(chosen) - known))


def _clean(text: str) -> str:
    return _SPACES.sub(" ", text).strip()
