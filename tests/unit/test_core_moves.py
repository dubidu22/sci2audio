"""Move edits: a block's script read at a position in another block (#213, D-61 (1), D-558).

A move edit covers a whole block and names `to`, an empty span in another block. Applying
it reads the block's own script (its own edits applied) at `to` instead of where the block
stands; every piece keeps the span it stands for, so read-along and the report still point
at the printed place. Rules (plan Q2): one move per block, no chains, `to` never strictly
inside another edit and never at the position of an empty edit that is not a move; moves
to one position are read in block order.
"""

import json

import pytest
from core_strategies import edits_on, overlaps, small_documents, spans_in
from hypothesis import assume, given
from hypothesis import strategies as st

from sci2audio.core import (
    BlockKind,
    Document,
    Edit,
    EditKind,
    OverlappingEditsError,
    ScriptPiece,
    Span,
    SpanError,
    apply_edits,
    check_edits,
    from_data,
    to_data,
)
from sci2audio.testing import make_document

DOC = make_document(
    [
        (BlockKind.PARAGRAPH, "It works.1 It holds."),  # the mark "1" is 9-10
        (BlockKind.PARAGRAPH, "Second paragraph."),
        (BlockKind.FOOTNOTE, "1 A note."),
        (BlockKind.FOOTNOTE, "2 Other note."),
    ]
)


def move(block: int, to: Span, step: str = "places") -> Edit:
    length = len(DOC.blocks[block].text)
    return Edit(Span(block, 0, length), EditKind.MOVE, "read at its mark", step, to=to)


MARK = Edit(Span(0, 9, 10), EditKind.REMOVE, "footnote mark", "footnotes")
INTRO = Edit(Span(2, 0, 1), EditKind.REPLACE, "introduced", "footnotes", "Footnote 1.")


# --- what a move edit is ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("span", "to", "replacement"),
    [
        (Span(2, 0, 9), None, ""),  # no target
        (Span(2, 0, 9), Span(0, 3, 4), ""),  # target not a position
        (Span(2, 0, 9), Span(0, 3, 3), "x"),  # a replacement
        (Span(2, 0, 0), Span(0, 3, 3), ""),  # nothing to move
        (Span(2, 0, 9), Span(2, 3, 3), ""),  # into its own block
    ],
    ids=["no-target", "target-not-a-position", "replacement", "empty", "own-block"],
)
def test_a_move_needs_a_block_and_a_position_in_another_block(
    span: Span, to: Span | None, replacement: str
) -> None:
    with pytest.raises(ValueError, match="move"):
        Edit(span, EditKind.MOVE, "r", "s", replacement=replacement, to=to)


@pytest.mark.parametrize("kind", [EditKind.REMOVE, EditKind.REPLACE, EditKind.ASK])
def test_only_a_move_has_a_target(kind: EditKind) -> None:
    with pytest.raises(ValueError, match="only a move"):
        Edit(Span(0, 0, 2), kind, "r", "s", replacement="x", to=Span(1, 0, 0))


def test_a_move_round_trips_through_export_and_other_edits_do_not_name_a_target() -> None:
    edit = move(2, Span(0, 10, 10))
    assert from_data(Edit, json.loads(json.dumps(to_data(edit)))) == edit
    assert "to" not in to_data(MARK)  # defaults are left out: older records stay the same


# --- applying moves --------------------------------------------------------------------


def test_a_moved_block_is_read_at_its_target_with_its_own_edits() -> None:
    pieces = apply_edits(DOC, [move(2, Span(0, 10, 10)), MARK, INTRO])
    assert pieces == (
        ScriptPiece("It works.", Span(0, 0, 9)),
        ScriptPiece("Footnote 1.", Span(2, 0, 1)),
        ScriptPiece(" A note.", Span(2, 1, 9)),
        ScriptPiece(" It holds.", Span(0, 10, 20)),
        ScriptPiece("Second paragraph.", Span(1, 0, 17)),
        ScriptPiece("2 Other note.", Span(3, 0, 13)),
    )


def test_kept_text_is_split_exactly_at_the_target() -> None:
    pieces = apply_edits(DOC, [move(3, Span(1, 6, 6))])
    assert pieces[1:4] == (
        ScriptPiece("Second", Span(1, 0, 6)),
        ScriptPiece("2 Other note.", Span(3, 0, 13)),
        ScriptPiece(" paragraph.", Span(1, 6, 17)),
    )
    assert [p.span.block for p in pieces].count(3) == 1  # not read at its own place too


@pytest.mark.parametrize("at", [0, 17], ids=["start", "end"])
def test_a_move_to_either_end_of_a_block(at: int) -> None:
    pieces = apply_edits(DOC, [move(2, Span(1, at, at))])
    blocks = [p.span.block for p in pieces]
    assert blocks == ([0, 2, 1, 3] if at == 0 else [0, 1, 2, 3])


def test_moves_to_one_position_are_read_in_block_order() -> None:
    to = Span(0, 10, 10)
    for edits in ([move(3, to), move(2, to)], [move(2, to), move(3, to)]):
        assert [p.span.block for p in apply_edits(DOC, edits)] == [0, 2, 3, 0, 1]


def test_moves_into_one_block_are_read_at_their_positions_whatever_their_block_order() -> None:
    pieces = apply_edits(DOC, [move(2, Span(0, 15, 15)), move(3, Span(0, 5, 5))])
    assert [(p.span.block, p.text) for p in pieces[:5]] == [
        (0, "It wo"),
        (3, "2 Other note."),
        (0, "rks.1 It h"),
        (2, "1 A note."),
        (0, "olds."),
    ]


def test_a_move_to_the_end_of_a_removed_span_and_the_start_of_a_replacement() -> None:
    number = Edit(Span(0, 11, 13), EditKind.REPLACE, "word", "numbers", "Its")
    pieces = apply_edits(DOC, [MARK, number, move(2, Span(0, 10, 10))])
    assert [p.text for p in pieces[:4]] == ["It works.", "1 A note.", " ", "Its"]


def test_a_move_whose_block_reads_nothing_moves_nothing() -> None:
    gone = Edit(Span(2, 0, 9), EditKind.REMOVE, "left out", "footnote-texts")
    pieces = apply_edits(DOC, [gone, move(2, Span(0, 10, 10))])
    assert all(p.span.block != 2 for p in pieces)
    assert "".join(p.text for p in pieces if p.span.block == 0) == DOC.blocks[0].text


# --- invalid moves ---------------------------------------------------------------------


def test_a_move_must_cover_its_whole_block() -> None:
    part = Edit(Span(2, 0, 5), EditKind.MOVE, "r", "places", to=Span(0, 10, 10))
    with pytest.raises(SpanError, match="whole block"):
        check_edits(DOC, [part])


def test_a_target_outside_its_block_is_refused() -> None:
    with pytest.raises(SpanError, match="ends after"):
        check_edits(DOC, [move(2, Span(0, 99, 99))])
    with pytest.raises(SpanError, match="block 7"):
        check_edits(DOC, [move(2, Span(7, 0, 0))])


def test_a_block_moves_at_most_once() -> None:
    first, second = move(2, Span(0, 10, 10)), move(2, Span(1, 0, 0))
    with pytest.raises(OverlappingEditsError) as error:
        check_edits(DOC, [first, second])
    assert {error.value.first, error.value.second} == {first, second}


@pytest.mark.parametrize("order", [0, 1])
def test_a_moved_block_is_no_target(order: int) -> None:
    edits = [move(2, Span(0, 10, 10)), move(3, Span(2, 5, 5))]
    with pytest.raises(OverlappingEditsError, match="moved"):
        check_edits(DOC, edits[order:] + edits[:order])


@pytest.mark.parametrize(
    "other",
    [
        Edit(Span(0, 8, 12), EditKind.REMOVE, "r", "s"),
        Edit(Span(0, 3, 15), EditKind.REPLACE, "r", "s", "x"),
        Edit(Span(0, 9, 11), EditKind.ASK, "r", "s"),
        Edit(Span(0, 10, 10), EditKind.PAUSE, "r", "s"),
        Edit(Span(0, 10, 10), EditKind.REPLACE, "r", "s", "inserted"),
    ],
    ids=["inside-removal", "inside-replacement", "inside-ask", "pause-there", "insert-there"],
)
def test_a_target_inside_another_edit_or_at_an_insertion_is_refused(other: Edit) -> None:
    moved = move(2, Span(0, 10, 10))
    with pytest.raises(OverlappingEditsError) as error:
        apply_edits(DOC, [moved, other])
    assert {error.value.first, error.value.second} == {moved, other}


def test_a_move_does_not_overlap_the_edits_inside_its_own_block() -> None:
    whole = Edit(Span(2, 0, 9), EditKind.REMOVE, "left out", "footnote-texts")
    for inside in (INTRO, whole, Edit(Span(2, 9, 9), EditKind.PAUSE, "r", "s")):
        check_edits(DOC, [move(2, Span(0, 10, 10)), inside])


# --- properties ------------------------------------------------------------------------


@st.composite
def documents_with_moves(draw: st.DrawFn) -> tuple[Document, list[Edit], list[Edit]]:
    """A document, valid plain edits on it, and valid moves (each rule of Q2 kept)."""
    document = draw(small_documents())
    plain: list[Edit] = []
    for _ in range(draw(st.integers(0, 8))):
        edit = draw(edits_on(draw(spans_in(document))))
        if not any(overlaps(edit.span, other.span) for other in plain):
            plain.append(edit)
    moves: list[Edit] = []
    sources: set[int] = set()
    targets: set[int] = set()
    for attempt in range(draw(st.integers(1, 4))):
        # the first attempt always moves block 0, which has text, into another block
        source = 0 if not attempt else draw(st.integers(0, len(document.blocks) - 1))
        target = (
            draw(st.integers(1, len(document.blocks) - 1))
            if not attempt
            else draw(st.integers(0, len(document.blocks) - 1))
        )
        text = document.blocks[source].text
        if not text or source == target or source in sources | targets or target in sources:
            continue
        positions = [
            at
            for at in range(len(document.blocks[target].text) + 1)
            if not any(_blocks_target(edit, target, at) for edit in plain)
        ]
        if not positions:
            continue
        at = draw(st.sampled_from(positions))
        sources.add(source)
        targets.add(target)
        span = Span(source, 0, len(text))
        moves.append(Edit(span, EditKind.MOVE, "test", "s3", to=Span(target, at, at)))
    assume(moves)
    return document, plain, moves


def _blocks_target(edit: Edit, block: int, at: int) -> bool:
    span = edit.span
    if span.block != block:
        return False
    return span.start < at < span.end or span.start == span.end == at


@given(case=documents_with_moves(), data=st.data())
def test_valid_moves_never_raise_and_their_order_is_irrelevant(
    case: tuple[Document, list[Edit], list[Edit]], data: st.DataObject
) -> None:
    document, plain, moves = case
    pieces = apply_edits(document, plain + moves)
    shuffled = data.draw(st.permutations(plain + moves))
    assert apply_edits(document, shuffled) == pieces
    for piece in pieces:
        document.check_span(piece.span)


@given(case=documents_with_moves())
def test_moves_reorder_the_script_and_change_no_block_s_reading(
    case: tuple[Document, list[Edit], list[Edit]],
) -> None:
    document, plain, moves = case
    still, moved = apply_edits(document, plain), apply_edits(document, plain + moves)
    for index in range(len(document.blocks)):
        before = "".join(p.text for p in still if p.span.block == index)
        assert "".join(p.text for p in moved if p.span.block == index) == before
        # pauses too: each block reads the same pieces, only in another place
        assert sum(p.pause for p in moved if p.span.block == index) == sum(
            p.pause for p in still if p.span.block == index
        )


@given(case=documents_with_moves())
def test_a_moved_block_is_read_in_one_piece_right_at_its_target(
    case: tuple[Document, list[Edit], list[Edit]],
) -> None:
    document, plain, moves = case
    pieces = apply_edits(document, plain + moves)
    blocks = [p.span.block for p in pieces]
    for edit in moves:
        source, to = edit.span.block, edit.to
        assert to is not None
        where = [n for n, block in enumerate(blocks) if block == source]
        if not where:
            continue  # its own edits left nothing to read
        assert where == list(range(where[0], where[-1] + 1))  # one run, not split up
        # in the target block, everything before it ends at the target, and after it
        # starts there; other blocks moved to the same position may stand between
        target = [n for n, block in enumerate(blocks) if block == to.block]
        before = [pieces[n] for n in target if n < where[0]]
        after = [pieces[n] for n in target if n > where[-1]]
        assert all(p.span.end <= to.start for p in before)
        assert all(p.span.start >= to.start for p in after)
    # the target block's own pieces stay in order of their spans
    for index in range(len(document.blocks)):
        starts = [p.span.start for p in pieces if p.span.block == index]
        assert starts == sorted(starts)
