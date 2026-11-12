"""Chapters (Q6): level-1 sections, the text before the first heading, the reference list."""

from itertools import pairwise

import pytest
from app_helpers import document_with
from core_strategies import documents
from hypothesis import given

from sci2audio.app import (
    REFERENCE_NAMES,
    Chapter,
    default_selection,
    document_title,
    find_chapters,
    is_reference_title,
)
from sci2audio.app.chapters import selected
from sci2audio.core import Document, Section

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
    assert selected(chapters, None) == (frozenset({0}), ())
    assert selected(chapters, {0, 3, 7}) == (frozenset({0}), (3, 7))
    assert selected(chapters, set()) == (frozenset(), ())


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
