"""Layout on made-up pages: headings and the section tree (Issue #21 step 3), and the
file's outline as a second signal for headings (#24, D-270 to D-272).

One column between x 70 and x 526, body text in 10 point on a 14 point line pitch, as in
`test_layout_paragraphs`. Headings stand on a line of their own with white above them.
"""

import dataclasses
import itertools

from core_strategies import contents
from hypothesis import given
from hypothesis import strategies as st
from test_layout import LEFT, RIGHT, content

from sci2audio.core import (
    BlockKind,
    Box,
    Content,
    Document,
    Metadata,
    OutlineEntry,
    Section,
    TextLine,
    TextRun,
)
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

    def build(self, *outline: OutlineEntry, metadata: Metadata | None = None) -> Document:
        """The document of this page, with the outline entries given (all on page 1)."""
        found = content(self.lines, metadata=metadata)
        return build_document(dataclasses.replace(found, outline=outline))


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


def test_a_title_starting_with_a_one_letter_word_gets_no_made_up_number() -> None:
    """Review of #50: "A" counts as a number only where letters number headings."""
    page = Page().heading("1 Introduction").body().heading("2 Method").body()
    page.heading("A Note on Ethics").body()
    doc = page.build()
    assert headings(doc)[-1] == ("A Note on Ethics", "")
    assert [s.level for s in doc.sections] == [1, 1, 1]


def test_letters_number_appendices_when_more_than_one_heading_uses_them() -> None:
    page = Page().heading("1 Introduction").body().heading("2 Method").body()
    page.heading("A Proofs").body().heading("A.1 Lemmas", 10.0).body()
    assert [label for _, label in headings(page.build())] == ["1", "2", "A", "A.1"]


def test_sizes_a_rounding_error_apart_are_one_style() -> None:
    """Review of #50: 11.94 and 12.0 point headings are one style, not two."""
    page = Page().heading("1 Introduction", 11.94).body().heading("2 Method", 12.0).body()
    page.heading("3 Results", 11.94).body().heading("References", 12.0).body()
    doc = page.build()
    assert [s.title for s in doc.sections] == [
        "1 Introduction",
        "2 Method",
        "3 Results",
        "References",
    ]


@st.composite
def numbered_papers(draw: st.DrawFn) -> tuple[Page, list[tuple[str, int, str]]]:
    """A page of numbered sections and subsections over paragraphs, maybe an abstract
    first and references last, with the headings it holds: title, level, number."""
    names = st.sampled_from(["Introduction", "Method", "Results", "Data", "Discussion"])
    page, expected = Page(), []

    def heading(text: str, level: int, number: str) -> None:
        page.heading(text, 12.0 if level == 1 else 10.0)
        expected.append((text, level, number))
        page.body(draw(st.integers(2, 3)))

    if draw(st.booleans()):
        heading("Abstract", 1, "")
    for section in range(1, draw(st.integers(2, 3)) + 1):
        heading(f"{section} {draw(names)}", 1, str(section))
        for sub in range(1, draw(st.integers(0, 1)) + 1):
            heading(f"{section}.{sub} {draw(names)}", 2, f"{section}.{sub}")
    if draw(st.booleans()):
        heading("References", 1, "")
    return page, expected


@given(numbered_papers())
def test_any_numbered_paper_gets_its_headings_and_levels(
    paper: tuple[Page, list[tuple[str, int, str]]],
) -> None:
    """Review of #50: a property that sees headings in every example."""
    page, expected = paper
    doc = page.build()
    sections, stack = [], list(doc.sections)
    while stack:
        section = stack.pop(0)
        sections.append(section)
        stack[:0] = section.children
    found = [(s.title, s.level, doc.blocks[s.start].label) for s in sections]
    assert found == expected


# The outline as a second signal (#24): it adds, never removes (D-270); the font rules' level
# stands (D-271); an entry matches on its own page only (D-272).


def plain(page: Page, text: str) -> Page:
    """A heading set like the body text: not bold, not larger, so the font rules miss it."""
    return page.heading(text, 10.0, bold=False)


def test_the_outline_adds_a_heading_set_like_the_body_text() -> None:
    page = Page().heading("1 Introduction").body().heading("2 Method").body()
    plain(page, "Limitations").body()
    assert headings(page.build()) == [("1 Introduction", "1"), ("2 Method", "2")]
    doc = page.build(OutlineEntry("Introduction", 1, 1), OutlineEntry("Limitations ", 1, 1))
    assert headings(doc)[-1] == ("Limitations", "")
    assert tree(doc.sections) == [("1 Introduction", 1), ("2 Method", 1), ("Limitations", 1)]


def test_an_added_heading_with_a_number_takes_its_level_and_label_from_it() -> None:
    page = Page().heading("1 Introduction").body().heading("2 Method").body()
    plain(page, "2.1 Fine Print").body()
    doc = page.build(OutlineEntry("Fine Print", 1, 1))  # the outline's level 1 loses
    assert headings(doc)[-1] == ("2.1 Fine Print", "2.1")
    assert tree(doc.sections) == [("1 Introduction", 1), ("2 Method", 1), [("2.1 Fine Print", 2)]]


def test_an_entry_may_carry_the_printed_number_itself() -> None:
    page = Page().heading("1 Introduction").body().heading("2 Method").body()
    plain(page, "3 Outlook").body()
    assert headings(page.build(OutlineEntry("3 Outlook", 1, 1)))[-1] == ("3 Outlook", "3")


def test_an_added_heading_without_a_number_takes_the_entry_level() -> None:
    page = Page().heading("Summary", 14.0).body().heading("Statement of need", 14.0).body()
    plain(page, "A Closer Look").body()
    doc = page.build(
        OutlineEntry("Summary", 1, 1),
        OutlineEntry("Statement of need", 1, 1),
        OutlineEntry("A Closer Look", 2, 1),
    )
    assert headings(doc)[-1] == ("A Closer Look", "")  # "A" is no number here
    assert tree(doc.sections) == [("Summary", 1), ("Statement of need", 1), [("A Closer Look", 2)]]


def test_the_font_rules_level_stands_when_the_outline_disagrees() -> None:
    page = Page().heading("1 Introduction").body().heading("1.1 Setup", 10.0).body()
    page.heading("2 Method").body()
    doc = page.build(OutlineEntry("Introduction", 1, 1), OutlineEntry("Setup", 1, 1))
    assert tree(doc.sections) == [("1 Introduction", 1), [("1.1 Setup", 2)], ("2 Method", 1)]


def test_the_font_rules_level_stands_for_unnumbered_headings_too() -> None:
    """Review of #146 (M1): without numbers the outline's level would differ (D-271)."""
    page = Page().heading("Summary", 14.0).body().heading("Details", 12.0).body()
    page.heading("Statement of need", 14.0).body().heading("More", 12.0).body()
    alone = page.build()
    assert tree(alone.sections) == [
        ("Summary", 1),
        [("Details", 2)],
        ("Statement of need", 1),
        [("More", 2)],
    ]
    doc = page.build(OutlineEntry("Summary", 1, 1), OutlineEntry("Details", 1, 1))
    assert tree(doc.sections) == tree(alone.sections)


def test_an_added_numbered_heading_under_the_appendices_title_moves_down_too() -> None:
    """Review of #146 (S1): the same shift as the font rules give "A.1"."""
    page = Page().heading("1 Introduction").body().heading("2 Method").body()
    page.heading("Appendices", 16.0).body().heading("A Proofs").body()
    page.heading("A.1 First", 10.0).body()
    plain(page, "A.2 Second").body()
    page.heading("B More").body().heading("B.1 Third", 10.0).body()
    alone = page.build()
    assert ("A.2 Second", "") not in headings(alone)
    doc = page.build(OutlineEntry("Second", 1, 1))
    assert tree(doc.sections) == [
        ("1 Introduction", 1),
        ("2 Method", 1),
        ("Appendices", 1),
        [
            ("A Proofs", 2),
            [("A.1 First", 3), ("A.2 Second", 3)],
            ("B More", 2),
            [("B.1 Third", 3)],
        ],
    ]


def test_the_first_of_two_entries_naming_one_block_decides_its_level() -> None:
    """Review of #146 (N1)."""
    page = Page().heading("Summary", 14.0).body().heading("Statement of need", 14.0).body()
    plain(page, "A Closer Look").body()
    first = (OutlineEntry("Summary", 1, 1), OutlineEntry("Statement of need", 1, 1))
    doc = page.build(
        *first, OutlineEntry("A Closer Look", 2, 1), OutlineEntry("A Closer Look", 1, 1)
    )
    assert tree(doc.sections)[-1] == [("A Closer Look", 2)]


def test_a_heading_missing_from_the_outline_stays() -> None:
    """Outlines are often partial (arsiwalla lists 5 of its 8 headings)."""
    page = Page().heading("Abstract").body().heading("1 Introduction").body()
    page.heading("2 Method").body().heading("References").body()
    doc = page.build(OutlineEntry("Introduction", 1, 1))
    assert [text for text, _ in headings(doc)] == [
        "Abstract",
        "1 Introduction",
        "2 Method",
        "References",
    ]


def test_a_title_root_is_not_a_heading_and_its_children_move_up() -> None:
    """The liu paper: its single top entry is the paper's title, set large on page 1."""
    page = Page().heading("A Study of Things", 16.0).body()
    plain(page, "Limitations").body()
    doc = page.build(OutlineEntry("A Study of Things", 1, 1), OutlineEntry("Limitations", 2, 1))
    assert headings(doc) == [("Limitations", "")]
    assert tree(doc.sections) == [("Limitations", 1)]


def test_an_entry_naming_the_files_own_title_is_not_a_heading() -> None:
    page = Page().heading("A Study of Things", 16.0).body()
    plain(page, "Limitations").body()
    doc = page.build(
        OutlineEntry("A Study of Things", 1, 1),
        OutlineEntry("Limitations", 1, 1),
        metadata=Metadata(title="A study of  things"),
    )
    assert headings(doc) == [("Limitations", "")]


def test_an_entry_with_two_matching_blocks_or_none_on_its_page_adds_nothing() -> None:
    page = Page().heading("1 Introduction").body().heading("2 Method").body()
    plain(page, "Limitations").body()
    plain(page, "Limitations").body()
    plain(page, "Outlook").body()
    found = [("1 Introduction", "1"), ("2 Method", "2")]
    assert headings(page.build(OutlineEntry("Limitations", 1, 1))) == found
    assert headings(page.build(OutlineEntry("Discussion", 1, 1))) == found
    assert headings(page.build(OutlineEntry("Outlook", 1))) == found  # points at no page


def test_an_entry_matches_on_its_own_page_only() -> None:
    first = Page().heading("1 Introduction").body().heading("2 Method").body()
    second = plain(Page(), "Limitations").body()
    doc = content(first.lines, second.lines)
    on_page_one = dataclasses.replace(doc, outline=(OutlineEntry("Limitations", 1, 1),))
    on_page_two = dataclasses.replace(doc, outline=(OutlineEntry("Limitations", 1, 2),))
    assert [b.text for b in build_document(on_page_one).blocks if b.kind is BlockKind.HEADING] == [
        "1 Introduction",
        "2 Method",
    ]
    assert headings(build_document(on_page_two))[-1] == ("Limitations", "")


def test_an_entry_without_letters_adds_nothing() -> None:
    page = Page().heading("1 Introduction").body().heading("2 Method").body()
    plain(page, "2024").body()
    assert headings(page.build(OutlineEntry("2024", 1, 1)))[-1] == ("2 Method", "2")


def test_titles_are_compared_after_nfkc_case_and_spaces() -> None:
    """A ligature on the page ("ﬁ"), full-width letters (only NFKC folds them, review of
    #146, S2), another case and extra spaces in the bookmark."""
    page = Page().heading("1 Introduction").body().heading("2 Method").body()
    plain(page, "Final  Deﬁnitions").body()
    plain(page, "Closing Words").body()
    doc = page.build(
        OutlineEntry(" final definitions ", 1, 1),
        # "Closing" in full-width letters
        OutlineEntry("\uff23\uff4c\uff4f\uff53\uff49\uff4e\uff47 Words", 1, 1),
    )
    assert headings(doc)[-2:] == [("Final  Deﬁnitions", ""), ("Closing Words", "")]


@st.composite
def outlined(draw: st.DrawFn) -> Content:
    """Any content, with an outline drawn from its own line texts: random levels in a valid
    nesting, each pointing at a random page."""
    found = draw(contents())
    lines = [line.text for page in found.pages for line in page.lines]
    if not lines:
        return found
    outline: list[OutlineEntry] = []
    for _ in range(draw(st.integers(0, 6))):
        level = draw(st.integers(1, outline[-1].level + 1 if outline else 1))
        page = draw(st.integers(1, len(found.pages)))
        outline.append(OutlineEntry(draw(st.sampled_from(lines)), level, page))
    return dataclasses.replace(found, outline=tuple(outline))


@given(outlined())
def test_an_outline_only_adds_headings(found: Content) -> None:
    """On any content: layout never fails, and every heading found without the outline is
    a heading with it, with the same label and section level (D-270, D-271)."""
    without = build_document(dataclasses.replace(found, outline=()))
    doc = build_document(found)
    assert {(s.start, s.level) for s in walk(without.sections)} <= {
        (s.start, s.level) for s in walk(doc.sections)
    }
    for index, block in enumerate(without.blocks):
        if block.kind is BlockKind.HEADING:
            assert doc.blocks[index].kind is BlockKind.HEADING
            assert doc.blocks[index].label == block.label


def walk(sections: tuple[Section, ...]) -> list[Section]:
    out: list[Section] = []
    for section in sections:
        out.append(section)
        out.extend(walk(section.children))
    return out
