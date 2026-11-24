"""The library's count of a document's captures, and finding a sentence again.

v1.3 kept markers with an optional note in the web layer's own file `markers.json` in the
document's working folder (#474, D-722, D-728). The captures (#397) replace them, and the
carry-over (`app.captures`, #475) is the one reader of that file: the library counts a
document's markers as a load would carry them over (`count_captures`), so the two can never
judge one file in two ways (#887).

An anchor is tied to the text, never to one audiobook: its sentence's block, its character
offsets in that block's text and the text itself as printed. On every page it is looked for
again in the document the audiobook was made from (`locate`), so a capture outlives a new
audiobook and a changed layout; one that can't be found is listed as not found, never
dropped. The stored anchor is never rewritten.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Protocol

from sci2audio.app.captures import (
    CapturesBroken,
    MarkersNotCarried,
    peek_carry_over,
    read_captures,
)
from sci2audio.core import CaptureType, Document, Span

NEAR_BLOCKS = 20  # how far from its block a sentence cut differently is looked for

State = Literal["found", "not-read", "not-found"]


@dataclass(frozen=True)
class Anchor:
    """A sentence in the document's text: block, character offsets, the text as printed."""

    block: int
    start: int
    end: int
    text: str


class Anchored(Protocol):
    """What finding a sentence again needs: a capture's anchor (#397)."""

    @property
    def block(self) -> int: ...
    @property
    def start(self) -> int: ...
    @property
    def end(self) -> int: ...
    @property
    def text(self) -> str: ...


def anchor_of(document: Document, span: Span) -> Anchor:
    """The anchor of the sentence `span` reads. The span must be valid for the document."""
    text = document.blocks[span.block].text
    return Anchor(span.block, span.start, span.end, text[span.start : span.end])


def count_captures(work: Path, document_id: str) -> dict[str, Any]:
    """The document's captures by type (`note`, `quote`, `mark`), for the removal box
    (ADR-008 2.1 item 4, #396), counted as the box is drawn: from `captures.json`, or,
    while there is none, the v1.3 markers as the carry-over (#475) would make them, with
    nothing written. `unread` names the file that is there but can't be used (`captures`
    or `markers`), else None: markers a load refuses to carry over are `markers` too.

    Not `peek_captures`: its OSError does not say which of the two files failed."""
    counts: dict[str, Any] = {**dict.fromkeys(CaptureType, 0), "unread": None}
    try:
        captures = read_captures(work, document_id)
    except (CapturesBroken, OSError):
        return counts | {"unread": "captures"}
    if captures is not None:  # markers.json is not read while captures.json is there
        return counts | captures.count()
    try:
        carried = peek_carry_over(work, document_id)
    except MarkersNotCarried:  # a CapturesBroken, so it is caught first
        return counts | {"unread": "markers"}
    except CapturesBroken:  # a captures.json put in place since, that can't be read
        return counts | {"unread": "captures"}
    except OSError:
        return counts | {"unread": "markers"}
    return counts if carried is None else counts | carried.count()


# ---- finding a marker again (plan section 3) ----------------------------------------------


def _normal(text: str) -> tuple[str, list[int]]:
    """The text as it reads, with where each of its characters stands in `text`: soft
    hyphens and a hyphen that joins a word across a line end left out, every run of white
    space one space, none at either end."""
    out: list[str] = []
    where: list[int] = []
    at, size = 0, len(text)
    while at < size:
        char = text[at]
        if char == "­":
            at += 1
            continue
        if char == "-" and text[at + 1 : at + 2] == "\n" and text[at + 2 : at + 3].islower():
            at += 2
            continue
        if char.isspace():
            if out and out[-1] != " ":
                out.append(" ")
                where.append(at)
            at += 1
            continue
        out.append(char)
        where.append(at)
        at += 1
    if out and out[-1] == " ":
        out.pop()
        where.pop()
    return "".join(out), where


def _occurrences(hay: str, needle: str) -> list[int]:
    found: list[int] = []
    at = hay.find(needle)
    while at >= 0:
        found.append(at)
        at = hay.find(needle, at + 1)
    return found


class _Finder:
    """Looks for anchors in one document; each block is made readable once."""

    def __init__(self, document: Document) -> None:
        self.texts = [block.text for block in document.blocks]
        self._normal: dict[int, tuple[str, list[int]]] = {}

    def normal(self, block: int) -> tuple[str, list[int]]:
        if block not in self._normal:
            self._normal[block] = _normal(self.texts[block])
        return self._normal[block]

    def find(self, anchor: Anchored) -> tuple[int, int, int] | None:
        """(block, start, end) of the anchor's sentence in this document, or None."""
        found = self.place(anchor)
        return None if found is None else found[0]

    def place(self, anchor: Anchored) -> tuple[tuple[int, int, int], tuple[int, int]] | None:
        """As `find`, and (block, start) of the sentence's first character: a sentence the
        layout now splits is placed in the block holding most of it, but it starts in an
        earlier one, and an export names the page where it starts (#399)."""
        needle = _normal(anchor.text)[0]
        if not needle:
            return None
        count = len(self.texts)
        # 1. the same place, with the same text
        if 0 <= anchor.block < count and anchor.end <= len(self.texts[anchor.block]):
            here = self.texts[anchor.block][anchor.start : anchor.end]
            if _normal(here)[0] == needle:
                return (anchor.block, anchor.start, anchor.end), (anchor.block, anchor.start)
        # 2. the same text in one block, nearest the old block (and its old offset)
        for block in sorted(range(count), key=lambda b: (abs(b - anchor.block), b)):
            hay, where = self.normal(block)
            starts = _occurrences(hay, needle)
            if starts:
                best = min(starts, key=lambda s: abs(where[s] - anchor.start))
                first = where[best]
                return (block, first, where[best + len(needle) - 1] + 1), (block, first)
        # 3. the same text across neighbouring blocks (a sentence the layout now splits)
        return self._across(anchor, needle)

    def _across(
        self, anchor: Anchored, needle: str
    ) -> tuple[tuple[int, int, int], tuple[int, int]] | None:
        low = max(0, min(anchor.block, len(self.texts)) - NEAR_BLOCKS)
        high = min(len(self.texts), anchor.block + NEAR_BLOCKS + 1)
        hay: list[str] = []
        owner: list[tuple[int, int]] = []  # per character of the joined text: (block, raw)
        for block in range(low, high):
            text, where = self.normal(block)
            if not text:
                continue
            if hay:
                hay.append(" ")
                owner.append((-1, -1))
            hay.extend(text)
            owner.extend((block, raw) for raw in where)
        starts = _occurrences("".join(hay), needle)
        if not starts:
            return None
        start = starts[0]
        stretch = [o for o in owner[start : start + len(needle)] if o[0] >= 0]
        shares: dict[int, list[int]] = {}
        for block, raw in stretch:
            shares.setdefault(block, []).append(raw)
        block = max(shares, key=lambda b: (len(shares[b]), -b))
        raws = shares[block]
        return (block, raws[0], raws[-1] + 1), stretch[0]


def finder(document: Document) -> Callable[[Anchored], tuple[int, int] | None]:
    """Where an anchor's sentence starts in `document` now, as (block, offset), or None:
    found as `locate` finds it, so an export (#399) orders captures as the pages place them
    and names the page where each sentence starts."""
    places = _Finder(document)

    def start(anchor: Anchored) -> tuple[int, int] | None:
        found = places.place(anchor)
        return None if found is None else found[1]

    return start


def locate[T](
    items: Sequence[T], anchor: Callable[[T], Anchored], document: Document, spans: Sequence[Span]
) -> list[tuple[T, int | None, State]]:
    """Each item, by its anchor, where this audiobook reads it (`spans`: the read-along's
    chunks, in order), in reading order: found ones by their chunk, then those whose text
    this audiobook does not read, then those not found, each group in the given order. The
    sentence shown is the chunk that overlaps the found place most (the first on a tie).
    No item is ever left out."""
    finder = _Finder(document)
    by_block: dict[int, list[tuple[int, Span]]] = {}
    for number, span in enumerate(spans):
        if span.start < span.end:
            by_block.setdefault(span.block, []).append((number, span))
    found: list[tuple[int, int, tuple[T, int | None, State]]] = []
    unread: list[tuple[T, int | None, State]] = []
    lost: list[tuple[T, int | None, State]] = []
    for order, item in enumerate(items):
        where = finder.find(anchor(item))
        if where is None:
            lost.append((item, None, "not-found"))
            continue
        block, start, end = where
        best, most = None, 0
        for number, span in by_block.get(block, ()):
            overlap = min(end, span.end) - max(start, span.start)
            if overlap > most:
                best, most = number, overlap
        if best is None:
            unread.append((item, None, "not-read"))
        else:
            found.append((best, order, (item, best, "found")))
    found.sort(key=lambda entry: (entry[0], entry[1]))
    return [entry[2] for entry in found] + unread + lost


def same_sentence(anchor: Anchored, others: Sequence[Anchored], document: Document | None) -> bool:
    """Whether one of `others` stands on the sentence `anchor` stands on, with no audiobook
    to place them in (#934): sentences never overlap, so two anchors that overlap in one
    block are one sentence, whatever their offsets. Each is found in `document` first, as
    its text may have moved; one not found there is no sentence of it. Without a document,
    their own places count."""
    finder = None if document is None else _Finder(document)

    def where(item: Anchored) -> tuple[int, int, int] | None:
        return (item.block, item.start, item.end) if finder is None else finder.find(item)

    here = where(anchor)
    if here is None:
        return False
    block, start, end = here
    for other in others:
        there = where(other)
        if there is not None and there[0] == block and min(end, there[2]) > max(start, there[1]):
            return True
    return False
