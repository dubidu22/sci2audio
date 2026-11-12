"""Marked edits that text steps propose, and how accepted edits become the listening script.

A text step never changes the text (D-57). It returns `Edit`s that point at spans of the
original, each with a kind, a reason and the id of the step. The app chooses which edits to
accept and calls `apply_edits`, which turns the document into `ScriptPiece`s: the text the
voice reads, each piece pointing back at the original span it stands for (read-along, OU-02).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from itertools import pairwise

from sci2audio.core.document import Document, Span


class OverlappingEditsError(ValueError):
    """Two edits claim the same text; the app must choose one before applying."""

    def __init__(self, first: Edit, second: Edit) -> None:
        self.first = first
        self.second = second
        super().__init__(
            f"edit from step {first.step!r} at {_where(first.span)} overlaps edit from step "
            f"{second.step!r} at {_where(second.span)}; accept only one of them"
        )


class EditKind(StrEnum):
    """What an edit proposes (D-57)."""

    REMOVE = "remove"  # leave the span out
    REPLACE = "replace"  # read `replacement` instead of the span (an empty span inserts it)
    PAUSE = "pause"  # pause at the position of an empty span
    ASK = "ask"  # the step is unsure: the user decides; until then the original is read


@dataclass(frozen=True)
class Edit:
    """A proposed change to the spoken text, with the reason a person reads in the report."""

    span: Span
    kind: EditKind
    reason: str
    step: str  # id of the text step that proposed it
    replacement: str = ""  # REPLACE: the text to read; ASK: the step's proposal, may be empty

    def __post_init__(self) -> None:
        if not self.reason.strip() or not self.step.strip():
            raise ValueError(f"an edit needs a reason and a step id, got {self}")
        empty = self.span.start == self.span.end
        if self.kind is EditKind.REMOVE and (empty or self.replacement):
            raise ValueError("a remove edit needs a non-empty span and no replacement")
        if self.kind is EditKind.REPLACE and not self.replacement:
            raise ValueError("a replace edit needs a replacement; use remove to leave text out")
        if self.kind is EditKind.PAUSE and (not empty or self.replacement):
            raise ValueError("a pause edit needs an empty span and no replacement")


@dataclass(frozen=True)
class ScriptPiece:
    """A piece of the listening script and the original span it stands for.

    Kept text has the same characters as its span; a replacement has its own text; a pause
    has no text and an empty span. Removed spans produce no piece.
    """

    text: str
    span: Span
    pause: bool = False


def check_edits(document: Document, edits: Iterable[Edit]) -> list[Edit]:
    """Return the edits in document order, or raise if one is outside or two overlap.

    Two edits overlap when they share a character, when a position lies strictly inside the
    other's span, or when both mark the same position (their order would be a guess).
    """
    ordered = sorted(edits, key=lambda e: (e.span.block, e.span.start, e.span.end))
    for edit in ordered:
        document.check_span(edit.span)
    for first, second in pairwise(ordered):
        a, b = first.span, second.span
        if a.block == b.block and (b.start < a.end or (a == b and a.start == a.end)):
            raise OverlappingEditsError(first, second)
    return ordered


def apply_edits(document: Document, edits: Iterable[Edit]) -> tuple[ScriptPiece, ...]:
    """Build the listening script from the original text and the accepted edits.

    Raises SpanError or OverlappingEditsError for invalid edits; never on valid ones.
    """
    by_block: dict[int, list[Edit]] = {}
    for edit in check_edits(document, edits):
        by_block.setdefault(edit.span.block, []).append(edit)
    pieces: list[ScriptPiece] = []
    for index, block in enumerate(document.blocks):
        cursor = 0
        for edit in by_block.get(index, []):
            _keep(pieces, block.text, index, cursor, edit.span.start)
            if edit.kind is EditKind.REPLACE:
                pieces.append(ScriptPiece(edit.replacement, edit.span))
            elif edit.kind is EditKind.PAUSE:
                pieces.append(ScriptPiece("", edit.span, pause=True))
            elif edit.kind is EditKind.ASK:
                _keep(pieces, block.text, index, edit.span.start, edit.span.end)
            cursor = edit.span.end
        _keep(pieces, block.text, index, cursor, len(block.text))
    return tuple(pieces)


def _keep(pieces: list[ScriptPiece], text: str, block: int, start: int, end: int) -> None:
    if start < end:
        pieces.append(ScriptPiece(text[start:end], Span(block, start, end)))


def _where(span: Span) -> str:
    return f"block {span.block}, characters {span.start}-{span.end}"
