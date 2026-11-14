"""Footnotes read after the sentence that holds their mark (#213, D-558, plan Q4, Q5, Q7).

The regression cases (tests/regression, issue 213) pin the scripts; these tests pin the
sentence-end helper, which notes move and which stay, and the category switches.
"""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from sci2audio.core import Block, BlockKind, Document, Edit, EditKind, Span
from sci2audio.testing import make_document
from sci2audio.testing.regression import render
from sci2audio.textprep import (
    BUILT_IN_STEPS,
    Category,
    Stage,
    Status,
    StepContext,
    TextStep,
    run_steps,
)
from sci2audio.textprep.footnotes import FootnotePlaceStep, FootnoteStep
from sci2audio.textprep.utterances import sentence_end

EN = StepContext("en")

# --- the sentence end ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "mark", "end"),
    [
        ("It grew1 a lot. Then it fell.", "1", "It grew1 a lot."),
        ("It grew a lot.1 Then it fell.", "1", "It grew a lot.1"),  # after the mark
        ("It grew a lot.1", "1", "It grew a lot.1"),
        ("It grew1 and then", "1", "It grew1 and then"),  # runs to the block's end
        ("It grew1 and then  \n", "1", "It grew1 and then"),
        ("As J. Doe et al.3 show in Fig. 2, it holds. We use it.", "3", "it holds."),
        ("It is “large”.7 So it is.", "7", "“large”.7"),
        ("Is it?2 Yes.", "2", "Is it?2"),
        ("One (two).4 Three.", "4", "(two).4"),
    ],
)
def test_the_sentence_ends_where_the_cutter_would_end_it(text: str, mark: str, end: str) -> None:
    start = text.index(mark)
    got = sentence_end(text, start + len(mark), [(start, start + len(mark))], "en")
    assert text[:got].endswith(end)
    assert got == text.index(end) + len(end)


def test_two_marks_after_one_full_stop_both_go_with_the_sentence() -> None:
    text = "We used Qualys5 and Mozilla.56 Both agree."
    marks = [(14, 15), (28, 29), (29, 30)]
    assert sentence_end(text, 15, marks, "en") == 30
    assert sentence_end(text, 30, marks, "en") == 30


def test_german_ordinals_and_abbreviations_end_no_sentence() -> None:
    text = "Er wurde 3. Sieger im Lauf4 am Sonntag, z. B. hier. Danach ruhte er."
    start = text.index("4")
    assert text[: sentence_end(text, start + 1, [(start, start + 1)], "de")].endswith("hier.")


def test_a_position_outside_the_text_is_refused() -> None:
    with pytest.raises(ValueError, match="outside"):
        sentence_end("Short.", 7, [], "en")


def test_a_text_of_nothing_but_marks_ends_after_its_last_mark() -> None:
    assert sentence_end("1  ", 1, [(0, 1)], "en") == 1
    assert sentence_end("1 2 ", 1, [(0, 1), (2, 3)], "en") == 3


@given(
    text=st.text(alphabet="ab .?!\n1”(", max_size=40),
    data=st.data(),
)
def test_the_end_lies_in_the_text_after_the_position_and_outside_the_marks(
    text: str, data: st.DataObject
) -> None:
    position = data.draw(st.integers(0, len(text)))
    cuts = sorted(data.draw(st.lists(st.integers(0, len(text)), max_size=6)))
    gaps = [(a, b) for a, b in zip(cuts[::2], cuts[1::2], strict=False) if a < b]
    end = sentence_end(text, position, gaps, "en")
    assert 0 <= end <= len(text)
    assert not any(a < end < b for a, b in gaps)
    removed = {i for a, b in gaps for i in range(a, b)}
    printed_before = position > 0 and position - 1 not in removed and text[position - 1].strip()
    if printed_before:
        assert end >= position  # a mark right after printed text: its sentence ends later


# --- which notes move ------------------------------------------------------------------


def paper() -> Document:
    return make_document(
        [
            (BlockKind.PARAGRAPH, "It works.1 It holds.2 Done."),
            Block(BlockKind.FOOTNOTE, "1 A note.", label="1"),
            Block(BlockKind.FOOTNOTE, "2 Another.", label="2"),
        ],
        tags={0: [(9, 10, "sup"), (20, 21, "sup")]},
    )


def test_each_note_moves_after_its_sentence() -> None:
    edits = FootnotePlaceStep().find(paper(), EN)
    assert [(e.span, e.to, e.kind) for e in edits] == [
        (Span(1, 0, 9), Span(0, 10, 10), EditKind.MOVE),
        (Span(2, 0, 10), Span(0, 21, 21), EditKind.MOVE),
    ]
    assert edits[0].reason == "footnote 1 is read after the sentence that holds its mark"
    assert render(run_steps(paper(), EN, strict=True)) == [
        "It works.",
        "Footnote 1. A note.",
        "It holds.",
        "Footnote 2. Another.",
        "Done.",
    ]


def test_leaving_out_all_footnotes_still_leaves_them_out() -> None:
    run = run_steps(paper(), EN, switched_off=(), strict=True)
    moves = [o for o in run.outcomes if o.edit.step == "footnote-places"]
    assert [o.status for o in moves] == [Status.SET_ASIDE] * 2
    assert {o.won_by.step for o in moves if o.won_by} == {"footnote-texts"}
    assert render(run) == ["It works. It holds. Done."]


def test_switching_footnotes_off_reads_marks_and_leaves_notes_where_printed() -> None:
    off = {Category.FOOTNOTES, Category.FOOTNOTE_TEXTS}
    run = run_steps(paper(), EN, switched_off=off, strict=True)
    assert render(run) == ["It works.1 It holds.2 Done.", "1 A note.", "2 Another."]


def test_a_note_whose_mark_is_not_found_stays_where_printed() -> None:
    document = make_document(
        [
            (BlockKind.PARAGRAPH, "It works. 1 It holds."),
            Block(BlockKind.FOOTNOTE, "1 A note.", label="1"),
        ]
    )  # the "1" is not set small: no mark
    assert FootnotePlaceStep().find(document, EN) == []


def test_a_mark_inside_another_note_moves_nothing_and_the_first_mark_wins() -> None:
    ref = ("sup", "role:doc-noteref", "link:b2l0")
    document = make_document(
        [
            (BlockKind.PARAGRAPH, "First use.1 Then more."),
            (BlockKind.FOOTNOTE, "See also1 there."),
            (BlockKind.FOOTNOTE, "The linked note."),
        ],
        tags={0: [(10, 11, ref)], 1: [(8, 9, ref)]},
    )
    edits = FootnotePlaceStep().find(document, EN)
    assert [(e.span.block, e.to) for e in edits] == [(2, Span(0, 11, 11))]  # not into note 1
    only_in_a_note = make_document(
        [
            (BlockKind.PARAGRAPH, "No mark here."),
            (BlockKind.FOOTNOTE, "See also1 there."),
            (BlockKind.FOOTNOTE, "The linked note."),
        ],
        tags={1: [(8, 9, ref)]},
    )
    assert FootnotePlaceStep().find(only_in_a_note, EN) == []


def test_a_note_marked_twice_moves_to_its_first_mark() -> None:
    ref = ("sup", "role:doc-noteref", "link:b2l0")
    document = make_document(
        [
            (BlockKind.PARAGRAPH, "Once.1 More."),
            (BlockKind.PARAGRAPH, "Twice.1 Done."),
            (BlockKind.FOOTNOTE, "The note."),
        ],
        tags={0: [(5, 6, ref)], 1: [(6, 7, ref)]},
    )
    assert [e.to for e in FootnotePlaceStep().find(document, EN)] == [Span(0, 6, 6)]


def test_a_note_with_no_text_is_not_moved(monkeypatch: pytest.MonkeyPatch) -> None:
    # layout gives every block with an item some text; a move needs text to carry
    document = make_document(
        [(BlockKind.PARAGRAPH, "It works.1 Done."), (BlockKind.FOOTNOTE, "")],
        tags={0: [(9, 10, "sup")]},
    )
    mark = Edit(Span(0, 9, 10), EditKind.REMOVE, "mark", "footnotes")
    monkeypatch.setattr(FootnoteStep, "marked", lambda self, d, c: ([mark], [(mark, 1)]))
    assert FootnotePlaceStep().find(document, EN) == []


class Holding(TextStep):
    """An inline step whose replacement holds the end of the sentence with the mark."""

    id = "holding"
    languages = ("en",)
    category = Category.CITATIONS
    stage = Stage.INLINE

    def find(self, document: Document, context: StepContext) -> list[Edit]:
        return [Edit(Span(0, 11, 17), EditKind.REPLACE, "test", self.id, "lot, t")]


def test_a_note_whose_place_another_rule_rewrote_stays_where_printed() -> None:
    document = make_document(
        [
            (BlockKind.PARAGRAPH, "It grew1 a lot. Then it fell."),
            Block(BlockKind.FOOTNOTE, "1 A note.", label="1"),
        ],
        tags={0: [(7, 8, "sup")]},
    )
    assert [e.to for e in FootnotePlaceStep().find(document, EN)] == [Span(0, 15, 15)]
    steps = [*BUILT_IN_STEPS[:-1], Holding(), BUILT_IN_STEPS[-1]]
    run = run_steps(document, EN, steps, strict=True)
    move = next(o for o in run.outcomes if o.edit.step == "footnote-places")
    assert move.status is Status.SET_ASIDE
    assert move.won_by is not None
    assert move.won_by.step == "holding"
    assert render(run) == ["It grew a lot, then it fell.", "Footnote 1. A note."]
