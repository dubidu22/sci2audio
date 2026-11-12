"""Layout on made-up pages: paragraphs and lines split by extraction (Issue #21 step 2, #27).

Pages are 600 x 800 points with body text in 10 point on a 14 point line pitch, one column
between x 70 and x 526 or two columns with a 16 point gutter, as in `test_layout`.
"""

from hypothesis import given
from hypothesis import strategies as st
from test_layout import GUTTER, LEFT, MIDDLE, RIGHT, content, line

from sci2audio.core import BlockKind, Box, Document, Drawing, TextLine, TextRun
from sci2audio.layout import build_document

PITCH = 14.0
LEFT_END, RIGHT_START = MIDDLE - GUTTER / 2, MIDDLE + GUTTER / 2


def lines(name: str, x0: float, x1: float, top: float, count: int, **shape: float) -> list:
    """A paragraph: `count` full lines from `top`; `indent` moves the first line in, `last`
    is the share of the width the last line fills (1 = full)."""
    found = []
    for k in range(count):
        start = x0 + (shape.get("indent", 0.0) if k == 0 else 0.0)
        end = x1 if k < count - 1 else x0 + shape.get("last", 0.5) * (x1 - x0)
        found.append(line(f"{name}{k}", start, top + PITCH * k, end))
    return found


def bold(text: str, x0: float, y0: float, x1: float) -> TextLine:
    line_ = line(text, x0, y0, x1)
    return TextLine(line_.id, (TextRun(text, "Times-Bold", 10.0, bold=True),), line_.box)


def paragraphs(doc: Document) -> list[str]:
    return [b.text for b in doc.blocks if b.kind is BlockKind.PARAGRAPH]


def joined(*groups: list[TextLine]) -> str:
    return "\n".join(li.text for group in groups for li in group)


# One column


def test_the_lines_of_a_paragraph_are_one_block() -> None:
    text = lines("a", LEFT, RIGHT, 100, 6)
    doc = build_document(content(text))
    assert paragraphs(doc) == [joined(text)]
    block = doc.blocks[0]
    assert [part.item for part in block.parts] == [li.id for li in text]
    assert [block.text[p.start :].split("\n")[0] for p in block.parts] == [li.text for li in text]


def test_a_short_last_line_ends_a_paragraph() -> None:
    first = lines("a", LEFT, RIGHT, 100, 4, last=0.6)
    second = lines("b", LEFT, RIGHT, 100 + 4 * PITCH, 4)
    assert paragraphs(build_document(content(first + second))) == [joined(first), joined(second)]


def test_an_indented_first_line_starts_a_paragraph_after_a_full_line() -> None:
    first = lines("a", LEFT, RIGHT, 100, 4, last=1.0)
    second = lines("b", LEFT, RIGHT, 100 + 4 * PITCH, 4, indent=15)
    assert paragraphs(build_document(content(first + second))) == [joined(first), joined(second)]


def test_more_white_than_the_line_spacing_starts_a_paragraph() -> None:
    first = lines("a", LEFT, RIGHT, 100, 4, last=1.0)
    second = lines("b", LEFT, RIGHT, 100 + 4 * PITCH + 10, 4)
    assert paragraphs(build_document(content(first + second))) == [joined(first), joined(second)]


def test_a_change_of_size_or_weight_starts_a_paragraph() -> None:
    heading = bold("2.1 Methods and Data", LEFT, 100, 250)
    body = lines("a", LEFT, RIGHT, 100 + PITCH, 4)
    big = line("3 Results", LEFT, 100 + 6 * PITCH, 200, size=12)
    more = lines("b", LEFT, RIGHT, 100 + 8 * PITCH, 4)
    doc = build_document(content([heading, *body, big, *more]))
    assert paragraphs(doc) == [heading.text, joined(body), big.text, joined(more)]


def test_entries_with_hanging_indents_stay_apart() -> None:
    entries, top = [], 100.0
    for name, count in (("a", 3), ("b", 2), ("c", 3)):
        entry = [line(f"{name}0", LEFT, top, RIGHT)]
        entry += [line(f"{name}{k}", LEFT + 15, top + PITCH * k, RIGHT) for k in range(1, count)]
        entries.append(entry)
        top += PITCH * count
    doc = build_document(content([li for entry in entries for li in entry]))
    assert paragraphs(doc) == [joined(entry) for entry in entries]


def test_a_narrower_block_is_not_cut_at_every_line() -> None:
    """An abstract set narrower than its column: its lines end before the column's edge."""
    abstract = lines("a", LEFT + 20, RIGHT - 20, 100, 5)
    body = lines("b", LEFT, RIGHT, 100 + 6 * PITCH, 5)
    doc = build_document(content(abstract + body))
    assert paragraphs(doc) == [joined(abstract), joined(body)]


# Across columns and pages


def two_column_text(left_count: int = 12, right_top: float = 100) -> tuple[list, list]:
    left = lines("l", LEFT, LEFT_END, 100, left_count, last=1.0)
    right = lines("r", RIGHT_START, RIGHT, right_top, 12)
    return left, right


def test_a_paragraph_runs_on_into_the_next_column() -> None:
    left, right = two_column_text()
    assert paragraphs(build_document(content(left + right))) == [joined(left, right)]


def test_an_indented_line_at_the_top_of_a_column_starts_a_paragraph() -> None:
    left, right = two_column_text()
    right[0] = line(right[0].text, RIGHT_START + 15, 100, RIGHT)
    assert paragraphs(build_document(content(left + right))) == [joined(left), joined(right)]


def test_a_heading_at_the_top_of_the_next_column_is_not_skipped() -> None:
    left, right = two_column_text(right_top=100 + PITCH)
    heading = bold("2 Related Work", RIGHT_START, 100, RIGHT_START + 90)
    doc = build_document(content([*left, heading, *right]))
    assert paragraphs(doc) == [joined(left), heading.text, joined(right)]


def test_a_paragraph_runs_on_across_a_page_and_the_page_number_waits() -> None:
    first = [*lines("a", LEFT, RIGHT, 100, 10, last=1.0), line("1", 295, 770, 305)]
    second = [*lines("b", LEFT, RIGHT, 100, 4), line("2", 295, 770, 305)]
    doc = build_document(content(first, second))
    assert [b.text for b in doc.blocks] == [joined(first[:-1], second[:-1]), "1", "2"]
    assert [b.kind for b in doc.blocks[1:]] == [BlockKind.FURNITURE] * 2


def test_a_footnote_does_not_cut_a_paragraph_and_follows_it() -> None:
    left, right = two_column_text(left_count=10)
    rule = Drawing("rule", Box(LEFT, 700, LEFT + 60, 700.5))
    note = line("1 A note in small letters.", LEFT, 705, LEFT + 120, size=8)
    doc = build_document(content([*left, note, *right], drawings=(rule,)))
    texts = [b.text for b in doc.blocks]
    assert texts == [joined(left, right), "", note.text]


def test_a_table_at_the_top_of_the_next_page_does_not_cut_a_paragraph() -> None:
    first = lines("a", LEFT, RIGHT, 100, 10, last=1.0)
    cells = [
        line(f"c{r}{c}", LEFT + 120 * c, 80 + 12 * r, LEFT + 60 + 120 * c, size=9)
        for r in range(4)
        for c in range(3)
    ]
    caption = line("Table 1: Numbers.", 200, 140, 300, size=9)
    rest = lines("b", LEFT, RIGHT, 180, 4)
    doc = build_document(content(first, [*cells, caption, *rest]))
    assert paragraphs(doc)[0] == joined(first, rest)
    assert paragraphs(doc)[1:] == [*(li.text for li in cells), caption.text]


# Lines split by extraction (#27)


def test_a_line_split_at_a_wide_word_gap_is_one_line_again() -> None:
    text = lines("a", LEFT, RIGHT, 100, 5)
    split = [
        line("words before a wide", LEFT, 100 + PITCH, 300),
        line("gap", 316, 100 + PITCH, RIGHT),
    ]
    text[1:2] = split
    doc = build_document(content(text))
    expected = joined(text).replace("wide\ngap", "wide gap")
    assert paragraphs(doc) == [expected]
    assert [p.item for p in doc.blocks[0].parts] == [li.id for li in text]


def test_a_numbered_heading_split_from_its_title_is_one_line() -> None:
    number, title = line("2.1", LEFT, 100, LEFT + 15), line("Probing Models", LEFT + 27, 100, 200)
    body = lines("a", LEFT, RIGHT, 100 + PITCH, 4)
    doc = build_document(content([number, title, *body]))
    assert paragraphs(doc)[0].startswith("2.1 Probing Models")


def test_two_columns_with_a_narrow_gutter_are_not_joined() -> None:
    """The gutter is barely wider than a wide word gap; the columns still stay apart."""
    gutter = 10.0
    left = lines("l", LEFT, MIDDLE - gutter / 2, 100, 12, last=1.0)
    right = lines("r", MIDDLE + gutter / 2, RIGHT, 100, 12)
    stored = [li for pair in zip(left, right, strict=True) for li in pair]
    doc = build_document(content(stored))
    assert paragraphs(doc) == [joined(left, right)]


def test_table_cells_stay_apart() -> None:
    above = lines("a", LEFT, RIGHT, 100, 3)
    cells = [
        [line(f"r{r}c{c}", LEFT + 150 * c, 160 + PITCH * r, LEFT + 60 + 150 * c) for c in range(3)]
        for r in range(4)
    ]
    doc = build_document(content([*above, *(cell for row in cells for cell in row)]))
    found = [text for block in paragraphs(doc) for text in block.split("\n")]
    assert found == [li.text for li in above] + [cell.text for row in cells for cell in row]


# Properties


@st.composite
def paragraph_pages(draw: st.DrawFn) -> tuple:
    """A page of 1 to 3 columns of paragraphs that end in a short line, any of them set
    apart by white or begun with an indent, stored in any order."""
    count = draw(st.integers(1, 3))
    width = (RIGHT - LEFT - GUTTER * (count - 1)) / count
    stored, expected = [], []
    for col in range(count):
        x0, top = LEFT + col * (width + GUTTER), 80.0
        for _ in range(draw(st.integers(2, 4))):
            indent = draw(st.sampled_from([0.0, 12.0]))
            text = lines(
                f"c{col}t{int(top)}-",
                x0,
                x0 + width,
                top,
                draw(st.integers(3, 6)),
                indent=indent,
                last=draw(st.floats(0.1, 0.7)),
            )
            stored += text
            expected.append(joined(text))
            top += PITCH * len(text) + draw(st.sampled_from([0.0, 8.0]))
    return content(draw(st.permutations(stored))), expected


@given(paragraph_pages())
def test_any_clean_page_keeps_each_paragraph_in_one_block(page: tuple) -> None:
    found, expected = page
    assert paragraphs(build_document(found)) == expected
