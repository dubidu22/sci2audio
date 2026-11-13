"""Layout of documents without positions, read from their tags (#75, D-405 to D-418)."""

from dataclasses import dataclass

from core_strategies import outlines
from hypothesis import given
from hypothesis import strategies as st

from sci2audio.core import (
    BlockKind,
    Box,
    Content,
    Document,
    FurnitureRole,
    Metadata,
    OutlineEntry,
    Page,
    Picture,
    Source,
    SourceFormat,
    TextLine,
    TextRun,
)
from sci2audio.layout import LayoutSettings, build_document
from sci2audio.layout.tagged import positioned

P = ("p",)
NOTES = ("section", "role:doc-endnotes", "ol")


@dataclass(frozen=True)
class Img:
    alt: str = ""


def line(text: str, *tags: str) -> tuple[TextRun, ...]:
    return (TextRun(text, tags=tags),)


def runs(*pieces: tuple[str, tuple[str, ...]]) -> tuple[TextRun, ...]:
    return tuple(TextRun(text, tags=tags) for text, tags in pieces)


def content(*pages: list, outline: tuple[OutlineEntry, ...] = (), title: str = "") -> Content:
    """Pages of lines (tuples of runs) and pictures (`Img`), in the order given."""
    built = []
    for number, items in enumerate(pages, 1):
        lines, pictures, order = [], [], []
        for item in items:
            if isinstance(item, Img):
                pictures.append(Picture(f"p{number}-i{len(pictures) + 1}", alt=item.alt))
                order.append(pictures[-1].id)
            else:
                lines.append(TextLine(f"p{number}-l{len(lines) + 1}", item))
                order.append(lines[-1].id)
        built.append(Page(number, tuple(lines), tuple(pictures), order=tuple(order)))
    return Content(
        Source("book.epub", SourceFormat.EPUB),
        tuple(built),
        Metadata(title=title),
        outline=outline,
    )


def kinds(doc: Document) -> list[tuple[str, str]]:
    return [(block.kind.value, block.text) for block in doc.blocks]


def tree(doc: Document) -> list[tuple[str, int, int]]:
    def walk(sections: tuple) -> list:
        return [x for s in sections for x in [(s.title, s.level, s.start), *walk(s.children)]]

    return walk(doc.sections)


# ---- routing (D-405) ------------------------------------------------------------------


def test_content_with_any_box_is_read_by_positions() -> None:
    plain = content([line("Methods", "h2")])
    assert not positioned(plain)
    boxed = Content(
        plain.source,
        (Page(1, plain.pages[0].lines, (Picture("i", Box(0, 0, 10, 10)),)),),
    )
    assert positioned(boxed)
    # by positions, a line without a box is a paragraph whatever its tags (as before #75)
    assert kinds(build_document(boxed))[0] == ("paragraph", "Methods")
    assert kinds(build_document(plain)) == [("heading", "Methods")]


def test_language_comes_from_settings_then_file_then_english() -> None:
    found = content([line("x", "p")])
    assert build_document(found).language == "en"
    assert build_document(found, LayoutSettings(language="de")).language == "de"


# ---- elements -------------------------------------------------------------------------


def test_a_line_after_a_br_continues_its_element_unless_a_picture_stands_between() -> None:
    doc = build_document(
        content(
            [
                line("Roses are red,", "p"),
                line("violets blue;", "p", "br"),
                Img(),
                line("sugar is sweet", "p", "br"),
            ]
        )
    )
    assert kinds(doc) == [
        ("paragraph", "Roses are red,\nviolets blue;"),
        ("figure", ""),
        ("paragraph", "sugar is sweet"),
    ]
    assert [p.start for p in doc.blocks[0].parts] == [0, len("Roses are red,\n")]


def test_inline_markup_does_not_change_the_kind_but_a_whole_line_does() -> None:
    doc = build_document(
        content(
            [
                runs(("Text with ", P), ("x^2", ("p", "span", "role:math")), (".", P)),
                runs(("emphasis", ("p", "em")), (" first", P)),
                line("x = y (3)", "div", "role:math"),
                line("Heading in a link", "h2", "a", "link:p1-l1"),
            ]
        )
    )
    assert [b.kind for b in doc.blocks] == [
        BlockKind.PARAGRAPH,
        BlockKind.PARAGRAPH,
        BlockKind.FORMULA,
        BlockKind.HEADING,
    ]
    assert doc.blocks[2].label == "3"


def test_code_and_quotes_are_paragraphs_keeping_their_lines() -> None:
    doc = build_document(
        content(
            [
                line("def f():", "pre", "code"),
                line("    return 1", "pre", "code", "br"),
                line("A quote.", "blockquote", "p"),
            ]
        )
    )
    assert kinds(doc) == [
        ("paragraph", "def f():\n    return 1"),
        ("paragraph", "A quote."),
    ]


def test_hidden_text_contents_and_page_breaks_are_furniture() -> None:
    doc = build_document(
        content(
            [
                line("not shown", "p", "hidden"),
                line("for eyes only", "span", "aria-hidden"),
                line("Contents", "nav", "epub:toc", "h2"),
                line("Chapter 1", "nav", "epub:toc", "ol", "li", "a", "link:p1"),
                line("xii", "span", "epub:pagebreak"),
                line("Text.", "p"),
            ]
        )
    )
    assert [(b.kind, b.role) for b in doc.blocks] == [
        (BlockKind.FURNITURE, None),
        (BlockKind.FURNITURE, None),
        (BlockKind.FURNITURE, FurnitureRole.CONTENTS),
        (BlockKind.FURNITURE, FurnitureRole.PAGE_NUMBER),
        (BlockKind.PARAGRAPH, None),
    ]
    assert doc.blocks[2].text == "Contents\nChapter 1"  # one table of contents
    assert doc.sections == ()  # its heading is furniture, not a section


# ---- notes (D-406, D-414) -------------------------------------------------------------


def test_notes_are_one_footnote_each_where_the_file_puts_them() -> None:
    doc = build_document(
        content(
            [
                runs(("Cited.", P), ("1", ("p", "a", "role:doc-noteref", "link:p1-l4"))),
                line("More text.", "p"),
                line("Notes", *NOTES[:2], "h2"),
                line("First note,", *NOTES, "li", "#n1", "p"),
                line("its second paragraph.", *NOTES, "li", "#n1", "p"),
                line("Second note.", *NOTES, "li", "#n2", "p"),
                line("An aside note.", "aside", "#a1", "epub:footnote", "p"),
            ]
        )
    )
    assert kinds(doc) == [
        ("paragraph", "Cited.1"),
        ("paragraph", "More text."),
        ("heading", "Notes"),
        ("footnote", "First note,\nits second paragraph."),
        ("footnote", "Second note."),
        ("footnote", "An aside note."),
    ]
    assert {b.label for b in doc.blocks} == {""}  # no note prints its mark


def test_a_note_that_prints_its_mark_carries_it_as_label() -> None:
    doc = build_document(
        content(
            [
                runs(("Cited.", P), ("*", ("p", "sup", "epub:noteref", "link:p1-l2"))),
                line("* A starred note.", "aside", "epub:footnote", "p"),
            ]
        )
    )
    assert (doc.blocks[1].kind, doc.blocks[1].label) == (BlockKind.FOOTNOTE, "*")


# ---- tables, figures, captions (D-412, D-413) -----------------------------------------


def test_a_table_is_one_block_and_its_caption_a_caption_before_it() -> None:
    table = ("table",)
    doc = build_document(
        content(
            [
                line("Table 1: Results.", *table, "caption"),
                line("Group", *table, "thead", "tr", "th"),
                Img("a sparkline"),
                line("A", *table, "tbody", "tr", "td"),
                line("After.", "p"),
            ]
        )
    )
    assert kinds(doc) == [
        ("caption", "Table 1: Results."),
        ("table", "Group\nA"),
        ("paragraph", "After."),
    ]
    assert (doc.blocks[0].label, doc.blocks[0].describes) == ("Table 1", 1)
    assert [p.item for p in doc.blocks[1].parts] == ["p1-l2", "p1-i1", "p1-l3"]


def test_a_tables_caption_names_the_table_after_it_before_a_picture_before_it() -> None:
    doc = build_document(
        content([Img(), line("Table 2: Data.", "table", "caption"), line("a", "table", "td")])
    )
    assert [(b.kind.value, b.describes) for b in doc.blocks] == [
        ("figure", None),
        ("caption", 2),
        ("table", None),
    ]


def test_a_picture_inside_a_note_keeps_the_note_whole() -> None:
    note = (*NOTES, "li", "#n1")  # text right inside the note's element
    doc = build_document(content([line("See", *note), Img(), line("this.", *note, "br")]))
    assert kinds(doc) == [("footnote", "See\nthis.")]


def test_two_tables_with_nothing_between_them_are_one() -> None:
    """The tags carry no table identity (D-412)."""
    doc = build_document(content([line("a", "table", "td"), line("b", "table", "td")]))
    assert kinds(doc) == [("table", "a\nb")]


def test_each_picture_is_a_figure_and_a_figcaption_names_the_one_next_to_it() -> None:
    doc = build_document(
        content(
            [
                Img("a chart"),
                line("Figure 1: A chart.", "figure", "figcaption"),
                line("Text.", "p"),
                line("Figure 2. Caption first.", "figure", "figcaption"),
                Img(),
                Img(),
                line("Another caption.", "figure", "figcaption"),
            ]
        )
    )
    assert [(b.kind.value, b.label, b.describes) for b in doc.blocks] == [
        ("figure", "", None),
        ("caption", "Figure 1", 0),
        ("paragraph", "", None),
        ("caption", "Figure 2", 4),
        ("figure", "", None),
        ("figure", "", None),
        ("caption", "", 5),
    ]
    assert doc.blocks[0].text == ""


def test_svg_text_is_a_figure() -> None:
    doc = build_document(
        content([line("x axis", "svg", "text"), line("y axis", "svg", "text"), line("T.", "p")])
    )
    assert kinds(doc) == [("figure", "x axis\ny axis"), ("paragraph", "T.")]


def test_list_items_carry_no_label() -> None:
    doc = build_document(
        content(
            [
                line("one", "ol", "li"),
                line("inner", "ol", "li", "ul", "li"),
                line("two", "ol", "li", "p"),
            ]
        )
    )
    assert [(b.kind, b.label) for b in doc.blocks] == [(BlockKind.LIST_ITEM, "")] * 3


# ---- headings and sections (D-407, D-408) ---------------------------------------------


def test_levels_count_from_each_pages_highest_rank_closing_gaps() -> None:
    doc = build_document(
        content(
            [line("Title", "h1"), line("A", "h3"), line("B", "h3"), line("t", "p")],
            [line("1 Chapter", "h2"), line("1.1 Part", "h4"), line("t", "p")],
        )
    )
    assert tree(doc) == [
        ("Title", 1, 0),
        ("A", 2, 1),
        ("B", 2, 2),
        ("1 Chapter", 1, 4),
        ("1.1 Part", 2, 5),
    ]
    assert [doc.blocks[k].label for k in (4, 5)] == ["1", "1.1"]


def test_the_outline_gives_each_page_its_base_level() -> None:
    outline = (
        OutlineEntry("Part I", 1, 1),
        OutlineEntry("Chapter 1", 2, 2),
        OutlineEntry("Section", 2, 2, "p2-l3"),  # its own level, not its rank's
        OutlineEntry("Part II", 1, 4),
    )
    doc = build_document(
        content(
            [line("Part I", "h1")],
            [line("Chapter 1", "h2"), line("Lead", "h3"), line("Section", "h3"), line("t", "p")],
            [line("Continued", "h2")],  # no entry: the base of the page before
            [line("Part II", "h1")],
            outline=outline,
        )
    )
    assert tree(doc) == [
        ("Part I", 1, 0),
        ("Chapter 1", 2, 1),
        ("Lead", 3, 2),
        ("Section", 2, 3),
        ("Continued", 2, 5),
        ("Part II", 1, 6),
    ]


def test_a_single_top_entry_naming_the_book_is_skipped() -> None:
    outline = (OutlineEntry("Book", 1, 1), OutlineEntry("One", 2, 2), OutlineEntry("Two", 2, 3))
    doc = build_document(
        content([line("Book", "h1")], [line("One", "h2")], [line("Two", "h2")], outline=outline)
    )
    assert tree(doc) == [("Book", 1, 0), ("One", 1, 1), ("Two", 1, 2)]


def test_the_outline_makes_the_sections_of_pages_without_headings() -> None:
    outline = (
        OutlineEntry("Chapter One", 1, 1),
        OutlineEntry("2. The Second", 1, 2, "p2-l2"),
        OutlineEntry("Empty", 1, 3),
        OutlineEntry("Has headings", 1, 4),
    )
    doc = build_document(
        content(
            [line("CHAPTER ONE", "p", "span"), line("Text.", "p")],
            [line("Before.", "p"), line("The Second", "p"), line("Text.", "p")],
            [],
            [line("Own heading", "h2"), line("Text.", "p")],
            outline=outline,
        )
    )
    assert tree(doc) == [
        ("CHAPTER ONE", 1, 0),
        ("The Second", 1, 3),
        ("Own heading", 1, 5),
    ]
    assert [b.kind for b in doc.blocks[:5]] == [
        BlockKind.HEADING,
        BlockKind.PARAGRAPH,
        BlockKind.PARAGRAPH,
        BlockKind.HEADING,
        BlockKind.PARAGRAPH,
    ]


def test_an_entry_whose_title_is_not_printed_starts_a_section_without_a_heading() -> None:
    outline = (OutlineEntry("Titlepage", 1, 1), OutlineEntry("Story", 1, 2, "p2-l2"))
    doc = build_document(
        content(
            [line("By H. G. Wells.", "p")],
            [line("Epigraph.", "p"), line("It began.", "p")],
            outline=outline,
        )
    )
    assert tree(doc) == [("Titlepage", 1, 0), ("Story", 1, 2)]
    assert BlockKind.HEADING not in {b.kind for b in doc.blocks}


def test_letters_number_headings_only_where_several_do() -> None:
    lettered = build_document(content([line("A Proofs", "h2"), line("B More", "h2")]))
    assert [b.label for b in lettered.blocks] == ["A", "B"]
    single = build_document(content([line("A Note on Ethics", "h2")]))
    assert single.blocks[0].label == ""


def test_an_empty_heading_is_a_paragraph() -> None:
    doc = build_document(content([line(" ", "h2"), line("t", "p")]))
    assert doc.blocks[0].kind is BlockKind.PARAGRAPH
    assert doc.sections == ()


# ---- any tagged content ---------------------------------------------------------------

TAGS = [
    *("p", "h1", "h2", "h3", "h6", "li", "ol", "table", "td", "caption", "figure"),
    *("figcaption", "pre", "svg", "nav", "aside", "section", "em", "span", "math"),
    *("br", "hidden", "aria-hidden", "#n1", "#n2", "role:math", "role:doc-endnotes"),
    *("role:doc-endnote", "epub:footnote", "epub:toc", "epub:pagebreak", "role:doc-noteref"),
    *("link:p1-l1", "link:p1-l2", "link:p2-l1", "lang:en"),
]
texts = st.sampled_from(["x", " ", "1", "*", "Table 1: A", "Figure 2. B", "1.2 Head", "A B"])


@st.composite
def tagged_contents(draw: st.DrawFn) -> Content:
    pages = []
    for number in range(1, draw(st.integers(0, 3)) + 1):
        lines = []
        for k in range(draw(st.integers(0, 6))):
            pieces = draw(
                st.lists(
                    st.tuples(texts, st.lists(st.sampled_from(TAGS), max_size=5).map(tuple)),
                    min_size=1,
                    max_size=3,
                )
            )
            lines.append(TextLine(f"p{number}-l{k + 1}", runs(*pieces)))
        pictures = [
            Picture(f"p{number}-i{k + 1}", alt=draw(texts)) for k in range(draw(st.integers(0, 2)))
        ]
        ids = [item.id for item in (*lines, *pictures)]
        order = tuple(draw(st.permutations(ids))) if draw(st.booleans()) else ()
        pages.append(Page(number, tuple(lines), tuple(pictures), order=order))
    built = tuple(pages)
    return Content(
        Source("x.epub", SourceFormat.EPUB),
        built,
        Metadata(title=draw(texts)),
        outline=draw(outlines(built)),
    )


@given(tagged_contents())
def test_any_tagged_content_gives_a_document_keeping_every_item_once(found: Content) -> None:
    """Never fails; every item is in exactly one block (the `Document` checks it); a heading
    comes from an h tag or an outline entry; sections start in reading order."""
    doc = build_document(found)
    items = found.items()
    named = {entry.item for entry in found.outline if entry.item}
    pages = {entry.page for entry in found.outline}
    for block in doc.blocks:
        if block.kind is BlockKind.HEADING:
            first = items[block.parts[0].item]
            tags = {t for run in getattr(first[1], "runs", ()) for t in run.tags}
            assert (
                tags & {"h1", "h2", "h3", "h6"}
                or {p.item for p in block.parts} & named
                or first[0].number in pages
            )
    starts = [s.start for s in _flat(doc.sections)]
    assert starts == sorted(set(starts))


def _flat(sections: tuple) -> list:
    return [x for s in sections for x in (s, *_flat(s.children))]
