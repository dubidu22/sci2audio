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
    the figure is read between the columns' paragraphs (#905): with a caption that names
    it, the figure holds its labels."""
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
    held = ["fig", *upper, *lower] if captioned else ["fig"]
    assert [[ids.get(p.item, p.item) for p in b.parts] for b in figures] == [held]
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
    sentence: one that runs on into the right column is never cut by the float, which
    then follows it, #61.)"""
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
