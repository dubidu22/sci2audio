"""Move steps in the runner (#213, plan Q3, D-558): moves run last, in a stage of their own.

A move-stage step proposes only moves and only a move-stage step proposes them. A move
never blocks a rule about the text: it is set aside when its block or its target block is
claimed by a block-stage edit, when its target lies strictly inside an accepted edit or at
an accepted insertion, or when it would move a block twice or chain; the block is then read
where it stands. `StepRun.read_at` tells where each block is read.
"""

from dataclasses import replace

import pytest
from core_strategies import edits_on, small_documents, spans_in
from hypothesis import given
from hypothesis import strategies as st

from sci2audio.core import Block, BlockKind, Document, Edit, EditKind, Span, check_edits
from sci2audio.testing import make_document
from sci2audio.testing.regression import render
from sci2audio.textprep import (
    Category,
    Stage,
    Status,
    StepContext,
    StepError,
    TextStep,
    check_registry,
    cut_utterances,
    run_steps,
    spoken_text,
)

EN = StepContext("en")


class Fixed(TextStep):
    """A step that proposes the edits it was given (with its own id filled in)."""

    def __init__(self, step_id, edits=(), *, stage=Stage.INLINE, category=Category.FOOTNOTES):
        self.id = step_id
        self.stage = stage
        self.category = category
        self.languages = ("en",)
        self.edits = [replace(edit, step=step_id) for edit in edits]

    def find(self, document: Document, context: StepContext) -> list[Edit]:
        return list(self.edits)


DOC = make_document(
    [
        (BlockKind.PARAGRAPH, "It works.1 It holds."),
        Block(BlockKind.FOOTNOTE, "1 A note.", label="1"),
        Block(BlockKind.FOOTNOTE, "2 Other note.", label="2"),
        (BlockKind.FURNITURE, "Journal 3:1-9"),
    ]
)


def move(block: int, target: int, at: int) -> Edit:
    span = Span(block, 0, len(DOC.blocks[block].text))
    return Edit(span, EditKind.MOVE, "read at its mark", "x", to=Span(target, at, at))


def remove(block: int, start: int, end: int) -> Edit:
    return Edit(Span(block, start, end), EditKind.REMOVE, reason="test", step="x")


def insert(block: int, at: int, text: str) -> Edit:
    return Edit(Span(block, at, at), EditKind.REPLACE, "test", "x", replacement=text)


def mover(*edits: Edit, step_id: str = "places") -> Fixed:
    return Fixed(step_id, edits, stage=Stage.MOVE)


def said(run) -> list[str]:
    """The script, one line per run of pieces of one block, in reading order."""
    lines: list[tuple[int, list]] = []
    for piece in run.script():
        if not lines or lines[-1][0] != piece.span.block:
            lines.append((piece.span.block, []))
        lines[-1][1].append(piece)
    return [spoken_text(pieces) for _, pieces in lines]


# --- the stage ---------------------------------------------------------------------------


def test_move_steps_run_after_every_inline_step() -> None:
    check_registry([Fixed("b", stage=Stage.BLOCK), Fixed("i"), mover(), mover(step_id="m2")])
    with pytest.raises(ValueError, match="inline step 'i' comes after move step 'places'"):
        check_registry([mover(), Fixed("i")])
    with pytest.raises(ValueError, match="block step 'b' comes after move step 'places'"):
        check_registry([mover(), Fixed("b", stage=Stage.BLOCK)])


@pytest.mark.parametrize(
    ("step", "message"),
    [
        (Fixed("bad", [move(1, 0, 10)]), "only a move step proposes moves"),
        (Fixed("bad", [remove(0, 9, 10)], stage=Stage.MOVE), "a move step proposes only moves"),
        (Fixed("bad", [move(1, 0, 10), move(1, 0, 3)], stage=Stage.MOVE), "overlaps"),
    ],
    ids=["move-from-inline", "plain-from-move", "moves-a-block-twice"],
)
def test_a_step_breaking_the_move_rules_is_dropped(step: TextStep, message: str) -> None:
    good = Fixed("good", [remove(0, 9, 10)])
    run = run_steps(DOC, EN, [good, step])
    assert [problem.step for problem in run.problems] == ["bad"]
    assert message in run.problems[0].message
    with pytest.raises(StepError, match=message):
        run_steps(DOC, EN, [good, step], strict=True)


# --- settling ----------------------------------------------------------------------------


def test_an_accepted_move_reads_the_block_at_its_target() -> None:
    marks = Fixed("footnotes", [remove(0, 9, 10)])
    run = run_steps(DOC, EN, [marks, mover(move(1, 0, 10))], strict=True)
    assert [o.status for o in run.outcomes] == [Status.ACCEPTED, Status.ACCEPTED]
    assert said(run) == ["It works.", "1 A note.", "It holds.", "2 Other note.", "Journal 3:1-9"]
    assert [run.read_at(block) for block in range(4)] == [0, 0, 2, 3]


def test_moves_from_two_steps_to_one_place_are_read_in_block_order() -> None:
    run = run_steps(
        DOC, EN, [mover(move(2, 0, 10)), mover(move(1, 0, 10), step_id="m2")], strict=True
    )
    assert run.edits(Status.SET_ASIDE) == ()
    assert said(run)[:4] == ["It works.1", "1 A note.", "2 Other note.", "It holds."]


def test_a_block_left_out_by_a_block_step_is_not_moved() -> None:
    # "Footnote texts" switched on: its whole-block removal claims the note (D-128)
    texts = Fixed("footnote-texts", [remove(1, 0, 9)], stage=Stage.BLOCK,
                  category=Category.FOOTNOTE_TEXTS)  # fmt: skip
    run = run_steps(DOC, EN, [texts, mover(move(1, 0, 10))], switched_off=(), strict=True)
    moved = run.outcomes[1]
    assert (moved.status, moved.won_by) == (Status.SET_ASIDE, texts.edits[0])
    assert run.read_at(1) == 1
    assert said(run) == ["It works.1 It holds.", "2 Other note.", "Journal 3:1-9"]


@pytest.mark.parametrize("at", [0, 7, 13], ids=["start", "inside", "end"])
def test_a_move_into_a_block_left_out_by_a_block_step_is_set_aside(at: int) -> None:
    # at the block's two ends too, which the core overlap rule would let through (D-128)
    furniture = Fixed("furniture", [remove(3, 0, 13)], stage=Stage.BLOCK,
                      category=Category.PAGE_FURNITURE)  # fmt: skip
    run = run_steps(DOC, EN, [furniture, mover(move(1, 3, at))], strict=True)
    assert run.outcomes[1].status is Status.SET_ASIDE
    assert run.outcomes[1].won_by == furniture.edits[0]
    assert said(run) == ["It works.1 It holds.", "1 A note.", "2 Other note."]


@pytest.mark.parametrize(
    "winner",
    [remove(0, 8, 12), insert(0, 10, "inserted"), Edit(Span(0, 10, 10), EditKind.PAUSE, "t", "x")],
    ids=["inside-a-removal", "at-an-insertion", "at-a-pause"],
)
def test_a_target_held_by_an_accepted_edit_sets_the_move_aside(winner: Edit) -> None:
    rule = Fixed("rule", [winner])
    run = run_steps(DOC, EN, [rule, mover(move(1, 0, 10))], strict=True)
    assert run.outcomes[1].status is Status.SET_ASIDE
    assert run.outcomes[1].won_by == rule.edits[0]


def test_a_target_at_the_edge_of_an_accepted_edit_is_fine() -> None:
    rule = Fixed("rule", [remove(0, 9, 10), remove(0, 10, 11)])
    run = run_steps(DOC, EN, [rule, mover(move(1, 0, 10))], strict=True)
    assert run.edits(Status.SET_ASIDE) == ()


def test_a_block_moves_once_and_moves_never_chain() -> None:
    first = mover(move(1, 0, 10))
    again = mover(move(1, 0, 3), step_id="again")
    into_moved = mover(move(2, 1, 4), step_id="into-moved")
    moving_a_target = mover(
        Edit(Span(0, 0, 20), EditKind.MOVE, "t", "x", to=Span(2, 0, 0)), step_id="target"
    )
    run = run_steps(DOC, EN, [first, again, into_moved, moving_a_target], strict=True)
    assert [o.status for o in run.outcomes] == [Status.ACCEPTED] + [Status.SET_ASIDE] * 3
    assert {o.won_by for o in run.outcomes[1:]} == {first.edits[0]}
    run_steps(
        DOC, EN, [mover(move(2, 0, 3), step_id="m2"), first], strict=True
    ).script()  # two targets: fine


def test_a_switched_off_move_leaves_the_block_where_it_stands() -> None:
    run = run_steps(DOC, EN, [mover(move(1, 0, 10))], switched_off={Category.FOOTNOTES})
    assert run.outcomes[0].status is Status.SWITCHED_OFF
    assert run.read_at(1) == 1
    assert said(run)[:2] == ["It works.1 It holds.", "1 A note."]


# --- properties --------------------------------------------------------------------------


@st.composite
def runs_with_moves(draw: st.DrawFn) -> tuple[Document, list[TextStep]]:
    """A document, an inline step with valid edits and two move steps with any moves."""
    document = draw(small_documents())
    plain: list[Edit] = []
    for _ in range(draw(st.integers(0, 6))):
        edit = draw(edits_on(draw(spans_in(document))))
        try:
            check_edits(document, [*plain, edit])
        except ValueError:
            continue
        plain.append(edit)
    steps: list[TextStep] = [Fixed("inline", plain)]
    for number in range(2):
        moves: list[Edit] = []
        for _ in range(draw(st.integers(0, 3))):
            source = draw(st.integers(0, len(document.blocks) - 1))
            target = draw(st.integers(0, len(document.blocks) - 1))
            text = document.blocks[source].text
            if not text or source == target:
                continue
            at = draw(st.integers(0, len(document.blocks[target].text)))
            edit = Edit(
                Span(source, 0, len(text)), EditKind.MOVE, "t", "x", to=Span(target, at, at)
            )
            try:
                check_edits(document, [*moves, edit])
            except ValueError:
                continue
            moves.append(edit)
        steps.append(mover(*moves, step_id=f"move-{number}"))
    return document, steps


@given(case=runs_with_moves())
def test_settled_moves_always_apply_and_read_every_block_once(
    case: tuple[Document, list[TextStep]],
) -> None:
    document, steps = case
    run = run_steps(document, EN, steps, strict=True)
    pieces = run.script()  # the accepted edits pass core's rules: never raises
    still = run_steps(document, EN, steps[:1], strict=True).script()
    for index in range(len(document.blocks)):  # each block reads the same, maybe elsewhere
        text = "".join(p.text for p in pieces if p.span.block == index)
        assert text == "".join(p.text for p in still if p.span.block == index)
    moved = {e.span.block: e.to.block for e in run.accepted if e.kind is EditKind.MOVE}
    for index in range(len(document.blocks)):
        assert run.read_at(index) == moved.get(index, index)


# --- what comes after the runner: utterances and the regression renderer -----------------


def test_a_block_read_inside_a_paragraph_is_cut_on_its_own() -> None:
    marks = Fixed("footnotes", [remove(0, 9, 10)])
    run = run_steps(DOC, EN, [marks, mover(move(1, 0, 10))], strict=True)
    utterances = cut_utterances(DOC, run.script())
    assert [(u.text, u.span) for u in utterances[:3]] == [
        ("It works.", Span(0, 0, 9)),  # the removed mark ends a run: no utterance holds it
        ("1 A note.", Span(1, 0, 9)),
        ("It holds.", Span(0, 11, 20)),
    ]
    assert render(run)[:3] == ["It works.", "1 A note.", "It holds."]
