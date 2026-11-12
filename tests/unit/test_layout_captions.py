"""Layout on made-up pages: captions and list items (Issue #21 step 3, PR C2, D-85).

One column between x 70 and x 526 as in `test_layout`, body text in 10 point on a 14
point pitch. White between two lines ends a paragraph.
"""

import itertools

from hypothesis import given
from hypothesis import strategies as st
from test_layout import LEFT, RIGHT, content

from sci2audio.core import BlockKind, Box, Document, TextLine, TextRun
from sci2audio.layout import build_document

PITCH = 14.0
HALF = (LEFT + RIGHT) / 2
_ids = itertools.count()


def text_line(text: str | tuple[TextRun, ...], y: float, x0: float = LEFT, end: float = HALF):
    runs = (TextRun(text, "Times", 10.0),) if isinstance(text, str) else text
    return TextLine(f"t{next(_ids)}", runs, Box(x0, y, end, y + 10))


def page(*rows: str | tuple[TextRun, ...], full: bool = False, top: float = 100) -> list:
    """One line per row, each a paragraph of its own with white between them, or with
    `full` one paragraph: all lines but the last run to the column's edge."""
    last = len(rows) - 1
    if full:
        return [
            text_line(row, top + PITCH * k, end=RIGHT if k < last else HALF)
            for k, row in enumerate(rows)
        ]
    return [text_line(row, top + 2 * PITCH * k) for k, row in enumerate(rows)]


def build(*rows: str | tuple[TextRun, ...], full: bool = False) -> Document:
    return build_document(content([*running(), *page(*rows, full=full, top=300)]))


def running() -> list[TextLine]:
    """A paragraph of running text at the top of the page, which sets the line pitch."""
    return page(*(f"Running text, line {k}." for k in range(10)), full=True)


def kinds(doc: Document, kind: BlockKind) -> list[tuple[str, str]]:
    return [(b.label, b.text) for b in doc.blocks if b.kind is kind]


def captions(doc: Document) -> list[tuple[str, str]]:
    return kinds(doc, BlockKind.CAPTION)


def items(doc: Document) -> list[tuple[str, str]]:
    return kinds(doc, BlockKind.LIST_ITEM)


def bold(label: str, rest: str) -> tuple[TextRun, ...]:
    return (TextRun(label, "Times-Bold", 10.0, bold=True), TextRun(rest, "Times", 10.0))


# Captions


def test_a_label_with_a_colon_or_full_stop_opens_a_caption() -> None:
    doc = build("Table 2: Results on the test set.", "Figure 1. A plot of the data.")
    assert captions(doc) == [
        ("Table 2", "Table 2: Results on the test set."),
        ("Figure 1", "Figure 1. A plot of the data."),
    ]


def test_caption_labels_keep_their_printed_form() -> None:
    doc = build("Fig. 3: Short form.", "Table A.2: In an appendix.", "TABLE 4. In capitals.")
    assert [label for label, _ in captions(doc)] == ["Fig. 3", "Table A.2", "TABLE 4"]


def test_a_bold_label_without_punctuation_opens_a_caption() -> None:
    doc = build(bold("Algorithm 1", " CKY"), "Text after the caption ends.")
    assert captions(doc) == [("Algorithm 1", "Algorithm 1 CKY")]


def test_a_label_in_the_text_style_without_punctuation_is_running_text() -> None:
    doc = build("Algorithm 1 runs in cubic time.", "Figure 1 gives the accuracy.")
    assert captions(doc) == []


def test_figure_and_table_named_in_running_text_stay_paragraphs() -> None:
    """D-85: "Figure 1 gives …" at a paragraph's start, "see Table 2." inside one."""
    doc = build(
        "Figure 1 gives the accuracy for each of the five models and",
        "the results, which we discuss below; for the numbers, see",
        "Table 2. The model does well on all of them.",
        full=True,
    )
    assert captions(doc) == []
    assert [b.kind for b in doc.blocks] == [BlockKind.PARAGRAPH] * 2


def test_an_algorithm_caption_ends_where_its_numbered_lines_start() -> None:
    """The pseudocode below the caption is the algorithm the caption names (#38, PR D1)."""
    doc = build(bold("Algorithm 3", " Faster prefix probability"), "1: P = I - P", full=True)
    assert captions(doc) == [("Algorithm 3", "Algorithm 3 Faster prefix probability")]
    caption = next(b for b in doc.blocks if b.kind is BlockKind.CAPTION)
    assert caption.describes is not None
    assert (doc.blocks[caption.describes].kind, doc.blocks[caption.describes].text) == (
        BlockKind.FIGURE,
        "1: P = I - P",
    )


def test_a_table_or_figure_caption_is_not_cut_at_a_numbered_line() -> None:
    """Only an algorithm's caption ends where numbered lines start (D-87)."""
    for name in ("Figure 1", "Table 1"):
        doc = build(f"{name}: A caption whose next line", "1: is not code.", full=True)
        assert captions(doc) == [(name, f"{name}: A caption whose next line\n1: is not code.")]
        assert [b.kind for b in doc.blocks][-1] is BlockKind.CAPTION


def test_a_caption_over_two_lines_is_one_caption() -> None:
    doc = build("Figure 2: Accuracy of the models over the", "test set.", full=True)
    assert captions(doc) == [("Figure 2", "Figure 2: Accuracy of the models over the\ntest set.")]


# List items


def test_bulleted_lines_are_list_items() -> None:
    doc = build("• A first point;", "• a second point;", "• the last one.")
    assert items(doc) == [
        ("•", "• A first point;"),
        ("•", "• a second point;"),
        ("•", "• the last one."),
    ]


def test_a_numbered_list_in_one_block_is_cut_into_its_items() -> None:
    doc = build("1. First Party Collection", "2. Third Party Sharing", "3. User Choice", full=True)
    assert items(doc) == [
        ("1.", "1. First Party Collection"),
        ("2.", "2. Third Party Sharing"),
        ("3.", "3. User Choice"),
    ]


def test_an_item_over_several_lines_is_one_item() -> None:
    rows = [
        "1. A long first item that goes on over",
        "more than one line.",
        "2. A short second item.",
    ]
    doc = build_document(
        content(
            [
                *running(),
                text_line(rows[0], 300, end=RIGHT),
                text_line(rows[1], 300 + PITCH, x0=LEFT + 12),
                text_line(rows[2], 300 + 2 * PITCH),
            ]
        )
    )
    assert items(doc) == [("1.", f"{rows[0]}\n{rows[1]}"), ("2.", rows[2])]


def test_lettered_and_roman_lists() -> None:
    letters = build("(a) the first;", "(b) the second.")
    roman = build("(i) A is a set;", "(ii) it is closed;", "(iii) it has a unit.")
    assert [label for label, _ in items(letters)] == ["(a)", "(b)"]
    assert [label for label, _ in items(roman)] == ["(i)", "(ii)", "(iii)"]


def test_i_after_h_is_a_letter() -> None:
    rows = [f"({ch}) entry {ch};" for ch in "abcdefghij"]
    assert [label for label, _ in items(build(*rows))] == [f"({ch})" for ch in "abcdefghij"]


def test_a_list_inside_an_item_does_not_end_the_outer_list() -> None:
    doc = build("(i) one;", "(ii) two, that is:", "• x = y;", "• y = x.", "(iii) three.")
    assert [label for label, _ in items(doc)] == ["(i)", "(ii)", "•", "•", "(iii)"]


def test_one_numbered_line_is_not_a_list() -> None:
    assert items(build("1. Only this line is numbered.")) == []


def test_a_list_starts_at_its_first_marker() -> None:
    assert items(build("2. A second point;", "3. a third point.")) == []


def test_a_block_whose_markers_make_no_list_stays_whole() -> None:
    """A block is cut only where its pieces become items: one that starts at "2.", or
    whose markers are not set alike, stays one paragraph (review of #53)."""
    late = build("2. A second point that goes on", "3. a third point.", full=True)
    assert items(late) == []
    assert late.blocks[-1].text == "2. A second point that goes on\n3. a third point."
    rows = [
        text_line("(1)", 300, end=LEFT + 14),
        text_line("William went running.", 300, x0=LEFT + 30, end=RIGHT),
        text_line("(2) is understood as asserting this.", 300 + PITCH),
    ]
    mixed = build_document(content([*running(), *rows]))
    assert items(mixed) == []
    assert mixed.blocks[-1].kind is BlockKind.PARAGRAPH
    assert mixed.blocks[-1].text.endswith("\n(2) is understood as asserting this.")


def test_text_between_items_ends_the_list() -> None:
    doc = build("1. One point.", "Some text in between.", "2. Another point.")
    assert items(doc) == []


def test_a_paragraph_that_names_an_example_is_not_a_list_item() -> None:
    """Numbered examples set apart (marker, gap, text), and a paragraph that opens by naming
    one: "(1) is understood as …". The items of one list are set alike."""
    lines = []
    for y, marker, text in [(300, "(1)", "William went running."), (356, "(2)", "Did he?")]:
        lines += [text_line(marker, y, end=LEFT + 14), text_line(text, y, x0=LEFT + 30)]
    lines.append(text_line("(1) is understood as asserting this.", 328))
    doc = build_document(content([*running(), *lines]))
    assert items(doc) == []


def test_a_number_on_a_line_of_its_own_is_not_a_marker() -> None:
    """A formula's number read before the formula: "(1)\\nX -> a"."""
    doc = build("(1)", "X -> a", "(2)", "S -> e", full=True)
    assert items(doc) == []


def test_sub_figure_labels_on_one_line_are_not_a_list() -> None:
    """nowak p3 "(a) ξ(Y | X) (b) ξ(Y Z | X)" and liu p3 "(a) (b)": the labels under a
    figure's panels stand on one row, so they open one block, not two."""
    assert items(build("(a) left panel (b) right panel")) == []
    assert items(build("(a) (b)")) == []


# Properties


_STYLES = {
    "bullet": lambda n: "•",
    "dot": lambda n: f"{n}.",
    "paren": lambda n: f"({n})",
    "letter": lambda n: f"({'abcdefgh'[n - 1]})",
    "roman": lambda n: f"({['i', 'ii', 'iii', 'iv', 'v', 'vi'][n - 1]})",
}


@st.composite
def lists(draw: st.DrawFn) -> tuple[list[str], bool, list[str]]:
    """Rows of a list of 2 to 6 items in one marker style, set one block per item or all
    in one block, with the markers expected."""
    style = _STYLES[draw(st.sampled_from(sorted(_STYLES)))]
    count = draw(st.integers(2, 6))
    marks = [style(n) for n in range(1, count + 1)]
    words = st.sampled_from(["Alpha", "beta", "Gamma", "delta", "x = y"])
    rows = [f"{mark} {draw(words)} {n}" for n, mark in enumerate(marks)]
    return rows, draw(st.booleans()), marks


@given(lists())
def test_any_list_is_read_item_by_item(found: tuple[list[str], bool, list[str]]) -> None:
    rows, full, marks = found
    doc = build(*rows, full=full)
    assert items(doc) == list(zip(marks, rows, strict=True))


@st.composite
def caption_rows(draw: st.DrawFn) -> tuple[str, str | None]:
    """A row that opens with a table, figure or algorithm label, and the caption label
    expected (None for running text: no colon or full stop after the label)."""
    name = draw(st.sampled_from(["Figure", "Fig.", "Table", "Algorithm", "TABLE"]))
    number = draw(st.sampled_from(["1", "12", "A.2", "S3", "2.1"]))
    after = draw(st.sampled_from([":", ".", " shows", " gives the"]))
    label = f"{name} {number}"
    return f"{label}{after} the results of the run", label if after in ":." else None


@given(caption_rows())
def test_any_label_with_punctuation_opens_a_caption(found: tuple[str, str | None]) -> None:
    row, label = found
    doc = build(row)
    assert captions(doc) == ([(label, row)] if label else [])
