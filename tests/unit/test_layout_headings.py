"""Layout on made-up pages: headings and the section tree (Issue #21 step 3).

One column between x 70 and x 526, body text in 10 point on a 14 point line pitch, as in
`test_layout_paragraphs`. Headings stand on a line of their own with white above them.
"""

import itertools

from core_strategies import contents
from hypothesis import given
from test_layout import LEFT, RIGHT, content

from sci2audio.core import BlockKind, Box, Content, Document, Section, TextLine, TextRun
from sci2audio.layout import build_document
from sci2audio.layout.headings import title

PITCH = 14.0
_ids = itertools.count()


def set_line(text: str, y: float, size: float = 10.0, bold: bool = False) -> TextLine:
    """One line at the left of the column, as wide as its letters."""
    font = "Times-Bold" if bold else "Times"
    box = Box(LEFT, y, min(RIGHT, LEFT + 0.5 * size * len(text)), y + size)
    return TextLine(f"h{next(_ids)}", (TextRun(text, font, size, bold=bold),), box)


class Page:
    """Lines set from the top of a page down, a heading with white above it."""

    def __init__(self) -> None:
        self.lines: list[TextLine] = []
        self.y = 80.0

    def heading(self, text: str, size: float = 12.0, bold: bool = True) -> "Page":
        self.y += 8
        self.lines.append(set_line(text, self.y, size, bold))
        self.y += size + 6
        return self

    def body(self, count: int = 4, size: float = 10.0) -> "Page":
        """A paragraph of running text: full lines, the last one ending halfway."""
        for k in range(count):
            n = next(_ids)
            right = RIGHT if k < count - 1 else (LEFT + RIGHT) / 2
            box = Box(LEFT, self.y, right, self.y + size)
            run = TextRun(f"running text {n} goes on", "Times", size)
            self.lines.append(TextLine(f"b{n}", (run,), box))
            self.y += PITCH
        return self

    def build(self) -> Document:
        return build_document(content(self.lines))


def headings(doc: Document) -> list[tuple[str, str]]:
    """Each heading's text and printed number."""
    return [(b.text, b.label) for b in doc.blocks if b.kind is BlockKind.HEADING]


def tree(sections: tuple[Section, ...]) -> list:
    """The section titles and levels, children nested in a list after their parent."""
    out: list = []
    for section in sections:
        out.append((section.title, section.level))
        if section.children:
            out.append(tree(section.children))
    return out


def test_numbered_headings_take_their_level_from_the_number() -> None:
    page = Page().heading("1 Introduction").body().heading("1.1 Setup", 10.0).body()
    page.heading("1.2 Data", 10.0).body().heading("2 Results").body()
    doc = page.build()
    assert headings(doc) == [
        ("1 Introduction", "1"),
        ("1.1 Setup", "1.1"),
        ("1.2 Data", "1.2"),
        ("2 Results", "2"),
    ]
    assert tree(doc.sections) == [
        ("1 Introduction", 1),
        [("1.1 Setup", 2), ("1.2 Data", 2)],
        ("2 Results", 1),
    ]


def test_a_section_runs_from_its_heading_to_the_next_of_its_level() -> None:
    doc = Page().heading("1 Aims").body().heading("1.1 Scope", 10.0).body().heading("2 Ends")
    doc = doc.body().build()
    first, second = doc.sections
    assert (first.start, first.end, second.start, second.end) == (0, 4, 4, 6)
    assert (first.children[0].start, first.children[0].end) == (2, 4)


def test_unnumbered_headings_set_like_the_sections_are_level_one() -> None:
    page = Page().heading("Abstract").body().heading("1 Introduction").body()
    page.heading("2 Method").body().heading("Limitations").body()
    doc = page.build()
    assert headings(doc) == [
        ("Abstract", ""),
        ("1 Introduction", "1"),
        ("2 Method", "2"),
        ("Limitations", ""),
    ]
    assert [s.level for s in doc.sections] == [1, 1, 1, 1]


def test_a_section_name_counts_in_any_bold_style() -> None:
    """An abstract's heading is often set smaller than the sections' headings."""
    page = Page().heading("Abstract", 9.0).body(3, 9.0).heading("1 Introduction", 14.0).body()
    page.heading("2 Method", 14.0).body()
    doc = page.build()
    assert headings(doc) == [("Abstract", ""), ("1 Introduction", "1"), ("2 Method", "2")]
    assert [s.level for s in doc.sections] == [1, 1, 1]


def test_title_and_authors_at_the_top_are_not_headings() -> None:
    page = Page().heading("A Study of Things", 16.0).heading("Ann Author")
    page.heading("Some University", 12.0, bold=False).heading("Abstract").body()
    page.heading("1 Introduction").body().heading("2 Method").body()
    assert headings(page.build()) == [
        ("Abstract", ""),
        ("1 Introduction", "1"),
        ("2 Method", "2"),
    ]


def test_a_bold_line_in_another_style_without_a_number_is_not_a_heading() -> None:
    """A table's header row or an example's label in the subsections' style."""
    page = Page().heading("1 Data").body().heading("1.1 Setup", 10.0).body()
    page.heading("Structure Example", 10.0).body(2)
    assert headings(page.build()) == [("1 Data", "1"), ("1.1 Setup", "1.1")]


def test_a_numbered_line_in_another_style_is_not_a_heading() -> None:
    page = Page().heading("1 Data").body().heading("2 Rows", 10.0).body().heading("3 End")
    assert headings(page.body().build()) == [("1 Data", "1"), ("3 End", "3")]


def test_a_bold_lead_in_or_a_number_alone_is_not_a_heading() -> None:
    page = Page().heading("1 Data").body().heading("A For every submission:").body()
    page.heading("80.2", 10.0).body().heading("2 End").body()
    assert headings(page.build()) == [("1 Data", "1"), ("2 End", "2")]


def test_appendices_under_a_common_title_move_one_level_down() -> None:
    page = Page().heading("1 Introduction").body().heading("References").body()
    page.heading("Appendices", 14.0).heading("A Proofs").body().heading("A.1 Lemmas", 10.0)
    doc = page.body().build()
    assert tree(doc.sections) == [
        ("1 Introduction", 1),
        ("References", 1),
        ("Appendices", 1),
        [("A Proofs", 2), [("A.1 Lemmas", 3)]],
    ]


def test_without_numbers_a_larger_bold_style_used_more_than_once_is_level_one() -> None:
    page = Page().heading("Ann Author", 12.0).body(2, 9.0).heading("Summary", 14.0).body()
    page.heading("Statement of need", 14.0).body().heading("Example", 14.0).body()
    doc = page.build()
    assert headings(doc) == [("Summary", ""), ("Statement of need", ""), ("Example", "")]
    assert [s.level for s in doc.sections] == [1, 1, 1]


def test_without_numbers_a_bold_body_size_line_is_not_a_heading() -> None:
    """A figure's bold labels, set like the text, in a paper with no headings."""
    page = Page().body().heading("Total", 10.0).heading("Extrinsic", 10.0).body()
    page.heading("Intrinsic", 10.0).body()
    doc = page.build()
    assert headings(doc) == []
    assert doc.sections == ()


def test_a_heading_over_two_lines_is_one_title() -> None:
    page = Page().heading("1 Data").body().heading("2 Relevance for Ellipsis-Dependent")
    page.lines.append(set_line("Reasoning", page.y - 4, 12.0, bold=True))
    page.y += 14
    doc = page.body().build()
    assert [s.title for s in doc.sections] == [
        "1 Data",
        "2 Relevance for Ellipsis-Dependent Reasoning",
    ]


def test_title_joins_a_word_split_at_a_line_end() -> None:
    assert title("2 Semi-\nring weights") == "2 Semiring weights"
    assert title("2.4 Ellipsis-\nDependent Reasoning") == "2.4 Ellipsis-Dependent Reasoning"
    assert title(" Abstract \n") == "Abstract"


@given(contents())
def test_sections_start_at_headings_and_carry_their_text(found: Content) -> None:
    """On any content: each section starts at a heading block whose lines are its title, and
    each heading starts a section (the Document checks that sections nest)."""
    doc = build_document(found)
    sections, stack = [], list(doc.sections)
    while stack:
        section = stack.pop(0)
        sections.append(section)
        stack[:0] = section.children
    heads = [i for i, b in enumerate(doc.blocks) if b.kind is BlockKind.HEADING]
    assert [s.start for s in sections] == heads
    for section in sections:
        assert section.title == title(doc.blocks[section.start].text)


def test_one_numbered_bold_line_does_not_make_a_document_numbered() -> None:
    page = Page().heading("Summary", 14.0).body().heading("3 GPUs", 14.0).body()
    page.heading("Statement of need", 14.0).body()
    doc = page.build()
    assert [text for text, _ in headings(doc)] == ["Summary", "3 GPUs", "Statement of need"]
    assert [s.level for s in doc.sections] == [1, 1, 1]
