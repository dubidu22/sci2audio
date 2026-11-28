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

Inline code is read as printed (#854): an inline edit that touches a run the file marks as
code (`inline_code`: a character of it, or a position strictly inside it) is dropped before
anything else, from built-in steps and plugins alike, so arrows, operators and numbers in
"Use `x => x + 1` here." stay as typed while the prose around them is still read. Code
that holds only links (URLs, DOIs, e-mail addresses, with the punctuation and brackets
around them) is not protected: the links step leaves it out as before; nor is a word split
over a line end, whose hyphen and line break the line-end hyphen step takes away as layout,
not code (#913). Block edits (a code block's notice, furniture) and moves claim whole
blocks and are not touched. A dropped edit is no outcome: the report lists what a rule
changes, and inside code none does.

A step that raises or returns invalid edits is dropped, with a problem in the result: the
run never stops halfway (D-61 (3)). `strict=True` raises instead, for tests. Steps from
`installed_steps` bring the plugins they hold and the plugins that did not load: the result
lists the first, and the second as problems (#216).
"""

from __future__ import annotations

from bisect import bisect_left, insort
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from functools import cached_property

from sci2audio.core import (
    Document,
    Edit,
    EditKind,
    ScriptPiece,
    Span,
    TextLine,
    apply_edits,
    check_edits,
)
from sci2audio.textprep.furniture import HIDDEN_TAGS, PAGE_BREAK_TAGS
from sci2audio.textprep.hyphens import HYPHENS, LineEndHyphenStep
from sci2audio.textprep.links import find_links
from sci2audio.textprep.plugins import InstalledSteps, PluginError, PluginInfo
from sci2audio.textprep.registry import BUILT_IN_STEPS, check_registry
from sci2audio.textprep.steps import (
    DEFAULT_SWITCHED_OFF,
    Category,
    Stage,
    StepContext,
    StepError,
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
    """What the steps proposed for one document, settled.

    The data behind the report (UC-01, #70): every edit with its reason, step, category and
    status, set-aside edits with the edit that won, problems and the steps not run for the
    job's language. An inline edit that touches inline code is dropped before it gets an
    outcome (#854), so it is not here: the code is read as printed.
    """

    document: Document
    outcomes: tuple[Outcome, ...]
    problems: tuple[StepProblem, ...] = ()
    not_run: tuple[str, ...] = ()  # ids of steps that don't handle the job's language
    plugins: tuple[PluginInfo, ...] = ()  # the plugin steps among the steps (#216)

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
    # each step may know which categories this run will not apply (D-595)
    context = replace(context, switched_off=frozenset(switched_off))
    accepted = _Accepted()
    code = inline_code(document)
    outcomes: list[Outcome] = []
    problems: list[StepProblem] = []
    not_run: list[str] = []
    plugins: tuple[PluginInfo, ...] = ()
    if isinstance(steps, InstalledSteps):
        plugins = steps.plugins
        problems += [
            StepProblem(problem.name, f"plugin not loaded: {problem.message}")
            for problem in steps.problems
        ]
    for step in steps:
        if not step.handles(context.language):
            not_run.append(step.id)
            continue
        try:
            edits = _proposed(step, document, context)
        except Exception as error:
            if strict:
                raise StepError(f"text step {step.id!r} failed: {error}") from error
            # a plugin's error arrives as its own text, made inside the guard's time limit
            said = (
                str(error) if isinstance(error, PluginError) else f"{type(error).__name__}: {error}"
            )
            problems.append(StepProblem(step.id, said))
            continue
        if step.stage is Stage.INLINE and code:
            edits = [
                edit
                for edit in edits
                if not _in_code(code, edit.span) or _layout_join(step, edit, document)
            ]
        for edit in edits:
            if step.category in switched_off:
                outcomes.append(Outcome(edit, step.category, Status.SWITCHED_OFF))
            elif (winner := accepted.overlapping(edit)) is not None:
                outcomes.append(Outcome(edit, step.category, Status.SET_ASIDE, winner))
            else:
                accepted.add(edit, step.stage)
                outcomes.append(Outcome(edit, step.category, Status.ACCEPTED))
    return StepRun(document, tuple(outcomes), tuple(problems), tuple(not_run), plugins)


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


CODE_TAG = "code"
# a run inside one of these is no inline code: `pre` is a code block, which has its notice;
# a hidden run or page-break marker is left out by the hidden-runs step
_NOT_INLINE_CODE = frozenset({"pre"}) | HIDDEN_TAGS | PAGE_BREAK_TAGS
# what may stand around and between links in code left to the links step: the punctuation
# and brackets it strips at a link's end (`links._TRAILING`, `links._PAIRS`), their opening
# brackets and quotes, and white space
_AROUND_LINKS = frozenset(
    ".,;:!?*()[]<>'\" \t\n"
    "\N{LEFT SINGLE QUOTATION MARK}\N{RIGHT SINGLE QUOTATION MARK}"
    "\N{LEFT DOUBLE QUOTATION MARK}\N{RIGHT DOUBLE QUOTATION MARK}"
    "\N{DOUBLE LOW-9 QUOTATION MARK}"
)


def inline_code(document: Document) -> dict[int, list[tuple[int, int]]]:
    """Where each block holds inline code: (start, end) in its text, in order, runs side by
    side joined. Inline code is a run the file tags `code` (Markdown's backticks, an EPUB's
    `<code>`) outside `pre`, not hidden, and not only links (`_only_links`). A line whose
    text is not where its part says (it never should be) is skipped, so a span never points
    at other text."""
    items = document.content.items()
    found: dict[int, list[tuple[int, int]]] = {}
    for index, block in enumerate(document.blocks):
        spans: list[tuple[int, int]] = []
        for part in block.parts:
            line = items[part.item][1]
            if not isinstance(line, TextLine):
                continue
            if block.text[part.start : part.start + len(line.text)] != line.text:
                continue
            offset = part.start
            for run in line.runs:
                end = offset + len(run.text)
                tags = set(run.tags)
                if CODE_TAG in tags and not _NOT_INLINE_CODE & tags:
                    if spans and spans[-1][1] == offset:
                        offset = spans.pop()[0]
                    spans.append((offset, end))
                offset = end
        if spans := [span for span in spans if not _only_links(block.text[slice(*span)])]:
            found[index] = spans
    return found


def _only_links(text: str) -> bool:
    """True for code that holds links and nothing else (#854): one or more URLs, DOIs,
    arXiv ids or e-mail addresses as `links.find_links` finds them, with only white space,
    commas, the sentence punctuation and the brackets and quotes the links step strips
    around a link between and around them ("`<https://example.org/a>.`", "`https://a.org,
    https://b.org`"). The links step leaves such code out with its reason, as it does the
    same links printed without backticks."""
    links = find_links(text)
    at = 0
    for link in links:
        if not _AROUND_LINKS.issuperset(text[at : link.start].strip()):
            return False
        at = link.end
    return bool(links) and _AROUND_LINKS.issuperset(text[at:].strip())


def _layout_join(step: TextStep, edit: Edit, document: Document) -> bool:
    """True for the built-in line-end hyphen step's join of a word split over a line end:
    it takes away the hyphen and the line break that the page's layout put there, no
    character of the code, so a typewriter word split so reads whole ("matplot-" and "lib"
    are "matplotlib", #913). Every other edit that touches inline code is dropped."""
    removed = document.blocks[edit.span.block].text[edit.span.start : edit.span.end]
    return (
        isinstance(step, LineEndHyphenStep)
        and edit.kind is EditKind.REMOVE
        and len(removed) == 2
        and removed[0] in HYPHENS
        and removed[1] == "\n"
    )


def _in_code(code: Mapping[int, list[tuple[int, int]]], span: Span) -> bool:
    """True if the span touches inline code: shares a character with it, or is a position
    strictly inside it. The spans of a block are in order and never overlap."""
    spans = code.get(span.block)
    if not spans:
        return False
    position = bisect_left(spans, (span.end, span.end))
    for start, end in spans[max(position - 1, 0) : position + 1]:
        if overlap(Span(span.block, start, end), span):
            return True
    return False


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
        # check and make the search linear per edit (#83)
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
