"""Run the text steps on a document and settle overlapping edits (D-61, Q15).

Every step whose languages fit the job runs, also the steps of switched-off categories, so
the report can show what each switch would change without a second run. Their edits are
marked switched off and block nothing. The switched-on edits are then taken in step order
(the registry order: coarse to fine), and inside one step in document order: an edit that
overlaps an edit already accepted is set aside, and remembers the edit that won. A block
that an accepted block-stage edit covers takes no further edit at all, not even a mark at
its start or end. `ask`
edits are accepted like any other; `apply_edits` reads the original for them (D-61 (3)).

Moves (#213) come from move steps, which run last. A move claims no text: it is set aside
when its block or its target block is claimed by a block-stage edit, when its target lies
strictly inside an accepted edit or at an accepted insertion or pause, or when its block is
already moved or would chain (a moved block is no target, a target block does not move).
`StepRun.read_at` says in which block's place a block is read.

A step that raises or returns invalid edits is dropped, with a problem in the result: the
run never stops halfway (D-61 (3)). `strict=True` raises instead, for tests.
"""

from __future__ import annotations

from bisect import bisect_left, insort
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from functools import cached_property

from sci2audio.core import Document, Edit, EditKind, ScriptPiece, Span, apply_edits, check_edits
from sci2audio.textprep.registry import BUILT_IN_STEPS, check_registry
from sci2audio.textprep.steps import (
    DEFAULT_SWITCHED_OFF,
    Category,
    Stage,
    StepContext,
    TextStep,
)


class Status(StrEnum):
    """What became of a proposed edit."""

    ACCEPTED = "accepted"  # goes into the script
    SET_ASIDE = "set-aside"  # overlaps an edit of an earlier step, which won
    SWITCHED_OFF = "switched-off"  # its category is switched off


@dataclass(frozen=True)
class Outcome:
    """A proposed edit, its category and what became of it."""

    edit: Edit
    category: Category
    status: Status
    won_by: Edit | None = None  # SET_ASIDE: the accepted edit it overlaps


@dataclass(frozen=True)
class StepProblem:
    """A step that failed or broke the rules; none of its edits were used."""

    step: str
    message: str


@dataclass(frozen=True)
class StepRun:
    """Everything the steps proposed for one document, settled.

    The data behind the report (UC-01, #70): every edit with its reason, step, category and
    status, set-aside edits with the edit that won, problems and the steps not run for the
    job's language.
    """

    document: Document
    outcomes: tuple[Outcome, ...]
    problems: tuple[StepProblem, ...] = ()
    not_run: tuple[str, ...] = ()  # ids of steps that don't handle the job's language

    def edits(self, status: Status) -> tuple[Edit, ...]:
        """The edits with this status, in step order, then document order."""
        return tuple(outcome.edit for outcome in self.outcomes if outcome.status is status)

    @property
    def accepted(self) -> tuple[Edit, ...]:
        return self.edits(Status.ACCEPTED)

    def script(self) -> tuple[ScriptPiece, ...]:
        """The listening script: the original with the accepted edits applied."""
        return apply_edits(self.document, self.accepted)

    @cached_property
    def moved(self) -> Mapping[int, int]:
        """Each block an accepted move reads elsewhere, and the block it is read in."""
        return {
            edit.span.block: edit.to.block
            for edit in self.accepted
            if edit.kind is EditKind.MOVE and edit.to is not None
        }

    def read_at(self, block: int) -> int:
        """The block in whose place block number `block` is read: its move's target block,
        else itself (#213). Chapters follow it: a footnote is heard where its mark is."""
        return self.moved.get(block, block)


class StepError(RuntimeError):
    """A step failed or returned invalid edits (raised only in strict runs)."""


def run_steps(
    document: Document,
    context: StepContext,
    steps: Sequence[TextStep] = BUILT_IN_STEPS,
    switched_off: Collection[Category] = DEFAULT_SWITCHED_OFF,
    *,
    strict: bool = False,
) -> StepRun:
    """Run the steps on the document and settle their edits.

    `switched_off` defaults to the categories that are off unless the user turns them on
    (`DEFAULT_SWITCHED_OFF`: "Footnote texts"); pass an empty set to use every category.

    Raise ValueError if the steps are not in a valid order (`check_registry`); in a strict
    run also StepError for a step that fails or breaks the rules.
    """
    check_registry(steps)
    accepted = _Accepted()
    outcomes: list[Outcome] = []
    problems: list[StepProblem] = []
    not_run: list[str] = []
    for step in steps:
        if not step.handles(context.language):
            not_run.append(step.id)
            continue
        try:
            edits = _proposed(step, document, context)
        except Exception as error:
            if strict:
                raise StepError(f"text step {step.id!r} failed: {error}") from error
            problems.append(StepProblem(step.id, f"{type(error).__name__}: {error}"))
            continue
        for edit in edits:
            if step.category in switched_off:
                outcomes.append(Outcome(edit, step.category, Status.SWITCHED_OFF))
            elif (winner := accepted.overlapping(edit)) is not None:
                outcomes.append(Outcome(edit, step.category, Status.SET_ASIDE, winner))
            else:
                accepted.add(edit, step.stage)
                outcomes.append(Outcome(edit, step.category, Status.ACCEPTED))
    return StepRun(document, tuple(outcomes), tuple(problems), tuple(not_run))


def _proposed(step: TextStep, document: Document, context: StepContext) -> list[Edit]:
    """The step's edits in document order; raise StepError if they break the rules."""
    edits = step.find(document, context)
    if not isinstance(edits, list) or not all(isinstance(edit, Edit) for edit in edits):
        raise StepError(f"find must return a list of Edit, got {type(edits).__name__}")
    for edit in edits:
        if edit.step != step.id:
            raise StepError(f"an edit names step {edit.step!r}, not {step.id!r}")
    ordered = check_edits(document, edits)  # inside the blocks, no overlap among its own
    for edit in ordered:
        if (edit.kind is EditKind.MOVE) != (step.stage is Stage.MOVE):
            rule = (
                "a move step proposes only moves"
                if step.stage is Stage.MOVE
                else ("only a move step proposes moves")
            )
            raise StepError(f"{rule}, got a {edit.kind} edit at {edit.span}")
    if step.stage is Stage.BLOCK:
        for edit in ordered:
            if edit.span != whole_block(document, edit.span.block):
                raise StepError(f"block step edit at {edit.span} does not cover its block")
    return ordered


def whole_block(document: Document, index: int) -> Span:
    """The span of a block's whole text."""
    return Span(index, 0, len(document.blocks[index].text))


def overlap(a: Span, b: Span) -> bool:
    """True if two spans claim the same text, as `core.check_edits` decides it.

    They share a character, a position lies strictly inside the other span, or both mark
    the same position.
    """
    if a.block != b.block:
        return False
    if a.start == a.end == b.start == b.end:
        return True
    return a.start < b.end and b.start < a.end


class _Accepted:
    """The accepted edits per block, sorted by span, for fast overlap checks.

    A block whose whole text an accepted block-stage edit covers is claimed by it: every
    later edit in that block is set aside, including marks at the block's two ends, which
    touch no character and so overlap nothing by the core rule (D-105: whole-block
    decisions stay intact). Accepted moves are kept apart: they claim no text (#213).
    """

    def __init__(self) -> None:
        self._blocks: dict[int, list[tuple[int, int, int]]] = {}
        self._edits: list[Edit] = []
        self._claimed: dict[int, Edit] = {}  # block index -> its accepted block-stage edit
        self._moved: dict[int, Edit] = {}  # moved block -> its accepted move
        self._targets: dict[int, Edit] = {}  # target block -> an accepted move into it

    def overlapping(self, edit: Edit) -> Edit | None:
        """The accepted edit this one overlaps, or the edit that claimed its block, if any."""
        if edit.kind is EditKind.MOVE:
            return self._blocking_move(edit)
        if (claim := self._claimed.get(edit.span.block)) is not None:
            return claim
        return self._holding(edit.span)

    def _holding(self, span: Span) -> Edit | None:
        spans = self._blocks.get(span.block, [])
        start, end = span.start, span.end
        # Accepted spans never overlap, so sorted by start their ends never decrease: only
        # the span just before `start` can reach past it; later ones start at `start` or on.
        low = bisect_left(spans, (start, end))
        # an index loop, not a slice: a slice would copy the rest of the list on every
        # check and make the search linear per edit (review round 2 of #83)
        for position in range(max(low - 1, 0), len(spans)):
            a, b, number = spans[position]
            if a > end:
                break
            if overlap(Span(span.block, a, b), span):
                return self._edits[number]
        return None

    def _blocking_move(self, edit: Edit) -> Edit | None:
        """Why a move cannot be accepted: the edit that claimed its block or its target
        block, the accepted edit its target lies strictly inside (or the insertion or pause
        at its target), or the accepted move it would repeat or chain with."""
        source, to = edit.span.block, _target(edit)
        for found in (
            self._claimed.get(source),
            self._claimed.get(to.block),
            self._moved.get(source),
            self._moved.get(to.block),  # moving into a block that is moved
            self._targets.get(source),  # moving a block that something moves into
        ):
            if found is not None:
                return found
        # the core overlap rule against an empty span at the target is exactly "strictly
        # inside, or an empty edit at the same position"
        return self._holding(to)

    def add(self, edit: Edit, stage: Stage) -> None:
        if edit.kind is EditKind.MOVE:
            self._moved[edit.span.block] = edit
            self._targets.setdefault(_target(edit).block, edit)
            return
        spans = self._blocks.setdefault(edit.span.block, [])
        insort(spans, (edit.span.start, edit.span.end, len(self._edits)))
        self._edits.append(edit)
        if stage is Stage.BLOCK:
            self._claimed[edit.span.block] = edit


def _target(edit: Edit) -> Span:
    """A move's target; `core.Edit` itself makes sure a move has one."""
    if edit.to is None:
        raise ValueError(f"a move edit needs a position to move to, got {edit}")
    return edit.to
