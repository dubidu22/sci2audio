"""Layout on made-up pages: display formulas as placeholders with their printed numbers
(Issue #21 step 3, PR D2, D-93; #34).

One column between x 70 and x 526 as in `test_layout`, body text in 10 point. Running text
fills the column; a display formula stands indented, set in a math font, its number at the
column's right edge.
"""

import itertools

from hypothesis import given
from hypothesis import strategies as st
from test_layout import GUTTER, LEFT, MIDDLE, RIGHT, line, short
from test_layout_graphics import build, listing, of, running

from sci2audio.core import BlockKind, Box, Document, Drawing, Picture, TextLine, TextRun

_ids = itertools.count()


def math(text: str, x0: float, y0: float, x1: float, size: float = 10.0) -> TextLine:
    """A piece of a formula, set in a math font."""
    return TextLine(f"m{next(_ids)}", (TextRun(text, "CMMI10", size),), Box(x0, y0, x1, y0 + size))


def number(text: str, y0: float, right: float = RIGHT) -> TextLine:
    """An equation number at the column's right edge."""
    return line(text, right - 6 * len(text), y0, right)


def paragraph(top: float, count: int) -> list[TextLine]:
    """Running text whose last line ends short."""
    lines = running(top, count)
    return [*lines[:-1], short(lines[-1])]


def formulas(doc: Document) -> list[tuple[str, str]]:
    return [(b.label, b.text) for b in of(doc, BlockKind.FORMULA)]


def paragraph_texts(doc: Document) -> list[str]:
    return [b.text for b in of(doc, BlockKind.PARAGRAPH)]


def joined(lines: list[TextLine]) -> str:
    return "\n".join(li.text for li in lines)


# Numbered formulas


def test_a_formula_with_its_number_apart_is_one_formula_block() -> None:
    before, after = paragraph(100, 4), paragraph(200, 3)
    doc = build([*before, math("x = y + z", 250, 160, 330), number("(1)", 160), *after])
    assert formulas(doc) == [("1", "x = y + z (1)")]
    assert paragraph_texts(doc) == [joined(before), joined(after)]


def test_a_number_at_the_end_of_an_indented_line_labels_it() -> None:
    """Extraction may keep the number in the formula's line."""
    doc = build([*paragraph(100, 4), math("a = b + c (2)", 200, 160, RIGHT), *paragraph(200, 3)])
    assert formulas(doc) == [("2", "a = b + c (2)")]


def test_a_formula_number_keeps_its_printed_form() -> None:
    doc = build([*paragraph(100, 4), math("a = b", 250, 160, 300), number("(16a)", 160)])
    assert formulas(doc) == [("16a", "a = b (16a)")]


def test_a_sum_with_its_limits_is_one_formula() -> None:
    """The limits above and below a sum, set smaller, are rows of the formula."""
    top = math("n", 262, 152, 268, size=7)
    main = math("S = Σ f(x)", 240, 160, 320)
    bottom = math("x∈X", 258, 171, 274, size=7)
    doc = build([*paragraph(100, 4), top, main, bottom, number("(3)", 160), *paragraph(200, 3)])
    assert formulas(doc) == [("3", "n\nS = Σ f(x) (3)\nx∈X")]


def test_two_rows_under_one_number_are_one_formula() -> None:
    rows = [math("a = b + c", 240, 160, 330), math("+ d + e", 250, 176, 320)]
    doc = build([*paragraph(100, 4), *rows, number("(4)", 168), *paragraph(210, 3)])
    assert formulas(doc) == [("4", "a = b + c\n(4)\n+ d + e")]


def test_aligned_rows_with_a_number_each_are_one_formula_each() -> None:
    """Eq. (16a) to (16f) in nowak: one block per printed number."""
    items = []
    for k, label in enumerate(["(5)", "(6)", "(7)"]):
        items += [math(f"x{k} = y{k}", 240, 160 + 16 * k, 320), number(label, 160 + 16 * k)]
    doc = build([*paragraph(100, 4), *items, *paragraph(230, 3)])
    assert formulas(doc) == [("5", "x0 = y0 (5)"), ("6", "x1 = y1 (6)"), ("7", "x2 = y2 (7)")]


def test_a_paragraph_holding_a_formula_is_cut_at_it() -> None:
    """The formula stands where it is printed: text before it, the formula, text after it,
    each line's text as found (D-93)."""
    before = [line(f"Running text, line {k}.", LEFT, 100 + 14 * k, RIGHT) for k in range(3)]
    formula = math("p(x) = q(x)", 250, 142, 330)
    after = [line(f"where text goes on, line {k}.", LEFT, 156 + 14 * k, RIGHT) for k in range(3)]
    doc = build([*before, formula, number("(8)", 142), *after])
    assert [b.kind for b in doc.blocks] == [
        BlockKind.PARAGRAPH,
        BlockKind.FORMULA,
        BlockKind.PARAGRAPH,
    ]
    assert [b.text for b in doc.blocks] == [joined(before), "p(x) = q(x) (8)", joined(after)]


def test_what_waited_for_a_paragraph_cut_at_a_formula_follows_its_own_page() -> None:
    """A figure at page 1's foot waits for the paragraph that runs on to page 2; the
    formula at page 1's foot cuts it again. The figure follows the formula, the end of
    page 1, not the text on page 2 (D-434, #196)."""
    before = [line(f"Running text, line {k}.", LEFT, 100 + 14 * k, RIGHT) for k in range(3)]
    formula = math("p(x) = q(x)", 250, 142, 330)
    figure = Picture("fig", Box(150, 300, 450, 400))
    after = [line(f"where text goes on, line {k}.", LEFT, 100 + 14 * k, RIGHT) for k in range(3)]
    doc = build([*before, formula, number("(8)", 142), figure], after)
    assert [(b.kind, b.text) for b in doc.blocks] == [
        (BlockKind.PARAGRAPH, joined(before)),
        (BlockKind.FORMULA, "p(x) = q(x) (8)"),
        (BlockKind.FIGURE, ""),
        (BlockKind.PARAGRAPH, joined(after)),
    ]
    assert doc.blocks[2].parts[0].item == "fig"


def test_a_fraction_bar_is_part_of_its_formula() -> None:
    bar = Drawing("bar", Box(250, 165, 290, 165.5))
    rows = [math("a", 266, 154, 274), math("b", 266, 167, 274), math("= c", 295, 160, 315)]
    doc = build([*paragraph(100, 3), *rows, bar, number("(9)", 160), *paragraph(200, 3)])
    found = of(doc, BlockKind.FORMULA)
    assert len(found) == 1
    assert "bar" in [part.item for part in found[0].parts]
    assert found[0].label == "9"


def test_a_picture_with_an_equation_number_is_that_formula() -> None:
    """arsiwalla's Eq. (4) is a drawn diagram: the formula holds it (D-93)."""
    picture = Picture("diagram", Box(200, 150, 380, 210))
    doc = build([*paragraph(100, 3), picture, number("(4)", 175), *paragraph(230, 3)])
    assert of(doc, BlockKind.FIGURE) == []
    found = of(doc, BlockKind.FORMULA)
    assert [b.label for b in found] == ["4"]
    assert "diagram" in [part.item for part in found[0].parts]


def test_a_row_piece_reaching_the_edge_is_part_of_its_formula() -> None:
    """nowak (14): the second row's last piece ends near the column's edge, but it starts a
    formula's indent in, so it is no running text (review of PR #61)."""
    rows = [math("P = I + P + P", 110, 160, 300), math("= I + P", 110, 176, 170)]
    edge = math("P n = (I - P) -1", 175, 176, RIGHT - 4)
    doc = build([*paragraph(100, 4), *rows, edge, number("(14)", 160), *paragraph(210, 3)])
    assert formulas(doc) == [("14", "P = I + P + P (14)\n= I + P P n = (I - P) -1")]


def test_inline_maths_on_a_row_of_running_text_stays_in_its_paragraph() -> None:
    """A piece of maths on the same row as running text, just below a formula, is no row
    of the formula (liu p3, the extrinsic OHE as a sum)."""
    above = paragraph(100, 4)
    formula = [math("a = b", 250, 157, 300), number("(7)", 157)]
    below = [line("The total is", LEFT, 173, 160), math("s = s sd + s sk", 165, 173, 260)]
    below += [line("as plotted.", 265, 173, RIGHT), line("And the text goes on.", LEFT, 187, 200)]
    doc = build([*above, *formula, *below])
    assert formulas(doc) == [("7", "a = b (7)")]
    assert paragraph_texts(doc)[-1] == (
        "The total is s = s sd + s sk as plotted.\nAnd the text goes on."
    )


def test_a_diagram_its_arrows_join_is_one_formula() -> None:
    """arsiwalla Eq. (2): the arrows reach from the numbered row to the rows above and
    below, and bring them into the formula (review of PR #61)."""
    top = [math("A", 285, 140, 295), math("X", 200, 152, 215), math("Y", 370, 152, 385)]
    middle = [math("R", 180, 190, 192), math("S", 390, 190, 402), number("(2)", 190)]
    bottom = [math("U", 200, 228, 215), math("V", 370, 228, 385), math("B", 285, 240, 295)]
    arrows = [
        Drawing("across", Box(220, 157, 365, 158)),
        Drawing("left", Box(207, 164, 208, 226)),
        Drawing("right", Box(377, 164, 378, 226)),
        Drawing("under", Box(220, 233, 365, 234)),
    ]
    page = [*paragraph(100, 2), *top, *middle, *bottom, *arrows, *paragraph(270, 3)]
    doc = build(page)
    assert formulas(doc) == [("2", "A\nX Y\nR S (2)\nU V\nB")]
    found = of(doc, BlockKind.FORMULA)[0]
    assert {"across", "left", "right", "under"} <= {part.item for part in found.parts}


def test_a_frame_does_not_bring_a_quotation_into_a_formula() -> None:
    """A framed box (a definition, a prompt) holding a formula and a centred quotation: the
    frame's rules are no connectors, and plain text never joins a formula by growth, so the
    quotation is still read (review of PR #61, round 2)."""
    running_text = [
        line(f"Running text, line {k}.", LEFT, y, RIGHT) for k, y in enumerate([180, 194, 208])
    ]
    quote = [
        line("To be, or not to be,", 220, 230, 330),
        line("that is the question.", 225, 244, 325),
    ]
    more = [
        line(f"More running text, line {k}.", LEFT, y, RIGHT) for k, y in enumerate([262, 276, 290])
    ]
    frame = [
        Drawing("top", Box(LEFT - 4, 150, RIGHT + 4, 150.5)),
        Drawing("bottom", Box(LEFT - 4, 310, RIGHT + 4, 310.5)),
        Drawing("left", Box(LEFT - 4, 150, LEFT - 3.5, 310.5)),
        Drawing("right", Box(RIGHT + 3.5, 150, RIGHT + 4, 310.5)),
    ]
    page = [*paragraph(100, 3), math("a = b + c", 250, 160, 330), number("(1)", 160)]
    doc = build([*page, *running_text, *quote, *more, *paragraph(340, 3), *frame])
    assert formulas(doc) == [("1", "a = b + c (1)")]
    texts = "\n".join(paragraph_texts(doc))
    assert "To be, or not to be," in texts
    assert "that is the question." in texts


def test_a_caption_after_a_formula_at_a_page_top_is_no_part_of_the_paragraph() -> None:
    """nowak p5: the paragraph runs on past the formula at the page's top; the algorithm
    under the formula, caption and lines, comes out on its own, and the paragraph goes on
    in the other column (paragraphs.py, review of PR #61)."""
    left_x1, right_x0 = MIDDLE - GUTTER / 2, MIDDLE + GUTTER / 2
    page1 = [line(f"Left column, line {k}.", LEFT, 100 + 14 * k, left_x1) for k in range(30)]
    page1 += [line(f"Right column, line {k}.", right_x0, 100 + 14 * k, RIGHT) for k in range(29)]
    page1 += [line("and the sentence goes on", right_x0, 100 + 14 * 29, RIGHT)]
    pieces = [math("π(i, X, k) = Σ", 130, 90, 290), math("ξ(Y, Z | X) · β(i, Y, j)", 296, 90, 420)]
    code = ["def Fast(w):", "π ← 0", "return π"]
    page2 = [*pieces, number("(16a)", 90), *listing(LEFT, 120, "Algorithm 3", "Fast", code)]
    page2 += [line(f"onto the next page {k}.", right_x0, 120 + 14 * k, RIGHT) for k in range(20)]
    doc = build(page1, page2)
    texts = [b.text for b in doc.blocks]
    running_on = next(b for b in doc.blocks if "and the sentence goes on" in b.text)
    assert "onto the next page 0." in running_on.text
    assert "Algorithm 3" not in running_on.text
    assert "π ← 0" not in running_on.text
    caption = next(b for b in doc.blocks if b.text.startswith("Algorithm 3"))
    assert caption.kind is BlockKind.CAPTION
    assert texts.index(running_on.text) < texts.index(caption.text)


# Not formulas


def test_running_text_ending_with_a_number_in_brackets_is_no_formula() -> None:
    lines = [
        *running(100, 3),
        line("so the result follows from (3)", LEFT, 142, RIGHT),
        *running(156, 2),
    ]
    doc = build(lines)
    assert formulas(doc) == []


def test_numbered_examples_at_the_left_edge_are_no_formulas() -> None:
    """hardt's language examples (1) to (4) stand at the left, the example after them."""
    items = []
    for k in range(3):
        items += [
            line(f"({k + 1})", LEFT, 160 + 16 * k, LEFT + 12),
            line(f"John left {k}.", LEFT + 30, 160 + 16 * k, 250),
        ]
    doc = build([*paragraph(100, 4), *items, *paragraph(230, 3)])
    assert formulas(doc) == []


def test_a_centred_math_line_without_a_number_is_an_unnumbered_formula() -> None:
    doc = build([*paragraph(100, 4), math("O → S → I", 250, 160, 330), *paragraph(200, 3)])
    assert formulas(doc) == [("", "O → S → I")]


def test_a_centred_line_of_words_is_no_formula() -> None:
    doc = build(
        [*paragraph(100, 4), line("To be or not to be.", 220, 160, 360), *paragraph(200, 3)]
    )
    assert formulas(doc) == []


# A formula across both columns (#34)


def test_a_formula_across_both_columns_is_read_once_between_them() -> None:
    """The formula's pieces leave no white wide enough for a gutter: they are one formula
    read across the page, and a paragraph runs on past it onto the next page (#34)."""
    left_x1, right_x0 = MIDDLE - GUTTER / 2, MIDDLE + GUTTER / 2
    page1 = [line(f"Left column, line {k}.", LEFT, 100 + 14 * k, left_x1) for k in range(30)]
    page1 += [line(f"Right column, line {k}.", right_x0, 100 + 14 * k, RIGHT) for k in range(29)]
    page1 += [line("and the sentence goes on", right_x0, 100 + 14 * 29, RIGHT)]
    pieces = [math("π(i, X, k) = Σ", 130, 90, 290), math("ξ(Y, Z | X) · β(i, Y, j)", 296, 90, 420)]
    page2 = [*pieces, number("(16a)", 90)]
    page2 += [line(f"onto the next page {k}.", LEFT, 130 + 14 * k, left_x1) for k in range(20)]
    page2 += [line(f"Right again, line {k}.", right_x0, 130 + 14 * k, RIGHT) for k in range(20)]
    doc = build(page1, page2)
    assert formulas(doc) == [("16a", "π(i, X, k) = Σ ξ(Y, Z | X) · β(i, Y, j) (16a)")]
    running_on = next(b for b in doc.blocks if "and the sentence goes on" in b.text)
    assert "onto the next page 0." in running_on.text
    texts = [b.text for b in doc.blocks]
    assert sum("Left column" in t for t in texts) >= 1
    assert all(t.count("16a") <= 1 for t in texts)


def test_a_formula_across_both_columns_mid_page_ends_the_paragraph_before_it() -> None:
    """Below its page's top the formula stands where it is printed: the text after it is a
    paragraph of its own, not read on before the formula (D-93)."""
    left_x1, right_x0 = MIDDLE - GUTTER / 2, MIDDLE + GUTTER / 2
    top = [line(f"Left top, line {k}.", LEFT, 100 + 14 * k, left_x1) for k in range(10)]
    top += [line(f"Right top, line {k}.", right_x0, 100 + 14 * k, RIGHT) for k in range(9)]
    top += [line("and the sentence goes on", right_x0, 100 + 14 * 9, RIGHT)]
    pieces = [math("π(i, X, k) = Σ", 130, 250, 290), math("ξ(Y, Z) · β(i, Y, j)", 296, 250, 420)]
    below = [line(f"after the formula {k}.", LEFT, 280 + 14 * k, left_x1) for k in range(10)]
    below += [line(f"Right below, line {k}.", right_x0, 280 + 14 * k, RIGHT) for k in range(10)]
    doc = build([*top, *pieces, number("(5)", 250), *below])
    texts = [b.text for b in doc.blocks]
    at = next(k for k, b in enumerate(doc.blocks) if b.kind is BlockKind.FORMULA)
    assert doc.blocks[at].label == "5"
    assert "and the sentence goes on" in texts[at - 1]
    assert texts[at + 1].startswith("after the formula 0.")
    assert not any("after the formula" in t for t in texts[:at])


# Properties


@st.composite
def numbered(draw: st.DrawFn) -> tuple[list, list[str], list[str]]:
    """A page of two paragraphs with one to three numbered formula rows between them: the
    items, the numbers expected, and the paragraphs' text."""
    labels = draw(
        st.lists(
            st.sampled_from(["1", "2", "12", "3b", "A.1", "S2"]),
            min_size=1,
            max_size=3,
            unique=True,
        )
    )
    words = st.sampled_from(
        [
            "x = y",
            "a + b",
            "Σ f(x)",
            "p(τ) = 1",
            "\N{GREEK SMALL LETTER BETA} \N{LESS-THAN OR EQUAL TO} \N{GREEK SMALL LETTER GAMMA}",
        ]
    )
    before = paragraph(100, draw(st.integers(2, 5)))
    top = 100 + 14 * len(before) + 16
    items = []
    for k, label in enumerate(labels):
        x0 = draw(st.integers(120, 300))
        items += [math(draw(words), x0, top + 16 * k, x0 + 60), number(f"({label})", top + 16 * k)]
    after = paragraph(top + 16 * len(labels) + 16, draw(st.integers(1, 4)))
    return [*before, *items, *after], labels, [joined(before), joined(after)]


@given(numbered())
def test_numbered_rows_between_paragraphs_are_one_formula_each(page: tuple) -> None:
    items, labels, texts = page
    doc = build(items)
    assert [b.label for b in of(doc, BlockKind.FORMULA)] == labels
    assert paragraph_texts(doc) == texts
