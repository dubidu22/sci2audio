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

from sci2audio.app import default_selection, find_chapters
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
from sci2audio.layout.build import columns_per_page
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
        """A paragraph of running text: full lines, the last one ending halfway. It starts
        and ends a sentence: a row ending inside a sentence goes on with a row that starts in
        lower case, whatever its shape (#454)."""
        for k in range(count):
            n = next(_ids)
            last = k == count - 1
            right = RIGHT if not last else (LEFT + RIGHT) / 2
            box = Box(LEFT, self.y, right, self.y + size)
            words = f"{'Running' if k == 0 else 'running'} text {n}"
            run = TextRun(f"{words} {'ends.' if last else 'goes on'}", "Times", size)
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
    """#50: "A" counts as a number only where letters number headings."""
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
    """#50: 11.94 and 12.0 point headings are one style, not two."""
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
    """#50: a property that sees headings in every example."""
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
    """#146: without numbers the outline's level would differ (D-271)."""
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
    """#146: the same shift as the font rules give "A.1"."""
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
    """#146: a second common title does not move the shift's start, and
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
    """#146."""
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
    """A ligature on the page ("ﬁ"), full-width letters (only NFKC folds them,
    #146), another case and extra spaces in the bookmark."""
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
@example(  # an outline entry on level 2 sets the base level of a page without positions (#199)
    Content(
        Source("0", SourceFormat.PDF),
        (
            PdfPage(
                1,
                lines=(
                    TextLine("i0", (TextRun("0", tags=("h1",)),)),
                    TextLine("i1", (TextRun("0"), TextRun("0"), TextRun("A"))),
                ),
            ),
        ),
        Metadata(),
        outline=(
            OutlineEntry("0", 1, 1),
            OutlineEntry("0", 1, 1),
            OutlineEntry("00A", 2, 1),
        ),
    )
)
@example(  # two ranks on one page: both move by the base level the outline sets (#199)
    Content(
        Source("0", SourceFormat.EPUB),
        (
            PdfPage(
                1,
                lines=(
                    TextLine("i0", (TextRun("Part", tags=("h1",)),)),
                    TextLine("i1", (TextRun("Chapter", tags=("h2",)),)),
                    TextLine("i2", (TextRun("Text."),)),
                ),
            ),
        ),
        Metadata(),
        outline=(OutlineEntry("0", 1, 1), OutlineEntry("0", 1, 1), OutlineEntry("Part", 2, 1)),
    )
)
def test_an_outline_only_adds_headings(found: Content) -> None:
    """On any content: layout never fails, and every heading found without the outline is
    a heading with it, with the same label and section start (D-270, D-271). With positions
    its level stays too; without (EPUB, Markdown, text) the outline sets each page's base
    heading level, so a level may change (D-405 to D-418, #199)."""
    without = build_document(dataclasses.replace(found, outline=()))
    doc = build_document(found)
    if positioned(found):
        assert {(s.start, s.level) for s in walk(without.sections)} <= {
            (s.start, s.level) for s in walk(doc.sections)
        }
    else:
        assert {s.start for s in walk(without.sections)} <= {s.start for s in walk(doc.sections)}
        # the outline moves a page's headings by one amount, its base level (D-407); a
        # heading an entry names by `item` takes the entry's level, but `outlined()` never
        # sets `item`
        items = found.items()
        levels = {s.start: s.level for s in walk(doc.sections)}
        shifts: dict[int, set[int]] = {}
        for s in walk(without.sections):
            page = items[without.blocks[s.start].parts[0].item][0].number
            shifts.setdefault(page, set()).add(levels[s.start] - s.level)
        assert all(len(shift) == 1 for shift in shifts.values())
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


def test_a_narrow_rule_under_an_indented_line_joins_that_line() -> None:
    """#181: a rule from x 70 to 165 under a line indented to x 85 is read before the line;
    it joins the line's block, not the paragraph read before. It stops short of the line's
    end, so it marks no heading (D-385 kept, D-840); rules as wide as half the text and as
    the whole column do."""
    for x1, heading in ((165.0, False), (326.0, True), (RIGHT, True)):
        page = numbered().ruled("Ethics Review Form", indent=15.0, x1=x1).body()
        doc = page.build()
        assert page.drawings[0].id in holder(doc, "Ethics Review Form"), x1
        assert (("Ethics Review Form", "") in headings(doc)) is heading, x1


def test_a_rule_under_less_than_half_of_a_line_still_joins_the_block_before() -> None:
    """Liu p4: a rule read before a line it lies under for less than half of the line's width
    (a fraction bar) is not that line's; it joins the block read before, as before (D-90,
    D-840)."""
    page = numbered().ruled("Ethics Review Form of a longer kind", indent=30.0, x1=LEFT + 40)
    doc = page.body().build()
    assert page.drawings[0].id not in holder(doc, "Ethics Review Form of a longer kind")


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
    """#180: the rule is measured against the block's whole last row. An
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


# Roman numerals alone (#459)


def roman_paper(first: str = "I", size: float = 12.0, bold: bool = False) -> Page:
    """Sections numbered by centred Roman numerals alone, set larger than the body and not
    bold, as in the German journal of #459."""
    page = Page().body()
    for numeral in (first, "II", "III"):
        page.heading(numeral, size, bold).body()
    return page


def test_a_heading_that_is_only_the_numeral_i_is_found_like_ii_and_iii() -> None:
    """#459: "I" has one letter, too few for a heading on its own (`heading_letters`)."""
    doc = roman_paper().build()
    assert headings(doc) == [("I", ""), ("II", ""), ("III", "")]
    assert [s.title for s in doc.sections] == ["I", "II", "III"]


def test_a_lone_i_is_a_heading_only_in_the_style_of_the_roman_headings() -> None:
    """A pronoun on a line of its own is set like the text; an "I" in another heading style,
    or with no Roman heading in the document, stays text."""
    body_style = Page().body().heading("I", 10.0, False).body()
    body_style.heading("II", 12.0, False).body().heading("III", 12.0, False).body()
    assert headings(body_style.build()) == [("II", ""), ("III", "")]
    bold_other = Page().body().heading("I", 12.0, True).body()
    bold_other.heading("II", 14.0).body().heading("III", 14.0).body()
    assert headings(bold_other.build()) == [("II", ""), ("III", "")]
    named = Page().body().heading("I", 14.0).body().heading("Methods", 14.0).body()
    named.heading("Results", 14.0).body()
    assert headings(named.build()) == [("Methods", ""), ("Results", "")]


# Roman section numbers, lettered subsections (IEEE style, #49)


def ieee_paper(*numerals: str) -> Page:
    """Sections numbered "I.", "II.", ... in 12 point bold, each with two lettered
    subsections "A." and "B." in 10 point bold, on one page (800 points high)."""
    page = Page()
    for numeral in numerals:
        page.heading(f"{numeral}. Section {numeral}").body(2)
        page.heading("A. First part", 10.0).body(2).heading("B. Second part", 10.0).body(2)
    return page


def test_roman_section_numbers_are_level_one_and_letters_under_them_level_two() -> None:
    doc = ieee_paper("I", "II", "III", "IV").build()
    assert [label for _, label in headings(doc)] == [
        *("I", "A", "B", "II", "A", "B", "III", "A", "B", "IV", "A", "B")
    ]
    parts = [("A. First part", 2), ("B. Second part", 2)]
    assert tree(doc.sections) == [
        ("I. Section I", 1),
        parts,
        ("II. Section II", 1),
        parts,
        ("III. Section III", 1),
        parts,
        ("IV. Section IV", 1),
        parts,
    ]


def test_roman_numbers_up_to_xii_are_read_as_printed() -> None:
    numerals = ("I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII")
    page = Page()
    for numeral in numerals:
        page.heading(f"{numeral}. Section {numeral}").body(2)
    doc = page.build()
    assert [label for _, label in headings(doc)] == list(numerals)
    assert [s.level for s in doc.sections] == [1] * len(numerals)


def test_a_letter_i_under_a_roman_section_is_a_subsection() -> None:
    """The ninth subsection "I." is not section one again: Roman numbers count up."""
    page = Page().heading("I. Introduction").body(2)
    for letter in "ABCDEFGHI":
        page.heading(f"{letter}. Part {letter}", 10.0).body(2)
    page.heading("II. Method").body(2)
    doc = page.build()
    assert tree(doc.sections)[0] == ("I. Introduction", 1)
    assert [s.level for s in walk(doc.sections)] == [1, *[2] * 9, 1]
    assert headings(doc)[9] == ("I. Part I", "I")


def test_roman_numbers_out_of_sequence_are_no_heading_numbers() -> None:
    page = Page().heading("II. Method").body().heading("IV. Results").body()
    page.heading("III. Discussion").body()
    assert [label for _, label in headings(page.build())] == ["", "", ""]


def test_the_outline_adds_a_lettered_subsection_under_a_roman_section() -> None:
    page = Page().heading("I. Introduction").body(2).heading("II. Method").body(2)
    plain(page, "A. Fine Print").body(2)
    doc = page.build(OutlineEntry("A. Fine Print", 1, 1))  # the outline level loses
    assert headings(doc)[-1] == ("A. Fine Print", "A")
    assert tree(doc.sections) == [
        ("I. Introduction", 1),
        ("II. Method", 1),
        [("A. Fine Print", 2)],
    ]


def test_roman_numbers_inside_an_arabic_document_are_no_section_numbers() -> None:
    """Two bold "I." and "II." lines in an Arabic section are a list, not the sections."""
    page = Page().heading("1 Introduction").body(2)
    page.heading("I. Accuracy matters", 10.0).body(2).heading("II. Speed matters", 10.0).body(2)
    page.heading("2 Method").body(2).heading("3 Results").body(2)
    assert headings(page.build()) == [
        ("1 Introduction", "1"),
        ("2 Method", "2"),
        ("3 Results", "3"),
    ]


def test_the_outline_reads_no_letter_without_a_dot_or_arabic_number_in_a_roman_document() -> None:
    page = Page().heading("I. Introduction").body(2).heading("II. Method").body(2)
    plain(page, "A Note on Ethics").body(2)
    plain(page, "1. Limits").body(2)
    doc = page.build(OutlineEntry("A Note on Ethics", 1, 1), OutlineEntry("1. Limits", 1, 1))
    assert headings(doc)[-2:] == [("A Note on Ethics", ""), ("1. Limits", "")]
    assert [s.level for s in doc.sections] == [1, 1, 1, 1]


def test_the_outline_reads_a_letter_i_as_a_subsection_and_the_next_roman_as_a_section() -> None:
    """The outline path counts the Roman sections as the font rules do: "I." after "H." under
    section I is the ninth subsection, "III." after section II is section III."""
    page = Page().heading("I. Introduction").body(2)
    for letter in "ABCDEFGH":
        page.heading(f"{letter}. Part {letter}", 10.0).body(2)
    plain(page, "I. Part I").body(2)
    page.heading("II. Method").body(2)
    plain(page, "III. Results").body(2)
    doc = page.build(OutlineEntry("I. Part I", 1, 1), OutlineEntry("III. Results", 1, 1))
    assert headings(doc)[9] == ("I. Part I", "I")
    assert headings(doc)[-1] == ("III. Results", "III")
    assert [s.level for s in walk(doc.sections)] == [1, *[2] * 9, 1, 1]


def test_a_letter_in_a_document_with_arabic_numbers_stays_an_appendix_at_level_one() -> None:
    page = Page().heading("1 Introduction").body().heading("2 Method").body()
    page.heading("A Proofs").body().heading("B Data").body()
    doc = page.build()
    assert [label for _, label in headings(doc)] == ["1", "2", "A", "B"]
    assert [s.level for s in doc.sections] == [1, 1, 1, 1]


# IEEE third-level numbers "1)" under a lettered subsection (#798)


def test_a_parenthesised_number_under_a_lettered_subsection_is_level_three() -> None:
    page = Page().heading("I. Introduction").body(2).heading("II. Method").body(2)
    page.heading("A. Setup", 10.0).body(2)
    page.heading("1) Hardware", 10.0).body(2).heading("2) Software", 10.0).body(2)
    page.heading("B. Data", 10.0).body(2).heading("1) Sources", 10.0).body(2)
    page.heading("III. Results").body(2)
    doc = page.build()
    assert headings(doc)[2:7] == [
        ("A. Setup", "A"),
        ("1) Hardware", "1)"),
        ("2) Software", "2)"),
        ("B. Data", "B"),
        ("1) Sources", "1)"),
    ]
    assert tree(doc.sections) == [
        ("I. Introduction", 1),
        ("II. Method", 1),
        [
            ("A. Setup", 2),
            [("1) Hardware", 3), ("2) Software", 3)],
            ("B. Data", 2),
            [("1) Sources", 3)],
        ],
        ("III. Results", 1),
    ]


def test_a_parenthesised_number_in_body_style_stays_a_list_item() -> None:
    page = Page().heading("I. Introduction").body(2).heading("II. Method").body(2)
    page.heading("A. Setup", 10.0).body(2)
    for text in ("1) The first entry of the list.", "2) The second entry of the list."):
        page.lines.append(set_line(text, page.y))
        page.y += PITCH
    page.body(2).heading("B. Data", 10.0).body(2)
    doc = page.build()
    items = [b.text for b in doc.blocks if b.kind is BlockKind.LIST_ITEM]
    assert items == ["1) The first entry of the list.", "2) The second entry of the list."]
    assert [label for _, label in headings(doc)] == ["I", "II", "A", "B"]


def test_a_parenthesised_number_without_a_letter_before_it_is_no_heading_number() -> None:
    """Under a Roman section with no lettered subsection yet, a bold "1)" is no third level."""
    page = Page().heading("I. Introduction").body(2)
    page.heading("1) Bold step", 10.0).body(2).heading("2) Next step", 10.0).body(2)
    page.heading("II. Method").body(2).heading("A. Setup", 10.0).body(2)
    doc = page.build()
    assert headings(doc) == [("I. Introduction", "I"), ("II. Method", "II"), ("A. Setup", "A")]


def test_a_parenthesised_number_in_an_arabic_document_is_no_heading_number() -> None:
    page = Page().heading("1 Introduction").body(2).heading("1.1 Setup", 10.0).body(2)
    page.heading("1) Bold step", 10.0).body(2).heading("2) Next step", 10.0).body(2)
    page.heading("2 Method").body(2)
    doc = page.build()
    assert [label for _, label in headings(doc)] == ["1", "1.1", "2"]


def test_a_letter_in_the_section_before_does_not_number_a_parenthesised_line() -> None:
    """A new Roman section starts without a letter: a bold "1)" in III. before any letter of
    III. is no third level, though II. had a lettered subsection."""
    page = Page().heading("I. Introduction").body(2).heading("II. Method").body(2)
    page.heading("A. Setup", 10.0).body(2).heading("1) Hardware", 10.0).body(2)
    page.heading("III. Results").body(2)
    page.heading("1) Bold step", 10.0).body(2).heading("2) Next step", 10.0).body(2)
    doc = page.build()
    assert [label for _, label in headings(doc)] == ["I", "II", "A", "1)", "III"]


def test_a_lettered_line_that_is_no_heading_does_not_number_a_parenthesised_line() -> None:
    """A line "A. Note" set apart from the lettered subsections (9 point bold) is no heading,
    so the bold "1)" after it has no letter over it."""
    page = Page().heading("I. Introduction").body(2)
    page.heading("A. Setup", 10.0).body(2).heading("1) Hardware", 10.0).body(2)
    page.heading("B. Data", 10.0).body(2)
    page.heading("II. Method").body(2).heading("A. Note", 9.0).body(2)
    page.heading("1) Bold step", 10.0).body(2)
    doc = page.build()
    assert [label for _, label in headings(doc)] == ["I", "A", "1)", "B", "II"]


def test_a_parenthesised_line_with_no_letter_of_its_section_does_not_vote() -> None:
    """Bold "1)" lines in II., which has no letter, take no part in the depth-3 style vote:
    the "A.1." heading in I. keeps its own style."""
    page = Page().heading("I. Introduction").body(2).heading("A. Setup", 10.0).body(2)
    page.heading("A.1. Detail", 11.0).body(2).heading("B. Data", 10.0).body(2)
    page.heading("II. Method").body(2)
    page.heading("1) Bold step", 10.0).body(2).heading("2) Next step", 10.0).body(2)
    page.heading("III. Results").body(2)
    doc = page.build()
    assert [label for _, label in headings(doc)] == ["I", "A", "A.1", "B", "II", "III"]


def test_a_parenthesised_line_under_a_letter_that_is_no_heading_does_not_vote() -> None:
    page = Page().heading("I. Introduction").body(2).heading("A. Setup", 10.0).body(2)
    page.heading("A.1. Detail", 11.0).body(2).heading("B. Data", 10.0).body(2)
    page.heading("II. Method").body(2).heading("A. Note", 9.0).body(2)
    for text in ("1) Bold step", "2) Next step", "3) Last step"):
        page.heading(text, 10.0).body(2)
    page.heading("III. Results").body(2)
    doc = page.build()
    assert [label for _, label in headings(doc)] == ["I", "A", "A.1", "B", "II", "III"]


def test_parenthesised_numbers_do_not_outvote_the_style_of_lettered_third_levels() -> None:
    """#918: three bold 10 point "1)" lines under "A." in II. do not take the depth-3 style
    from two bold 11 point "A.1." lines under "A." in I.: each keeps its own style."""
    page = Page().heading("I. Introduction").body(2).heading("A. Setup", 10.0).body(2)
    page.heading("A.1. Detail", 11.0).body(2).heading("A.2. More", 11.0).body(2)
    page.heading("II. Method").body(2).heading("A. Data", 10.0).body(2)
    for text in ("1) One", "2) Two", "3) Three"):
        page.heading(text, 10.0).body(2)
    page.heading("III. Results").body(2)
    doc = page.build()
    assert [label for _, label in headings(doc)] == [
        *("I", "A", "A.1", "A.2", "II", "A", "1)", "2)", "3)", "III")
    ]
    assert tree(doc.sections) == [
        ("I. Introduction", 1),
        [("A. Setup", 2), [("A.1. Detail", 3), ("A.2. More", 3)]],
        ("II. Method", 1),
        [("A. Data", 2), [("1) One", 3), ("2) Two", 3), ("3) Three", 3)]],
        ("III. Results", 1),
    ]


def test_parenthesised_numbers_in_another_style_than_most_of_them_are_no_headings() -> None:
    """The "1)" numbers vote among themselves: one in another style is no heading."""
    page = Page().heading("I. Introduction").body(2).heading("II. Method").body(2)
    page.heading("A. Setup", 10.0).body(2)
    page.heading("1) Hardware", 10.0).body(2).heading("2) Software", 10.0).body(2)
    page.heading("3) Odd one", 11.0).body(2)
    page.heading("III. Results").body(2)
    doc = page.build()
    assert [label for _, label in headings(doc)] == ["I", "II", "A", "1)", "2)", "III"]


def test_a_letter_the_font_rules_drop_numbers_no_parenthesised_line() -> None:
    """#918: "A. Setup" is set like the letters but stands over a line set larger than the
    body, so it is no heading; the bold "1)" lines after it have no letter over them, for
    the font rules and for the outline alike."""
    page = Page().heading("I. Introduction").body(2).heading("A. Scope", 10.0).body(2)
    page.heading("B. Plan", 10.0).body(2).heading("II. Method").body(2)
    page.heading("A. Setup", 10.0).heading("A larger line of text", 11.0, False).body(2)
    page.heading("1) Hardware", 10.0).body(2).heading("2) Software", 10.0).body(2)
    plain(page, "3) Fine print").body(2)
    page.heading("III. Results").body(2)
    doc = page.build(OutlineEntry("3) Fine print", 1, 1))
    assert [label for _, label in headings(doc)] == ["I", "A", "B", "II", "", "III"]
    assert headings(doc)[4] == ("3) Fine print", "")


def test_the_outline_reads_no_parenthesised_number_after_a_letter_of_the_section_before() -> None:
    page = Page().heading("I. Introduction").body(2).heading("II. Method").body(2)
    page.heading("A. Setup", 10.0).body(2)
    page.heading("III. Results").body(2)
    plain(page, "1) Fine print").body(2)
    doc = page.build(OutlineEntry("1) Fine print", 1, 1))
    assert headings(doc)[-1] == ("1) Fine print", "")
    assert [s.level for s in walk(doc.sections)] == [1, 1, 2, 1, 1]


def test_the_outline_adds_a_parenthesised_number_under_a_letter_at_level_three() -> None:
    page = Page().heading("I. Introduction").body(2).heading("II. Method").body(2)
    page.heading("A. Setup", 10.0).body(2)
    plain(page, "1) Fine print").body(2)
    doc = page.build(OutlineEntry("1) Fine print", 1, 1))  # the outline level loses
    assert headings(doc)[-1] == ("1) Fine print", "1)")
    assert [s.level for s in walk(doc.sections)] == [1, 1, 2, 3]


def test_the_outline_reads_no_parenthesised_number_without_a_letter_before_it() -> None:
    page = Page().heading("I. Introduction").body(2).heading("II. Method").body(2)
    plain(page, "1) Fine print").body(2)
    doc = page.build(OutlineEntry("1) Fine print", 1, 1))
    assert headings(doc)[-1] == ("1) Fine print", "")
    assert [s.level for s in walk(doc.sections)] == [1, 1, 1]


# An IEEE third-level heading run into its paragraph, "1) Hardware: The board …" (#826, #963).
# Extraction cuts the printed line after the emphasised "1) Hardware:" into two lines on one
# baseline: the heading keeps the line's id, the rest gets it with "b" added and loses its
# leading space; their boxes overlap by about 0.6 point (glyph boxes, PR #964).

RUN_IN_REST = "The board is small and runs on one cell of power"


def run_in(
    page: Page, head: str, rest: str = RUN_IN_REST, italic: bool = False, rows: int = 2
) -> Page:
    """The two lines extraction makes of a run-in heading's printed line, a full row, then
    `rows` more rows of its paragraph."""
    font = "Times-Italic" if italic else "Times-Bold"
    y, n = page.y, next(_ids)
    run = TextRun(head, font, 10.0, bold=not italic, italic=italic)
    page.lines.append(TextLine(f"p1-l{n}", (run,), Box(LEFT, y, 108.0, y + 10.0)))
    rest_run = TextRun(rest, "Times", 10.0)
    page.lines.append(TextLine(f"p1-l{n}b", (rest_run,), Box(107.4, y, RIGHT, y + 10.0)))
    page.y += PITCH
    return page.body(rows) if rows else page


def ieee_run_ins(italic: bool = False) -> Page:
    page = Page().heading("I. Introduction").body(2).heading("II. Method").body(2)
    page.heading("A. Setup", 10.0).body(2)
    run_in(page, "1) Hardware:", italic=italic)
    run_in(page, "2) Software:", "The code is written in a language of its own", italic)
    return page.heading("B. Data", 10.0).body(2).heading("III. Results").body(2)


def test_a_run_in_heading_cut_from_its_line_is_level_three() -> None:
    doc = ieee_run_ins().build()
    assert headings(doc)[2:5] == [("A. Setup", "A"), ("1) Hardware:", "1)"), ("2) Software:", "2)")]
    assert tree(doc.sections) == [
        ("I. Introduction", 1),
        ("II. Method", 1),
        [("A. Setup", 2), [("1) Hardware", 3), ("2) Software", 3)], ("B. Data", 2)],
        ("III. Results", 1),
    ]
    at = [b.text for b in doc.blocks].index("1) Hardware:")
    rest = doc.blocks[at + 1]
    assert rest.kind is BlockKind.PARAGRAPH
    assert rest.text.split("\n")[0] == RUN_IN_REST
    assert len(rest.text.split("\n")) == 3


def test_an_italic_run_in_heading_is_level_three() -> None:
    doc = ieee_run_ins(italic=True).build()
    assert [s.title for s in walk(doc.sections)][3:5] == ["1) Hardware", "2) Software"]
    assert [s.level for s in walk(doc.sections)][3:5] == [3, 3]


def test_the_overlapping_halves_of_a_run_in_line_are_one_column_read_heading_first() -> None:
    """The heading's box ends 0.6 point right of where the rest's box starts: one column,
    one row, read heading then rest."""
    page = ieee_run_ins()
    assert columns_per_page(content(page.lines)) == [1]
    texts = [b.text for b in page.build().blocks]
    at = texts.index("1) Hardware:")
    assert texts[at + 1].startswith(RUN_IN_REST)


def test_a_run_in_head_alone_on_its_row_is_not_cut_from_the_lines_under_it() -> None:
    """An emphasised "1) Hardware:" that runs to the column's edge, with no rest of its
    printed line on its row, goes on with the lines under it as the paragraph's first line:
    the cut is made only between two halves of one row, as `paragraphs.continues` has it
    (PR #968)."""
    page = Page().heading("I. Introduction").body(2).heading("II. Method").body(2)
    page.heading("A. Setup", 10.0).body(2)
    head = TextRun("1) Hardware:", "Times-Italic", 10.0, italic=True)
    page.lines.append(TextLine("alone", (head,), Box(LEFT, page.y, RIGHT, page.y + 10.0)))
    page.y += PITCH
    page.body(2).heading("B. Data", 10.0).body(2).heading("III. Results").body(2)
    doc = page.build()
    assert [label for _, label in headings(doc)] == ["I", "II", "A", "B", "III"]
    block = next(b for b in doc.blocks if b.text.startswith("1) Hardware:"))
    assert block.kind is BlockKind.PARAGRAPH
    assert len(block.text.split("\n")) == 3


def test_a_run_in_heading_after_a_full_row_starts_its_own_block() -> None:
    page = Page().heading("I. Introduction").body(2).heading("II. Method").body(2)
    page.heading("A. Setup", 10.0).body(1)
    full = TextRun("running text that fills the whole row of the column goes on", "Times", 10.0)
    page.lines.append(TextLine("full", (full,), Box(LEFT, page.y, RIGHT, page.y + 10.0)))
    page.y += PITCH
    run_in(page, "1) Hardware:")
    run_in(page, "2) Software:")
    page.heading("B. Data", 10.0).body(2)
    doc = page.build()
    assert [label for _, label in headings(doc)] == ["I", "II", "A", "1)", "2)", "B"]
    assert all(b.text != "1) Hardware:" or b.kind is BlockKind.HEADING for b in doc.blocks)


def test_a_run_in_line_that_is_no_heading_reads_as_one_line_with_a_space() -> None:
    """In an Arabic document "1)" numbers no heading: the two halves stay one block, as the
    whole line would, joined by the space the page prints after the colon."""
    page = Page().heading("1 Introduction").body(2).heading("1.1 Setup", 10.0).body(2)
    run_in(page, "1) Hardware:")
    run_in(page, "2) Software:")
    page.heading("2 Method").body(2)
    doc = page.build()
    assert [label for _, label in headings(doc)] == ["1", "1.1", "2"]
    joined = [b for b in doc.blocks if b.text.startswith("1) Hardware")]
    assert [b.text.split("\n")[0] for b in joined] == [f"1) Hardware: {RUN_IN_REST}"]
    assert joined[0].kind is BlockKind.LIST_ITEM


def test_a_run_in_line_in_the_top_headings_style_is_no_unnumbered_heading() -> None:
    """Level-1 headings set bold in the body size: a run-in "1) Hardware:" in that style is
    no unnumbered level-1 heading, as the whole line ending in a colon never was."""
    page = Page().heading("1 Introduction", 10.0).body(2).heading("2 Method", 10.0).body(2)
    run_in(page, "1) Hardware:")
    page.heading("3 Results", 10.0).body(2)
    doc = page.build()
    assert [label for _, label in headings(doc)] == ["1", "2", "3"]
    assert any(b.text.startswith(f"1) Hardware: {RUN_IN_REST}") for b in doc.blocks)


def test_a_run_in_heading_without_a_letter_over_it_stays_in_its_paragraph() -> None:
    page = Page().heading("I. Introduction").body(2).heading("II. Method").body(2)
    run_in(page, "1) Hardware:")
    run_in(page, "2) Software:")
    page.heading("III. Results").body(2)
    doc = page.build()
    assert [label for _, label in headings(doc)] == ["I", "II", "III"]
    assert any(b.text.startswith(f"1) Hardware: {RUN_IN_REST}") for b in doc.blocks)


def test_body_style_numbered_items_stay_list_items_beside_run_in_headings() -> None:
    page = Page().heading("I. Introduction").body(2).heading("II. Method").body(2)
    page.heading("A. Setup", 10.0).body(2)
    run_in(page, "1) Hardware:")
    for text in ("1) The first entry of the list.", "2) The second entry of the list."):
        page.lines.append(set_line(text, page.y))
        page.y += PITCH
    run_in(page, "2) Software:")
    page.heading("B. Data", 10.0).body(2)
    doc = page.build()
    items = [b.text for b in doc.blocks if b.kind is BlockKind.LIST_ITEM]
    assert items == ["1) The first entry of the list.", "2) The second entry of the list."]
    assert [label for _, label in headings(doc)] == ["I", "II", "A", "1)", "2)", "B"]


# The publisher's front matter named by the outline (#456, D-755)


def journal_issue(*outline: OutlineEntry) -> Document:
    """Four pages: a repository's cover sheet, the journal's cover, its imprint, then the
    article: its title and author in body style, a heading set larger, running text."""
    sheet = [set_line("Cite this paper as follows", 80), set_line("Terms of use", 100)]
    cover = [set_line("Journal of Tests", 80, 14.0), set_line("Issue 55", 100)]
    imprint = [set_line("Editors: A. Editor", 80), set_line("Copyright 2017", 100)]
    article = Page()
    plain(article, "An Article About Tests")
    plain(article, "Ann Author")
    article.heading("Introduction", 14.0).body().heading("Method", 14.0).body()
    found = content(sheet, cover, imprint, article.lines)
    return build_document(dataclasses.replace(found, outline=outline))


FRONT = (
    OutlineEntry("Cover", 1, 2),
    OutlineEntry("Impressum", 1, 3),
    OutlineEntry("Bildung und Tests", 1, 4),  # the article's entry: no printed match
)


def publisher_sections(doc: Document) -> list[tuple[str, int, int]]:
    pages = {item: page.number for item, (page, _) in doc.content.items().items()}
    return [
        (
            s.title,
            pages[doc.blocks[s.start].parts[0].item],
            pages[doc.blocks[s.end - 1].parts[0].item],
        )
        for s in doc.sections
        if s.publisher
    ]


def test_outline_entries_naming_front_matter_start_publisher_sections() -> None:
    """Each starts at its page's first block and ends before the page the next entry points
    to; the first starts at block 0, so the cover sheet before it joins it. The article's
    title and author stay out of them, and its headings are found as before."""
    doc = journal_issue(*FRONT)
    assert publisher_sections(doc) == [("Cover", 1, 2), ("Impressum", 3, 3)]
    assert [(s.title, s.publisher) for s in doc.sections] == [
        ("Cover", True),
        ("Impressum", True),
        ("Introduction", False),
        ("Method", False),
    ]
    outside = [b.text for b in doc.blocks[doc.sections[1].end : doc.sections[2].start]]
    assert outside == ["An Article About Tests", "Ann Author"]
    assert headings(doc) == [("Introduction", ""), ("Method", "")]


def test_german_and_english_front_matter_names_are_known() -> None:
    for name in ("Inhaltsverzeichnis", "Titelei", "Imprint", "Table of Contents", "COPYRIGHT."):
        doc = journal_issue(OutlineEntry(name, 1, 3), OutlineEntry("Article", 1, 4))
        assert publisher_sections(doc) == [(name, 1, 3)]  # the title as stored


def test_without_an_outline_nothing_is_front_matter() -> None:
    """D-755: the cover sheet and imprint are found only through the outline, never by the
    pages' looks."""
    doc = journal_issue()
    assert [s.publisher for s in doc.sections] == [False, False]
    assert [s.title for s in doc.sections] == ["Introduction", "Method"]


def test_a_front_matter_entry_on_a_page_with_a_heading_starts_no_publisher_section() -> None:
    """The printed heading stands; an entry pointing at a page without blocks, or another
    title, adds nothing."""
    doc = journal_issue(OutlineEntry("Contents", 1, 4), OutlineEntry("Cover", 1, 2))
    assert publisher_sections(doc) == [("Cover", 1, 3)]
    doc = journal_issue(OutlineEntry("Covers of the issue", 1, 2))
    assert publisher_sections(doc) == []


def test_front_matter_with_no_entry_after_it_ends_at_the_next_heading() -> None:
    doc = journal_issue(OutlineEntry("Cover", 1, 2))
    assert [(s.title, s.publisher) for s in doc.sections] == [
        ("Cover", True),
        ("Introduction", False),
        ("Method", False),
    ]
    assert doc.blocks[doc.sections[0].end].text == "Introduction"


def test_two_front_matter_entries_for_one_page_make_one_publisher_section() -> None:
    """The first entry names it; the second starts nothing inside it."""
    doc = journal_issue(OutlineEntry("Cover", 1, 2), OutlineEntry("Titelei", 1, 2), *FRONT[1:])
    assert publisher_sections(doc) == [("Cover", 1, 2), ("Impressum", 3, 3)]


def test_front_matter_entries_are_taken_in_page_order() -> None:
    """The first front matter by page starts at block 0, whatever the outline's order."""
    doc = journal_issue(
        OutlineEntry("Impressum", 1, 3), OutlineEntry("Cover", 1, 2), OutlineEntry("Article", 1, 4)
    )
    assert publisher_sections(doc) == [("Cover", 1, 2), ("Impressum", 3, 3)]


def test_front_matter_with_nothing_after_it_ends_with_its_page() -> None:
    """No heading and no later entry: the cover ends with its own page, so the body text
    after it stays a chapter read by default, not the publisher's."""
    sheet = [set_line("Cite this paper as follows", 80), set_line("Terms of use", 100)]
    cover = [set_line("Journal of Tests", 80), set_line("Issue 55", 100)]
    found = content(sheet, cover, Page().body().body().lines)
    doc = build_document(dataclasses.replace(found, outline=(OutlineEntry("Cover", 1, 2),)))
    assert publisher_sections(doc) == [("Cover", 1, 2)]
    chapters = find_chapters(doc)
    assert [c.publisher for c in chapters] == [True, False]
    assert default_selection(chapters) == {1}
    assert "Running text" in doc.blocks[chapters[1].start].text


def test_front_matter_that_would_be_the_whole_document_is_none() -> None:
    sheet = [set_line("Cite this paper as follows", 80), set_line("Terms of use", 100)]
    found = content(sheet, [set_line("Issue 55", 80), *Page().body().lines])
    doc = build_document(dataclasses.replace(found, outline=(OutlineEntry("Cover", 1, 2),)))
    assert publisher_sections(doc) == []


def test_front_matter_in_several_sections_that_would_be_the_whole_document_is_none() -> None:
    """Two pages, each named front matter, leave nothing to read by
    default; the file is then read as without front matter."""
    for second in ("Cover", "Impressum"):
        found = content(Page().body().lines, Page().body().lines)
        outline = (OutlineEntry("Cover", 1, 1), OutlineEntry(second, 1, 2))
        doc = build_document(dataclasses.replace(found, outline=outline))
        assert publisher_sections(doc) == []
        assert default_selection(find_chapters(doc))


def test_headings_under_front_matter_follow_it_at_the_top() -> None:
    """Deeper headings after the imprint, which the section tree first puts under it, stay
    sections (and chapters) of their own."""
    imprint = [set_line("Editors: A. Editor", 80), set_line("Copyright 2017", 100)]
    article = Page().heading("1.1 Background").body().heading("1.2 Aims").body()
    article.heading("2 Results", 14.0).body().heading("2.1 More").body()
    found = content(imprint, article.lines)
    doc = build_document(dataclasses.replace(found, outline=(OutlineEntry("Impressum", 1, 1),)))
    assert tree(doc.sections) == [
        ("Impressum", 1),
        ("1.1 Background", 2),
        ("1.2 Aims", 2),
        ("2 Results", 1),
        [("2.1 More", 2)],
    ]
    assert [c.title for c in find_chapters(doc)] == [
        "Impressum",
        "1.1 Background",
        "1.2 Aims",
        "2 Results",
    ]


def test_front_matter_after_a_heading_starts_at_its_own_page() -> None:
    """With a heading before it, the contents page does not reach back to block 0."""
    title_page = Page().heading("A Study of Tests", 14.0).body()
    contents_page = [set_line("Einleitung 3", 80), set_line("Methode 4", 100)]
    article = Page().heading("Einleitung", 14.0).body().heading("Methode", 14.0).body()
    found = content(title_page.lines, contents_page, article.lines)
    outline = (OutlineEntry("A Study of Tests", 1, 1), OutlineEntry("Inhalt", 1, 2))
    doc = build_document(dataclasses.replace(found, outline=outline))
    assert [(s.title, s.publisher) for s in doc.sections] == [
        ("A Study of Tests", False),
        ("Inhalt", True),
        ("Einleitung", False),
        ("Methode", False),
    ]
    assert publisher_sections(doc) == [("Inhalt", 2, 2)]


# Numbered headings set like list markers (#54)


def test_two_numbered_headings_next_to_each_other_are_headings_not_list_items() -> None:
    """#54: "1. Introduction" and "2. Related work" open with list markers in sequence, and
    lists are found before headings; heading-sized or bold, they are headings."""
    for size, bold in ((12.0, True), (12.0, False), (10.0, True)):
        page = Page().heading("1. Introduction", size, bold)
        page.heading("2. Related work", size, bold).body()
        doc = page.build()
        found = [(b.kind, b.text) for b in doc.blocks if b.text.startswith(("1.", "2."))]
        assert found == [
            (BlockKind.HEADING, "1. Introduction"),
            (BlockKind.HEADING, "2. Related work"),
        ], (size, bold)
        assert headings(doc) == [("1. Introduction", "1"), ("2. Related work", "2")]


def test_a_numbered_list_in_body_text_stays_a_list() -> None:
    page = Page().heading("1 Data").body()
    for text in ("1. The first entry of the list.", "2. The second entry of the list."):
        page.lines.append(set_line(text, page.y))
        page.y += PITCH
    doc = page.body().build()
    items = [b.text for b in doc.blocks if b.kind is BlockKind.LIST_ITEM]
    assert items == ["1. The first entry of the list.", "2. The second entry of the list."]
