"""The step runner: which edits are accepted, set aside or switched off (#63, D-61, Q15)."""

from dataclasses import replace

import pytest
from core_strategies import documents, edits_on, overlaps, spans_in
from hypothesis import given
from hypothesis import strategies as st

from sci2audio.core import (
    Block,
    BlockKind,
    Document,
    Edit,
    EditKind,
    Section,
    Span,
    apply_edits,
    check_edits,
)
from sci2audio.testing import make_document, rebuilt_from_script
from sci2audio.textprep import (
    BUILT_IN_STEPS,
    DEFAULT_SWITCHED_OFF,
    Category,
    Stage,
    Status,
    StepContext,
    StepError,
    TextStep,
    overlap,
    run_steps,
    spoken_text,
)

EN = StepContext("en")


class Fixed(TextStep):
    """A step that proposes the edits it was given (with its own id filled in)."""

    def __init__(self, step_id, edits=(), *, stage=Stage.INLINE, category=Category.CITATIONS,
                 languages=("en",)):  # fmt: skip
        self.id = step_id
        self.stage = stage
        self.category = category
        self.languages = languages
        self.edits = [replace(edit, step=step_id) for edit in edits]

    def find(self, document: Document, context: StepContext) -> list[Edit]:
        return list(self.edits)


def remove(block: int, start: int, end: int) -> Edit:
    return Edit(Span(block, start, end), EditKind.REMOVE, reason="test", step="x")


def say(block: int, start: int, end: int, text: str = "said") -> Edit:
    return Edit(Span(block, start, end), EditKind.REPLACE, reason="test", step="x",
                replacement=text)  # fmt: skip


def pause(block: int, at: int) -> Edit:
    return Edit(Span(block, at, at), EditKind.PAUSE, reason="test", step="x")


DOC = make_document([(BlockKind.PARAGRAPH, "Several studies (Smith, 2019) agree."),
                     (BlockKind.FURNITURE, "Journal 3:1-9")])  # fmt: skip


def test_the_earlier_step_wins_and_the_later_edit_is_set_aside_with_its_winner() -> None:
    first = Fixed("first", [remove(0, 16, 29)])
    second = Fixed("second", [say(0, 17, 22, "Smith and colleagues"), pause(0, 36)])
    run = run_steps(DOC, EN, [first, second], strict=True)
    assert [(o.edit.step, o.status) for o in run.outcomes] == [
        ("first", Status.ACCEPTED),
        ("second", Status.SET_ASIDE),
        ("second", Status.ACCEPTED),
    ]
    assert run.outcomes[1].won_by == first.edits[0]
    assert run.outcomes[0].category is Category.CITATIONS
    assert render_blocks(DOC, run.script()) == ["Several studies agree. [pause]", "Journal 3:1-9"]


def test_a_whole_block_removal_sets_aside_every_rule_inside_that_block() -> None:
    block = Fixed("furniture", [remove(1, 0, 13)], stage=Stage.BLOCK,
                  category=Category.PAGE_FURNITURE)  # fmt: skip
    inline = Fixed("inline", [say(1, 0, 7, "J."), pause(1, 7), pause(1, 13), pause(1, 0)])
    run = run_steps(DOC, EN, [block, inline], strict=True)
    # the block step claims the whole block: even marks at its two ends, which touch no
    # character, are set aside, so nothing is read where the block was removed (D-105)
    assert [o.status for o in run.outcomes] == [Status.ACCEPTED] + [Status.SET_ASIDE] * 4
    assert all(o.won_by == block.edits[0] for o in run.outcomes[1:])
    assert render_blocks(DOC, run.script())[1] == ""


def test_an_insertion_at_the_start_of_a_removed_block_is_not_read() -> None:
    block = Fixed("furniture", [remove(1, 0, 13)], stage=Stage.BLOCK,
                  category=Category.PAGE_FURNITURE)  # fmt: skip
    inline = Fixed("inline", [say(1, 0, 0, "Note: "), pause(1, 13), pause(0, 0)])
    run = run_steps(DOC, EN, [block, inline], strict=True)
    assert [o.status for o in run.outcomes] == [
        Status.ACCEPTED,
        Status.ACCEPTED,  # block 0 is not claimed
        Status.SET_ASIDE,
        Status.SET_ASIDE,
    ]
    assert [p for p in run.script() if p.span.block == 1] == []


def test_two_marks_at_one_position_overlap() -> None:
    run = run_steps(DOC, EN, [Fixed("a", [pause(0, 5)]), Fixed("b", [pause(0, 5)])], strict=True)
    assert [o.status for o in run.outcomes] == [Status.ACCEPTED, Status.SET_ASIDE]


def test_switched_off_edits_are_reported_and_block_nothing() -> None:
    off = Fixed("off", [remove(0, 16, 29)], category=Category.CITATIONS)
    on = Fixed("on", [say(0, 17, 22, "Smith")], category=Category.ABBREVIATIONS)
    run = run_steps(DOC, EN, [off, on], switched_off={Category.CITATIONS}, strict=True)
    assert [o.status for o in run.outcomes] == [Status.SWITCHED_OFF, Status.ACCEPTED]
    assert run.edits(Status.SWITCHED_OFF) == tuple(off.edits)
    assert run.accepted == tuple(on.edits)


def test_ask_edits_are_accepted_and_read_the_original() -> None:
    ask = Edit(Span(0, 0, 7), EditKind.ASK, reason="unsure", step="x", replacement="Some")
    run = run_steps(DOC, EN, [Fixed("asker", [ask])], strict=True)
    assert run.edits(Status.ACCEPTED)[0].kind is EditKind.ASK
    assert spoken_text(run.script()).startswith("Several studies")


def test_steps_for_another_language_do_not_run() -> None:
    german = Fixed("german", [remove(0, 0, 7)], languages=("de",))
    any_language = Fixed("any", [remove(0, 8, 15)], languages=("*",))
    run = run_steps(DOC, StepContext("en-GB"), [german, any_language], strict=True)
    assert run.not_run == ("german",)
    assert [o.edit.step for o in run.outcomes] == ["any"]


class Raising(Fixed):
    def find(self, document: Document, context: StepContext) -> list[Edit]:
        raise KeyError("boom")


class Returning(Fixed):
    def __init__(self, step_id, value):
        super().__init__(step_id)
        self.value = value

    def find(self, document: Document, context: StepContext) -> list[Edit]:
        return self.value


@pytest.mark.parametrize(
    ("step", "message"),
    [
        (Raising("bad"), "KeyError: 'boom'"),
        (Returning("bad", (remove(0, 0, 3),)), "find must return a list of Edit"),
        (Returning("bad", [remove(0, 0, 3)]), "names step 'x', not 'bad'"),
        (Fixed("bad", [remove(0, 0, 99)]), "ends after the block's text"),
        (Fixed("bad", [remove(5, 0, 1)]), "points at block 5"),
        (Fixed("bad", [remove(0, 0, 5), remove(0, 3, 8)]), "overlaps"),
        (Fixed("bad", [remove(0, 0, 5)], stage=Stage.BLOCK), "does not cover its block"),
    ],
)
def test_a_step_that_fails_or_breaks_the_rules_is_dropped_with_a_problem(
    step: TextStep, message: str
) -> None:
    good = Fixed("good", [remove(0, 30, 35)])
    steps = [step, good] if step.stage is Stage.BLOCK else [good, step]
    run = run_steps(DOC, EN, steps)
    assert [problem.step for problem in run.problems] == ["bad"]
    assert message in run.problems[0].message
    assert [o.edit.step for o in run.outcomes] == ["good"]
    with pytest.raises(StepError, match="bad"):
        run_steps(DOC, EN, steps, strict=True)


def test_steps_in_a_bad_order_are_refused() -> None:
    with pytest.raises(ValueError, match="block steps run first"):
        run_steps(DOC, EN, [Fixed("i"), Fixed("b", stage=Stage.BLOCK)])


def test_the_default_steps_are_the_built_in_ones() -> None:
    run = run_steps(DOC, EN, strict=True)
    assert run == run_steps(DOC, EN, BUILT_IN_STEPS, strict=True)
    assert [o.edit.step for o in run.outcomes] == ["page-furniture", "citations"]
    assert render_blocks(DOC, run.script()) == ["Several studies agree.", ""]
    # a document every built-in step has something to do in: each runs, in registry order
    every = make_document(
        [
            (BlockKind.FURNITURE, "12"),
            (BlockKind.PARAGRAPH, "Noise matters.1"),
            (BlockKind.PARAGRAPH, "It took 5 mg, e.g. here."),
            Block(BlockKind.FOOTNOTE, "1 A note.", label="1"),
            Block(BlockKind.FORMULA, "x = 1 (2)", label="2"),
            (BlockKind.TABLE, "a b"),
            (BlockKind.CODE, "print(1)"),
            (BlockKind.HEADING, "References"),
            (BlockKind.PARAGRAPH, "Doe, J. (2020). A study."),
            (BlockKind.PARAGRAPH, "It is released at https://example.org/a."),
            (BlockKind.PARAGRAPH, "Noise (Smith, 2019) matters."),
            (BlockKind.PARAGRAPH, "An e\N{LATIN SMALL LIGATURE FFI}cient develop-\nment."),
            (BlockKind.PARAGRAPH, "It held (p < .05) in 3\u20135 cases."),
        ],
        tags={1: [(14, 15, "sup")]},
        sections=[Section("References", 1, 7, 9)],
    )
    steps = [o.edit.step for o in run_steps(every, EN, strict=True).outcomes]
    assert list(dict.fromkeys(steps)) == [step.id for step in BUILT_IN_STEPS]


def test_footnote_texts_are_off_unless_switched_on() -> None:
    assert {c for c in Category if not c.on_by_default} == {Category.FOOTNOTE_TEXTS}
    assert {Category.FOOTNOTE_TEXTS} == DEFAULT_SWITCHED_OFF
    note = make_document([Block(BlockKind.FOOTNOTE, "1 A note.", label="1")])
    assert render_blocks(note, run_steps(note, EN, strict=True).script()) == ["Footnote 1. A note."]
    everything = run_steps(note, EN, switched_off=(), strict=True)
    assert render_blocks(note, everything.script()) == [""]


# ---- properties -------------------------------------------------------------------------


@st.composite
def proposals(draw: st.DrawFn, document: Document, step_id: str, stage: Stage) -> list[Edit]:
    """Valid edits one step could propose: inside their blocks, not overlapping each other."""
    if not document.blocks:
        return []
    edits: list[Edit] = []
    with_text = [i for i, block in enumerate(document.blocks) if block.text]
    for _ in range(draw(st.integers(1, 6))):
        if stage is Stage.BLOCK:
            index = draw(st.sampled_from(with_text or range(len(document.blocks))))
            span = Span(index, 0, len(document.blocks[index].text))
            if not span.end:
                continue
            edit = replace(draw(edits_on(span).filter(lambda e: e.kind is not EditKind.PAUSE)),
                           step=step_id)  # fmt: skip
        else:
            span = draw(spans_in(document))
            if with_text and not document.blocks[span.block].text and draw(st.booleans()):
                index = draw(st.sampled_from(with_text))  # mostly blocks with text
                length = len(document.blocks[index].text)
                start = draw(st.integers(0, length))
                span = Span(index, start, draw(st.integers(start, length)))
            edit = replace(draw(edits_on(span)), step=step_id)
        if not any(overlaps(edit.span, other.span) for other in edits):
            edits.append(edit)
    return edits


@st.composite
def runs(draw: st.DrawFn) -> tuple[Document, list[Fixed]]:
    document = draw(documents())
    stages = sorted(draw(st.lists(st.sampled_from(Stage), min_size=1, max_size=4)),
                    key=lambda stage: stage is Stage.INLINE)  # fmt: skip
    steps = []
    for number, stage in enumerate(stages):
        step_id = f"step-{number}"
        category = draw(st.sampled_from(Category))
        edits = draw(proposals(document, step_id, stage))
        steps.append(Fixed(step_id, edits, stage=stage, category=category, languages=("*",)))
    return document, steps


def greedy(steps: list[Fixed], switched_off: set[Category]) -> list[Edit]:
    """The overlap rule written plainly: in step order, keep what overlaps nothing kept and
    lies in no block a kept block-stage edit covers."""
    kept: list[Edit] = []
    claimed: set[int] = set()
    for step in steps:
        if step.category in switched_off:
            continue
        for edit in sorted(step.edits, key=lambda e: (e.span.block, e.span.start, e.span.end)):
            if edit.span.block in claimed:
                continue
            if not any(overlaps(edit.span, other.span) for other in kept):
                kept.append(edit)
                if step.stage is Stage.BLOCK:
                    claimed.add(edit.span.block)
    return kept


@given(runs(), st.sets(st.sampled_from(Category)))
def test_the_runner_settles_any_proposals_by_the_written_rule(
    case: tuple[Document, list[Fixed]], switched_off: set[Category]
) -> None:
    document, steps = case
    run = run_steps(document, StepContext(document.language), steps, switched_off,
                    strict=True)  # fmt: skip
    # every proposal is reported exactly once
    assert sorted(map(repr, (o.edit for o in run.outcomes))) == sorted(
        repr(edit) for step in steps for edit in step.edits
    )
    # the accepted edits are those of the plain greedy rule and always apply
    assert list(run.accepted) == greedy(steps, switched_off)
    check_edits(document, run.accepted)
    apply_edits(document, run.accepted)
    order = {step.id: number for number, step in enumerate(steps)}
    stages = {step.id: step.stage for step in steps}
    # a block an accepted block-stage edit covers holds no other step's accepted edit
    claimed = {e.span.block: e.step for e in run.accepted if stages[e.step] is Stage.BLOCK}
    assert all(claimed.get(e.span.block, e.step) == e.step for e in run.accepted)
    for outcome in run.outcomes:
        off = outcome.category in switched_off
        assert (outcome.status is Status.SWITCHED_OFF) is off
        if outcome.status is Status.SET_ASIDE:
            winner = outcome.won_by
            assert winner in run.accepted
            claims = (
                stages[winner.step] is Stage.BLOCK and winner.span.block == outcome.edit.span.block
            )
            assert overlap(winner.span, outcome.edit.span) or claims
            assert order[winner.step] < order[outcome.edit.step]
        else:
            assert outcome.won_by is None


@given(runs(), st.sampled_from(Category))
def test_switching_a_category_off_is_like_leaving_its_steps_out(
    case: tuple[Document, list[Fixed]], category: Category
) -> None:
    document, steps = case
    context = StepContext(document.language)
    switched = run_steps(document, context, steps, {category}, strict=True)
    without = run_steps(document, context, [s for s in steps if s.category is not category],
                        (), strict=True)  # fmt: skip
    assert switched.accepted == without.accepted
    assert switched.script() == without.script()
    # the other steps' outcomes, statuses and winners included, are those of the run without
    assert [o for o in switched.outcomes if o.category is not category] == list(without.outcomes)


@given(documents())
def test_the_built_in_steps_never_fail_and_are_idempotent(document: Document) -> None:
    context = StepContext(document.language)
    first = run_steps(document, context, strict=True)
    check_edits(document, first.accepted)
    script = first.script()
    rebuilt = rebuilt_from_script(document, script)
    second = run_steps(rebuilt, context, strict=True)
    assert render_blocks(rebuilt, second.script()) == render_blocks(document, script)


def render_blocks(document: Document, script) -> list[str]:
    return [
        spoken_text([piece for piece in script if piece.span.block == index], show_pauses=True)
        for index in range(len(document.blocks))
    ]
