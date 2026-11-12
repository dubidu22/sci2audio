"""Run the text steps on a document and settle overlapping edits (D-61, Q15).

Every step whose languages fit the job runs, also the steps of switched-off categories, so
the report can show what each switch would change without a second run. Their edits are
marked switched off and block nothing. The switched-on edits are then taken in step order
(the registry order: coarse to fine), and inside one step in document order: an edit that
overlaps an edit already accepted is set aside, and remembers the edit that won. A block
that an accepted block-stage edit covers takes no further edit at all, not even a mark at
its start or end. `ask`
edits are accepted like any other; `apply_edits` reads the original for them (D-61 (3)).

A step that raises or returns invalid edits is dropped, with a problem in the result: the
run never stops halfway (D-61 (3)). `strict=True` raises instead, for tests.
"""

from __future__ import annotations

from bisect import bisect_left, insort
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from enum import StrEnum

from sci2audio.core import Document, Edit, ScriptPiece, Span, apply_edits, check_edits
from sci2audio.textprep.registry import BUILT_IN_STEPS, check_registry
from sci2audio.textprep.steps import Category, Stage, StepContext, TextStep


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


class StepError(RuntimeError):
    """A step failed or returned invalid edits (raised only in strict runs)."""


def run_steps(
    document: Document,
    context: StepContext,
    steps: Sequence[TextStep] = BUILT_IN_STEPS,
    switched_off: Collection[Category] = frozenset(),
    *,
    strict: bool = False,
) -> StepRun:
    """Run the steps on the document and settle their edits.

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
    decisions stay intact).
    """

    def __init__(self) -> None:
        self._blocks: dict[int, list[tuple[int, int, int]]] = {}
        self._edits: list[Edit] = []
        self._claimed: dict[int, Edit] = {}  # block index -> its accepted block-stage edit

    def overlapping(self, edit: Edit) -> Edit | None:
        """The accepted edit this one overlaps, or the edit that claimed its block, if any."""
        if (claim := self._claimed.get(edit.span.block)) is not None:
            return claim
        spans = self._blocks.get(edit.span.block, [])
        start, end = edit.span.start, edit.span.end
        # Accepted spans never overlap, so sorted by start their ends never decrease: only
        # the span just before `start` can reach past it; later ones start at `start` or on.
        low = bisect_left(spans, (start, end))
        # an index loop, not a slice: a slice would copy the rest of the list on every
        # check and make the search linear per edit (review round 2 of #83)
        for position in range(max(low - 1, 0), len(spans)):
            a, b, number = spans[position]
            if a > end:
                break
            if overlap(Span(edit.span.block, a, b), edit.span):
                return self._edits[number]
        return None

    def add(self, edit: Edit, stage: Stage) -> None:
        spans = self._blocks.setdefault(edit.span.block, [])
        insort(spans, (edit.span.start, edit.span.end, len(self._edits)))
        self._edits.append(edit)
        if stage is Stage.BLOCK:
            self._claimed[edit.span.block] = edit
