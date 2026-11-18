"""Chapters (Q6): level-1 sections, the text before the first heading, the reference list."""

from itertools import pairwise
from pathlib import Path

import pytest
from app_helpers import document_with
from core_strategies import documents
from hypothesis import given

from sci2audio.app import (
    REFERENCE_NAMES,
    Chapter,
    JobSettings,
    default_selection,
    document_title,
    find_chapters,
    is_reference_title,
)
from sci2audio.app.chapters import PUBLISHER_TAGS, selected
from sci2audio.app.job import read_document
from sci2audio.core import Document, Section
from sci2audio.testing import make_document

TIME_MACHINE = (
    Path(__file__).resolve().parents[1] / "corpus" / "epub" / "wells-the-time-machine.epub"
)
P = "paragraph"
H = "heading"


def titles(document: Document) -> list[tuple[str, int, int, bool]]:
    return [(c.title, c.start, c.end, c.references) for c in find_chapters(document)]


def test_each_level_1_section_is_a_chapter_and_the_front_text_the_first() -> None:
    sections = (
        Section("1 Introduction", 1, 2, 4, (Section("1.1 Aims", 2, 3, 4),)),
        Section("2 Method", 1, 4, 5),
    )
    blocks = [(P, "Title"), (P, "Authors"), (H, "1 Introduction"), (H, "1.1 Aims"), (H, "2 Method")]
    document = document_with(blocks, sections, title="A Paper About Things")
    assert titles(document) == [
        ("A Paper About Things", 0, 2, False),
        ("1 Introduction", 2, 4, False),
        ("2 Method", 4, 5, False),
    ]


def test_the_front_chapter_is_titled_with_the_file_name_without_metadata() -> None:
    document = document_with([(P, "x"), (H, "Intro")], (Section("Intro", 1, 1, 2),),
                             name="acl2023-hardt-ellipsis.pdf")  # fmt: skip
    assert titles(document)[0] == ("acl2023-hardt-ellipsis", 0, 1, False)
    assert document_title(document) == "acl2023-hardt-ellipsis"


def test_the_metadata_title_has_its_white_space_cleaned() -> None:
    document = document_with([(P, "x")], title="  Deep\n  Learning  ")
    assert document_title(document) == "Deep Learning"


def test_a_document_without_headings_is_one_chapter() -> None:
    document = document_with([(P, "a"), (P, "b"), (P, "c")], title="Orbital Hall")
    assert titles(document) == [("Orbital Hall", 0, 3, False)]


def test_no_front_chapter_when_the_first_heading_is_the_first_block() -> None:
    document = document_with([(H, "Summary"), (P, "x")], (Section("Summary", 1, 0, 2),))
    assert titles(document) == [("Summary", 0, 2, False)]


def test_an_empty_document_is_one_empty_chapter() -> None:
    document = document_with([], title="Nothing")
    assert titles(document) == [("Nothing", 0, 0, False)]


def test_gaps_in_the_section_tree_belong_to_the_chapter_before() -> None:
    blocks = [(H, "A"), (P, "a"), (P, "gap"), (H, "B"), (P, "b"), (P, "tail")]
    sections = (Section("A", 1, 0, 2), Section("B", 1, 3, 5))
    assert titles(document_with(blocks, sections)) == [("A", 0, 3, False), ("B", 3, 6, False)]


def test_a_top_level_section_of_a_deeper_level_starts_a_chapter_too() -> None:
    blocks = [(H, "1.1 Start"), (P, "a"), (H, "2 Next"), (P, "b")]
    sections = (Section("1.1 Start", 2, 0, 2), Section("2 Next", 1, 2, 4))
    assert titles(document_with(blocks, sections)) == [
        ("1.1 Start", 0, 2, False),
        ("2 Next", 2, 4, False),
    ]


def test_titles_keep_their_printed_number_and_read_line_breaks_as_spaces() -> None:
    blocks = [(H, "2 Related\nWork"), (P, "x")]
    sections = (Section("2 Related\nWork", 1, 0, 2),)
    assert titles(document_with(blocks, sections))[0][0] == "2 Related Work"


def test_a_section_without_a_title_gets_a_numbered_one() -> None:
    sections = (Section("A", 1, 0, 1), Section("  ", 1, 1, 2))
    assert titles(document_with([(H, "A"), (P, "x")], sections))[1][0] == "Section 2"


@pytest.mark.parametrize(
    "title",
    ["References", "REFERENCES", "7 References", "A References", "References:", "Bibliography",
     "Works Cited", "Literature cited", "IV. References", "Literaturverzeichnis", "Reference list"],
)  # fmt: skip
def test_reference_lists_are_found_by_their_title(title: str) -> None:
    assert is_reference_title(title)


@pytest.mark.parametrize(
    "title",
    ["A Appendix", "Appendices", "Supplementary Material: Appendices", "A Proof of Lem. 1",
     "Related Work", "References and Notes on Sources", "1 Introduction", "Acknowledgements"],
)  # fmt: skip
def test_appendices_and_other_sections_are_not_reference_lists(title: str) -> None:
    assert not is_reference_title(title)


def test_reference_names_are_one_table_with_english_first() -> None:
    assert next(iter(REFERENCE_NAMES)) == "en"
    assert "References" in REFERENCE_NAMES["en"]


def test_the_reference_list_is_deselected_by_default_and_appendices_stay() -> None:
    blocks = [(H, "1 Intro"), (H, "References"), (P, "[1] A."), (H, "A Appendix"), (P, "x")]
    sections = (
        Section("1 Intro", 1, 0, 1),
        Section("References", 1, 1, 3),
        Section("A Appendix", 1, 3, 5),
    )
    chapters = find_chapters(document_with(blocks, sections))
    assert [c.references for c in chapters] == [False, True, False]
    assert default_selection(chapters) == {0, 2}


def test_a_chosen_selection_is_taken_as_given_and_unknown_indices_are_ignored() -> None:
    chapters = find_chapters(document_with([(P, "a")]))
    assert selected(chapters, None) == ((0,), ())
    assert selected(chapters, (0, 3, 7)) == ((0,), (3, 7))
    assert selected(chapters, ()) == ((), ())


def test_a_chosen_selection_keeps_its_order() -> None:
    """#119: the chosen chapters come back in the order they are read."""
    blocks = [(H, "A"), (H, "B"), (H, "C")]
    sections = (Section("A", 1, 0, 1), Section("B", 1, 1, 2), Section("C", 1, 2, 3))
    chapters = find_chapters(document_with(blocks, sections))
    assert selected(chapters, (2, 0, 5, 2)) == ((2, 0), (5,))


def test_a_chapter_needs_a_title_and_a_valid_range() -> None:
    with pytest.raises(ValueError, match="title"):
        Chapter(0, " ", 0, 1)
    with pytest.raises(ValueError, match="start <= end"):
        Chapter(0, "x", 2, 1)


@given(documents())
def test_chapters_hold_every_block_exactly_once_in_order(document: Document) -> None:
    chapters = find_chapters(document)
    assert [c.index for c in chapters] == list(range(len(chapters)))
    assert chapters[0].start == 0
    assert chapters[-1].end == len(document.blocks)
    for before, after in pairwise(chapters):
        assert before.end == after.start
    assert all(c.title.strip() == c.title and c.title for c in chapters)
    starts = [s.start for s in document.sections]
    front = not starts or starts[0] > 0
    assert len(chapters) == len(starts) + front
    if front:
        assert chapters[0].title == document_title(document)


def test_a_blank_file_name_and_title_give_untitled() -> None:
    document = document_with([(P, "x")], name=" .pdf")
    assert document_title(document) == ".pdf"
    assert document_title(document_with([(P, "x")], name=" ")) == "Untitled"


# ---- publishers' pages (#190) -------------------------------------------------------------


def _tagged_book(*heading_tags: tuple[str, ...]) -> Document:
    """A book of one chapter per entry, its heading line tagged with those source tags."""
    blocks: list[tuple[str, str]] = []
    sections = []
    tags: dict[int, list[tuple[int, int, tuple[str, ...]]]] = {}
    for number, chapter_tags in enumerate(heading_tags):
        title = f"Part {number}"
        start = len(blocks)
        blocks += [(H, title), (P, f"text {number}")]
        sections.append(Section(title, 1, start, start + 2))
        tags[start] = [(0, len(title), ("section", *chapter_tags, "h2"))]
    return make_document(blocks, "en", "book.epub", tags=tags, sections=sections)


@pytest.mark.parametrize("tag", sorted(PUBLISHER_TAGS))
def test_a_publishers_page_is_not_chosen_by_default(tag: str) -> None:
    document = _tagged_book(("epub:chapter",), (tag,), ("epub:chapter",))
    chapters = find_chapters(document)
    assert [c.publisher for c in chapters] == [False, True, False]
    assert default_selection(chapters) == {0, 2}
    assert not chapters[1].references


@pytest.mark.parametrize(
    "tag",
    [
        "epub:titlepage",
        "epub:halftitlepage",
        "epub:dedication",
        "epub:epigraph",
        "epub:preface",
        "epub:foreword",
        "epub:introduction",
        "epub:prologue",
        "epub:chapter",
        "epub:epilogue",
        "epub:endnotes",
        "epub:footnotes",
        "epub:afterword",
        "epub:appendix",
        "role:doc-chapter",
        "role:doc-epilogue",
        "role:doc-endnotes",
        "role:doc-introduction",
    ],
)
def test_the_book_itself_stays_chosen(tag: str) -> None:
    chapters = find_chapters(_tagged_book((tag,)))
    assert [c.publisher for c in chapters] == [False]
    assert default_selection(chapters) == {0}


def test_a_publishers_page_can_still_be_chosen() -> None:
    chapters = find_chapters(_tagged_book(("epub:chapter",), ("epub:colophon",)))
    assert selected(chapters, {0, 1}) == ((0, 1), ())


def test_only_the_heading_lines_tags_count() -> None:
    """A colophon tag inside a chapter's text does not make the chapter a publisher's page."""
    blocks = [(H, "One"), (P, "made by a press")]
    tags = {1: [(0, 4, ("section", "epub:colophon", "p"))]}
    document = make_document(blocks, "en", "book.epub", tags=tags,
                             sections=[Section("One", 1, 0, 2)])  # fmt: skip
    assert [c.publisher for c in find_chapters(document)] == [False]


def test_the_front_text_and_untagged_files_are_never_publishers_pages() -> None:
    blocks = [(P, "front"), (H, "Colophon"), (P, "x")]
    document = document_with(blocks, (Section("Colophon", 1, 1, 3),))
    chapters = find_chapters(document)
    assert [c.publisher for c in chapters] == [False, False]  # a title alone says nothing
    assert default_selection(chapters) == {0, 1}


def test_the_time_machine_leaves_out_its_imprint_colophon_and_uncopyright() -> None:
    document = read_document(TIME_MACHINE, JobSettings(), lambda _phase: None)
    chapters = find_chapters(document)
    left_out = [c.title for c in chapters if c.index not in default_selection(chapters)]
    assert left_out == ["Imprint", "Colophon", "Uncopyright"]
    kept = [c.title for c in chapters if c.index in default_selection(chapters)]
    story = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]
    assert kept == ["The Time Machine", *story, "Epilogue", "Endnotes"]
    assert len([*story, "Epilogue"]) == 13


def test_front_matter_is_deselected_by_default_and_can_still_be_chosen() -> None:
    """#456 (D-755): a publisher section from a PDF's outline is a chapter of its own, not
    read by default; the reader may still choose it. The article's title page after it,
    before the first heading, is a chapter titled like the document."""
    blocks = [
        (P, "Repository cover sheet"),
        (P, "Journal cover"),
        (P, "Imprint"),
        (P, "An Article"),
        (P, "A. Author"),
        (H, "Introduction"),
        (P, "text"),
    ]
    sections = (
        Section("Cover", 1, 0, 2, publisher=True),
        Section("Impressum", 1, 2, 3, publisher=True),
        Section("Introduction", 1, 5, 7),
    )
    chapters = find_chapters(document_with(blocks, sections, title="An Article"))
    assert [(c.title, c.start, c.end, c.publisher) for c in chapters] == [
        ("Cover", 0, 2, True),
        ("Impressum", 2, 3, True),
        ("An Article", 3, 5, False),
        ("Introduction", 5, 7, False),
    ]
    assert default_selection(chapters) == {2, 3}
    assert selected(chapters, (0, 3)) == ((0, 3), ())


def test_front_matter_right_before_a_section_leaves_no_title_chapter() -> None:
    blocks = [(P, "Imprint"), (H, "Introduction"), (P, "text")]
    sections = (Section("Impressum", 1, 0, 1, publisher=True), Section("Introduction", 1, 1, 3))
    assert [c.title for c in find_chapters(document_with(blocks, sections))] == [
        "Impressum",
        "Introduction",
    ]
