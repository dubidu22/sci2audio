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
    """The text blocks: paragraphs, and headings, which step 3 of #21 tells apart."""
    return [b.text for b in doc.blocks if b.kind in {BlockKind.PARAGRAPH, BlockKind.HEADING}]


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


def test_two_line_paragraphs_with_indented_first_lines_stay_apart() -> None:
    """The second paragraph's indent is measured against the line before it, not against
    the first paragraph's own indented first line (nowak p4 footnotes 7 and 8)."""
    intro = lines("p", LEFT, RIGHT, 100, 3)
    first = lines("a", LEFT, RIGHT, 100 + 3 * PITCH, 2, indent=15, last=1.0)
    second = lines("b", LEFT, RIGHT, 100 + 5 * PITCH, 2, indent=15)
    doc = build_document(content([*intro, *first, *second]))
    assert paragraphs(doc) == [joined(intro), joined(first), joined(second)]


@given(st.sampled_from([(1, 2, 1), (1, 2, 1, 3, 1), (2, 1, 2, 1)]))
def test_hanging_entries_of_one_and_two_lines_stay_apart(counts: tuple[int, ...]) -> None:
    """Entries end in a short line; a two-line entry between one-line entries has its
    second line further in, which is not the indented first line of a paragraph."""
    entries, top = [], 100.0
    for n, count in enumerate(counts):
        entry = [line(f"e{n}-0", LEFT, top, RIGHT if count > 1 else 300)]
        entry += [
            line(f"e{n}-{k}", LEFT + 15, top + PITCH * k, RIGHT if k < count - 1 else 320)
            for k in range(1, count)
        ]
        entries.append(entry)
        top += PITCH * count
    doc = build_document(content([li for entry in entries for li in entry]))
    assert paragraphs(doc) == [joined(entry) for entry in entries]


def test_a_paragraph_does_not_end_inside_a_hyphenated_word() -> None:
    """A full line ending in a word split by a hyphen goes on, also between entries of a
    list with hanging indents (the second line here starts further in)."""
    first = line("[18] G. Montam-", LEFT, 100, RIGHT)
    second = line("baux, The European Physical Journal B", LEFT + 15, 100 + PITCH, 320)
    after = line("[19] A. Name, Journal", LEFT, 100 + 2 * PITCH, 300)
    doc = build_document(content([first, second, after]))
    assert paragraphs(doc) == [joined([first, second]), after.text]


def test_a_bold_run_in_head_does_not_make_its_line_bold() -> None:
    """A paragraph that opens with a bold head on its first line ("Definition 1.") is one
    paragraph, whether the head is a piece of its own or a run of the line."""
    head = bold("Domain-specific Continual Pre-training", LEFT, 100, 420)
    rest = line("In the", 432, 100, RIGHT)
    body = lines("a", LEFT, RIGHT, 100 + PITCH, 4)
    runs = (
        TextRun("Definition 1.", "Times-Bold", 10.0, bold=True),
        TextRun(" A", "Times-Italic", 10.0, italic=True),
        TextRun(" probabilistic context-free gram-", "Times-BoldItalic", 10.0, bold=True),
    )
    top = 100 + 6 * PITCH
    defined = TextLine("def", runs, Box(LEFT, top, RIGHT, top + 10))
    more = lines("b", LEFT, RIGHT, top + PITCH, 3)
    doc = build_document(content([head, rest, *body, defined, *more]))
    first = f"{head.text} {rest.text}\n{joined(body)}"
    assert paragraphs(doc) == [first, joined([defined, *more])]


def test_a_footnote_mark_or_subscripts_do_not_cut_a_paragraph() -> None:
    """A line's size is the size most of its letters have: a small piece on its baseline
    (a footnote mark, a subscript) does not make it a line in smaller letters."""
    text = lines("a", LEFT, RIGHT, 100, 6)
    y1, y2 = 100 + PITCH, 100 + 3 * PITCH
    marked = [
        line("rules of the grammar.", LEFT, y1, RIGHT - 6),
        line("1", RIGHT - 5, y1 - 3, RIGHT, size=7),
    ]
    subscripts = [
        line("where x", LEFT, y2, 120),
        line("ij", 121, y2 + 3, 128, size=7),
        line("is the weight of the edge from y", 131, y2, RIGHT - 9),
        line("kl", RIGHT - 8, y2 + 3, RIGHT, size=7),
    ]
    rows = [[li] for li in text]
    rows[1], rows[3] = marked, subscripts
    doc = build_document(content([li for row in rows for li in row]))
    assert paragraphs(doc) == ["\n".join(" ".join(li.text for li in row) for row in rows)]


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


def test_the_gap_after_a_subscript_is_measured_from_the_line_s_end() -> None:
    """A subscript stored as a piece of its own may stand below the end of the piece before
    it; the white after them starts where the line's letters end, not where the subscript
    does (liu p2 "Next one feeds n(-1)E | into the")."""
    text = lines("a", LEFT, RIGHT, 100, 5)
    y = 100 + 2 * PITCH
    split = [
        line("ing integral. Next one feeds n", LEFT, y, 300),
        line("E", 262, y + 3, 270, size=7),
        line("into the", 316, y, RIGHT),
    ]
    # the row below has a sliver of white halfway between the subscript and "into the"
    below = [
        line("band off-diagonal", LEFT, y + PITCH, 292.9),
        line("terms", 293.1, y + PITCH, RIGHT),
    ]
    rows = [[li] for li in text]
    rows[2:4] = [split, below]
    doc = build_document(content([li for row in rows for li in row]))
    assert paragraphs(doc) == ["\n".join(" ".join(li.text for li in row) for row in rows)]


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


@st.composite
def run_on_pages(draw: st.DrawFn) -> tuple:
    """A page of 2 or 3 columns whose paragraphs may end in a full line: inside a column
    the next paragraph then starts with an indent or after white; at a column's foot it
    runs on into the next column. The first column may end in a footnote under a short
    rule, which follows the paragraph open there. Stored in any order."""
    count = draw(st.integers(2, 3))
    width = (RIGHT - LEFT - GUTTER * (count - 1)) / count
    stored: list[TextLine] = []
    found: list[list[TextLine]] = []  # the paragraphs in reading order
    note, after = None, -1  # the footnote, and the paragraph it follows
    drawings: tuple = ()
    running = False  # the last paragraph runs on into this column
    for col in range(count):
        x0, top = LEFT + col * (width + GUTTER), 80.0
        chunks = draw(st.integers(2, 3))
        for k in range(chunks):
            last_chunk = k == chunks - 1
            run_on = last_chunk and col < count - 1 and draw(st.booleans())
            full = run_on if last_chunk else draw(st.booleans())
            goes_on = running and k == 0
            ended_full = k > 0 and found[-1][-1].box.x1 >= x0 + width - 1
            if goes_on:
                indent, gap = 0.0, 0.0
            else:
                ways = ["indent", "white", "both"] if ended_full else ["none", "indent", "white"]
                way = draw(st.sampled_from(ways))
                indent = 12.0 if way in ("indent", "both") else 0.0
                gap = 8.0 if k and way in ("white", "both") else 0.0
            top += gap
            text = lines(
                f"c{col}p{k}-",
                x0,
                x0 + width,
                top,
                draw(st.integers(3, 5)),
                indent=indent,
                last=1.0 if full else draw(st.floats(0.1, 0.7)),
            )
            stored += text
            if goes_on:
                found[-1] += text
            else:
                found.append(text)
            top += PITCH * len(text)
            running = run_on
        if col == 0 and draw(st.booleans()):
            drawings = (Drawing("rule", Box(x0, 700, x0 + 60, 700.5)),)
            note = line("1 A note in small letters.", x0, 705, x0 + 0.6 * width, size=8)
            stored.append(note)
            after = len(found) - 1
    expected = [joined(paragraph) for paragraph in found]
    if note:
        expected.insert(after + 1, note.text)
    return content(draw(st.permutations(stored)), drawings=drawings), expected


@given(run_on_pages())
def test_paragraphs_run_on_across_columns_and_past_a_footnote(page: tuple) -> None:
    found, expected = page
    assert paragraphs(build_document(found)) == expected
