"""Layout on made-up pages: headings and the section tree (Issue #21 step 3), the file's
outline as a second signal for headings (#24, D-270 to D-272), and headings with a rule
drawn under them (#48, D-385 to D-391).

One column between x 70 and x 526, body text in 10 point on a 14 point line pitch, as in
`test_layout_paragraphs`. Headings stand on a line of their own with white above them.
"""

import dataclasses
import itertools

from core_strategies import contents
from hypothesis import example, given
from hypothesis import strategies as st
from test_layout import LEFT, RIGHT, content

from sci2audio.core import (
    BlockKind,
    Box,
    Content,
    Document,
    Drawing,
    Metadata,
    OutlineEntry,
    Picture,
    Section,
    Source,
    SourceFormat,
    TextLine,
    TextRun,
)
from sci2audio.core import Page as PdfPage
from sci2audio.layout import build_document
from sci2audio.layout.headings import title
from sci2audio.layout.tagged import positioned

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
        self.drawings: list[Drawing] = []
        self.y = 80.0

    def heading(self, text: str, size: float = 12.0, bold: bool = True) -> "Page":
        self.y += 8
        self.lines.append(set_line(text, self.y, size, bold))
        self.y += size + 6
        return self

    def ruled(
        self,
        text: str,
        size: float = 10.0,
        x0: float = LEFT,
        x1: float = RIGHT,
        top: float = -1.5,
        thick: float = 0.8,
        indent: float = 0.0,
    ) -> "Page":
        """A bold heading line with a rule drawn under it, by default across the column with
        its top 1.5 points above the line box's foot (inside it, as on the ACL checklist):
        `top` is measured from the box's foot, `x0` and `x1` are the rule's ends, `indent`
        sets the line that far in from the column's left edge."""
        self.heading(text, size)
        found = self.lines[-1]
        box = found.box
        assert box is not None
        if indent:
            box = Box(box.x0 + indent, box.y0, box.x1 + indent, box.y1)
            self.lines[-1] = dataclasses.replace(found, box=box)
        foot = box.y1
        box = Box(x0, foot + top, x1, foot + top + thick)
        self.drawings.append(Drawing(f"d{next(_ids)}", box))
        self.y = max(self.y, box.y1 + 6)
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
        found = content(self.lines, metadata=metadata, drawings=tuple(self.drawings))
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
@example(  # an algorithm caption and a drawing, both flat, on one box (#123)
    Content(
        Source("0", SourceFormat.PDF),
        (
            PdfPage(
                1,
                lines=(
                    TextLine(
                        "i0", (TextRun("Algorithm 0 ", bold=True), TextRun("0")), Box(0, 0, 1, 0)
                    ),
                ),
                drawings=(Drawing("d", Box(0, 0, 1, 0)),),
            ),
        ),
    )
)
@example(  # an outline entry on a page of content without positions that has no heading (#195)
    Content(
        Source("0", SourceFormat.PDF),
        (PdfPage(1, pictures=(Picture("i0", None),)),),
        Metadata(),
        outline=(OutlineEntry("A", 1, 1, ""),),
    )
)
def test_sections_start_at_headings_and_carry_their_text(found: Content) -> None:
    """On any content: each heading starts a section and the section's title is its lines.
    With positions, each section starts at a heading. Without (EPUB, Markdown, text), an
    outline entry on a page without headings may start a section at a block that is no
    heading; it is titled as the entry (D-405 to D-418, #195)."""
    doc = build_document(found)
    sections, stack = [], list(doc.sections)
    while stack:
        section = stack.pop(0)
        sections.append(section)
        stack[:0] = section.children
    heads = [i for i, b in enumerate(doc.blocks) if b.kind is BlockKind.HEADING]
    starts = [s.start for s in sections]
    if positioned(found):
        assert starts == heads
    else:
        assert set(heads) <= set(starts)
    items = found.items()
    entries = {(e.page, " ".join(e.title.split())) for e in found.outline}
    for section in sections:
        block = doc.blocks[section.start]
        if block.kind is BlockKind.HEADING:
            assert section.title == title(block.text)
        else:
            page = items[block.parts[0].item][0].number if block.parts else None
            assert (page, section.title) in entries


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


def test_the_shift_starts_at_the_first_common_title_and_not_before() -> None:
    """Review of #146, round 2: a second common title does not move the shift's start, and
    an added numbered heading before the first one is not shifted."""
    page = Page().heading("1 Introduction").body()
    plain(page, "1.1 Early").body()
    page.heading("2 Method").body().heading("2.1 Setup", 10.0).body()
    page.heading("Appendices", 16.0).body().heading("A Proofs").body()
    page.heading("A.1 First", 10.0).body()
    plain(page, "A.2 Second").body()
    page.heading("Supplement", 16.0).body().heading("B More").body()
    page.heading("B.1 Third", 10.0).body()
    doc = page.build(OutlineEntry("Early", 1, 1), OutlineEntry("Second", 1, 1))
    levels = {s.title: s.level for s in walk(doc.sections)}
    assert levels["1.1 Early"] == levels["2.1 Setup"] == 2
    assert levels["A.2 Second"] == levels["A.1 First"] == 3


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


# A heading marked by a rule drawn under it (#48, D-385 to D-391): "ACL 2023 Responsible NLP
# Checklist" is set like the numbered subsections, with a rule under it across the page.


def numbered() -> Page:
    """A numbered paper with subsections in bold at body size."""
    page = Page().heading("1 Data").body().heading("1.1 Setup", 10.0).body()
    return page.heading("2 Results").body()


def holder(doc: Document, text: str) -> list[str]:
    """The item ids of the block whose text is `text`."""
    return [p.item for b in doc.blocks if b.text == text for p in b.parts]


def test_a_line_with_a_rule_under_it_is_a_level_one_heading() -> None:
    """The rule decides, not the words (D-385)."""
    page = numbered().ruled("Ethics Review Form").body()
    doc = page.build()
    assert ("Ethics Review Form", "") in headings(doc)
    assert tree(doc.sections)[-1] == ("Ethics Review Form", 1)
    assert page.drawings[0].id in holder(doc, "Ethics Review Form")  # its own part (D-391)


def test_the_same_line_without_a_rule_is_not_a_heading() -> None:
    """hardt's "Single Sentence" and "Two Actions": bold labels at body size."""
    doc = numbered().heading("Ethics Review Form", 10.0).body().build()
    assert ("Ethics Review Form", "") not in headings(doc)


def underline(page: Page) -> Page:
    """A rule exactly under the words, as a link is underlined."""
    return page.ruled("Ethics Review Form", x0=LEFT, x1=LEFT + 5 * len("Ethics Review Form"))


def test_a_rule_that_is_not_under_the_line_or_not_longer_than_it_marks_no_heading() -> None:
    """Each of the rule's conditions on its own (D-385): an underline of the words, a rule
    more than `heading_rule_gap` below the line, a bar thicker than `line_width`, a rule
    stopping short of the line's end, one starting after the line's start."""
    words = LEFT + 5 * len("Ethics Review Form")
    cases = {
        "underline": {"x1": words},
        "far below": {"top": 6.0},
        "thick": {"thick": 12.0},
        "short": {"indent": 200.0, "x1": words + 200.0 - 10},
        "starts late": {"x0": LEFT + 10},
    }
    for name, rule in cases.items():
        page = numbered().ruled("Ethics Review Form", **rule).body()  # type: ignore[arg-type]
        doc = page.build()
        assert page.drawings[0].id in holder(doc, "Ethics Review Form"), name
        assert ("Ethics Review Form", "") not in headings(doc), name


def test_a_rule_under_the_first_of_two_lines_marks_no_heading() -> None:
    """The rule must stand under the block's last line, below its middle."""
    page = numbered()
    page.ruled("Ethics Review")
    first = page.lines[-1]
    second = set_line("Form Two", first.box.y1 + 2, bold=True)  # type: ignore[union-attr]
    page.lines.append(second)
    page.y = second.box.y1 + 6  # type: ignore[union-attr]
    doc = page.body().build()
    assert page.drawings[0].id in holder(doc, "Ethics Review\nForm Two")
    assert ("Ethics Review\nForm Two", "") not in headings(doc)


def placed(text: str, x0: float, y0: float, bold: bool = True) -> TextLine:
    """A 10 point line at this place, 5 points a letter."""
    run = TextRun(text, "Times-Bold" if bold else "Times", 10.0, bold=bold)
    return TextLine(f"p{next(_ids)}", (run,), Box(x0, y0, x0 + 5 * len(text), y0 + 10))


def test_a_rule_under_the_last_of_two_lines_is_measured_against_that_line_only() -> None:
    """The last row is the lines at the last line's height: a longer first line above it
    does not count. A rule under the short second line, one em longer than it, marks a
    heading."""
    page = numbered()
    top = page.y + 8
    first, second = placed("Ethics Review Board of the", LEFT, top), placed("Study", LEFT, top + 12)
    rule = Drawing(f"d{next(_ids)}", Box(LEFT, top + 20.5, LEFT + 35, top + 21.3))
    page.lines += [first, second]
    page.drawings.append(rule)
    page.y = top + 28
    doc = page.body().build()
    assert rule.id in holder(doc, "Ethics Review Board of the\nStudy")
    assert ("Ethics Review Board of the\nStudy", "") in headings(doc)


def test_a_rule_just_below_the_line_and_one_em_longer_marks_a_heading() -> None:
    """The limits themselves: half an em below the line box, one em past the words."""
    words = LEFT + 5 * len("Ethics Review Form")
    page = numbered().ruled("Ethics Review Form", x1=words + 10.0, top=5.0).body()
    assert ("Ethics Review Form", "") in headings(page.build())


def test_a_ruled_line_before_the_first_numbered_heading_is_not_a_heading() -> None:
    """A title framed by rules (D-388)."""
    page = Page().ruled("A Study of Things", 14.0).body().heading("1 Data").body()
    doc = page.heading("1.1 Setup", 10.0).body().heading("2 End").body().build()
    assert headings(doc) == [("1 Data", "1"), ("1.1 Setup", "1.1"), ("2 End", "2")]


def test_a_ruled_line_in_a_document_without_numbered_headings_is_not_a_heading() -> None:
    page = Page().heading("Summary", 14.0).body().heading("Statement of need", 14.0).body()
    doc = page.ruled("Ethics Review Form").body().build()
    assert headings(doc) == [("Summary", ""), ("Statement of need", "")]


def test_a_ruled_line_ending_as_a_lead_in_is_not_a_heading() -> None:
    doc = numbered().ruled("Ethics Review Form:").body().build()
    assert ("Ethics Review Form:", "") not in headings(doc)


def test_a_numbered_heading_with_a_rule_under_it_keeps_its_level() -> None:
    page = Page().heading("1 Data").body().ruled("1.1 Setup").body().heading("2 End").body()
    assert tree(page.build().sections) == [("1 Data", 1), [("1.1 Setup", 2)], ("2 End", 1)]


def test_after_the_appendices_title_a_ruled_heading_is_level_one_and_the_shift_goes_on() -> None:
    """D-386 and D-387: chi's checklist after "Supplementary Material: Appendices"."""
    page = Page().heading("1 Introduction").body().heading("References").body()
    page.heading("Appendices", 14.0).heading("A Proofs").body().heading("A.1 Lemmas", 10.0)
    page.body().ruled("Ethics Review Form").body().heading("B More").body()
    levels = {s.title: s.level for s in walk(page.build().sections)}
    assert levels == {
        "1 Introduction": 1,
        "References": 1,
        "Appendices": 1,
        "A Proofs": 2,
        "A.1 Lemmas": 3,
        "Ethics Review Form": 1,
        "B More": 2,
    }


def test_a_header_row_split_into_cells_over_a_table_rule_is_not_a_heading() -> None:
    """Review of #180 (M1): the rule is measured against the block's whole last row. An
    uncaptioned table's bold header cells read as one block over a booktabs rule that
    overhangs the row by 6 points (`\\tabcolsep`) at each end: less than one em, so no
    heading, though it starts far before the last cell ("F1")."""
    for x0, x1 in ((LEFT, RIGHT), (170.0, 370.0)):
        page = numbered()
        top = page.y + 8
        cells = [("Model", x0 + 6), ("Accuracy", (x0 + x1) / 2), ("F1", x1 - 16)]
        row = [placed(text, left, top) for text, left in cells]
        rule = Drawing(f"d{next(_ids)}", Box(x0, top + 11, x1, top + 12))
        rows = [placed(f"m{k} 0.{k} 0.{k}", x0 + 6, top + 14 * k, bold=False) for k in (1, 2, 3)]
        page.lines += [*row, *rows]
        page.drawings.append(rule)
        page.y = top + 14 * 6
        doc = page.body().build()
        holding = next(b for b in doc.blocks if rule.id in [p.item for p in b.parts])
        assert {c.id for c in row} <= {p.item for p in holding.parts}, (x0, x1)
        assert holding.kind is not BlockKind.HEADING, (x0, x1)


def test_a_bold_line_over_a_wide_rule_inside_a_table_stays_in_the_table() -> None:
    """The risk of the rule: a table's bold header row over its rule. A table its caption
    names takes the row and the rule, and only paragraphs can become headings."""
    page = numbered()
    top = page.y + 20
    header = set_line("Structure Example", top, bold=True)
    rows = [set_line(f"Row {k} of the table", top + 14 * (k + 1)) for k in range(3)]
    rules = [
        Drawing("t1", Box(LEFT, top - 3, RIGHT, top - 2.5)),
        Drawing("t2", Box(LEFT, top + 8.5, RIGHT, top + 9.3)),
        Drawing("t3", Box(LEFT, top + 14 * 4 - 2, RIGHT, top + 14 * 4 - 1.5)),
    ]
    caption = set_line("Table 1: The structures.", top + 14 * 4 + 6)
    page.lines += [header, *rows, caption]
    page.drawings += rules
    page.y = top + 14 * 6
    doc = page.body().build()
    table = next(b for b in doc.blocks if b.kind is BlockKind.TABLE)
    assert header.id in [p.item for p in table.parts]
    assert "t2" in [p.item for p in table.parts]
    assert ("Structure Example", "") not in headings(doc)
