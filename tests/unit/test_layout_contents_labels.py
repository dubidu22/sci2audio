"""Contents pages with their page numbers at the left edge (#529) and page labels printed in a
running head (#535), on made-up pages (600 x 800 points, body text in 10 point)."""

from test_layout import (
    LEFT,
    RIGHT,
    column,
    content,
    head_roles,
    journal,
    journal_page,
    line,
    page_with_head,
    roles,
    short,
    texts,
)

from sci2audio.core import BlockKind, Content, Page, Source, SourceFormat, TextLine
from sci2audio.layout import build_document

# ---- a table of contents with its page numbers at the left edge (#529) -----------------

NUMBERS = LEFT  # the column of page numbers
INDENT = LEFT + 34  # where each entry's text starts, as on the German journal's page


def entry(page: str, rows: list[str], top: float) -> list[TextLine]:
    """An entry: its page number at the left edge, its first row beside it, and the rest of
    its rows at the entry's indent, 11 points apart."""
    first = [line(page, NUMBERS, top, NUMBERS + 5 * len(page)), line(rows[0], INDENT, top, 330)]
    return first + [line(text, INDENT, top + 11 * k, 330) for k, text in enumerate(rows[1:], 1)]


def contents_page(
    title: str, entries: list[tuple[str, list[str]]], after: list[TextLine]
) -> list[TextLine]:
    """A title, the entries 22 points apart from y 130, then `after` (from y 500)."""
    lines, top = [line(title, LEFT, 100, 140, size=14)], 130.0
    for page, rows in entries:
        lines += entry(page, rows, top)
        top += 11 * len(rows) + 11
    return [*lines, *after]


ENTRIES = [
    ("4", ["IN MEMORIAM", "A. Writer, a made-up name for the tests"]),
    (
        "6",
        [
            "ON THE OCCASION",
            "B. Writer/C. Writer",
            "On the history of a made-up theory.",
            "A symposium we wrote for these tests,",
            "in four rows after the first one",
        ],
    ),
    ("17", ["D. Writer", "One more title of our own"]),
    ("30", ["E. Writer", "And the last of them"]),
]


def test_a_contents_page_with_its_page_numbers_at_the_left_edge_is_furniture() -> None:
    """#529: title, every number and every row of each entry, up to four rows after its
    first; the body text after it stays text."""
    for title in ("Contents", "Inhalt", "Inhaltsverzeichnis"):
        after = column("text-", LEFT, RIGHT, 500, 6)
        doc = build_document(content(contents_page(title, ENTRIES, after)))
        rows = sum(len(rows) + 1 for _, rows in ENTRIES)  # each entry's number is a line too
        assert roles(doc) == ["contents"] * (1 + rows), title
        assert texts(doc, BlockKind.PARAGRAPH) == [li.text for li in after]


def test_a_fifth_row_after_an_entry_s_first_ends_the_contents() -> None:
    """An entry runs on for at most `contents_rows` rows: a fifth is not taken, and so
    nothing after it is."""
    rows = ["F. Writer", "row 1", "row 2", "row 3", "row 4", "row 5 is too many"]
    doc = build_document(content(contents_page("Contents", [("3", rows), ("9", ["G"])], [])))
    furniture = texts(doc, BlockKind.FURNITURE)
    assert furniture == ["Contents", "3", *rows[:5]]
    assert "row 5 is too many" in texts(doc, BlockKind.PARAGRAPH)


def test_numbered_rows_without_a_contents_title_stay_text() -> None:
    """A numbered list set like the entries ("1" at the left edge, its text at an indent),
    with no contents title above it, is text."""
    lines = contents_page("Results", [("1", ["First point"]), ("2", ["Second point"])], [])
    doc = build_document(content([*lines, *column("text-", LEFT, RIGHT, 500, 6)]))
    assert roles(doc) == []
    read = "\n".join(texts(doc))
    assert "First point" in read
    assert "Second point" in read


def test_a_numbered_heading_after_the_contents_is_not_an_entry() -> None:
    """Page numbers never go down from entry to entry: "1 Introduction" after the entry for
    page 30, set like an entry, is the text's first heading."""
    heading = [line("1", NUMBERS, 400, NUMBERS + 5), line("Introduction", INDENT, 400, 200)]
    body = column("text-", LEFT, RIGHT, 430, 6)
    doc = build_document(content(contents_page("Inhalt", ENTRIES, [*heading, *body])))
    assert "Introduction" not in texts(doc, BlockKind.FURNITURE)
    assert "Introduction" in "\n".join(texts(doc))
    assert texts(doc, BlockKind.FURNITURE)[-1] == "And the last of them"


def test_a_row_at_the_left_edge_without_a_number_ends_the_contents() -> None:
    """A row that is neither an entry nor at the entries' indent (a body line at the left
    edge, or a section line without a page number) ends the contents; so does a body line
    within reach of a narrow indent but not right of the page numbers."""
    body = column("text-", LEFT, RIGHT, 300, 6)
    doc = build_document(content(contents_page("Contents", ENTRIES[:1], body)))
    assert texts(doc, BlockKind.FURNITURE) == ["Contents", "4", *ENTRIES[0][1]]
    assert texts(doc, BlockKind.PARAGRAPH) == [li.text for li in body]
    narrow = [  # the entry's text 12 points right of its number: less than `contents_reach`
        line("Contents", LEFT, 100, 140, size=14),
        line("4", LEFT, 130, LEFT + 5),
        line("A. Writer", LEFT + 12, 130, 300),
        *body,
    ]
    doc = build_document(content(narrow))
    assert texts(doc, BlockKind.FURNITURE) == ["Contents", "4", "A. Writer"]


def test_numbers_away_from_the_left_edge_or_the_entries_indent_are_no_entries() -> None:
    """After the title, a number in the middle of the page with text beside it is no entry;
    after an entry, a number at the left edge whose text stands far from the entries'
    indent (a table row) ends the contents."""
    middle = [line("12", 300, 130, 310), line("A. Writer", 334, 130, 500)]
    body = column("text-", LEFT, RIGHT, 300, 6)
    doc = build_document(content([line("Contents", LEFT, 100, 140, size=14), *middle, *body]))
    assert roles(doc) == []
    table = [line("9", NUMBERS, 170, NUMBERS + 5), line("0.93", 400, 170, 430)]
    lines = contents_page("Contents", ENTRIES[:1], [*table, *body])
    doc = build_document(content(lines))
    assert texts(doc, BlockKind.FURNITURE) == ["Contents", "4", *ENTRIES[0][1]]


# ---- a page number printed in the running head line (#535) ----------------------------


def test_a_page_number_inside_the_running_head_is_the_page_s_label() -> None:
    """#535: "Tests in Print ∙ 61" on odd pages and "62 ∙ Journal of Tests ∙ 55/17" on even
    ones: the number that goes up with the page (page + 54) is the label; "55/17" is not."""
    doc = build_document(journal(6))
    assert doc.page_labels == ("55", "56", "57", "58", "59", "60")


def test_a_smaller_running_head_gives_its_page_number_too() -> None:
    """A head set smaller than the body, found by its shape (D-326), with the page number
    at its start or end: the label as well."""
    pages = [
        page_with_head(n, f"{n + 10} Journal of Tests" if n % 2 else f"In Print {n + 10}", 40, 8)
        for n in range(1, 5)
    ]
    doc = build_document(content(*pages))
    assert head_roles(doc) == [pages[n][0].text for n in range(4)]
    assert doc.page_labels == ("11", "12", "13", "14")


def test_a_number_in_a_head_that_does_not_follow_the_pages_is_no_label() -> None:
    """The same number on every page ("Heft 55") is a running head but no page label; nor
    is a number that fits one page only."""
    pages = [page_with_head(n, "Journal of Tests ∙ Heft 3", 40, 8) for n in range(1, 6)]
    doc = build_document(content(*pages))
    assert len(head_roles(doc)) == 5
    assert doc.page_labels == ("",) * 5


def test_a_page_number_of_its_own_comes_before_the_one_in_the_head() -> None:
    """A page that prints a page number alone at its foot keeps that label (#31)."""
    pages = []
    for n in range(1, 4):
        lines, drawings = journal_page(n)
        body = lines[:-6]
        body[-1] = short(body[-1])
        pages.append(
            Page(
                n,
                (*body, line(str(n + 100), 300, 770, 316)),
                drawings=tuple(drawings),
                width=600,
                height=800,
            )
        )
    doc = build_document(Content(Source("test.pdf", SourceFormat.PDF), tuple(pages)))
    assert doc.page_labels == ("101", "102", "103")
