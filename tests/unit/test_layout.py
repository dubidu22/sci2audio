"""Layout on made-up pages: furniture, columns and reading order (Issue #21, step 1, D-67).

Pages are 600 x 800 points with body text in 10 point, set like a two-column paper between
x 70 and x 526 unless a test says otherwise.
"""

import itertools
from collections.abc import Callable

import pytest
from core_strategies import contents
from hypothesis import example, given
from hypothesis import strategies as st

from sci2audio.core import (
    Block,
    BlockKind,
    Box,
    Content,
    Document,
    Drawing,
    Metadata,
    Page,
    Part,
    Picture,
    Source,
    SourceFormat,
    TextLine,
    TextRun,
)
from sci2audio.layout import LayoutSettings, build_document
from sci2audio.layout.build import _in_page_order, columns_per_page
from sci2audio.layout.furniture import _is_stamp, _pages_near, _repeated, edges
from sci2audio.layout.order import Element, Reading, reading_order
from sci2audio.layout.split import kept

LEFT, RIGHT, GUTTER = 70.0, 526.0, 16.0
MIDDLE = (LEFT + RIGHT) / 2
_ids = itertools.count()


def line(
    text: str, x0: float, y0: float, x1: float, size: float = 10.0, height: float = 0
) -> TextLine:
    box = Box(x0, y0, x1, y0 + (height or size))
    return TextLine(f"l{next(_ids)}", (TextRun(text, "Times", size),), box)


def column(name: str, x0: float, x1: float, top: float, count: int) -> list[TextLine]:
    return [line(f"{name}{k}", x0, top + 14 * k, x1) for k in range(count)]


def two_columns(name: str, top: float, count: int) -> tuple[list[TextLine], list[TextLine]]:
    left = column(f"{name}-left-", LEFT, MIDDLE - GUTTER / 2, top, count)
    right = column(f"{name}-right-", MIDDLE + GUTTER / 2, RIGHT, top, count)
    return left, right


def roles(doc: Document) -> list[str]:
    """The role of each furniture block, in reading order."""
    return [b.role.value for b in doc.blocks if b.role]


def short(li: TextLine) -> TextLine:
    """The line ending halfway: the last line of a paragraph."""
    box = li.box or Box(0, 0, 0, 0)
    return line(li.text, box.x0, box.y0, (box.x0 + box.x1) / 2)


def body_copy(lines: list[TextLine]) -> list[TextLine]:
    """The same lines with fresh ids, for another page."""
    return [line(li.text, *(lambda b: (b.x0, b.y0, b.x1))(li.box)) for li in lines]


def interleaved(left: list[TextLine], right: list[TextLine]) -> list[TextLine]:
    """As a file may store them: across the page, row by row."""
    return [li for pair in zip(left, right, strict=True) for li in pair]


def content(*pages: list[TextLine], metadata: Metadata | None = None, **first: tuple) -> Content:
    """Pages with these lines; `first` adds pictures or drawings to page 1."""
    return Content(
        Source("test.pdf", SourceFormat.PDF),
        tuple(
            Page(n, tuple(lines), width=600, height=800, **(first if n == 1 else {}))
            for n, lines in enumerate(pages, start=1)
        ),
        metadata or Metadata(),
    )


def texts(doc: Document, kind: BlockKind | None = None) -> list[str]:
    """The printed lines of the blocks, in reading order (a paragraph holds several)."""
    return [
        line for b in doc.blocks if kind is None or b.kind is kind for line in b.text.split("\n")
    ]


def columns_of(doc: Document) -> list[int]:
    return columns_per_page(doc.content)


# Columns and reading order


def test_two_columns_read_left_column_then_right() -> None:
    left, right = two_columns("a", 100, 20)
    doc = build_document(content(interleaved(left, right)))
    assert texts(doc) == [li.text for li in left + right]
    assert columns_of(doc) == [2]


def test_wide_title_and_figure_cut_the_page_into_bands() -> None:
    title = line("A Title Across The Page", LEFT, 60, RIGHT, size=14)
    top_left, top_right = two_columns("top", 100, 10)
    top_right[-1] = short(top_right[-1])  # a paragraph ends above the figure
    bottom_left, bottom_right = two_columns("bottom", 440, 10)
    figure = Drawing("d1", Box(LEFT, 320, RIGHT, 420))
    lines = [title, *interleaved(top_left, top_right), *interleaved(bottom_left, bottom_right)]
    doc = build_document(content(lines, drawings=(figure,)))
    expected = [title.text, *(li.text for li in top_left + top_right), ""]
    expected += [li.text for li in bottom_left + bottom_right]
    assert texts(doc) == expected
    kinds = [b.kind for b in doc.blocks]
    assert kinds.index(BlockKind.FIGURE) == 2  # after the title and the paragraph above it


def test_a_centred_line_over_the_gutter_does_not_join_the_columns() -> None:
    authors = [line("Ann Author", 260, 60, 340), line("Some University", 250, 74, 350)]
    left, right = two_columns("body", 110, 20)
    doc = build_document(content([*authors, *interleaved(left, right)]))
    assert texts(doc) == [li.text for li in authors + left + right]


def test_lines_that_only_touch_the_gutter_stay_in_their_column() -> None:
    left, right = two_columns("a", 100, 20)
    left[3] = line("reaches into the gutter", LEFT, 100 + 14 * 3, MIDDLE - 2)
    right[5] = line("starts in the gutter", MIDDLE + 2, 100 + 14 * 5, RIGHT)
    doc = build_document(content(interleaved(left, right)))
    assert texts(doc) == [li.text for li in left + right]


def test_a_short_column_beside_a_long_one_is_read_after_it() -> None:
    """Few lines in the right column: the document's text area, found with a share of the
    lines left out, misses its edge, but the left column's lines still don't span the page."""
    left = column("left-", LEFT, MIDDLE - GUTTER / 2, 80, 33)
    ends = [443.5, RIGHT, RIGHT, 416, RIGHT, RIGHT, 416]
    right = [line(f"right-{k}", MIDDLE + GUTTER / 2, 80 + 14 * k, x1) for k, x1 in enumerate(ends)]
    doc = build_document(content(interleaved(left[:7], right) + left[7:]))
    assert texts(doc) == [li.text for li in left + right]


def test_a_gutter_that_begins_inside_a_column_keeps_its_long_lines_in_it() -> None:
    """The middle column holds three paragraphs of two lines, each indented and then short,
    as many as the crossings a gutter allows: so the strip to its left ends where the indented
    lines begin, and the strip to its right begins where the short lines end."""
    width = (RIGHT - LEFT - 2 * GUTTER) / 3
    x0s = [LEFT + k * (width + GUTTER) for k in range(3)]
    first, last = column("a-", x0s[0], x0s[0] + width, 80, 15), column("c-", x0s[2], RIGHT, 80, 15)
    middle = [
        line(f"b-{k}", x0s[1] + (12 if k % 2 == 0 else 0), 80 + 14 * k, x0s[1] + width / 2)
        if k % 2
        else line(f"b-{k}", x0s[1] + 12, 80 + 14 * k, x0s[1] + width)
        for k in range(6)
    ]
    doc = build_document(content(interleaved(middle, last[:6]) + first + last[6:]))
    assert texts(doc) == [li.text for li in first + middle + last]


def test_a_centred_heading_atop_a_short_column_is_read_in_its_column() -> None:
    """#679: the left column holds so few lines that the strip beside it, which a few lines
    may cross, opens where its short lines end, left of where its centred heading starts.
    The heading ends inside that strip, so it is still read first in its own column."""
    x1 = MIDDLE - GUTTER / 2
    quarter = (x1 - LEFT) / 4
    heading = line("Methods", LEFT + 1.2 * quarter, 80, x1 - 1.2 * quarter)
    body = [line(f"left-{k}", LEFT, 94 + 14 * k, LEFT + quarter if k % 2 else x1) for k in range(6)]
    right = column("right-", MIDDLE + GUTTER / 2, RIGHT, 80, 40)
    doc = build_document(content([heading, *body, *right]))
    assert texts(doc) == [li.text for li in [heading, *body, *right]]
    assert columns_of(doc) == [2]


def nested_columns_page() -> tuple[Content, list[str]]:
    """A two-column page whose left column holds, between running text above and below, a
    block of two short columns of its own; the lines stored across the page, row by row.
    In reading order: the left column's text above, the block's left column, its right
    column, the left column's text below, then the page's right column (#32, D-67)."""
    lx1, rx0 = MIDDLE - GUTTER / 2, MIDDLE + GUTTER / 2
    inner = (lx1 - LEFT - GUTTER) / 2
    above = column("above-", LEFT, lx1, 100, 6)
    block_left = column("block-left-", LEFT, LEFT + inner, 100 + 14 * 6, 8)
    block_right = column("block-right-", lx1 - inner, lx1, 100 + 14 * 6, 8)
    below = column("below-", LEFT, lx1, 100 + 14 * 14, 6)
    left = [*above, *interleaved(block_left, block_right), *below]
    right = column("right-", rx0, RIGHT, 100, len(left))
    page = [li for pair in zip(left, right, strict=True) for li in pair]
    order = [*above, *block_left, *block_right, *below, *right]
    return content(page), [li.text for li in order]


def test_two_columns_inside_a_column_are_read_one_after_the_other() -> None:
    """#32, D-67: the cut into bands and columns is tried again inside each column found."""
    page, expected = nested_columns_page()
    doc = build_document(page)
    assert texts(doc) == expected
    assert columns_of(doc) == [2]


def test_the_cut_inside_a_column_stops_at_the_depth_limit() -> None:
    """With `column_depth` at 1 only the page's own columns are cut: the block inside the
    left column is read row by row across its two columns, as before #32."""
    page, _ = nested_columns_page()
    doc = build_document(page, LayoutSettings(column_depth=1))
    found = texts(doc)
    assert found.index("block-right-0") < found.index("block-left-1")


def read_lines(
    lines: list[TextLine], settings: LayoutSettings | None = None, figures: tuple[Box, ...] = ()
) -> Reading:
    """The lines (and figures, as pictures) put in reading order as a page of the made-up
    document: text area from LEFT to RIGHT, body text in 10 point."""
    elements = [Element(li.box or Box(0, 0, 0, 0), li) for li in lines]
    elements += [Element(box, graphics=(Picture(f"p{k}", box),)) for k, box in enumerate(figures)]
    return reading_order(elements, RIGHT - LEFT, 10.0, settings or LayoutSettings())


def names(reading: Reading) -> list[str]:
    """The text of each element read, a formula's lines joined by " | "."""
    return [
        e.line.text if e.line else " | ".join(li.text for li in e.lines) for e in reading.ordered
    ]


def page_lines(page: Content) -> list[TextLine]:
    return list(page.pages[0].lines)


def test_inner_columns_count_beside_the_page_columns() -> None:
    """#866: the page has two columns; the left one is cut into two again, so three
    columns are read side by side at its widest. `columns` stays the page's own count."""
    page, _ = nested_columns_page()
    reading = read_lines(page_lines(page))
    assert (reading.columns, reading.nested) == (2, 3)
    assert columns_per_page(page) == [2]
    assert columns_per_page(page, nested=True) == [3]
    flat = read_lines(page_lines(page), LayoutSettings(column_depth=1))
    assert (flat.columns, flat.nested) == (2, 2)


def two_levels_page() -> tuple[list[TextLine], list[str], list[str]]:
    """A two-column page whose left column holds a block of two columns (level 2), the
    left of which holds a block of two columns again (level 3), each block between running
    text of its column; the lines stored row by row across the page. Returns the lines, the
    left column's lines read with level 3 cut, and read with level 3 row by row (#872)."""
    lx1, rx0 = MIDDLE - GUTTER / 2, MIDDLE + GUTTER / 2
    two = (lx1 - LEFT - GUTTER) / 2  # a level-2 column
    three = (two - GUTTER) / 2  # a level-3 column
    above = column("page-above-", LEFT, lx1, 100, 6)
    top = 100 + 14 * 6
    upper = column("two-left-above-", LEFT, LEFT + two, top, 5)
    deep_left = column("three-l-", LEFT, LEFT + three, top + 14 * 5, 6)
    deep_right = column("three-r-", LEFT + two - three, LEFT + two, top + 14 * 5, 6)
    lower = column("two-left-below-", LEFT, LEFT + two, top + 14 * 11, 5)
    two_right = column("two-right-", lx1 - two, lx1, top, 16)
    below = column("page-below-", LEFT, lx1, top + 14 * 16, 6)
    right = column("right-", rx0, RIGHT, 100, 28)
    lines = sorted(
        [*above, *upper, *deep_left, *deep_right, *lower, *two_right, *below, *right],
        key=lambda li: (li.box.y0, li.box.x0) if li.box else (0, 0),
    )
    cut = [*above, *upper, *deep_left, *deep_right, *lower, *two_right, *below]
    rows = [*above, *upper, *interleaved(deep_left, deep_right), *lower, *two_right, *below]
    return lines, [li.text for li in cut], [li.text for li in rows]


def test_the_depth_limit_counts_down_at_each_level() -> None:
    """#872: under `column_depth` 2 the block inside the left column is read one column
    after the other, and the block inside its left column, a level further, row by row;
    under 3 that one is cut too."""
    lines, cut, rows = two_levels_page()
    right = [li.text for li in lines if li.text.startswith("right-")]
    assert names(read_lines(lines, LayoutSettings(column_depth=2))) == [*rows, *right]
    assert names(read_lines(lines, LayoutSettings(column_depth=3))) == [*cut, *right]


def test_an_element_in_an_inner_column_takes_its_gutters_as_sides() -> None:
    """#872: in the block inside the left column, a line of the block's left column has the
    block's gutter on its right, and one of its right column has that gutter on its left and
    the page's gutter on its right; the page's edge stays None."""
    page, _ = nested_columns_page()
    lines = page_lines(page)
    reading = read_lines(lines)
    lx1, rx0 = MIDDLE - GUTTER / 2, MIDDLE + GUTTER / 2
    inner = (lx1 - LEFT - GUTTER) / 2
    sides = {e.line.text: reading.sides[id(e)] for e in reading.ordered if e.line}
    assert sides["block-left-3"] == (None, LEFT + inner)
    assert sides["block-right-3"] == (lx1 - inner, lx1)
    assert sides["above-0"] == (None, lx1)
    assert sides["right-0"] == (rx0, None)


def test_a_formula_across_an_inner_gutter_is_one_element() -> None:
    """#872: a display formula in the block inside the left column runs across the block's
    gutter to its number at the column's right edge: it is read as one element between the
    block's rows above and below it, not as a line cutting the block and a number in the
    block's right column."""
    lx1 = MIDDLE - GUTTER / 2
    inner = (lx1 - LEFT - GUTTER) / 2
    above = column("above-", LEFT, lx1, 100, 6)
    top = 100 + 14 * 6
    block_left = column("block-left-", LEFT, LEFT + inner, top, 8)
    block_right = column("block-right-", lx1 - inner, lx1, top, 8)
    formula = [
        line("x = a + b", LEFT + 30, top + 14 * 8, LEFT + 140),
        line("(1)", lx1 - 14, top + 14 * 8, lx1),
    ]
    lower_left = column("lower-left-", LEFT, LEFT + inner, top + 14 * 9, 8)
    lower_right = column("lower-right-", lx1 - inner, lx1, top + 14 * 9, 8)
    below = column("below-", LEFT, lx1, top + 14 * 17, 6)
    left = [*above, *interleaved(block_left, block_right), *formula]
    left += [*interleaved(lower_left, lower_right), *below]
    right = column("right-", MIDDLE + GUTTER / 2, RIGHT, 100, 30)
    reading = read_lines([*left, *right])
    expected = [li.text for li in [*above, *block_left, *block_right]]
    expected += ["(1) | x = a + b"]
    expected += [li.text for li in [*lower_left, *lower_right, *below, *right]]
    assert names(reading) == expected


def test_a_figure_in_an_inner_column_does_not_make_its_edge_ragged() -> None:
    """#872: only lines judge whether a block's columns are running text: a figure in the
    block's left column reaching out past its lines leaves it a column."""
    page, expected = nested_columns_page()
    lines = page_lines(page)
    shifted = [
        line(li.text, li.box.x0 + 10, li.box.y0, li.box.x1)
        if li.text.startswith("block-left-") and li.box
        else li
        for li in lines
    ]
    gap = 100 + 14 * 9 + 10  # between two of the block's rows
    reading = read_lines(shifted, figures=(Box(LEFT, gap + 0.5, LEFT + 60, gap + 3.5),))
    found = [n for n in names(reading) if n]
    assert found == expected


def test_a_table_inside_a_column_is_still_read_row_by_row() -> None:
    """#32: a gutter between a table's cells inside a column (as in Hardt's Table 1) does
    not cut it, as the cells leave a ragged edge; only columns of running text are cut."""
    lx1, rx0 = MIDDLE - GUTTER / 2, MIDDLE + GUTTER / 2
    above = column("above-", LEFT, lx1, 100, 6)
    rows = []
    for k, (label, cell) in enumerate(((50, 40), (53, 96), (20, 63), (48, 79), (56, 99), (30, 57))):
        y = 100 + 14 * (6 + k)
        rows += [
            line(f"label-{k}", LEFT, y, LEFT + label),
            line(f"cell-{k}", LEFT + 75, y, LEFT + 75 + cell),
        ]
    below = column("below-", LEFT, lx1, 100 + 14 * 12, 6)
    left = [*above, *rows, *below]
    right = column("right-", rx0, RIGHT, 100, len(left))
    doc = build_document(content([*left, *right]))
    words = " ".join(texts(doc)).split()  # a row's cells may be joined into one line
    assert words == [li.text for li in [*above, *rows, *below, *right]]


def test_a_page_background_or_a_frame_does_not_cut_the_columns() -> None:
    for box in (Box(0, 0, 600, 800), Box(60, 90, 536, 520)):
        left, right = two_columns("a", 100, 30)
        doc = build_document(content(interleaved(left, right), drawings=(Drawing("d1", box),)))
        assert texts(doc) == ["", *(li.text for li in left + right)]  # the frame, then its text


def test_a_table_does_not_make_a_page_two_columns() -> None:
    left, right = two_columns("text", 100, 20)
    cells = [
        line(f"cell {row} {col}", x, 100 + 14 * row, x + 50)
        for row in range(12)
        for col, x in enumerate((100, 230, 330, 430))
    ]
    doc = build_document(content(interleaved(left, right), cells))
    assert columns_of(doc) == [2, 1]


def test_a_page_with_text_in_one_column_follows_the_document() -> None:
    left, right = two_columns("text", 100, 20)
    end = column("end-", LEFT, MIDDLE - GUTTER / 2, 100, 8)
    doc = build_document(content(interleaved(left, right), end))
    assert columns_of(doc) == [2, 2]


def diagram_page(caption: str | None, body: list[TextLine]) -> Content:
    """A diagram in a frame from y 60 to 300 whose labels stand in three columns (as on
    PrivacyScore p3, #238), its caption 10 pt under the frame if any, then the body from
    y 340."""
    labels = [  # set smaller than the body; two of three rows fill their column
        line(
            f"label {col}-{row} of the diagram", x0, 70 + 14 * row, x0 + (130 if row % 3 else 90), 8
        )
        for row in range(12)
        for col, x0 in enumerate((LEFT + 6, 233, 386))
    ]
    under = [line(caption, LEFT, 310, 250)] if caption else []
    return content(
        [*labels, *under, *body], drawings=(Drawing("frame", Box(LEFT, 60, RIGHT, 300)),)
    )


def test_text_inside_a_captioned_figure_is_not_counted_as_columns() -> None:
    """#238: the labels of a framed, captioned diagram are read inside its figure, and the
    page counts the columns of its body only: two under the diagram, or one. Without a
    caption no figure holds the labels, and their three columns count."""
    left, right = two_columns("body", 340, 25)
    two = build_document(diagram_page("Figure 1: The diagram.", interleaved(left, right)))
    assert columns_of(two) == [2]
    caption = next(b for b in two.blocks if b.kind is BlockKind.CAPTION)
    assert caption.describes is not None
    assert "label 0-0 of the diagram" in two.blocks[caption.describes].text
    one = build_document(diagram_page("Figure 1: The diagram.", column("b", LEFT, RIGHT, 340, 25)))
    assert columns_of(one) == [1]
    uncaptioned = build_document(diagram_page(None, column("b", LEFT, RIGHT, 340, 25)))
    assert columns_of(uncaptioned) == [3]
    # nor do the labels count for the share of the page's text a band of columns must hold:
    # six rows of two columns, a sixth of the labels' letters, still make the page two
    left, right = two_columns("body", 340, 6)
    short = build_document(diagram_page("Figure 1: The diagram.", interleaved(left, right)))
    assert columns_of(short) == [2]


def framed_in_a_column(top: int, cells: bool) -> Content:
    """`top` lines of text across the page, then a framed diagram in the left column (12
    labels of 8 pt, its caption and two lines under it) and text beside it: two short
    columns of running text, or (`cells`) a table's cells, most of whose letters stand in
    lines that leave white."""
    lx1, rx0 = MIDDLE - GUTTER / 2, MIDDLE + GUTTER / 2
    opening = [
        line(
            f"running text across the page, line {k} of the opening part", LEFT, 100 + 14 * k, RIGHT
        )
        for k in range(top)
    ]
    y = 100 + 14 * top + 20
    frame = Box(LEFT, y, lx1, y + 178)
    labels = [
        line(f"label {k} of the diagram, set long", LEFT + 4, y + 5 + 14 * k, lx1 - 4, 8)
        for k in range(12)
    ]
    caption = line("Figure 1: The diagram.", LEFT, frame.y1 + 8, lx1)
    if cells:
        under = [
            line(f"a short cell {k} of the table here", LEFT, frame.y1 + 30 + 14 * k, LEFT + 90)
            for k in range(4)
        ]
        beside = [
            line(f"a short cell {k} of the table there", rx0, y + 14 * k, rx0 + 110)
            if k % 3
            else line(f"x{k}", rx0, y + 14 * k, RIGHT)
            for k in range(10)
        ]
    else:
        under = column("left-", LEFT, lx1, frame.y1 + 30, 2)
        beside = column("right-", rx0, RIGHT, y, 8)
    lines = [*opening, *labels, caption, *under, *beside]
    return content(lines, drawings=(Drawing("frame", frame),))


def test_a_captioned_figure_s_labels_count_neither_for_the_share_nor_for_the_fill() -> None:
    """#238, each half of a band's count on its own: beside a framed diagram in the left
    column, two short columns of text hold far less than a fifth of the page's text (with
    the labels' letters they would hold more); and table cells beside it hold enough text
    but leave white (the labels would fill their column). One column both times."""
    assert columns_per_page(framed_in_a_column(20, cells=False)) == [1]
    assert columns_per_page(framed_in_a_column(6, cells=True)) == [1]


def test_a_captioned_table_s_cells_still_count_as_columns_if_they_fill_them() -> None:
    """#238 leaves out the text of figures only: a table's cells are judged as before, by
    the share of letters in lines that fill their column, so cells set like the diagram's
    labels, under a table's caption, make three columns."""
    body = column("b", LEFT, RIGHT, 340, 25)
    assert columns_per_page(diagram_page("Table 1: The results.", body)) == [3]


def test_the_figures_whose_text_is_not_counted_are_found_with_the_settings_given() -> None:
    """The figures are found with the settings passed in: with `caption_reach` at 1 em the
    caption 10 pt under the frame names nothing, and the labels' columns count."""
    body = column("b", LEFT, RIGHT, 340, 25)
    page = diagram_page("Figure 1: The diagram.", body)
    assert columns_per_page(page) == [1]
    assert columns_per_page(page, LayoutSettings(caption_reach=1.0)) == [3]


def test_items_without_a_position_follow_in_stored_order() -> None:
    boxless = [TextLine(f"x{k}", (TextRun(f"loose {k}"),)) for k in range(3)]
    placed = line("placed", LEFT, 100, RIGHT)
    doc = build_document(
        content([boxless[2], placed, boxless[0], boxless[1]], pictures=(Picture("p1"),))
    )
    assert texts(doc) == ["placed", "loose 2", "loose 0", "loose 1", ""]
    assert doc.blocks[-1].kind is BlockKind.FIGURE


def test_language_comes_from_settings_then_file_then_english() -> None:
    lines = [line("text", LEFT, 100, RIGHT)]
    file_says = content(lines, metadata=Metadata(language="en-GB"))
    assert build_document(file_says, LayoutSettings(language="de")).language == "de"
    assert build_document(file_says).language == "en-GB"
    assert build_document(content(lines)).language == "en"


# Furniture


def test_running_heads_and_page_numbers_are_furniture_read_at_their_place() -> None:
    pages = []
    for number in (1, 2, 3):
        body = column(f"p{number}-", LEFT, RIGHT, 100, 10)
        body[-1] = short(body[-1])  # the page's last paragraph ends on it
        if number == 2:
            body.append(line("Journal of Tests 2026", LEFT, 300, 200))  # quoted in the text
        pages.append(
            [*body, line(str(number), 295, 770, 305), line("Journal of Tests 2026", 200, 30, 400)]
        )
    doc = build_document(content(*pages))
    assert texts(doc, BlockKind.FURNITURE) == [
        *("Journal of Tests 2026", "1"),
        *("Journal of Tests 2026", "2"),
        *("Journal of Tests 2026", "3"),
    ]
    assert "Journal of Tests 2026" in texts(doc, BlockKind.PARAGRAPH)
    assert texts(doc)[:2] == ["Journal of Tests 2026", "p1-0"]  # the head before the text
    assert texts(doc)[11] == "1"  # the page number after it
    assert roles(doc) == ["running-head", "page-number"] * 3
    assert doc.page_labels == ("1", "2", "3")


def test_chapter_headings_and_a_continued_table_header_are_not_running_heads() -> None:
    chapters = [
        [line(f"Chapter {n}", LEFT, 40, 200, size=16), *column(f"c{n}-", LEFT, RIGHT, 70, 40)]
        for n in (1, 2, 3)
    ]
    tables = [
        [line("Model Accuracy F1", LEFT, 40, 300), *column(f"t{n}-", LEFT, 300, 54, 30)]
        for n in (4, 5)
    ]
    doc = build_document(content(*chapters, *tables))
    assert texts(doc, BlockKind.FURNITURE) == []


def page_with_head(number: int, head: str | None, y: float = 40, size: float = 10.0) -> list:
    """A page of body text from y 100, under a head at height `y` (none if `head` is None)."""
    body = column(f"p{number}-", LEFT, RIGHT, 100, 30)
    return body if head is None else [line(head, LEFT, y, 300, size=size), *body]


def head_roles(doc: Document) -> list[str]:
    return [b.text for b in doc.blocks if b.role and b.role.value == "running-head"]


def test_numbered_algorithms_at_the_top_of_two_pages_are_not_running_heads() -> None:
    """#33: body size, 1 em of white below, the same shape but not the same text (D-322)."""
    heads = {3: "Algorithm 1", 5: "Algorithm 2"}
    doc = build_document(content(*(page_with_head(n, heads.get(n), y=60) for n in range(1, 7))))
    assert texts(doc, BlockKind.FURNITURE) == []
    assert {"Algorithm 1", "Algorithm 2"} <= set(texts(doc))


def test_a_table_header_repeated_on_two_pages_without_a_rule_is_not_a_running_head() -> None:
    """#33: the same text on 2 of 6 pages, 1.2 em of white below: not most of the document."""
    pages = [page_with_head(n, None) for n in range(1, 7)]
    for n in (2, 3):
        rows = column(f"t{n}-", LEFT, 300, 62, 30)
        pages[n - 1] = [line("Model Accuracy F1", LEFT, 40, 300), *rows]
    doc = build_document(content(*pages))
    assert texts(doc, BlockKind.FURNITURE) == []
    assert texts(doc).count("Model Accuracy F1") == 2


def test_body_size_heads_that_alternate_by_page_are_running_heads() -> None:
    """Author on even pages, title on odd pages from page 2: one place, 6 of 7 pages (D-322)."""
    heads = {
        n: "A. Author and B. Author" if n % 2 == 0 else "A Title of Tests" for n in range(2, 8)
    }
    doc = build_document(content(*(page_with_head(n, heads.get(n)) for n in range(1, 8))))
    assert head_roles(doc) == [heads[n] for n in range(2, 8)]


def test_the_same_line_on_every_page_close_to_the_text_or_larger_is_not_a_running_head() -> None:
    """The same words on 4 of 4 pages, but 4 pt above the body (not apart), or apart but set
    larger than `head_size` times the body: text, as before #33."""
    close = [
        [line("Tests in Print", LEFT, 64, 300), *column(f"p{n}-", LEFT, RIGHT, 78, 30)]
        for n in range(4)
    ]
    large = [page_with_head(n, "Tests in Print", size=12) for n in range(4)]
    for pages in (close, large):
        assert texts(build_document(content(*pages)), BlockKind.FURNITURE) == []


def test_a_body_size_head_needs_head_pages_but_a_smaller_one_does_not() -> None:
    """Two pages are too few for a body-size head (D-324); a smaller head keeps the shape rule
    on `repeat_pages` pages (D-326)."""
    body = build_document(content(*(page_with_head(n, "Tests in Print") for n in (1, 2))))
    assert texts(body, BlockKind.FURNITURE) == []
    small = build_document(content(*(page_with_head(n, "Tests in Print", size=8) for n in (1, 2))))
    assert head_roles(small) == ["Tests in Print"] * 2


def header_page(number: int, cells: tuple[tuple[str, float, float], ...], head: bool) -> list:
    """A page with a body-size head at y 40 (if `head`) and a row of table-header cells at
    y 62, 1.2 em below the head and 1.2 em above the body (#149)."""
    body = column(f"p{number}-", LEFT, RIGHT, 84, 30)
    header = [line(text, x0, 62, x1) for text, x0, x1 in cells]
    return [*([line("Tests in Print", LEFT, 40, 300)] if head else []), *header, *body]


def test_a_continued_table_header_under_a_real_head_is_not_a_running_head() -> None:
    """The pooled count is per height: a real head on 6 of 6 pages at y 40 does not lend its
    pages to a header repeated at y 62 on 2 of them (#149)."""
    cells = (("Model Accuracy F1", LEFT, 300),)
    pages = [header_page(n, cells if n in (2, 3) else (), head=True) for n in range(1, 7)]
    doc = build_document(content(*pages))
    assert head_roles(doc) == ["Tests in Print"] * 6
    assert texts(doc).count("Model Accuracy F1") == 2


def test_a_table_header_in_two_cells_on_two_pages_is_not_a_running_head() -> None:
    """The pooled count counts pages, not lines: two cells on each of 2 of 6 pages are 4 lines
    but 2 pages (#149)."""
    cells = (("Model", LEFT, 150), ("Accuracy F1", 300, 450))
    pages = [header_page(n, cells if n in (2, 3) else (), head=False) for n in range(1, 7)]
    doc = build_document(content(*pages))
    assert texts(doc, BlockKind.FURNITURE) == []


def test_a_smaller_head_does_not_lend_its_pages_to_a_body_size_line() -> None:
    """A small head on 6 of 6 pages and a body-size header on 2 of them, on the same row: the
    small head is a running head by its own rule; the header is text (#149)."""
    pages = [
        [
            line("Preprint", LEFT, 40, 150, size=8),
            *([line("Model Accuracy F1", 350, 40, 500)] if n in (2, 3) else []),
            *column(f"p{n}-", LEFT, RIGHT, 100, 30),
        ]
        for n in range(1, 7)
    ]
    doc = build_document(content(*pages))
    assert head_roles(doc) == ["Preprint"] * 6
    assert texts(doc).count("Model Accuracy F1") == 2


def test_a_body_size_head_needs_head_share_of_the_pages() -> None:
    """On 4 of 8 pages a body-size head is furniture, on 3 of 8 it is text (D-324)."""
    for count, expected in ((4, 4), (3, 0)):
        pages = [
            page_with_head(n, "Tests in Print" if n > 8 - count else None) for n in range(1, 9)
        ]
        assert len(head_roles(build_document(content(*pages)))) == expected
    settings = LayoutSettings(head_share=0.3)  # the share is a setting
    pages = [page_with_head(n, "Tests in Print" if n > 5 else None) for n in range(1, 9)]
    assert len(head_roles(build_document(content(*pages), settings))) == 3


# Running heads in a small type area (#235, D-502 to D-505): the LNI template sets its text
# 17 % down Letter paper, so its heads stand below the paper's top `edge_band`.

TYPE_TOP = 136.0  # where the type area's first row stands: 0.17 of the page, as in LNI


def small_area_page(number: int, head: str | None) -> list:
    """A page whose printing starts at `TYPE_TOP`: a 9 point head (if any), then body text
    from 20 points lower, its last paragraph ending on the page."""
    body = column(f"p{number}-", LEFT, RIGHT, TYPE_TOP + 20, 30)
    body[-1] = short(body[-1])
    return body if head is None else [line(head, LEFT, TYPE_TOP, 300, size=9), *body]


def lni_heads(pages: int) -> dict[int, str]:
    """Author with the page number on even pages, title with it on odd pages from page 2."""
    return {
        n: f"{n} A. Author and B. Author" if n % 2 == 0 else f"A Title of Tests {n}"
        for n in range(2, pages + 1)
    }


def test_heads_in_a_small_type_area_are_running_heads() -> None:
    """Nothing in the paper's top band on any page: the type area's first row counts as the
    top band (D-502), and a head holding its page number is one running head (D-505)."""
    heads = lni_heads(5)
    doc = build_document(content(*(small_area_page(n, heads.get(n)) for n in range(1, 6))))
    assert head_roles(doc) == [heads[n] for n in range(2, 6)]
    assert doc.page_labels == ("", "2", "3", "4", "5")  # printed in the heads (#535)
    page_2 = texts(doc).index(heads[2])
    assert texts(doc)[page_2 + 1] == "p2-0"  # the head comes first on its page (D-504)


def test_anything_in_the_paper_top_band_keeps_the_heads_of_a_small_type_area_as_text() -> None:
    """One line, or one picture, in the top `edge_band` of one page: the band stays the
    paper's (D-502), as for the JOSS papers with their logo."""
    heads = lni_heads(5)
    pages = [small_area_page(n, heads.get(n)) for n in range(1, 6)]
    with_line = [[line("Preprint", LEFT, 40, 150), *pages[0]], *pages[1:]]
    with_logo = content(*pages, pictures=(Picture("logo", Box(LEFT, 30, 150, 70)),))
    for doc in (build_document(content(*with_line)), build_document(with_logo)):
        assert head_roles(doc) == []
        assert set(heads.values()) <= set(texts(doc, BlockKind.PARAGRAPH))


def test_only_the_first_row_of_a_small_type_area_joins_the_top_band() -> None:
    """A lone number one row below the first is no page number, even on a one-page
    document; in the first row it is one (D-502: not the whole band moved down)."""
    first_row = line("Running text set from the first row on.", LEFT, TYPE_TOP, RIGHT)
    below = [first_row, line("4", 295, TYPE_TOP + 16, 305), *column("p", LEFT, RIGHT, 170, 30)]
    first = [line("4", 295, TYPE_TOP, 305), *column("p", LEFT, RIGHT, TYPE_TOP + 20, 30)]
    assert roles(build_document(content(below))) == []
    assert roles(build_document(content(first))) == ["page-number"]


def test_the_bottom_band_stays_the_paper_s_in_a_small_type_area() -> None:
    """D-503: a small footnote line repeated at the foot of a small type area is text."""
    pages = [
        [*small_area_page(n, None), line("Az. 5 U 38/10.", LEFT, 640, 200, size=8)]
        for n in range(1, 4)
    ]
    assert roles(build_document(content(*pages))) == []


# Heads set smaller than the body (#156): the shape on two pages is not enough. Lines apart
# from the body that repeat their shape at one height on most pages are heads (coverage);
# in a short document, one apart from the body repeating word for word on half the pages
# is one too; a caption label never is.

SMALL = 9.0  # points: 0.9 of the body, below `small` (0.95)


def small_header_page(number: int, below: float) -> list:
    """A page whose table goes on from the page before: a small header at y 40, its first
    row `below` points under it, the rows set like body text."""
    header = line("Model Accuracy F1", LEFT, 40, 300, size=SMALL)
    return [header, *column(f"t{number}-", LEFT, 300, 40 + SMALL + below, 30)]


def test_a_small_continued_table_header_on_two_pages_is_not_a_running_head() -> None:
    """#156, first case: set at 0.9 of the body on 2 of 6 pages, its first row 2 pt below."""
    pages = [page_with_head(n, None) for n in range(1, 7)]
    for n in (2, 3):
        pages[n - 1] = small_header_page(n, below=2)
    doc = build_document(content(*pages))
    assert texts(doc, BlockKind.FURNITURE) == []
    assert texts(doc).count("Model Accuracy F1") == 2


def test_small_algorithm_captions_at_the_top_of_two_pages_are_not_running_heads() -> None:
    """#156, second case: "Algorithm 1" and "Algorithm 2" at 0.9 of the body, apart from the
    text, on two pages; on pages 3 and 4 their numbers even follow the page's."""
    for numbers in ((3, 5), (3, 4)):
        heads = dict(zip(numbers, ("Algorithm 1", "Algorithm 2"), strict=True))
        pages = [page_with_head(n, heads.get(n), y=60, size=SMALL) for n in range(1, 7)]
        doc = build_document(content(*pages))
        assert texts(doc, BlockKind.FURNITURE) == []
        assert {"Algorithm 1", "Algorithm 2"} <= set(texts(doc))


def test_small_heads_that_alternate_by_page_are_running_heads_where_one_is_close() -> None:
    """Author on even pages, title on odd ones, at 0.9 of the body on 6 of 7 pages; on page
    5 the text starts right under the head: it is still one, the other pages lend it theirs
    (coverage, as PrivacyScore p3 to p13)."""
    heads = {n: "A. Author and B. Author" if n % 2 == 0 else "A Title" for n in range(2, 8)}
    pages = [page_with_head(n, heads.get(n), size=SMALL) for n in range(1, 8)]
    pages[4] = [line(heads[5], LEFT, 40, 300, size=SMALL), *column("p5-", LEFT, RIGHT, 51, 30)]
    doc = build_document(content(*pages))
    assert head_roles(doc) == [heads[n] for n in range(2, 8)]


def test_a_small_continued_table_header_on_most_pages_close_to_its_rows_is_text() -> None:
    """Only lines apart from the body lend their pages: a long table's small header on 4 of 6
    pages, its rows 2 pt below, is not on most pages by that count."""
    pages = [small_header_page(n, 2) if n <= 4 else page_with_head(n, None) for n in range(1, 7)]
    doc = build_document(content(*pages))
    assert texts(doc, BlockKind.FURNITURE) == []
    assert texts(doc).count("Model Accuracy F1") == 4


def test_a_small_header_below_a_small_head_does_not_borrow_its_pages() -> None:
    """Coverage counts per height: a small head on 6 of 6 pages at y 40 and, apart from the
    text, a small table header at y 62 on 2 of them."""
    pages = []
    for n in range(1, 7):
        header = [line("Model Accuracy F1", LEFT, 62, 300, size=SMALL)] if n in (2, 3) else []
        pages.append(
            [
                line("Preprint", LEFT, 40, 150, size=SMALL),
                *header,
                *column(f"p{n}-", LEFT, RIGHT, 84, 30),
            ]
        )
    doc = build_document(content(*pages))
    assert head_roles(doc) == ["Preprint"] * 6
    assert texts(doc).count("Model Accuracy F1") == 2


def test_a_small_header_apart_from_its_rows_on_three_of_ten_pages_is_text() -> None:
    """Coverage needs `head_pages` pages and `head_share` of the document's: 3 of 10 pages
    are the first but not the second (#620)."""
    pages = [page_with_head(n, None) for n in range(1, 11)]
    for n in (2, 3, 4):
        pages[n - 1] = small_header_page(n, below=12)
    doc = build_document(content(*pages))
    assert texts(doc, BlockKind.FURNITURE) == []
    assert texts(doc).count("Model Accuracy F1") == 3


def test_small_heads_a_little_higher_or_lower_on_each_page_are_running_heads() -> None:
    """Heads 2 pt higher or lower from page to page, within `head_drift` (0.5 em, 5 pt):
    through coverage (author and title alternating on 6 of 7 pages), and through a short
    document's rule (the same head on 2 of 2 pages)."""
    heads = {n: "A. Author and B. Author" if n % 2 == 0 else "A Title" for n in range(2, 8)}
    pages = [page_with_head(n, heads.get(n), y=40 + 2 * (n % 3), size=SMALL) for n in range(1, 8)]
    assert head_roles(build_document(content(*pages))) == [heads[n] for n in range(2, 8)]
    pair = [page_with_head(n, "Tests in Print", y=38 + 2 * n, size=SMALL) for n in (1, 2)]
    assert head_roles(build_document(content(*pair))) == ["Tests in Print"] * 2


def test_a_small_line_listed_before_the_small_head_of_its_page_does_not_hide_it() -> None:
    """A file may list a small line in the middle of the page (a table cell) before the
    page's small head: the head is still found."""
    pages = [
        [line("n = 12", LEFT, 520, 120, size=SMALL), *page_with_head(n, "Tests in Print", size=8)]
        for n in (1, 2)
    ]
    assert head_roles(build_document(content(*pages))) == ["Tests in Print"] * 2


def test_an_edge_line_at_exactly_small_times_the_body_is_judged_as_body_size() -> None:
    """At `small` (0.95) times the body a line is body size: such a head on 2 of 2 pages is
    on too few (`head_pages`); a hair smaller it is a short document's small head."""
    at = [page_with_head(n, "Tests in Print", size=9.5) for n in (1, 2)]
    assert texts(build_document(content(*at)), BlockKind.FURNITURE) == []
    below = [page_with_head(n, "Tests in Print", size=9.4) for n in (1, 2)]
    assert head_roles(build_document(content(*below))) == ["Tests in Print"] * 2


heights = st.integers(0, 20).map(float)  # on a grid, so places exactly `drift` apart occur


@given(
    st.lists(st.tuples(st.integers(1, 6), heights), max_size=30),
    st.lists(heights, max_size=12),
    st.sampled_from([0.0, 0.5, 5.0]),
)
@example([(1, 0.0), (1, 1.0)], [5.0, 6.0], 5.0)  # two places of one page, one leaves
@example([(1, 0.0)], [10.0, 0.0], 0.5)  # heights asked for out of order
@example([(1, 5.0), (2, 0.0)], [0.0, 5.0], 5.0)  # exactly `drift` apart, both ways
def test_pages_near_counts_the_pages_as_repeated_does_for_each_height(
    places: list[tuple[int, float]], wanted: list[float], drift: float
) -> None:
    assert _pages_near(places, wanted, drift) == [_repeated(places, y, drift) for y in wanted]


def test_a_short_document_s_small_head_needs_white_below_it() -> None:
    """Two of two pages: a small head apart from the text is a running head (word for word
    on half the pages and more, D-326); the same head 2 pt above the text is not."""
    apart = build_document(content(*(page_with_head(n, "Tests in Print", size=8) for n in (1, 2))))
    assert head_roles(apart) == ["Tests in Print"] * 2
    close = [
        [line("Tests in Print", LEFT, 40, 300, size=8), *column(f"p{n}-", LEFT, RIGHT, 50, 30)]
        for n in (1, 2)
    ]
    assert texts(build_document(content(*close)), BlockKind.FURNITURE) == []


def test_a_small_header_apart_from_its_rows_on_two_of_six_pages_is_text() -> None:
    """Word for word and apart from the text, but on 2 of 6 pages: less than `head_share`."""
    pages = [page_with_head(n, None) for n in range(1, 7)]
    for n in (2, 3):
        pages[n - 1] = small_header_page(n, below=12)
    doc = build_document(content(*pages))
    assert texts(doc, BlockKind.FURNITURE) == []
    assert texts(doc).count("Model Accuracy F1") == 2


def test_word_for_word_means_the_numbers_too_in_a_short_document() -> None:
    """ "Step 1" on page 1 and "Step 2" on page 2: the numbers follow the pages, which makes a
    body-size journal head one head (#458), but not a short document's small one."""
    heads = {1: "Step 1", 2: "Step 2"}
    doc = build_document(content(*(page_with_head(n, heads[n], size=8) for n in (1, 2))))
    assert texts(doc, BlockKind.FURNITURE) == []


def test_a_small_caption_label_on_most_pages_is_not_a_running_head() -> None:
    """ "Algorithm 1" to "Algorithm 3" apart from the text at the top of pages 2 to 4 of 4:
    on most pages, but a caption's label (#156)."""
    heads = {n: f"Algorithm {n - 1}" for n in (2, 3, 4)}
    pages = [page_with_head(n, heads.get(n), y=60, size=SMALL) for n in range(1, 5)]
    doc = build_document(content(*pages))
    assert texts(doc, BlockKind.FURNITURE) == []
    assert set(heads.values()) <= set(texts(doc))


def test_a_small_caption_label_at_the_foot_of_two_pages_is_not_a_running_head() -> None:
    """At the foot of the page a small line needs only its shape on two pages (a footer may
    stand close under the notes), but a caption's label is never a head there either."""
    pages = [page_with_head(n, None) for n in range(1, 5)]
    for n in (2, 3):
        pages[n - 1].append(line(f"Figure {n}: Results.", LEFT, 725, 300, size=SMALL))
    doc = build_document(content(*pages))
    assert texts(doc, BlockKind.FURNITURE) == []
    footers = [page_with_head(n, None) for n in range(1, 5)]
    for n in (2, 3):
        footers[n - 1].append(line(f"Tests in Print {n}", LEFT, 725, 300, size=SMALL))
    assert head_roles(build_document(content(*footers))) == ["Tests in Print 2", "Tests in Print 3"]


def test_a_small_continued_table_header_in_the_first_row_of_a_small_type_area_is_text() -> None:
    """The first row of a small type area is in the top band (D-502, #156's comment): a small
    continued table header there, on 2 of 5 pages and close to its rows, stays text."""
    pages = [small_area_page(n, None) for n in range(1, 6)]
    for n in (2, 3):
        header = line("Model Accuracy F1", LEFT, TYPE_TOP, 300, size=SMALL)
        pages[n - 1] = [header, *column(f"t{n}-", LEFT, 300, TYPE_TOP + SMALL + 2, 30)]
    doc = build_document(content(*pages))
    assert texts(doc, BlockKind.FURNITURE) == []
    assert texts(doc).count("Model Accuracy F1") == 2


def test_the_last_line_of_a_full_page_is_not_a_footer() -> None:
    body = column("body-", LEFT, RIGHT, 40, 52)  # the last line stands at y 754 of 800
    doc = build_document(content(body))
    assert texts(doc, BlockKind.FURNITURE) == []


def test_a_word_alone_at_the_foot_is_not_a_page_number_but_a_numeral_is() -> None:
    body = column("text-", LEFT, RIGHT, 100, 47)  # down to y 754
    words = [line(word, LEFT, 758, LEFT + 30) for word in ("Vivid",)]  # close to the text
    numeral = line("xii", 295, 780, 305, size=8)
    doc = build_document(content([*body, *words], [*body_copy(body), numeral]))
    assert texts(doc, BlockKind.FURNITURE) == ["xii"]
    assert doc.page_labels == ("", "xii")


def test_figure_labels_are_not_furniture() -> None:
    body = column("text-", LEFT, RIGHT, 100, 30)
    axes = Drawing("axes", Box(100, 700, 500, 760))  # a plot at the foot of the page
    tick = line("0", 95, 762, 101)  # alone below the axis, where a page number would stand
    label = line("\u03c3 (e/2\u03c0) value", 30, 500, 44, height=90)  # turned, in the margin, short
    doc = build_document(content([*body, tick, label], drawings=(axes,)))
    assert texts(doc, BlockKind.FURNITURE) == []


def test_footer_line_numbers_and_side_stamp_are_furniture() -> None:
    body = column("text-", 100, 500, 100, 12)
    numbers = [line(str(k + 1), 70, 100 + 14 * k, 80) for k in range(12)]
    stamp = line("arXiv:2401.00001v1 [cs.CL] 1 Jan 2024", 20, 200, 34, height=400)
    footer = line("Licensed under CC BY 4.0", 100, 760, 300)
    in_text = line("42", 100, 300, 112)  # a bare number inside the text is read
    doc = build_document(content([*body, *numbers, stamp, footer, in_text]))
    furniture = texts(doc, BlockKind.FURNITURE)
    assert sorted(furniture) == sorted([stamp.text, footer.text, *(n.text for n in numbers)])
    assert sorted(roles(doc)) == sorted(["side-stamp", "footer", *["line-number"] * 12])
    assert doc.page_labels == ("",)
    assert "42" in texts(doc, BlockKind.PARAGRAPH)


def test_a_printed_table_of_contents_is_furniture() -> None:
    title = line("Contents", LEFT, 100, 140, size=14)
    entries = []
    for k, (name, page) in enumerate(
        [("1 Introduction", "3"), ("2 Methods", "7"), ("3 Results", "12")]
    ):
        entries += [line(name, LEFT, 130 + 14 * k, 200), line(page, 510, 130 + 14 * k, RIGHT)]
    after = column("text-", LEFT, RIGHT, 200, 6)
    doc = build_document(content([title, *entries, *after]))
    assert texts(doc, BlockKind.PARAGRAPH) == [li.text for li in after]
    assert roles(doc) == ["contents"] * 7


def test_a_sidebar_in_small_letters_beside_the_text_is_furniture() -> None:
    body = column("text-", 170, 550, 100, 40)
    sidebar = [line(f"DOI 10.1/{k}", 40, 300 + 12 * k, 120, size=7) for k in range(6)]
    doc = build_document(content([*body, *sidebar], column("more-", 170, 550, 100, 40)))
    assert texts(doc, BlockKind.FURNITURE) == [li.text for li in sidebar]
    assert texts(doc)[:40] == [li.text for li in body]  # read after the page's text
    assert roles(doc) == ["sidebar"] * 6


def test_footnote_marks_that_go_up_with_the_page_are_read() -> None:
    """One footnote per page, its mark a small line of its own at the left end of a row in
    the bottom band: the marks go up by one per page but are not page numbers."""
    pages, read = [], []
    for n in (1, 2, 3):
        body = column(f"p{n}-", LEFT, RIGHT, 100, 40)
        body[-1] = short(body[-1])
        mark = line(str(n), LEFT, 760 - 10 * n, LEFT + 4, size=6)
        note = line(f"Note {'abc'[n - 1]} in small letters.", LEFT + 8, 760 - 10 * n, 400, size=8)
        pages.append([*body, mark, note])
        read.append(f"{mark.text} {note.text}")  # the mark joins its note's line
    doc = build_document(content(*pages))
    assert texts(doc, BlockKind.FURNITURE) == []
    assert doc.page_labels == ("", "", "")
    assert [text for text in texts(doc) if "Note" in text] == read


def test_a_lone_superscript_digit_at_the_foot_does_not_stop_layout() -> None:
    body = column("p-", LEFT, RIGHT, 100, 10)
    doc = build_document(content([*body, line("\u00b2", 300, 770, 305, size=6)]))
    assert "\u00b2" in texts(doc)


def test_a_page_number_beside_a_footer_goes_up_with_the_page() -> None:
    """A page number on the row of a footer line (JOSS) is not alone on its row; it counts
    as a page number because it goes up by one from page to page. A number that stays the
    same, such as a year, does not."""
    pages = []
    for number in (1, 2, 3):
        body = column(f"p{number}-", LEFT, RIGHT, 100, 10)
        body[-1] = short(body[-1])
        cite = line("Doe, J. (2021). A paper. Journal of Tests, 2026", LEFT, 770, 500, size=8)
        pages.append([*body, cite, line(str(number + 40), 510, 769, 520)])
    doc = build_document(content(*pages))
    assert roles(doc) == ["running-head", "page-number"] * 3
    assert doc.page_labels == ("41", "42", "43")


def test_in_page_order_moves_a_block_back_past_every_later_page_block() -> None:
    """#200, made-up blocks: no page built today cuts the piece from the
    next page into more than one block before the waiting blocks, so the pass is tested
    on its own. A block moves back past every block from a later page, two from one page
    keep their order, a block without items stays where it is read, and blocks already in
    page order stay as they are (D-434)."""
    pages = [
        Page(n, tuple(line(f"{n}{k}", LEFT, 100 + 14 * k, RIGHT) for k in range(4))) for n in (1, 2)
    ]
    found = Content(Source("0", SourceFormat.PDF), tuple(pages), Metadata())
    one, two = pages[0].lines, pages[1].lines

    def block(item: TextLine | None) -> Block:
        return Block(
            BlockKind.PARAGRAPH, item.text if item else "", (Part(item.id),) if item else ()
        )

    ordered = [block(one[0]), block(one[1]), block(two[0]), block(two[1])]
    assert _in_page_order(ordered, found) == ordered
    cut = [block(one[0]), block(two[0]), block(two[1]), block(two[2]), block(one[1]), block(one[2])]
    assert [b.text for b in _in_page_order(cut, found)] == ["10", "11", "12", "20", "21", "22"]
    empty = [block(one[0]), block(two[0]), block(None), block(one[1])]
    assert [b.text for b in _in_page_order(empty, found)] == ["10", "11", "20", ""]


# Properties


@given(contents())
@example(content([line("\n", LEFT, 100, 200)]))  # a line's own break is kept (#53)
@example(  # a mark with no block before it stays before the running heads (#57)
    Content(
        Source("0", SourceFormat.PDF),
        (
            Page(1, (), (Picture("i0", Box(0, 0, 0, 0)), Picture("i1", Box(3, 0, 14, 21))), ()),
            Page(2, (), (Picture("i2", Box(0, 0, 11, 21)),), ()),
        ),
        Metadata(),
    )
)
@example(  # a paragraph runs on to page 2, a line without a position waits for it, and a
    # formula is cut out of its page-2 piece: blocks stay in page order (#196)
    Content(
        Source("0", SourceFormat.PDF),
        (
            Page(
                1,
                (
                    TextLine("i0", (TextRun("0", size=0.0),)),
                    TextLine("i1", (TextRun("0", size=1.0),), Box(0, 0, 0, 0)),
                ),
            ),
            Page(
                2,
                (
                    TextLine("i2", (TextRun("÷", size=1.0),), Box(1, 0, 1, 0)),
                    TextLine("i3", (TextRun("000", size=1.175494351e-38),)),
                ),
            ),
        ),
        Metadata(),
    )
)
def test_layout_never_fails_and_keeps_every_line(found: Content) -> None:
    doc = build_document(found)  # the Document itself checks that every item is in one block
    lines = {li.id: li.text for page in found.pages for li in page.lines}
    for block in doc.blocks:  # the lines' text, joined by a space or a break (graphics hold none)
        read = [part for part in block.parts if part.item in lines]
        if not read:
            continue
        ends = [p.start for p in read[1:]] + [len(block.text)]
        for part, end in zip(read, ends, strict=True):
            text = lines[part.item]
            assert block.text[part.start : part.start + len(text)] == text
            assert block.text[part.start + len(text) : end] in ("", " ", "\n")
        if block.kind in (BlockKind.FOOTNOTE, BlockKind.CAPTION, BlockKind.LIST_ITEM):
            assert block.text.lstrip().startswith(block.label)
    pages = [doc.content.items()[b.parts[0].item][0].number for b in doc.blocks]
    assert pages == sorted(pages)
    # each graphic stands where the text read before it ends (#58, D-332)
    lengths = {item: len(text) for item, text in lines.items()}
    assert all(kept(block, block.parts, lengths) == block for block in doc.blocks)


@given(
    st.lists(st.integers(1, 999), min_size=2, max_size=8, unique=True),
    st.floats(5, 60),
    st.floats(10, 40),
)
def test_a_body_size_edge_line_that_differs_on_every_page_is_never_a_running_head(
    numbers: list[int], y: float, white: float
) -> None:
    """#33: whatever its height and the white below it, a body-size line whose text changes
    from page to page is text (D-322)."""
    pages = [
        [line(f"Algorithm {k}", LEFT, y, 300), *column(f"p{n}-", LEFT, RIGHT, y + 10 + white, 20)]
        for n, k in enumerate(numbers)
    ]
    assert head_roles(build_document(content(*pages))) == []


@given(contents())
def test_anything_printed_in_the_paper_top_band_keeps_the_paper_band(found: Content) -> None:
    """D-502: the first row of a small type area joins the top band only when nothing but a
    side stamp is printed in the paper's top `edge_band` on any page; else every band is
    the paper's, as before #235."""
    settings = LayoutSettings()
    sized = [page for page in found.pages if page.height and page.width]
    printed = any(
        box.y0 <= settings.edge_band * (page.height or 0.0)
        for page in sized
        for box in (
            *(li.box for li in page.lines if li.box and not _is_stamp(li, page, settings)),
            *(g.box for g in (*page.pictures, *page.drawings) if g.box),
        )
    )
    first_row = edges(found, settings).first_row
    if printed:
        assert first_row is None
    for page in sized:
        for li in page.lines:  # the paper's band is always in the top band
            if li.box and li.box.y1 <= settings.edge_band * (page.height or 0.0):
                assert edges(found, settings).band(li.box, page) == "top"


@st.composite
def column_pages(draw: st.DrawFn) -> tuple[Content, list[str], int]:
    """A page of 1 to 3 columns of paragraphs, its lines stored in any order.

    Paragraphs end in a line of any length, and a column may hold a centred heading.
    """
    count = draw(st.integers(1, 3))
    width = (RIGHT - LEFT - GUTTER * (count - 1)) / count
    lines, expected = [], []
    for col in range(count):
        x0, row = LEFT + col * (width + GUTTER), 0
        for _ in range(draw(st.integers(2, 4))):  # a column holds at least 5 lines
            if draw(st.booleans()):  # a centred heading
                share = draw(st.floats(0.2, 0.7))
                start = x0 + (1 - share) * width / 2
                lines.append(line(f"c{col}r{row}", start, 80 + 14 * row, start + share * width))
                expected.append(lines[-1].text)
                row += 1
            length = draw(st.integers(3, 8))
            for k in range(length):
                share = draw(st.floats(0.85, 1.0) if k < length - 1 else st.floats(0.05, 1.0))
                lines.append(line(f"c{col}r{row}", x0, 80 + 14 * row, x0 + share * width))
                expected.append(lines[-1].text)
                row += 1
    stored = draw(st.permutations(lines))
    return content(list(stored)), expected, count


def found_679() -> tuple[Content, list[str], int]:
    """#679, drawn by the `dev` profile: column 0 holds 7 of the page's 50 lines, so the
    strip beside it, which 5 lines may cross, opens at the end of its two short lines
    (x 105.3), right where its centred heading starts."""
    full = [(70.0, 211.3), (227.3, 368.7), (384.7, 526.0)]
    other = [
        {0: (105.3, 176.0), 3: (70.0, 105.3), 6: (70.0, 105.3)},
        {6: (262.7, 333.3), 23: (262.7, 333.3)},
        {0: (420.0, 490.7), 4: (420.0, 490.7)},
    ]
    lines = []
    for col, rows in enumerate((7, 27, 16)):
        for row in range(rows):
            x0, x1 = other[col].get(row, full[col])
            lines.append(line(f"c{col}r{row}", x0, 80 + 14 * row, x1))
    return content(lines), [li.text for li in lines], 3


def found_873(middle: dict[int, float]) -> tuple[Content, list[str], int]:
    """#873, drawn by the `dev` and `nightly` profiles: columns 0 and 2 hold 27 lines each,
    two of them centred headings (half the column wide), column 1 only 6 lines, which end
    at `middle` (row: right edge) where they don't fill it. 6 is a tenth of the page's 60
    lines, so the whole middle column may cross the strip from column 0 to column 2."""
    width = (RIGHT - LEFT - 2 * GUTTER) / 3
    centred = {0: (0, 6), 2: (0, 16)}
    lines = []
    for col, rows in enumerate((27, 6, 27)):
        x0 = LEFT + col * (width + GUTTER)
        for row in range(rows):
            start, end = x0, middle.get(row, x0 + width) if col == 1 else x0 + width
            if row in centred.get(col, ()):
                start, end = x0 + width / 4, x0 + 3 * width / 4
            lines.append(line(f"c{col}r{row}", start, 80 + 14 * row, end))
    return content(lines), [li.text for li in lines], 3


def test_a_middle_column_as_short_as_the_crossings_a_gutter_allows_is_a_column() -> None:
    """#873 without its headings: 6 full lines between two columns of 27 are a tenth of the
    page, as many as may cross a gutter, yet they are a column of their own."""
    width = (RIGHT - LEFT - 2 * GUTTER) / 3
    lines = [
        line(f"c{col}r{row}", x0, 80 + 14 * row, x0 + width)
        for col, rows in enumerate((27, 6, 27))
        for x0 in [LEFT + col * (width + GUTTER)]
        for row in range(rows)
    ]
    found = content(lines)
    assert texts(build_document(found)) == [li.text for li in lines]
    assert columns_per_page(found) == [3]


@pytest.mark.parametrize(("captioned", "ended"), [(True, False), (False, False), (True, True)])
def test_a_figure_in_a_wide_gutter_is_read_between_the_columns_but_is_no_column(
    captioned: bool, ended: bool
) -> None:
    """#895: two columns with a gutter of 140 pt that holds a drawing (x 236 to 360), its
    axis labels and its caption. The white on each side of the figure is a gutter, so the
    figure is read after the left column and before the right one, but the page still has
    two columns of text: the labels lie on the drawing, and a caption is no column.

    The figure's column is read row by row: the drawing (from y 190), the upper row of
    labels (y 200), the lower one (y 210), then the caption. The left column's paragraph
    ends in a sentence, whether its last line fills the column or ends short (`ended`), so
    the figure is read between the columns' paragraphs (#905), and holds its labels, with a
    caption that names it or without one (#932)."""
    stop = {29: "."}  # each column ends its paragraph with a sentence
    left = [
        line(f"L{k}{stop.get(k, '')}", 70, 80 + 14 * k, 150 if ended and k == 29 else 228)
        for k in range(30)
    ]
    right = [line(f"R{k}{stop.get(k, '')}", 368, 80 + 14 * k, 526) for k in range(30)]
    # 116 pt wide together, more than a column's least width (114 pt): a column, were they
    # counted
    labels = [line(f"lab{k}", 238 + 20 * k, 200 + 10 * (k % 2), 254 + 20 * k) for k in range(6)]
    caption = [line("Figure 1: a thing", 240, 280, 356)] if captioned else []
    found = content(
        left + right + labels + caption, drawings=(Drawing("fig", Box(236, 190, 360, 260)),)
    )
    doc = build_document(found)
    assert columns_per_page(found) == [2]
    ids = {li.id: li.text for li in [*left, *right, *labels, *caption]}
    upper, lower = [li.text for li in labels[::2]], [li.text for li in labels[1::2]]
    figures = [b for b in doc.blocks if b.kind is BlockKind.FIGURE]
    assert [[ids.get(p.item, p.item) for p in b.parts] for b in figures] == [
        ["fig", *upper, *lower]
    ]
    read = [ids.get(p.item, p.item) for b in doc.blocks for p in b.parts]
    middle = ["fig", *upper, *lower, *[li.text for li in caption]]
    if captioned:
        assert [b.kind for b in doc.blocks] == [
            BlockKind.PARAGRAPH,
            BlockKind.FIGURE,
            BlockKind.CAPTION,
            BlockKind.PARAGRAPH,
        ]
    assert read == [li.text for li in left] + middle + [li.text for li in right]


@pytest.mark.parametrize("captioned", [True, False])
def test_running_text_under_a_figure_in_a_middle_column_stays_in_its_paragraph(
    captioned: bool,
) -> None:
    """#905: a figure at the top of the middle column of three, with four full lines under
    it (and its caption above them) is no figure in a gutter: the sentence runs on from the
    left column through those lines into the right one, and they are read in that order."""
    width = (RIGHT - LEFT - 2 * GUTTER) / 3
    x0 = LEFT + width + GUTTER
    middle = [line(f"c1r{row}", x0, 80 + 14 * row, x0 + width) for row in range(23, 27)]
    # a short caption, far enough from the drawing to count: the page has three columns
    caption = [line("Figure 1: a thing", x0, 80 + 14 * 21, x0 + 90)] if captioned else []
    lines = three_columns((27, 0, 27))
    lines = lines[:27] + caption + middle + lines[27:]
    bottom = 80 + 14 * (20 if captioned else 23) - 6
    found = content(lines, drawings=(Drawing("fig", Box(x0, 80, x0 + width, bottom)),))
    doc = build_document(found)
    ids = {li.id: li.text for li in lines}
    assert columns_per_page(found) == [3 if captioned else 2]
    read = [ids[p.item] for b in doc.blocks for p in b.parts if p.item in ids]
    running = [li.text for li in lines if li not in caption]
    assert [text for text in read if text in running] == running
    (block,) = [b for b in doc.blocks if any(ids.get(p.item) == "c1r23" for p in b.parts)]
    assert {"c0r26", "c2r0"} <= {ids.get(p.item) for p in block.parts}


@pytest.mark.parametrize(
    ("end", "starts"),
    [
        ("Werte in der", ("Messung und", "und so weiter")),
        ("values of the", ("measurement and", "and so on")),
        ("Werte im Jahr 2023", ("Messung und", "und so weiter")),
        ("values (Smith 2020)", ("Measurement and", "and so on")),
    ],
)
def test_ragged_lines_that_go_on_with_a_sentence_under_a_middle_figure_stay_in_order(
    end: str, starts: tuple[str, str]
) -> None:
    """#905: the left column of three ends inside a sentence, a figure fills the top of the
    middle column, and four ragged lines under it go on with that sentence, whether their
    first word is a German noun in capitals or a lower-case word, and whether the sentence
    breaks after a word, a number or a closing bracket. They are running text, not the
    figure's labels: they are read before the right column."""
    width = (RIGHT - LEFT - 2 * GUTTER) / 3
    x0 = LEFT + width + GUTTER
    first, right_start = starts
    lines = three_columns((27, 0, 27))
    left, right = lines[:27], lines[27:]
    left[-1] = line(end, LEFT, 80 + 14 * 26, LEFT + width)
    right[0] = line(f"{right_start} weiter", x0 + width + GUTTER, 80, RIGHT)
    middle = [
        line(
            f"{first} m{k}" if k == 0 else f"m{k} geht", x0, 80 + 14 * (23 + k), x0 + share * width
        )
        for k, share in enumerate((0.86, 0.93, 0.80, 0.90))
    ]
    found = content(
        left + middle + right, drawings=(Drawing("fig", Box(x0, 80, x0 + width, 80 + 14 * 22)),)
    )
    doc = build_document(found)
    ids = {li.id: li.text for li in left + middle + right}
    read = [ids[p.item] for b in doc.blocks for p in b.parts if p.item in ids]
    assert read == [li.text for li in left + middle + right]


@pytest.mark.parametrize("captioned", [True, False])
def test_a_figure_in_a_wide_gutter_keeps_its_labels_and_caption_apart_from_the_columns(
    captioned: bool,
) -> None:
    """#905: on the #895 page the figure's labels are in no paragraph of the left or right
    column, and the caption block holds the caption's line alone."""
    stop = {29: "."}  # each column ends its paragraph with a sentence
    left = [line(f"L{k}{stop.get(k, '')}", 70, 80 + 14 * k, 228) for k in range(30)]
    right = [line(f"R{k}{stop.get(k, '')}", 368, 80 + 14 * k, 526) for k in range(30)]
    labels = [line(f"lab{k}", 238 + 20 * k, 200 + 10 * (k % 2), 254 + 20 * k) for k in range(6)]
    caption = [line("Figure 1: a thing", 240, 280, 356)] if captioned else []
    found = content(
        left + right + labels + caption, drawings=(Drawing("fig", Box(236, 190, 360, 260)),)
    )
    doc = build_document(found)
    text = {li.id for li in left + right}
    for block in doc.blocks:
        items = {p.item for p in block.parts}
        assert not (items & text and items - text), block
    captions = [b for b in doc.blocks if b.kind is BlockKind.CAPTION]
    assert [[p.item for p in b.parts] for b in captions] == [[li.id for li in caption]][
        : len(caption)
    ]


@pytest.mark.parametrize("share", [1.0, 0.6])
@pytest.mark.parametrize("captioned", [False, True])
@pytest.mark.parametrize("count", [1, 2, 3])
def test_lines_under_a_figure_atop_a_middle_column_are_read_after_the_left_column(
    count: int, captioned: bool, share: float
) -> None:
    """#938: a figure fills the top of the middle column of three, with 1 to 3 lines under
    it (and a caption above them). Figure and lines are fewer items than a gutter may hold,
    so the white from the left column to the right one is one strip; the white on each side
    of the figure is a gutter all the same. The left column is read whole, then the
    figure's column, then the right column. (The left column's paragraph ends in a
    sentence; for one that runs on into the right column, see the #966 test below.)"""
    width = (RIGHT - LEFT - 2 * GUTTER) / 3
    x0 = LEFT + width + GUTTER
    top = 23 - count
    caption = [line("Figure 1: a thing", x0, 80 + 14 * top, x0 + 90)] if captioned else []
    middle = [
        line(f"c1r{row}", x0, 80 + 14 * row, x0 + share * width)
        for row in range(top + len(caption), top + len(caption) + count)
    ]
    lines = three_columns((27, 0, 27))
    left, right = lines[:27], lines[27:]
    left[-1] = line("c0r26.", LEFT, 80 + 14 * 26, LEFT + width)
    drawing = Drawing("fig", Box(x0, 80, x0 + width, 80 + 14 * (top - 1)))
    found = content(left + caption + middle + right, drawings=(drawing,))
    doc = build_document(found)
    ids = {li.id: li.text for li in left + caption + middle + right}
    read = [ids[p.item] for b in doc.blocks for p in b.parts if p.item in ids]
    assert read == [li.text for li in left + caption + middle + right]
    assert columns_per_page(found) == [2]


@pytest.mark.parametrize("end", ["c0r26", "c0r26,", "c0r26 2023"])
@pytest.mark.parametrize("count", [1, 2, 4])
def test_a_middle_figure_s_caption_and_lines_are_read_between_its_columns_when_the_left_runs_on(
    count: int, end: str
) -> None:
    """#966: the #938 page with a caption under the figure atop the middle column and 1 to
    4 lines under it, the last of them ragged, while the left column's last line fills it
    and ends no sentence, and the right column's first line fills it too. The middle
    column is printed between its neighbours, and its lines are running text, not the
    float's: they are read after the left column and before the right one, the caption
    before them, though the left column's paragraph would go on in the right column."""
    width = (RIGHT - LEFT - 2 * GUTTER) / 3
    x0 = LEFT + width + GUTTER
    top = 27 - count - 1
    caption = [line("Figure 1: a thing", x0, 80 + 14 * top, x0 + 90)]
    middle = [
        line(f"c1r{row}", x0, 80 + 14 * row, x0 + (0.6 if row == 26 else 1.0) * width)
        for row in range(top + 1, 27)
    ]
    lines = three_columns((27, 0, 27))
    left, right = lines[:27], lines[27:]
    left[-1] = line(end, LEFT, 80 + 14 * 26, LEFT + width)
    drawing = Drawing("fig", Box(x0, 80, x0 + width, 80 + 14 * (top - 1)))
    found = content(left + caption + middle + right, drawings=(drawing,))
    doc = build_document(found)
    ids = {li.id: li.text for li in left + caption + middle + right}
    read = [ids[p.item] for b in doc.blocks for p in b.parts if p.item in ids]
    assert read == [li.text for li in left + caption + middle + right]
    assert holding(doc, BlockKind.CAPTION) == [[caption[0].id]]


@pytest.mark.parametrize(
    ("end", "first"), [("the measure-", "ment of the"), ("die Mess-", "ung der Werte")]
)
def test_a_word_split_over_a_middle_figure_s_column_is_not_cut(end: str, first: str) -> None:
    """#966: the #966 page, but the left column's last line ends in a word split by a
    hyphen that the right column's first line goes on with. Reading the middle column
    between them would put the caption and that column inside the word, so the paragraph
    goes on in the right column with the word whole, and the float follows it (#61)."""
    width = (RIGHT - LEFT - 2 * GUTTER) / 3
    x0 = LEFT + width + GUTTER
    caption = line("Figure 1: a thing", x0, 80 + 14 * 24, x0 + 90)
    middle = [line("c1r25", x0, 80 + 14 * 25, x0 + width), line("c1r26", x0, 444, x0 + 80)]
    lines = three_columns((27, 0, 27))
    left, right = lines[:27], lines[27:]
    left[-1] = line(end, LEFT, 80 + 14 * 26, LEFT + width)
    right[0] = line(first, right[0].box.x0, right[0].box.y0, right[0].box.x1)
    drawing = Drawing("fig", Box(x0, 80, x0 + width, 80 + 14 * 23))
    doc = build_document(content([*left, caption, *middle, *right], drawings=(drawing,)))
    assert right[0].id in {p.item for p in block_of(doc, left[-1].id).parts}
    read = [p.item for b in doc.blocks for p in b.parts]
    assert read.index(caption.id) > read.index(right[0].id)


@pytest.mark.parametrize("where", ["top of the right column", "foot of the left column"])
def test_a_note_under_a_caption_in_the_paragraph_s_own_columns_waits_for_it(where: str) -> None:
    """#966, #61: two columns, the left one's last line running on into the right one. A
    figure with its caption and a note under the caption (at the line pitch, as a float's
    own lines stand) at the top of the right column, or at the foot of the left one, is in
    no column between the two: the paragraph goes on in the right column, and the figure,
    the caption and the note follow it."""
    rows = 30 if where == "top of the right column" else 24
    left = [line("L" if k == rows - 1 else f"L{k}", 70, 80 + 14 * k, 290) for k in range(rows)]
    if where == "top of the right column":
        x0, y0, top = 306, 80, 230
    else:
        x0, y0, top = 70, 80 + 14 * rows + 24, 80
    drawing = Drawing("fig", Box(x0, y0, x0 + 220, y0 + 100))
    caption = line("Figure 1: a thing", x0, y0 + 106, x0 + 110)
    note = line("Source: own data", x0, y0 + 120, x0 + 90)
    right = [line(f"R{k}{'.' if k == 15 else ''}", 306, top + 14 * k, 526) for k in range(16)]
    doc = build_document(content([*left, caption, note, *right], drawings=(drawing,)))
    assert right[0].id in {p.item for p in block_of(doc, left[-1].id).parts}
    read = [p.item for b in doc.blocks for p in b.parts]
    assert read == [li.id for li in left + right] + ["fig", caption.id, note.id]


def test_labels_under_a_gutter_figure_after_a_column_that_runs_on_wait_for_its_paragraph() -> None:
    """#966, #958: on the #895 page with no caption, a row of labels 2 pt under the drawing
    (not on it, so not taken for its labels after a left column that ends no sentence)
    stands in the column between the left and the right one. It is no text under a
    caption: the left column's paragraph goes on in the right column, and the labels
    follow it, as an interruption that is not running text does (#61)."""
    labels = [line(t, 244 + 28 * k, 262, 258 + 28 * k) for k, t in enumerate(("x", "10", "time"))]
    found, left, right = gutter_page("L29", labels)
    doc = build_document(found)
    assert right[0].id in {p.item for p in block_of(doc, left[-1].id).parts}
    read = [p.item for b in doc.blocks for p in b.parts]
    assert read.index(labels[0].id) > read.index(right[-1].id)


def middle_figure_page(
    end: str, starts: tuple[str, str], gap: float, rows: int = 4
) -> tuple[Content, list[TextLine], list[TextLine], list[TextLine]]:
    """Three columns of 27 lines, the left one ending in the line `end`, a figure atop the
    middle one from y 80 to y 388 and `rows` (up to four) ragged lines under it, the first
    `gap` points under the figure and opening with `starts[0]`; the right column's first
    line opens with `starts[1]`."""
    width = (RIGHT - LEFT - 2 * GUTTER) / 3
    x0 = LEFT + width + GUTTER
    first, right_start = starts
    lines = three_columns((27, 0, 27))
    left, right = lines[:27], lines[27:]
    left[-1] = line(end, LEFT, 80 + 14 * 26, LEFT + width)
    right[0] = line(f"{right_start} weiter", x0 + width + GUTTER, 80, RIGHT)
    texts = [f"{first} m0", "m1 goes", "m2 goes", "m3 goes"][:rows]
    middle = [
        line(text, x0, 388 + gap + 14 * k, x0 + share * width)
        for k, (text, share) in enumerate(zip(texts, (0.86, 0.93, 0.80, 0.90), strict=False))
    ]
    drawing = Drawing("fig", Box(x0, 80, x0 + width, 388))
    return content(left + middle + right, drawings=(drawing,)), left, middle, right


def block_of(doc: Document, item: str) -> Block:
    (block,) = [b for b in doc.blocks if any(p.item == item for p in b.parts)]
    return block


@pytest.mark.parametrize("gap", [14.0, 11.0])
@pytest.mark.parametrize(
    "starts",
    [("Measurement", "and so on"), ("Messung", "und so weiter")],
)
def test_running_text_under_a_middle_figure_goes_on_into_the_right_column(
    starts: tuple[str, str], gap: float
) -> None:
    """#945: the left column ends a sentence, and four ragged lines under a figure atop the
    middle column open a sentence with a capital that runs on into the right column. They
    are running text, not the figure's labels: they stand further under the figure than
    its labels would (more than `float_gap`, 1 em), so their last line and the right
    column's first are one paragraph."""
    found, left, middle, right = middle_figure_page("so it ends.", starts, gap)
    doc = build_document(found)
    ids = {li.id: li.text for li in left + middle + right}
    read = [ids[p.item] for b in doc.blocks for p in b.parts if p.item in ids]
    assert read == [li.text for li in left + middle + right]
    assert right[0].id in {p.item for p in block_of(doc, middle[-1].id).parts}


@pytest.mark.parametrize(
    ("end", "starts"),
    [
        ("Werte wie z. B.", ("Messung", "und so weiter")),
        ("Werte, d. h.", ("Messung", "und so weiter")),
        ("Werte u. a.", ("Messung", "und so weiter")),
        ("Werte in Abb.", ("Messung", "und so weiter")),
        ("Werte am 3.", ("Mai", "und so weiter")),
        ("values by Smith et al.", ("Measurement", "and so on")),
        ("values, e.g.", ("Measurement", "and so on")),
        ("values, i.e.", ("Measurement", "and so on")),
        ("values in Fig.", ("Measurement", "and so on")),
    ],
)
@pytest.mark.parametrize("rows", [4, 1])
def test_an_abbreviation_ending_the_left_column_is_no_sentence_end_for_a_middle_figure(
    end: str, starts: tuple[str, str], rows: int
) -> None:
    """#945: the left column of three ends in an abbreviation, a figure fills the top of the
    middle column and one to four ragged lines stand close under it, within `float_gap`.
    The abbreviation ends no sentence, and the lines do not lie on the figure, so they are
    not taken for its labels: the left column's last line and the first line under the
    figure are one paragraph."""
    found, left, middle, right = middle_figure_page(end, starts, 4.0, rows)
    doc = build_document(found)
    ids = {li.id: li.text for li in left + middle + right}
    read = [ids[p.item] for b in doc.blocks for p in b.parts if p.item in ids]
    assert read == [li.text for li in left + middle + right]
    assert middle[0].id in {p.item for p in block_of(doc, left[-1].id).parts}


@pytest.mark.parametrize("ended", [False, True])
@pytest.mark.parametrize("captioned", [True, False])
@pytest.mark.parametrize("end", ["L29", "L29,", "L29 2023", "L29.“", "L29.»"])
def test_a_gutter_figure_keeps_its_labels_when_the_left_column_runs_on(
    end: str, captioned: bool, ended: bool
) -> None:
    """#958: the #895 page with the left column's last line running on past the break (a
    word, a comma, a number), or ending a sentence in a German closing quote or guillemet,
    whether it fills the column or ends short (`ended`). The labels lie on the drawing, so
    they are the figure's: no block mixes them or the caption with the columns' lines, the
    caption block holds the caption alone, and the text is read in the page's order."""
    left = [
        line(end if k == 29 else f"L{k}", 70, 80 + 14 * k, 150 if ended and k == 29 else 228)
        for k in range(30)
    ]
    right = [line(f"R{k}{'.' if k == 29 else ''}", 368, 80 + 14 * k, 526) for k in range(30)]
    labels = [line(f"lab{k}", 238 + 20 * k, 200 + 10 * (k % 2), 254 + 20 * k) for k in range(6)]
    caption = [line("Figure 1: a thing", 240, 280, 356)] if captioned else []
    found = content(
        left + right + labels + caption, drawings=(Drawing("fig", Box(236, 190, 360, 260)),)
    )
    doc = build_document(found)
    assert columns_per_page(found) == [2]
    text = {li.id for li in left + right}
    for block in doc.blocks:
        items = {p.item for p in block.parts}
        assert not (items & text and items - text), block
    ids = {li.id: li.text for li in [*left, *right, *labels, *caption]}
    upper, lower = [li.text for li in labels[::2]], [li.text for li in labels[1::2]]
    read = [ids[p.item] for b in doc.blocks for p in b.parts if p.item in ids]
    assert read == [li.text for li in left] + upper + lower + [li.text for li in caption] + [
        li.text for li in right
    ]
    if captioned:
        figures = [b for b in doc.blocks if b.kind is BlockKind.FIGURE]
        assert [[ids.get(p.item, p.item) for p in b.parts] for b in figures] == [
            ["fig", *upper, *lower]
        ]
        captions = [b for b in doc.blocks if b.kind is BlockKind.CAPTION]
        assert [[p.item for p in b.parts] for b in captions] == [[caption[0].id]]


def test_a_caption_in_a_gutter_after_a_column_that_runs_on_waits_for_its_paragraph() -> None:
    """#958: on the #895 page with no labels, the left column's last line fills it and ends
    no sentence. The caption right after the figure sets the paragraph aside, and the right
    column goes on with it: the caption is read after the paragraph, as after any float
    (#61). Reading it as the figure's, between the columns, would move the paragraph's end
    before it."""
    left = [line(f"L{k}", 70, 80 + 14 * k, 228) for k in range(30)]
    right = [line(f"R{k}{'.' if k == 29 else ''}", 368, 80 + 14 * k, 526) for k in range(30)]
    caption = line("Figure 1: a thing", 240, 280, 310)  # short: no running text
    found = content(left + right + [caption], drawings=(Drawing("fig", Box(236, 190, 360, 260)),))
    doc = build_document(found)
    ids = {li.id: li.text for li in [*left, *right, caption]}
    read = [ids[p.item] for b in doc.blocks for p in b.parts if p.item in ids]
    assert read == [li.text for li in left + right] + [caption.text]
    assert right[0].id in {p.item for p in block_of(doc, left[-1].id).parts}


@pytest.mark.parametrize("captioned", [True, False])
def test_tick_labels_under_a_gutter_figure_after_a_sentence_end_are_the_figures(
    captioned: bool,
) -> None:
    """#945: on the #895 page with a row of ticks just under the drawing's box (within
    `float_gap`) and the axis's name under them (within `float_gap` of the ticks, not of
    the drawing), and the left column ending a sentence, ticks and name are the figure's
    labels: no block mixes them or the caption with the columns' lines."""
    left = [line(f"L{k}{'.' if k == 29 else ''}", 70, 80 + 14 * k, 228) for k in range(30)]
    right = [line(f"R{k}{'.' if k == 29 else ''}", 368, 80 + 14 * k, 526) for k in range(30)]
    ticks = [line(f"tick{k}", 240 + 28 * k, 262, 252 + 28 * k) for k in range(4)]
    ticks.append(line("time (s)", 280, 276, 320))
    caption = [line("Figure 1: a thing", 240, 296, 356)] if captioned else []
    found = content(
        left + right + ticks + caption, drawings=(Drawing("fig", Box(236, 190, 360, 260)),)
    )
    doc = build_document(found)
    text = {li.id for li in left + right}
    for block in doc.blocks:
        items = {p.item for p in block.parts}
        assert not (items & text and items - text), block
    ids = {li.id: li.text for li in [*left, *right, *ticks, *caption]}
    read = [ids[p.item] for b in doc.blocks for p in b.parts if p.item in ids]
    assert read == [li.text for li in left + ticks + caption + right]


def gutter_page(end: str, middle: list[TextLine]) -> tuple[Content, list[TextLine], list[TextLine]]:
    """The #895 page: two columns of 30 full lines, the left one ending in `end` and the
    right one in a full stop, and a drawing in the 140 pt gutter between them (x 236 to
    360, y 190 to 260) with the lines `middle` (its labels and caption)."""
    left = [line(end if k == 29 else f"L{k}", 70, 80 + 14 * k, 228) for k in range(30)]
    right = [line(f"R{k}{'.' if k == 29 else ''}", 368, 80 + 14 * k, 526) for k in range(30)]
    drawing = Drawing("fig", Box(236, 190, 360, 260))
    return content(left + right + middle, drawings=(drawing,)), left, right


def holding(doc: Document, kind: BlockKind) -> list[list[str]]:
    """The items of each block of the kind, in reading order."""
    return [[p.item for p in b.parts] for b in doc.blocks if b.kind is kind]


def unmixed(doc: Document, text: list[TextLine]) -> bool:
    """True if no block holds both lines of `text` and anything else."""
    ids = {li.id for li in text}
    return not any(
        {p.item for p in b.parts} & ids and {p.item for p in b.parts} - ids for b in doc.blocks
    )


def gutter_labels() -> list[TextLine]:
    """The #895 labels: two rows of three on the drawing (y 200 and 210)."""
    return [line(f"lab{k}", 238 + 20 * k, 200 + 10 * (k % 2), 254 + 20 * k) for k in range(6)]


@pytest.mark.parametrize("end", ["L29.", "L29"])
def test_a_caption_under_a_gutter_figure_names_it(end: str) -> None:
    """#906: on the #895 page, the caption under the figure in the gutter names it
    (`describes`), whether the left column ends a sentence or runs on (#958)."""
    labels = gutter_labels()
    caption = line("Figure 1: a thing", 240, 280, 356)
    found, _, _ = gutter_page(end, [*labels, caption])
    doc = build_document(found)
    (named,) = [b for b in doc.blocks if b.kind is BlockKind.CAPTION]
    assert [p.item for p in named.parts] == [caption.id]
    assert named.describes is not None
    assert [p.item for p in doc.blocks[named.describes].parts] == [
        "fig",
        *[li.id for li in labels[::2]],
        *[li.id for li in labels[1::2]],
    ]


@pytest.mark.parametrize("labelled", [True, False])
def test_a_caption_above_a_gutter_figure_is_a_caption_naming_it(labelled: bool) -> None:
    """#933: on the #895 page with the caption above the drawing (y 170), the caption is a
    CAPTION block of its own that names the figure, the labels on the drawing are the
    figure's, and neither joins the left or the right column's paragraph."""
    labels = gutter_labels() if labelled else []
    caption = line("Figure 1: a thing", 240, 170, 356)
    found, left, right = gutter_page("L29.", [caption, *labels])
    doc = build_document(found)
    upper, lower = [li.id for li in labels[::2]], [li.id for li in labels[1::2]]
    assert holding(doc, BlockKind.CAPTION) == [[caption.id]]
    (named,) = [b for b in doc.blocks if b.kind is BlockKind.CAPTION]
    assert named.describes is not None
    assert [p.item for p in doc.blocks[named.describes].parts] == ["fig", *upper, *lower]
    assert unmixed(doc, left + right)
    ids = {li.id: li.text for li in [*left, *right, *labels, caption]}
    read = [ids[p.item] for b in doc.blocks for p in b.parts if p.item in ids]
    assert read[: len(left)] == [li.text for li in left]
    assert read[-len(right) :] == [li.text for li in right]


@pytest.mark.parametrize("captioned", [True, False])
def test_ticks_across_a_gutter_figure_and_its_caption_under_them(captioned: bool) -> None:
    """#933: on the #895 page a row of five ticks just under the drawing (y 262) spans the
    gutter's figure from edge to edge, each 2 em from the next, with the caption under
    them. The ticks are the figure's, not running text that fills its column: the FIGURE
    block holds them and the CAPTION block holds the caption alone."""
    ticks = [line(str(10 * k), 238 + 28 * k, 262, 246 + 28 * k) for k in range(5)]
    caption = [line("Figure 1: a thing", 240, 280, 356)] if captioned else []
    found, left, right = gutter_page("L29.", [*ticks, *caption])
    doc = build_document(found)
    assert holding(doc, BlockKind.FIGURE) == [["fig", *[li.id for li in ticks]]]
    assert holding(doc, BlockKind.CAPTION) == [[li.id for li in caption]][: len(caption)]
    assert unmixed(doc, left + right)
    ids = {li.id: li.text for li in [*left, *right, *ticks, *caption]}
    read = [ids[p.item] for b in doc.blocks for p in b.parts if p.item in ids]
    assert read == [li.text for li in left + ticks + caption + right]


def bar_chart(x0: float, step: float = 50) -> tuple[Drawing, ...]:
    """A bar chart from x `x0` and from y 84 to y 197: two axes and four bars 20 pt wide,
    `step` apart, standing on the x axis."""
    axes = (
        Drawing("axis-x", Box(x0, 196, x0 + 4 * step + 10, 197)),
        Drawing("axis-y", Box(x0, 84, x0 + 1, 197)),
    )
    tops = (150, 120, 100, 130)
    bars = tuple(
        Drawing(f"bar{k}", Box(x0 + 20 + step * k, top, x0 + 40 + step * k, 196))
        for k, top in enumerate(tops)
    )
    return axes + bars


def chart_labels(x0: float) -> list[TextLine]:
    """Labels in the body size on the bar chart: two rows of two, at y 120 and y 150."""
    return [
        line(f"lab{k}", x0 + 10 + 50 * k, 120 + 30 * (k % 2), x0 + 30 + 50 * k) for k in range(4)
    ]


def items_of(doc: Document, lines: list[TextLine]) -> list[list[str]]:
    """The lines of `lines` each block holds, for the blocks that hold any."""
    ids = {li.id for li in lines}
    found = [[p.item for p in b.parts if p.item in ids] for b in doc.blocks]
    return [items for items in found if items]


@pytest.mark.parametrize("end", ["L29", "L29."])
def test_body_size_labels_of_a_figure_at_a_column_top_stay_with_it(end: str) -> None:
    """#932: a bar chart at the top of the right column, with two rows of labels set in the
    body size on it, and the left column ending in a full line, whether it ends a sentence
    or runs on. The labels are the figure's: each row stands in a block of its own right
    after the FIGURE block, not in the left column's paragraph, which goes on in the right
    column if its sentence does."""
    left = [line(end if k == 29 else f"L{k}", 70, 80 + 14 * k, 290) for k in range(30)]
    right = [line(f"R{k}{'.' if k == 19 else ''}", 306, 214 + 14 * k, 526) for k in range(20)]
    labels = chart_labels(310)
    doc = build_document(content(left + right + labels, drawings=bar_chart(310)))
    (figure,) = [k for k, b in enumerate(doc.blocks) if b.kind is BlockKind.FIGURE]
    upper, lower = [li.id for li in labels[::2]], [li.id for li in labels[1::2]]
    after = doc.blocks[figure + 1 : figure + 3]
    assert [[p.item for p in b.parts] for b in after] == [upper, lower]
    assert items_of(doc, labels) == [upper, lower]
    assert unmixed(doc, left + right)
    if end == "L29":
        assert right[0].id in {p.item for p in block_of(doc, left[-1].id).parts}


@pytest.mark.parametrize("end", ["L29", "L29."])
def test_body_text_next_to_or_under_a_figure_is_no_label(end: str) -> None:
    """#932: running text is never a figure's label. A full line 4 pt under a bar chart at
    the top of the right column, five lines beside a narrower chart, and short lines on one
    shaded box at the top of the right column (a background, D-840) are read in the same
    blocks as without the drawings."""
    left = [line(end if k == 29 else f"L{k}", 70, 80 + 14 * k, 290) for k in range(30)]
    under = [line("under goes on", 306, 201, 526)]
    beside = [line(f"B{k}", 446, 90 + 14 * k, 526) for k in range(5)]
    shaded = [line(f"x{k} = {k}", 312, 90 + 14 * k, 380) for k in range(4)]
    shade = (Drawing("shade", Box(306, 84, 526, 148)),)
    pages = [
        (under, 215, bar_chart(310)),
        (beside, 214, bar_chart(306, step=25)),
        (shaded, 160, shade),
    ]
    for lines, top, drawings in pages:
        right = [line(f"R{k}", 306, top + 14 * k, 526) for k in range(20)]
        text = left + lines + right
        drawn = build_document(content(text, drawings=drawings))
        assert items_of(drawn, text) == items_of(build_document(content(text)), text)


def frame(x0: float, y0: float, x1: float, y1: float) -> tuple[Drawing, ...]:
    """A frame of four rules 1 pt thick around the box."""
    return (
        Drawing("frame-top", Box(x0, y0, x1, y0 + 1)),
        Drawing("frame-bottom", Box(x0, y1 - 1, x1, y1)),
        Drawing("frame-left", Box(x0, y0, x0 + 1, y1)),
        Drawing("frame-right", Box(x1 - 1, y0, x1, y1)),
    )


@pytest.mark.parametrize("case", ["running text on the chart", "short lines in a frame"])
def test_short_lines_at_a_column_top_with_running_text_on_the_figure_or_in_rules_are_text(
    case: str,
) -> None:
    """#932: the left column runs on into the right one, whose top holds short lines on a
    figure. If a full line of running text lies on the figure too (a bar chart with text
    set over its foot), or the figure is only rules (a frame around a note), the short lines
    are running text, not the figure's labels: they are read in the same blocks as without
    the drawings."""
    left = [line("L29" if k == 29 else f"L{k}", 70, 80 + 14 * k, 290) for k in range(30)]
    if case == "running text on the chart":
        lines = [*chart_labels(310), line("running on over the chart", 306, 176, 526)]
        drawings, top = bar_chart(310), 214
    else:
        lines = [line(f"x{k} = {k}", 312, 90 + 14 * k, 380) for k in range(4)]
        drawings, top = frame(306, 84, 526, 148), 160
    right = [line(f"R{k}", 306, top + 14 * k, 526) for k in range(20)]
    text = left + lines + right
    drawn = build_document(content(text, drawings=drawings))
    assert items_of(drawn, text) == items_of(build_document(content(text)), text)


def test_ticks_on_a_gutter_figure_do_not_run_on_into_its_caption() -> None:
    """#933: on the #895 page with the left column running on, a row of ticks across the
    drawing's foot (on it, each 2 em from the next) and the caption 4 pt under it, as close
    as running text's next line: the caption is a CAPTION block of its own, not the end of
    the ticks' paragraph."""
    ticks = [line(str(10 * k), 238 + 28 * k, 248, 246 + 28 * k) for k in range(5)]
    caption = line("Figure 1: a thing", 240, 262, 356)
    found, _, _ = gutter_page("L29", [*ticks, caption])
    doc = build_document(found)
    assert holding(doc, BlockKind.CAPTION) == [[caption.id]]


def test_a_gutter_figure_of_rules_holds_its_labels() -> None:
    """#932: on the #895 page the drawing is a frame of four rules: lines only, which alone
    would join the block before them. With the labels read into its block it is a figure
    all the same, and the FIGURE block holds the rules and the labels."""
    labels = gutter_labels()
    left = [line(f"L{k}{'.' if k == 29 else ''}", 70, 80 + 14 * k, 228) for k in range(30)]
    right = [line(f"R{k}{'.' if k == 29 else ''}", 368, 80 + 14 * k, 526) for k in range(30)]
    rules = frame(236, 190, 360, 260)
    doc = build_document(content(left + right + labels, drawings=rules))
    (figure,) = holding(doc, BlockKind.FIGURE)
    assert {li.id for li in labels} | {d.id for d in rules} == set(figure)


def test_a_gutter_figure_on_two_pages_in_one_place_is_no_running_head() -> None:
    """#932: the #895 page twice, the figure in the same place on both: a figure whose labels
    are read into its block is a figure, not a journal's logo repeated on its pages."""
    pages = []
    for n in (1, 2):
        left = [line(f"L{k}{'.' if k == 29 else ''}", 70, 80 + 14 * k, 228) for k in range(30)]
        right = [line(f"R{k}{'.' if k == 29 else ''}", 368, 80 + 14 * k, 526) for k in range(30)]
        drawing = Drawing(f"fig{n}", Box(236, 190, 360, 260))
        lines = (*left, *right, *gutter_labels())
        pages.append(Page(n, lines, width=600, height=800, drawings=(drawing,)))
    found = Content(Source("test.pdf", SourceFormat.PDF), tuple(pages), Metadata())
    doc = build_document(found)
    figures = holding(doc, BlockKind.FIGURE)
    assert [f[0] for f in figures] == ["fig1", "fig2"]
    assert all(len(f) == 7 for f in figures)
    assert not [b for b in doc.blocks if b.kind is BlockKind.FURNITURE]


@pytest.mark.parametrize("short", [False, True])
@pytest.mark.parametrize("end", ["L29", "L29,", "L29 2023", "L29 et al.", "L29."])
def test_an_uncaptioned_gutter_figure_holds_its_labels_when_the_left_column_runs_on(
    end: str, short: bool
) -> None:
    """#1017: the #895 page with no caption, the left column's last line ending inside a
    sentence (a word, a comma, a number, an abbreviation) or ending one, filling the column
    or ending short. The labels lie on the drawing, so they go into its FIGURE block as
    after a sentence end (#932), and the text is read left column, figure, right column."""
    labels = gutter_labels()
    left = [
        line(end if k == 29 else f"L{k}", 70, 80 + 14 * k, 150 if short and k == 29 else 228)
        for k in range(30)
    ]
    right = [line(f"R{k}{'.' if k == 29 else ''}", 368, 80 + 14 * k, 526) for k in range(30)]
    doc = build_document(
        content(left + right + labels, drawings=(Drawing("fig", Box(236, 190, 360, 260)),))
    )
    upper, lower = [li.id for li in labels[::2]], [li.id for li in labels[1::2]]
    assert holding(doc, BlockKind.FIGURE) == [["fig", *upper, *lower]]
    assert unmixed(doc, left + right)
    read = [p.item for b in doc.blocks for p in b.parts]
    assert read == [li.id for li in left] + ["fig", *upper, *lower] + [li.id for li in right]


def test_the_lines_around_a_gutter_figure_s_labels_are_measured_against_each_other() -> None:
    """#1017: on the #895 page with no caption and the left column running on, the labels'
    last row ends 30 pt short of the figure's edge, and the right column opens with the
    short last line of a sentence, 30 pt short too, over a full line. With the labels read
    into the figure's block, the short line is measured against the left column's last line,
    as after a sentence end (#932): it ends its paragraph, and the full line starts one."""
    spots = ((240, 200), (250, 210), (280, 200), (314, 210))
    labels = [line(f"lab{k}", x, y, x + 16) for k, (x, y) in enumerate(spots)]
    _, left, right = gutter_page("L29", labels)
    right[0] = line("R0 ends.", 368, 80, 496)
    doc = build_document(
        content(left + right + labels, drawings=(Drawing("fig", Box(236, 190, 360, 260)),))
    )
    assert holding(doc, BlockKind.FIGURE) == [
        ["fig", *[li.id for li in labels[::2]]] + [li.id for li in labels[1::2]]
    ]
    assert right[1].id not in {p.item for p in block_of(doc, right[0].id).parts}


@pytest.mark.parametrize("end", ["L29", "L29."])
def test_labels_on_a_single_picture_at_a_column_top_stay_with_it(end: str) -> None:
    """#1017: a chart printed as one picture at the top of the right column, with two rows of
    labels in the body size set on it, and the left column ending in a full line, whether
    it ends a sentence or runs on. One graphic holds all the labels, as a shaded box holds
    its text (D-840), but a picture is no fill behind text: each row of labels is a block of
    its own right after the FIGURE block, not in the left column's paragraph, which goes on
    in the right column if its sentence does."""
    left = [line(end if k == 29 else f"L{k}", 70, 80 + 14 * k, 290) for k in range(30)]
    right = [line(f"R{k}{'.' if k == 19 else ''}", 306, 214 + 14 * k, 526) for k in range(20)]
    labels = chart_labels(310)
    chart = Picture("chart", Box(310, 84, 520, 197))
    doc = build_document(content(left + right + labels, pictures=(chart,)))
    (figure,) = [k for k, b in enumerate(doc.blocks) if b.kind is BlockKind.FIGURE]
    assert doc.blocks[figure].parts[0].item == "chart"
    upper, lower = [li.id for li in labels[::2]], [li.id for li in labels[1::2]]
    after = doc.blocks[figure + 1 : figure + 3]
    assert [[p.item for p in b.parts] for b in after] == [upper, lower]
    assert unmixed(doc, left + right)
    if end == "L29":
        assert right[0].id in {p.item for p in block_of(doc, left[-1].id).parts}


def three_columns(rows: tuple[int, int, int]) -> list[TextLine]:
    """Three columns of full lines, `rows` lines in each, from y 80 down."""
    width = (RIGHT - LEFT - 2 * GUTTER) / 3
    return [
        line(f"c{col}r{row}", x0, 80 + 14 * row, x0 + width)
        for col, count in enumerate(rows)
        for x0 in [LEFT + col * (width + GUTTER)]
        for row in range(count)
    ]


def test_a_middle_column_on_a_shaded_box_is_a_column() -> None:
    """#916: 27 full lines set on a shaded box (wider than the lines by 3 pt, as such a box
    is drawn) are running text, not a figure's labels: the page has three columns."""
    width = (RIGHT - LEFT - 2 * GUTTER) / 3
    x0 = LEFT + width + GUTTER
    shade = Drawing("shade", Box(x0 - 3, 76, x0 + width + 3, 80 + 14 * 27))
    found = content(three_columns((27, 27, 27)), drawings=(shade,))
    assert columns_per_page(found) == [3]


def test_underlines_through_a_short_middle_column_leave_it_a_column() -> None:
    """#916: the #873 short middle column (6 lines) with a thin rule under two of its lines
    (underlined words) is still a column: rules are no figure."""
    width = (RIGHT - LEFT - 2 * GUTTER) / 3
    x0 = LEFT + width + GUTTER
    page, _, _ = found_873({2: 298.0, 3: 351.0, 4: 351.0, 5: 298.0})
    rules = tuple(
        Drawing(f"under{row}", Box(x0 + 10, 80 + 14 * row + 9, x0 + 60, 80 + 14 * row + 9.5))
        for row in (2, 5)
    )
    found = content(list(page.pages[0].lines), drawings=rules)
    assert columns_per_page(found) == [3]


@pytest.mark.parametrize("captioned", [True, False])
def test_tick_labels_under_a_figure_in_a_wide_gutter_are_no_column(captioned: bool) -> None:
    """#916: the #895 page with its six labels just under the drawing's box, where a plot
    prints its x-axis ticks: they are the figure's, not a column of text."""
    left = [line(f"L{k}", 70, 80 + 14 * k, 228) for k in range(30)]
    right = [line(f"R{k}", 368, 80 + 14 * k, 526) for k in range(30)]
    ticks = [line(f"tick{k}", 238 + 20 * k, 262, 254 + 20 * k) for k in range(6)]
    caption = [line("Figure 1: a thing", 240, 280, 356)] if captioned else []
    found = content(
        left + right + ticks + caption, drawings=(Drawing("fig", Box(236, 190, 360, 260)),)
    )
    assert columns_per_page(found) == [2]


@pytest.mark.parametrize("side", ["first", "last"])
def test_a_figure_filling_most_of_an_outer_column_leaves_it_a_column(side: str) -> None:
    """#916: the first and last columns always count, however little text a figure leaves
    in them: three lines above a drawing with its labels still stand in a column of a
    two-column page."""
    x0, x1 = (LEFT, MIDDLE - GUTTER / 2) if side == "first" else (MIDDLE + GUTTER / 2, RIGHT)
    other = (MIDDLE + GUTTER / 2, RIGHT) if side == "first" else (LEFT, MIDDLE - GUTTER / 2)
    full = [line(f"F{k}", *other[:1], 80 + 14 * k, other[1]) for k in range(30)]
    text = [line(f"T{k}", x0, 80 + 14 * k, x1) for k in range(3)]
    labels = [line(f"lab{k}", x0 + 10 + 24 * k, 300, x0 + 20 + 24 * k) for k in range(6)]
    drawing = Drawing("fig", Box(x0, 140, x1, 480))
    found = content(full + text + labels, drawings=(drawing,))
    assert columns_per_page(found) == [2]


@pytest.mark.parametrize(("lines", "columns"), [(5, 3), (4, 2)])
def test_a_middle_column_that_is_mostly_a_figure_counts_with_five_lines_off_it(
    lines: int, columns: int
) -> None:
    """#916: a column between two others that holds a figure is a column if at least
    `column_items` (5) lines stand off the figure, and not with fewer."""
    width = (RIGHT - LEFT - 2 * GUTTER) / 3
    x0 = LEFT + width + GUTTER
    labels = [line(f"lab{k}", x0 + 10 + 22 * k, 300, x0 + 20 + 22 * k) for k in range(6)]
    drawing = Drawing("fig", Box(x0, 80 + 14 * lines + 20, x0 + width, 440))
    found = content(three_columns((27, lines, 27)) + labels, drawings=(drawing,))
    assert columns_per_page(found) == [columns]


@given(column_pages())
@example(found_679())
@example(found_873({2: 298.0, 3: 351.0, 4: 351.0, 5: 298.0}))
@example(found_873({}))
def test_any_clean_column_page_reads_column_by_column(page: tuple[Content, list[str], int]) -> None:
    found, expected, count = page
    doc = build_document(found)
    assert texts(doc) == expected
    assert columns_per_page(found) == [count]


# Running heads of a small journal page and its footnotes (#458, #456)


def journal_page(number: int, notes: bool = False) -> tuple[list[TextLine], list[Drawing]]:
    """A page of a journal printed small (600 x 800 here): a head with the page number in
    its line ("Tests in Print ∙ 61" on odd pages, "62 ∙ Journal of Tests ∙ 55/17" on even
    ones) standing 0.5 pt past the top band, a rule drawn just under it, 1.2 em of white,
    then body text; with `notes`, a footnote rule and notes in 8 point down to the paper's
    foot, in the bottom band (#458: Kehren after the crop box fix)."""
    printed = number + 54
    text = f"Tests in Print ∙ {printed}" if number % 2 else f"{printed} ∙ Journal of Tests ∙ 55/17"
    head = line(text, LEFT, 70.5, 300)  # y1 80.5: the band ends at 80
    rule = Drawing(f"rule-{number}", Box(LEFT, 80.0, RIGHT, 80.6))
    body = [  # down to y 733
        line(f"Running text of page {number}, row {k}, set in ten point.", LEFT, 93 + 14 * k, RIGHT)
        for k in range(46)
    ]
    drawings = [rule]
    if notes:
        body = body[:40]  # down to y 649
        body[-1] = short(body[-1])
        drawings.append(Drawing(f"note-rule-{number}", Box(LEFT, 680, LEFT + 150, 680.5)))
        body += [
            line("1", LEFT, 686, LEFT + 4, size=8),
            *(
                line(f"Note one of page {number}, row {k}.", LEFT + 17, 686 + 9 * k, RIGHT, size=8)
                for k in range(4)
            ),
            line("3", LEFT, 722, LEFT + 4, size=8),  # in the bottom band, from y 720
            line("Note three, in the bottom band,", LEFT + 17, 722, RIGHT, size=8),
            line(f"down to the foot of page {number}.", LEFT + 17, 731, 300, size=8),
        ]
    return [head, *body], drawings


def journal(count: int, notes: bool = False) -> Content:
    pages = [journal_page(n, notes) for n in range(1, count + 1)]
    return Content(
        Source("test.pdf", SourceFormat.PDF),
        tuple(
            Page(n, tuple(lines), drawings=tuple(drawings), width=600, height=800)
            for n, (lines, drawings) in enumerate(pages, start=1)
        ),
    )


def test_body_size_heads_with_the_page_number_in_their_line_are_running_heads() -> None:
    """#458: the number goes up with the page, so no two heads repeat word for word; the
    text with the number taken as its offset from the page number does (54 on each page)."""
    doc = build_document(journal(6))
    assert head_roles(doc) == [li.text for n in range(1, 7) for li in journal_page(n)[0][:1]]


def test_a_number_at_the_end_of_a_head_that_does_not_follow_the_page_is_kept() -> None:
    """D-323 still holds: "Algorithm 3" and "Algorithm 4" on pages 3 and 5 differ by two,
    not by the pages' distance, and stay text."""
    heads = {3: "Algorithm 3", 5: "Algorithm 4"}
    doc = build_document(content(*(page_with_head(n, heads.get(n), y=60) for n in range(1, 7))))
    assert texts(doc, BlockKind.FURNITURE) == []


def test_footnotes_in_the_bottom_band_are_neither_footers_nor_running_heads() -> None:
    """#458: notes in 8 point run down into the bottom band; smaller letters alone don't
    make them furniture, and note numbers at the same height on two pages are no head."""
    doc = build_document(journal(4, notes=True))
    assert roles(doc) == ["running-head"] * 4
    notes = "\n".join(b.text for b in doc.blocks if b.kind is BlockKind.FOOTNOTE)
    assert all(f"down to the foot of page {n}." in notes for n in range(1, 5))
    assert all(f"Note one of page {n}, row 0." in notes for n in range(1, 5))


def test_a_page_number_in_body_size_below_the_notes_is_still_a_page_number() -> None:
    """Under the notes' column with less than `apart` em of white, as on ACL pages (chi p3):
    body-size letters end the notes."""
    pages = []
    for n in range(1, 4):
        lines, drawings = journal_page(n, notes=True)
        pages.append(([*lines[1:], line(str(n), LEFT, 745, LEFT + 6)], drawings[1:]))
    doc = build_document(
        Content(
            Source("test.pdf", SourceFormat.PDF),
            tuple(
                Page(n, tuple(lines), drawings=tuple(drawings), width=600, height=800)
                for n, (lines, drawings) in enumerate(pages, start=1)
            ),
        )
    )
    assert roles(doc) == ["page-number"] * 3
    assert doc.page_labels == ("1", "2", "3")


def test_a_german_printed_table_of_contents_is_furniture() -> None:
    """#456: "Inhalt" and "Inhaltsverzeichnis" head a table of contents like "Contents"."""
    for name in ("Inhalt", "Inhaltsverzeichnis"):
        title = line(name, LEFT, 100, 160, size=14)
        entries = []
        for k, (entry, page) in enumerate([("1 Einleitung", "3"), ("2 Methoden", "7")]):
            entries += [line(entry, LEFT, 130 + 14 * k, 200), line(page, 510, 130 + 14 * k, RIGHT)]
        after = column("text-", LEFT, RIGHT, 200, 6)
        doc = build_document(content([title, *entries, *after]))
        assert roles(doc) == ["contents"] * 5


def noted_pages(extra: Callable[[int], list[TextLine]]) -> Content:
    """Four journal pages with notes down to y 739 and no head; `extra` adds lines to each."""
    pages = []
    for n in range(1, 5):
        lines, drawings = journal_page(n, notes=True)
        pages.append(
            Page(n, (*lines[1:], *extra(n)), drawings=tuple(drawings[1:]), width=600, height=800)
        )
    return Content(Source("test.pdf", SourceFormat.PDF), tuple(pages))


def note_texts(doc: Document) -> list[str]:
    return [b.text for b in doc.blocks if b.kind is BlockKind.FOOTNOTE]


def test_a_small_footer_set_tight_under_the_notes_stays_furniture() -> None:
    """#530: 8 pt of white under the notes, less than `apart`; repeated word
    for word at its height, the footer ends the notes and is a running head, as on main."""
    footer = "Journal of Tests, volume 55"
    doc = build_document(noted_pages(lambda n: [line(footer, LEFT, 747, 250, size=7)]))
    assert head_roles(doc) == [footer] * 4
    assert len(note_texts(doc)) == 4
    assert all(footer not in text for text in note_texts(doc))


def test_a_small_page_number_set_tight_under_the_notes_stays_a_page_number() -> None:
    """#530: a number alone on its row ends the notes; a note's mark is never
    alone (its text stands beside it)."""
    doc = build_document(noted_pages(lambda n: [line(str(n + 54), LEFT, 747, LEFT + 8, size=8)]))
    assert doc.page_labels == ("55", "56", "57", "58")
    assert all(not text.rstrip().endswith(("55", "56", "57", "58")) for text in note_texts(doc))


def test_a_small_line_tight_under_the_notes_away_from_their_rule_is_not_a_note() -> None:
    """#530: a one-off small footer at the right of the foot is no note line,
    however close under them: it stays a footer, as on main."""
    received = "Received 3 May 2017"
    foot = [  # one more note row down to y 748, the footer 4 pt under it, in the footer band
        line("and the note goes on.", LEFT + 17, 740, 300, size=8),
        line(received, 400, 752, RIGHT, size=7),
    ]
    doc = build_document(noted_pages(lambda n: foot if n == 1 else []))
    assert texts(doc, BlockKind.FURNITURE) == [received]
    assert all(received not in text for text in note_texts(doc))


def test_a_short_rule_in_the_upper_half_shields_no_lines_from_the_furniture_rules() -> None:
    """#530: only a rule in the lower half is a footnote rule. A small head
    with a short rule over it keeps the shape rule for smaller heads (D-326)."""
    pages = []
    for n in range(1, 4):
        body = [
            line(f"Running text of page {n}, row {k}.", LEFT, 100 + 14 * k, RIGHT)
            for k in range(40)
        ]
        head = line(f"Journal of Tests {n}", LEFT, 34, 250, size=8)
        rule = Drawing(f"top-rule-{n}", Box(LEFT, 30, LEFT + 100, 30.4))
        pages.append(Page(n, (head, *body), drawings=(rule,), width=600, height=800))
    doc = build_document(Content(Source("test.pdf", SourceFormat.PDF), tuple(pages)))
    assert head_roles(doc) == [f"Journal of Tests {n}" for n in range(1, 4)]
