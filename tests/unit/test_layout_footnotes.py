"""Layout on made-up pages: footnotes (Issue #21 step 3, #37).

A two-column page as in `test_layout`: body text in 10 point down to y 506, notes in
8 point from y 606 down, below a short rule, each opening with a 6 point mark.
"""

import itertools
from dataclasses import replace

from hypothesis import given
from hypothesis import strategies as st
from test_layout import GUTTER, LEFT, MIDDLE, RIGHT, content, line, short, two_columns

from sci2audio.core import BlockKind, Box, Document, Drawing, TextLine, TextRun
from sci2audio.layout import build_document
from sci2audio.layout.split import kept

LEFT_END = MIDDLE - GUTTER / 2  # the left column's right edge
RIGHT_START = MIDDLE + GUTTER / 2
RULE_Y = 600.0
_ids = itertools.count()


def note(mark: str, text: str, y: float, x0: float = LEFT, x1: float = LEFT_END) -> TextLine:
    """A notes line in 8 point, opening with a mark in 6 point ("" for none)."""
    runs = (TextRun(mark, "Times", 6.0),) if mark else ()
    runs += (TextRun(text, "Times", 8.0),)
    return TextLine(f"n{next(_ids)}", runs, Box(x0, y, x1, y + 8))


def mark(text: str, y: float) -> TextLine:
    """A mark in 6 point as a line of its own at the column's left edge."""
    return TextLine(f"m{next(_ids)}", (TextRun(text, "Times", 6.0),), Box(LEFT, y, LEFT + 4, y + 6))


def rule(x0: float = LEFT, width: float = 60.0, y: float = RULE_Y) -> Drawing:
    return Drawing(f"r{next(_ids)}", Box(x0, y, x0 + width, y + 0.4))


def build(notes: list[TextLine], *drawings: Drawing, rows: int = 30) -> Document:
    """The two columns of body text with these lines at the page's foot."""
    left, right = two_columns(f"p{next(_ids)}", 100, rows)
    return build_document(content([*left, *right, *notes], drawings=drawings))


def footnotes(doc: Document) -> list[tuple[str, str]]:
    """Each footnote's label and text."""
    return [(b.label, b.text) for b in doc.blocks if b.kind is BlockKind.FOOTNOTE]


def kind_of(doc: Document, item: str) -> BlockKind:
    return next(b.kind for b in doc.blocks if any(p.item == item for p in b.parts))


def test_the_text_below_a_rule_is_a_footnote_labelled_by_its_mark() -> None:
    doc = build([note("1", " A note on the data.", RULE_Y + 6)], rule())
    assert footnotes(doc) == [("1", "1 A note on the data.")]


def test_each_row_opening_with_a_mark_starts_a_note() -> None:
    notes = [
        note("1", " The first note,", RULE_Y + 6),
        note("", "going on.", RULE_Y + 16),
        note("2", " The second note.", RULE_Y + 26),
    ]
    assert footnotes(build(notes, rule())) == [
        ("1", "1 The first note,\ngoing on."),
        ("2", "2 The second note."),
    ]


def test_a_note_cut_into_pieces_on_one_row_is_one_note() -> None:
    """#37: a narrow column's note, cut at its wide word gaps, read as one."""
    notes = [
        note("3", " A note set", RULE_Y + 6, LEFT, 150),
        note("", "with wide gaps", RULE_Y + 6, 180, 240),
        note("", "in it.", RULE_Y + 6, 260, LEFT_END),
        note("4", " Another.", RULE_Y + 16, LEFT, 150),
    ]
    assert footnotes(build(notes, rule())) == [
        ("3", "3 A note set with wide gaps in it."),
        ("4", "4 Another."),
    ]


def test_a_narrow_justified_note_of_three_lines_is_one_note() -> None:
    """#37, as in hardt footnote 1: the white between the justified words of the first two
    lines lines up, which the paragraph step takes for table cells."""
    notes = [
        note("1", "Datasets", RULE_Y + 6, LEFT, 110),
        note("", "and associated programs can be ac-", RULE_Y + 6, 125, LEFT_END),
        note("", "cessed at", RULE_Y + 16, LEFT, 110),
        note("", "https://example.org/data/", RULE_Y + 16, 125, LEFT_END),
        note("", "ellipsis.", RULE_Y + 26, LEFT, 120),
    ]
    assert footnotes(build(notes, rule())) == [
        (
            "1",
            "1Datasets and associated programs can be ac-\n"
            "cessed at https://example.org/data/\nellipsis.",
        )
    ]


def test_a_mark_set_close_to_its_note_is_joined_without_a_space() -> None:
    """#36: Chi p11 "5https://...", Nowak p1 "1Specifically": the mark is a piece of its
    own, set close to the note's first word; the page prints no space between them."""
    lines = [
        TextLine(
            f"m{next(_ids)}",
            (TextRun("5", "Times", 6.0),),
            Box(LEFT, RULE_Y + 5, LEFT + 3, RULE_Y + 11),
        ),
        TextLine(
            f"n{next(_ids)}",
            (TextRun("Specifically, a note.", "Times", 8.0),),
            Box(LEFT + 3.2, RULE_Y + 6, LEFT_END, RULE_Y + 14),
        ),
    ]
    assert footnotes(build(lines, rule())) == [("5", "5Specifically, a note.")]


def test_a_mark_that_is_a_line_of_its_own_is_read() -> None:
    """Review of #52: the mark is a small line of its own at the left end of its row; its
    size is compared with the row's text, not with itself."""
    lines = [
        mark("1", RULE_Y + 6),
        note("", "A note.", RULE_Y + 6, LEFT + 8),
        mark("2", RULE_Y + 16),
        note("", "Second.", RULE_Y + 16, LEFT + 8),
    ]
    assert footnotes(build(lines, rule())) == [("1", "1 A note."), ("2", "2 Second.")]


def test_a_mark_with_white_before_it_is_read_and_the_text_kept_as_found() -> None:
    """Review of #52: a mark run printed with white before it (" 1") gives the label "1";
    the note's text keeps the white, as a block's text is its lines as found."""
    lines = [note(" 1", " A note.", RULE_Y + 6), note(" 2", " Second.", RULE_Y + 16)]
    assert footnotes(build(lines, rule())) == [("1", " 1 A note."), ("2", " 2 Second.")]


def test_two_rules_over_one_column_give_each_note_once() -> None:
    """Review of #52: a second short rule below the first (a rule within the notes) must
    not read the notes below it a second time."""
    lines = [note("1", " First.", RULE_Y + 6), note("2", " Second.", RULE_Y + 26)]
    doc = build(lines, rule(), rule(y=RULE_Y + 20))
    assert footnotes(doc) == [("1", "1 First."), ("2", "2 Second.")]


def test_a_mark_may_be_a_note_symbol() -> None:
    star, dagger = "\N{ASTERISK OPERATOR}", "\N{DAGGER}"
    notes = [note(star, "Equal contribution.", RULE_Y + 6), note(dagger, "Now at X.", RULE_Y + 16)]
    assert [label for label, _ in footnotes(build(notes, rule()))] == [star, dagger]


def test_a_number_in_the_text_size_is_not_a_mark() -> None:
    lines = [
        note("1", " A note that ends a line with", RULE_Y + 6),
        TextLine(
            "n-plain",
            (TextRun("12", "Times", 8.0), TextRun(" cases.", "Times", 8.0)),
            Box(LEFT, RULE_Y + 16, 200, RULE_Y + 24),
        ),
    ]
    assert footnotes(build(lines, rule())) == [("1", "1 A note that ends a line with\n12 cases.")]


def raised_note(number: str, text: str, y: float, rise: float) -> TextLine:
    """A notes line in 8 point whose mark is set in the text's size but raised by `rise`
    points, as superior figures are (#235: LNI from page 2 on). Boxes are loose, as
    extraction gives them: the mark's box is shorter at the bottom."""
    width = 4.0 * len(number)
    return TextLine(
        f"n{next(_ids)}",
        (
            TextRun(number, "Times", 8.0, box=Box(LEFT, y, LEFT + width, y + 7.2 - rise)),
            TextRun(text, "Times", 8.0, box=Box(LEFT + width, y, LEFT_END, y + 7.2)),
        ),
        Box(LEFT, y, LEFT_END, y + 7.2),
    )


def test_a_raised_mark_in_the_text_size_starts_a_note() -> None:
    """D-507: raised by `footnote_mark_rise` (0.1 em) or more, a mark in the text's size
    starts a note; 0.05 em is not enough, and a number on the baseline never is."""
    notes = [
        raised_note("4", " https://example.org/a", RULE_Y + 6, rise=2.8),  # 0.35 em, as LNI
        raised_note("5", " https://example.org/b", RULE_Y + 16, rise=0.8),  # 0.1 em
        raised_note("12", " cases on a line of note 5.", RULE_Y + 26, rise=0.4),  # 0.05 em
        raised_note("13", " cases on the baseline.", RULE_Y + 36, rise=0.0),
    ]
    assert [label for label, _ in footnotes(build(notes, rule()))] == ["4", "5"]


def test_the_text_below_a_rule_without_a_mark_is_one_note_without_a_label() -> None:
    notes = [note("", "Code at a public site.", RULE_Y + 6), note("", "Data too.", RULE_Y + 16)]
    assert footnotes(build(notes, rule())) == [("", "Code at a public site.\nData too.")]


def test_a_page_without_a_rule_has_no_footnotes() -> None:
    doc = build([note("1", " A small line at the foot.", RULE_Y + 6)])
    assert footnotes(doc) == []


def test_a_small_table_at_the_foot_without_a_rule_is_not_a_footnote() -> None:
    cells = [
        note("", text, RULE_Y + 6 + 10 * row, x0, x0 + 40)
        for row, numbers in enumerate([("Model", "F1"), ("1", "80.2"), ("2", "81.5")])
        for text, x0 in zip(numbers, (LEFT, LEFT + 100), strict=True)
    ]
    assert footnotes(build(cells)) == []


def test_a_rule_with_body_size_text_below_it_is_not_a_footnote_rule() -> None:
    """A short line over a table or a figure set in the text's size."""
    below = [line("1 Results in the text size", LEFT, RULE_Y + 6, 200)]
    doc = build(below, rule())
    assert footnotes(doc) == []
    assert kind_of(doc, below[0].id) is BlockKind.PARAGRAPH


def test_a_rule_across_the_column_is_not_a_footnote_rule() -> None:
    """A table's rule spans the column; a footnote rule is much narrower."""
    doc = build([note("1", " Small text under a full rule.", RULE_Y + 6)], rule(width=200))
    assert footnotes(doc) == []


def test_a_rule_high_on_the_page_is_not_a_footnote_rule() -> None:
    doc = build([note("1", " Small text high up.", 206)], rule(y=200), rows=6)
    assert footnotes(doc) == []


def test_a_note_in_the_right_column_leaves_the_left_column_alone() -> None:
    """Notes below a rule in the right column; the left column runs on to the foot."""
    left_foot = [line(f"left foot {k}", LEFT, RULE_Y + 6 + 14 * k, LEFT_END) for k in range(3)]
    notes = [note("5", " A note on the right.", RULE_Y + 6, RIGHT_START, RIGHT)]
    doc = build([*left_foot, *notes], rule(RIGHT_START))
    assert footnotes(doc) == [("5", "5 A note on the right.")]
    assert {kind_of(doc, li.id) for li in left_foot} == {BlockKind.PARAGRAPH}


def test_a_footnote_takes_the_place_of_its_notes_after_their_column_text() -> None:
    """The notes stand where the paragraph step read them: after the left column's text,
    before the right column's."""
    left, right = two_columns("place", 100, 30)
    left[-1] = short(left[-1])  # the left column's paragraph ends
    notes = [note("1", " A note.", RULE_Y + 6)]
    doc = build_document(content([*left, *right, *notes], drawings=(rule(),)))
    kinds = [b.kind for b in doc.blocks if b.kind is not BlockKind.FIGURE]
    assert kinds == [BlockKind.PARAGRAPH, BlockKind.FOOTNOTE, BlockKind.PARAGRAPH]
    assert kind_of(doc, right[0].id) is BlockKind.PARAGRAPH


def test_an_underbrace_drawn_in_a_note_is_part_of_that_note() -> None:
    """#58 (D-329, D-332), as in nowak p1: the underbrace of "n times" is drawn in two thin
    halves inside the box of footnote 1's line "| {z }". Read before footnote 2 is over, it
    used to join the end of footnote 2; it stands in footnote 1, just after that line."""
    first = note("1", " Specifically, a derives b in n steps:", RULE_Y + 6)
    brace = note("", "| {z }", RULE_Y + 16, LEFT + 30, LEFT + 90)
    times = note("", "n times", RULE_Y + 26, LEFT + 40, LEFT + 80)
    second = note("2", " The second note.", RULE_Y + 36)
    halves = [
        Drawing(f"u{next(_ids)}", Box(LEFT + 42, RULE_Y + 19, LEFT + 58, RULE_Y + 20)),
        Drawing(f"u{next(_ids)}", Box(LEFT + 62, RULE_Y + 19, LEFT + 78, RULE_Y + 20)),
    ]
    doc = build([first, brace, times, second], rule(), *halves)
    assert footnotes(doc) == [
        ("1", "1 Specifically, a derives b in n steps:\n| {z }\nn times"),
        ("2", "2 The second note."),
    ]
    one, two = [b for b in doc.blocks if b.kind is BlockKind.FOOTNOTE]
    end = one.text.index("| {z }") + len("| {z }")
    after = [(p.item, p.start) for p in one.parts[2:5]]
    assert after == [(brace.id, end - 6), (halves[0].id, end), (halves[1].id, end)]
    assert [p.item for p in two.parts] == [second.id]


def test_a_mark_in_a_piece_set_close_to_the_next_stands_between_them() -> None:
    """#58 with #36's joins (D-332, D-335): two pieces of a note's row set close together
    have no separator between them, so a mark drawn in the first piece starts where the
    second starts; the note is what keeping all its parts makes of it, and keeping the
    second piece alone leaves the mark at its start."""
    first = note("1", " Specifically, a", RULE_Y + 6, LEFT, 150)
    second = note("", "=> b holds.", RULE_Y + 6, 150.4, LEFT_END)
    bar = Drawing(f"u{next(_ids)}", Box(100, RULE_Y + 9, 110, RULE_Y + 9.5))
    doc = build([first, second], rule(), bar)
    assert footnotes(doc) == [("1", "1 Specifically, a=> b holds.")]
    block = next(b for b in doc.blocks if b.kind is BlockKind.FOOTNOTE)
    end = len(first.text)
    assert [(p.item, p.start) for p in block.parts[1:]] == [
        (first.id, 0),
        (bar.id, end),
        (second.id, end),
    ]
    lengths = {first.id: len(first.text), second.id: len(second.text)}
    assert kept(block, block.parts, lengths) == block
    plain = replace(block, kind=BlockKind.PARAGRAPH, label="")  # a piece with no mark
    rest = kept(plain, plain.parts[2:], lengths)
    assert (rest.text, [(p.item, p.start) for p in rest.parts]) == (
        second.text,
        [(bar.id, 0), (second.id, 0)],
    )


@st.composite
def foot_notes(draw: st.DrawFn) -> tuple[list[TextLine], list[tuple[str, str]]]:
    """Numbered notes below a rule, each of one to three rows, the first row maybe cut in
    two pieces, with the notes expected: label and text."""
    lines, expected, y = [], [], RULE_Y + 6
    first = draw(st.integers(1, 30))
    for mark in range(first, first + draw(st.integers(1, 4))):
        text = f" Note {mark} says"
        if draw(st.booleans()):
            lines += [note(str(mark), text, y, LEFT, 160), note("", "more", y, 180, LEFT_END)]
            text += " more"
        else:
            lines.append(note(str(mark), text, y))
        for row in range(draw(st.integers(0, 2))):
            y += 10
            lines.append(note("", f"and row {row}.", y))
            text += f"\nand row {row}."
        expected.append((str(mark), f"{mark}{text}"))
        y += 10
    return lines, expected


@given(foot_notes())
def test_any_notes_below_a_rule_are_read_note_by_note(
    found: tuple[list[TextLine], list[tuple[str, str]]],
) -> None:
    notes, expected = found
    doc = build(notes, rule())
    assert footnotes(doc) == expected
    held = [p.item for b in doc.blocks for p in b.parts]
    assert len(held) == len(set(held))
    assert {li.id for li in notes} <= set(held)


@st.composite
def page_feet(draw: st.DrawFn) -> tuple[list[TextLine], list[Drawing]]:
    """Small and body-size lines at the foot of either column, under zero to three short
    or long rules in the lower half of the page, most of them just above the lines."""
    lines = []
    for row in range(draw(st.integers(0, 8))):
        x0 = draw(st.sampled_from([LEFT, LEFT + 8, RIGHT_START, RIGHT_START + 8]))
        size = draw(st.sampled_from([8.0, 8.0, 8.0, 6.0, 10.0]))  # body size seldom
        marked = draw(st.sampled_from(["", "1", " 2", "\N{DAGGER}"]))
        white = draw(st.sampled_from(["", " ", "  "]))
        runs = ((TextRun(marked, "Times", 6.0),) if marked else ()) + (
            TextRun(f"{white}foot {row}{white}", "Times", size),
        )
        y = 560 + draw(st.integers(0, 20)) * 8
        right = LEFT_END if x0 < MIDDLE else RIGHT
        lines.append(TextLine(f"f{next(_ids)}", runs, Box(x0, y, right, y + size)))
    rules = [
        rule(
            draw(st.sampled_from([LEFT, RIGHT_START])),
            draw(st.floats(20, 110) | st.floats(10, 230)),
            draw(st.floats(510, 560) | st.floats(400, 760)),
        )
        for _ in range(draw(st.integers(0, 3)))
    ]
    return lines, rules


@given(page_feet())
def test_any_rules_and_lines_at_the_foot_keep_every_line_in_one_block(
    found: tuple[list[TextLine], list[Drawing]],
) -> None:
    """Review of #52: overlapping zones, rules over body text or over nothing never fail
    and never read a line twice; every line's text stands at its part's start; each
    footnote opens with its label after any white."""
    lines, rules = found
    doc = build(lines, *rules)
    held = [p.item for b in doc.blocks for p in b.parts]
    assert len(held) == len(set(held))
    texts = {li.id: li.text for page in doc.content.pages for li in page.lines}
    for block in doc.blocks:
        for part in block.parts:  # a block's text is its lines as found
            if part.item in texts:
                text = texts[part.item]
                assert block.text[part.start : part.start + len(text)] == text
        if block.kind is BlockKind.FOOTNOTE:
            assert block.text.lstrip().startswith(block.label)
