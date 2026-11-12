"""Layout on made-up pages: furniture, columns and reading order (Issue #21, step 1, D-67).

Pages are 600 x 800 points with body text in 10 point, set like a two-column paper between
x 70 and x 526 unless a test says otherwise.
"""

import itertools

from core_strategies import contents
from hypothesis import given
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
from sci2audio.layout.build import page_columns

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
    return [b.text for b in doc.blocks if kind is None or b.kind is kind]


def columns_of(doc: Document) -> list[int]:
    return [page_columns(doc.content, page, LayoutSettings()) for page in doc.content.pages]


# Columns and reading order


def test_two_columns_read_left_column_then_right() -> None:
    left, right = two_columns("a", 100, 20)
    doc = build_document(content(interleaved(left, right)))
    assert texts(doc) == [li.text for li in left + right]
    assert columns_of(doc) == [2]


def test_wide_title_and_figure_cut_the_page_into_bands() -> None:
    title = line("A Title Across The Page", LEFT, 60, RIGHT, size=14)
    top_left, top_right = two_columns("top", 100, 10)
    bottom_left, bottom_right = two_columns("bottom", 440, 10)
    figure = Drawing("d1", Box(LEFT, 320, RIGHT, 420))
    lines = [title, *interleaved(top_left, top_right), *interleaved(bottom_left, bottom_right)]
    doc = build_document(content(lines, drawings=(figure,)))
    expected = [title.text, *(li.text for li in top_left + top_right), ""]
    expected += [li.text for li in bottom_left + bottom_right]
    assert texts(doc) == expected
    assert doc.blocks[21].kind is BlockKind.FIGURE


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


def test_footer_line_numbers_and_side_stamp_are_furniture() -> None:
    body = column("text-", 100, 500, 100, 12)
    numbers = [line(str(k + 1), 70, 100 + 14 * k, 80) for k in range(12)]
    stamp = line("arXiv:2401.00001v1 [cs.CL] 1 Jan 2024", 20, 200, 34, height=400)
    footer = line("Licensed under CC BY 4.0", 100, 760, 300)
    in_text = line("42", 100, 300, 112)  # a bare number inside the text is read
    doc = build_document(content([*body, *numbers, stamp, footer, in_text]))
    furniture = texts(doc, BlockKind.FURNITURE)
    assert sorted(furniture) == sorted([stamp.text, footer.text, *(n.text for n in numbers)])
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


def test_a_sidebar_in_small_letters_beside_the_text_is_furniture() -> None:
    body = column("text-", 170, 550, 100, 40)
    sidebar = [line(f"DOI 10.1/{k}", 40, 300 + 12 * k, 120, size=7) for k in range(6)]
    doc = build_document(content([*body, *sidebar], column("more-", 170, 550, 100, 40)))
    assert texts(doc, BlockKind.FURNITURE) == [li.text for li in sidebar]


# Properties


@given(contents())
def test_layout_never_fails_and_keeps_every_line(found: Content) -> None:
    doc = build_document(found)  # the Document itself checks that every item is in one block
    lines = {li.id: li.text for page in found.pages for li in page.lines}
    for block in doc.blocks:
        if block.kind is not BlockKind.FIGURE:
            assert block.text == lines[block.parts[0].item]
    pages = [doc.content.items()[b.parts[0].item][0].number for b in doc.blocks]
    assert pages == sorted(pages)


@st.composite
def column_pages(draw: st.DrawFn) -> tuple[Content, list[str], int]:
    """A clean page of 1 to 3 columns, its lines stored in any order."""
    count = draw(st.integers(1, 3))
    width = (RIGHT - LEFT - GUTTER * (count - 1)) / count
    lines, expected = [], []
    for col in range(count):
        x0 = LEFT + col * (width + GUTTER)
        for row in range(draw(st.integers(5, 30))):
            share = draw(st.floats(0.85, 1.0))
            lines.append(line(f"c{col}r{row}", x0, 80 + 14 * row, x0 + share * width))
            expected.append(lines[-1].text)
    stored = draw(st.permutations(lines))
    return content(list(stored)), expected, count


@given(column_pages())
def test_any_clean_column_page_reads_column_by_column(page: tuple[Content, list[str], int]) -> None:
    found, expected, count = page
    doc = build_document(found)
    assert texts(doc) == expected
    assert page_columns(found, found.pages[0], LayoutSettings()) == count
