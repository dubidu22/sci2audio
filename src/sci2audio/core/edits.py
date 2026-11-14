"""Marked edits that text steps propose, and how accepted edits become the listening script.

A text step never changes the text (D-57). It returns `Edit`s that point at spans of the
original, each with a kind, a reason and the id of the step. The app chooses which edits to
accept and calls `apply_edits`, which turns the document into `ScriptPiece`s: the text the
voice reads, each piece pointing back at the original span it stands for (read-along, OU-02).

An edit lies inside one block (D-61 (1)). The one exception is a move (#213): it takes a whole
block and reads that block's script, with the block's own edits applied, at a position in
another block (a footnote after the sentence that holds its mark). Its pieces keep their own
spans, so read-along and the report still point at the place the block is printed.
"""

from __future__ import annotations

from bisect import bisect_left
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from itertools import pairwise

from sci2audio.core.document import Document, Span, SpanError


class OverlappingEditsError(ValueError):
    """Two edits claim the same text; the app must choose one before applying."""

    def __init__(self, first: Edit, second: Edit, how: str = "overlaps") -> None:
        self.first = first
        self.second = second
        super().__init__(
            f"edit from step {first.step!r} at {_where(first.span)} {how} edit from step "
            f"{second.step!r} at {_where(second.span)}; accept only one of them"
        )


class EditKind(StrEnum):
    """What an edit proposes (D-57)."""

    REMOVE = "remove"  # leave the span out
    REPLACE = "replace"  # read `replacement` instead of the span (an empty span inserts it)
    PAUSE = "pause"  # pause at the position of an empty span
    ASK = "ask"  # the step is unsure: the user decides; until then the original is read
    MOVE = "move"  # read the whole block at the position `to` in another block (#213)


@dataclass(frozen=True)
class Edit:
    """A proposed change to the spoken text, with the reason a person reads in the report."""

    span: Span
    kind: EditKind
    reason: str
    step: str  # id of the text step that proposed it
    replacement: str = ""  # REPLACE: the text to read; ASK: the step's proposal, may be empty
    # MOVE: where the block is read instead, an empty span (a position) in another block
    to: Span | None = None

    def __post_init__(self) -> None:
        if not self.reason.strip() or not self.step.strip():
            raise ValueError(f"an edit needs a reason and a step id, got {self}")
        empty = self.span.start == self.span.end
        if self.kind is EditKind.MOVE:
            self._check_move(empty)
        elif self.to is not None:
            raise ValueError(f"only a move edit has a target, not a {self.kind} edit")
        if self.kind is EditKind.REMOVE and (empty or self.replacement):
            raise ValueError("a remove edit needs a non-empty span and no replacement")
        if self.kind is EditKind.REPLACE and not self.replacement:
            raise ValueError("a replace edit needs a replacement; use remove to leave text out")
        if self.kind is EditKind.PAUSE and (not empty or self.replacement):
            raise ValueError("a pause edit needs an empty span and no replacement")

    def _check_move(self, empty: bool) -> None:
        to = self.to
        if empty or self.replacement:
            raise ValueError("a move edit needs a non-empty span and no replacement")
        if to is None or to.start != to.end:
            raise ValueError(f"a move edit needs a position to move to, got {to}")
        if to.block == self.span.block:
            raise ValueError(f"a move edit moves its block into another block, got {to}")


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

    A move takes its whole block, and lies outside the overlap rule for the edits inside
    that block. A block moves at most once and a moved block is no target, so moves never
    chain. A move's target may not lie strictly inside another edit, nor share its position
    with an empty edit that is not a move; moves to one position are read in block order.
    """
    ordered = sorted(edits, key=lambda e: (e.span.block, e.span.start, e.span.end))
    plain: list[Edit] = []
    moves: dict[int, Edit] = {}  # moved block -> its move
    for edit in ordered:
        document.check_span(edit.span)
        if edit.kind is not EditKind.MOVE:
            plain.append(edit)
            continue
        _check_move(document, edit)
        if (other := moves.get(edit.span.block)) is not None:
            raise OverlappingEditsError(other, edit)
        moves[edit.span.block] = edit
    for first, second in pairwise(plain):
        a, b = first.span, second.span
        if a.block == b.block and (b.start < a.end or (a == b and a.start == a.end)):
            raise OverlappingEditsError(first, second)
    starts = [(edit.span.block, edit.span.start) for edit in plain]
    for edit in moves.values():
        to = _to(edit)
        if (moved := moves.get(to.block)) is not None:
            raise OverlappingEditsError(edit, moved, "moves into a block that is moved itself")
        if (other := _at_target(plain, starts, to)) is not None:
            raise OverlappingEditsError(other, edit)
    return ordered


def _to(edit: Edit) -> Span:
    """A move's target; `Edit` itself makes sure a move has one."""
    if edit.to is None:
        raise ValueError(f"a move edit needs a position to move to, got {edit}")
    return edit.to


def _check_move(document: Document, edit: Edit) -> None:
    document.check_span(_to(edit))
    length = len(document.blocks[edit.span.block].text)
    if (edit.span.start, edit.span.end) != (0, length):
        raise SpanError(f"a move covers its whole block ({length} characters), got {edit.span}")


def _at_target(plain: Sequence[Edit], starts: Sequence[tuple[int, int]], to: Span) -> Edit | None:
    """The edit a move's target lies strictly inside, or an empty edit at the same
    position. Plain edits do not overlap and are sorted, so only the edits starting at or
    just before the position can hold it."""
    at = to.start
    first = bisect_left(starts, (to.block, at))
    for index in (first - 1, first):
        if 0 <= index < len(plain):
            span = plain[index].span
            if span.block == to.block and (
                span.start < at < span.end or span.start == span.end == at
            ):
                return plain[index]
    return None


def apply_edits(document: Document, edits: Iterable[Edit]) -> tuple[ScriptPiece, ...]:
    """Build the listening script from the original text and the accepted edits.

    A moved block is read at its target, after the target block's text up to that position
    and before the rest; blocks moved to one position are read in block order.

    Raises SpanError or OverlappingEditsError for invalid edits; never on valid ones.
    """
    by_block: dict[int, list[Edit]] = {}
    targets: dict[int, list[tuple[int, int]]] = {}  # target block -> (position, moved block)
    for edit in check_edits(document, edits):
        if edit.kind is EditKind.MOVE:
            to = _to(edit)
            targets.setdefault(to.block, []).append((to.start, edit.span.block))
        else:
            by_block.setdefault(edit.span.block, []).append(edit)
    sources = {block for places in targets.values() for _, block in places}
    pieces: list[ScriptPiece] = []
    for index in range(len(document.blocks)):
        if index in sources:
            continue
        own = _block_pieces(document, index, by_block.get(index, []))
        if places := targets.get(index):
            moved = [
                (at, _block_pieces(document, block, by_block.get(block, [])))
                for at, block in sorted(places)
            ]
            own = _inserted(own, moved)
        pieces += own
    return tuple(pieces)


def _block_pieces(document: Document, index: int, edits: list[Edit]) -> list[ScriptPiece]:
    text = document.blocks[index].text
    pieces: list[ScriptPiece] = []
    cursor = 0
    for edit in edits:
        _keep(pieces, text, index, cursor, edit.span.start)
        if edit.kind is EditKind.REPLACE:
            pieces.append(ScriptPiece(edit.replacement, edit.span))
        elif edit.kind is EditKind.PAUSE:
            pieces.append(ScriptPiece("", edit.span, pause=True))
        elif edit.kind is EditKind.ASK:
            _keep(pieces, text, index, edit.span.start, edit.span.end)
        cursor = edit.span.end
    _keep(pieces, text, index, cursor, len(text))
    return pieces


def _inserted(
    own: list[ScriptPiece], moved: list[tuple[int, list[ScriptPiece]]]
) -> list[ScriptPiece]:
    """A block's pieces with the moved blocks' pieces read at their positions, `moved`
    sorted by position: each after every piece that ends at its position or before, ahead
    of every piece that starts there or after. Only kept text can hold a position strictly
    inside (`check_edits`); it is split there exactly."""
    out: list[ScriptPiece] = []
    waiting = list(reversed(moved))  # the next position last
    for piece in own:
        span = piece.span
        while waiting:
            at, insert = waiting[-1]
            if span.start >= at:  # starts at the position or after (no empty edit is at it)
                out += insert
            elif span.start < at < span.end:  # kept text that holds the position: split it
                cut = at - span.start
                out.append(ScriptPiece(piece.text[:cut], Span(span.block, span.start, at)))
                out += insert
                piece = ScriptPiece(piece.text[cut:], Span(span.block, at, span.end))
                span = piece.span
            else:
                break
            waiting.pop()
        out.append(piece)
    for _, insert in reversed(waiting):
        out += insert
    return out


def _keep(pieces: list[ScriptPiece], text: str, block: int, start: int, end: int) -> None:
    if start < end:
        pieces.append(ScriptPiece(text[start:end], Span(block, start, end)))


def _where(span: Span) -> str:
    return f"block {span.block}, characters {span.start}-{span.end}"
