"""Layout on made-up pages: furniture, columns and reading order (Issue #21, step 1, D-67).

Pages are 600 x 800 points with body text in 10 point, set like a two-column paper between
x 70 and x 526 unless a test says otherwise.
"""

import itertools

from core_strategies import contents
from hypothesis import example, given
from hypothesis import strategies as st

from sci2audio.core import (
    BlockKind,
    Box,
    Content,
    Document,
    Drawing,
    Metadata,
    Page,
    Picture,
    Source,
    SourceFormat,
    TextLine,
    TextRun,
)
from sci2audio.layout import LayoutSettings, build_document
from sci2audio.layout.build import columns_per_page
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
    y 62, 1.2 em below the head and 1.2 em above the body (review of #149)."""
    body = column(f"p{number}-", LEFT, RIGHT, 84, 30)
    header = [line(text, x0, 62, x1) for text, x0, x1 in cells]
    return [*([line("Tests in Print", LEFT, 40, 300)] if head else []), *header, *body]


def test_a_continued_table_header_under_a_real_head_is_not_a_running_head() -> None:
    """The pooled count is per height: a real head on 6 of 6 pages at y 40 does not lend its
    pages to a header repeated at y 62 on 2 of them (review of #149, M1)."""
    cells = (("Model Accuracy F1", LEFT, 300),)
    pages = [header_page(n, cells if n in (2, 3) else (), head=True) for n in range(1, 7)]
    doc = build_document(content(*pages))
    assert head_roles(doc) == ["Tests in Print"] * 6
    assert texts(doc).count("Model Accuracy F1") == 2


def test_a_table_header_in_two_cells_on_two_pages_is_not_a_running_head() -> None:
    """The pooled count counts pages, not lines: two cells on each of 2 of 6 pages are 4 lines
    but 2 pages (review of #149, M2)."""
    cells = (("Model", LEFT, 150), ("Accuracy F1", 300, 450))
    pages = [header_page(n, cells if n in (2, 3) else (), head=False) for n in range(1, 7)]
    doc = build_document(content(*pages))
    assert texts(doc, BlockKind.FURNITURE) == []


def test_a_smaller_head_does_not_lend_its_pages_to_a_body_size_line() -> None:
    """A small head on 6 of 6 pages and a body-size header on 2 of them, on the same row: the
    small head is a running head by its own rule; the header is text (review of #149, S1)."""
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


# Properties


@given(contents())
@example(content([line("\n", LEFT, 100, 200)]))  # a line's own break is kept (review of #53)
@example(  # a mark with no block before it stays before the running heads (review of #57)
    Content(
        Source("0", SourceFormat.PDF),
        (
            Page(1, (), (Picture("i0", Box(0, 0, 0, 0)), Picture("i1", Box(3, 0, 14, 21))), ()),
            Page(2, (), (Picture("i2", Box(0, 0, 11, 21)),), ()),
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


@given(column_pages())
def test_any_clean_column_page_reads_column_by_column(page: tuple[Content, list[str], int]) -> None:
    found, expected, count = page
    doc = build_document(found)
    assert texts(doc) == expected
    assert columns_per_page(found) == [count]
