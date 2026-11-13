"""Tests for what extraction records (issue #17, PR 1): examples, refused values, export.

When the export format changes on purpose, accept the new golden file with
`uv run pytest --snapshot-update` and explain the diff in the PR (D-60).
"""

import dataclasses
import json

import pytest
from core_strategies import contents
from hypothesis import given
from syrupy.assertion import SnapshotAssertion

from sci2audio.core import (
    Box,
    Content,
    Drawing,
    Metadata,
    OutlineEntry,
    Page,
    Picture,
    Source,
    SourceFormat,
    TextLine,
    TextRun,
    from_data,
    to_data,
)

ROMAN = TextRun("We study ", font="Times-Roman", size=10, box=Box(72, 700, 120, 712))
BOLD = TextRun("sound", font="Times-Bold", size=10, bold=True, box=Box(120, 700, 150, 712))

# A made-up two-page PDF: a heading, a line in two styles, a running head, a chart, and
# bookmarks as a PDF stores them: no printed number, a trailing space, one with no target.
PAPER = Content(
    source=Source("paper.pdf", SourceFormat.PDF, sha256="ab12"),
    metadata=Metadata(title="A Small Paper", authors=("A. Author",), date="2024", language="en"),
    pages=(
        Page(
            1,
            lines=(
                TextLine("p1-l1", (TextRun("1 Introduction", "Helvetica-Bold", 14, bold=True),)),
                TextLine("p1-l2", (ROMAN, BOLD), Box(72, 700, 150, 712)),
            ),
            width=612,
            height=792,
        ),
        Page(
            2,
            lines=(TextLine("p2-l1", (TextRun("A Small Paper", "Times-Italic", 8, italic=True),)),),
            pictures=(Picture("p2-pic1", Box(72, 100, 540, 400)),),
            drawings=(Drawing("p2-d1", Box(72, 410, 540, 410.5)),),
            width=612,
            height=792,
        ),
    ),
    outline=(
        OutlineEntry("Introduction", 1, 1),
        OutlineEntry("Motivation ", 2, 1),
        OutlineEntry("Results", 1, 2),
        OutlineEntry("", 1),
    ),
)

# The same idea from an EPUB: no positions, but the source's own tags, the order of lines
# and pictures, where the image is stored, and an outline entry pointing at an anchor.
EPUB = Content(
    source=Source("book.epub", SourceFormat.EPUB),
    pages=(
        Page(
            1,
            lines=(
                TextLine("c1-1", (TextRun("Chapter One", tags=("h2",)),)),
                TextLine("c1-2", (TextRun("It was "), TextRun("dark", italic=True, tags=("em",)))),
                TextLine("c1-3", (TextRun("Part Two", tags=("h3", "#part-2")),)),
            ),
            pictures=(Picture("c1-img1", alt="A map of the island", ref="epub/images/map.png"),),
            order=("c1-1", "c1-img1", "c1-2", "c1-3"),
        ),
    ),
    outline=(OutlineEntry("Chapter One", 1, 1), OutlineEntry("Part Two", 2, 1, item="c1-3")),
)

# A plain-text file that was not UTF-8: read as Windows-1252, a guess (D-345, D-346). One
# page; the second printed line of the paragraph continues the first (D-344).
TEXT = Content(
    source=Source("notes.txt", SourceFormat.TEXT, encoding="windows-1252", encoding_guessed=True),
    pages=(
        Page(
            1,
            lines=(
                TextLine("p1-l1", (TextRun("Caf\u00e9 notes \u2013 first line", tags=("p",)),)),
                TextLine("p1-l2", (TextRun("and its second line", tags=("p", "br")),)),
            ),
            order=("p1-l1", "p1-l2"),
        ),
    ),
)


def test_line_text_joins_its_runs() -> None:
    assert PAPER.pages[0].lines[1].text == "We study sound"


def test_items_by_id() -> None:
    page, item = PAPER.items()["p2-pic1"]
    assert page.number == 2
    assert isinstance(item, Picture)
    assert len(EPUB.items()) == 4


def test_objects_are_frozen() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        PAPER.pages[0].number = 5  # type: ignore[misc]


@pytest.mark.parametrize(
    "make",
    [
        lambda: Source("dir/paper.pdf", SourceFormat.PDF),
        lambda: Source("C:\\paper.pdf", SourceFormat.PDF),
        lambda: Source("", SourceFormat.PDF),
        lambda: Source("notes.txt", SourceFormat.TEXT, encoding_guessed=True),  # guessed what?
        lambda: Source("paper.pdf", SourceFormat.PDF, encoding="utf-8"),  # brings its own
        lambda: Source("book.epub", SourceFormat.EPUB, encoding="utf-8"),
        lambda: Box(5, 0, 1, 1),
        lambda: Box(0, 5, 1, 1),
        lambda: Box(float("nan"), 0, 1, 1),
        lambda: TextRun(""),
        lambda: TextRun("a", size=-1),
        lambda: TextRun("a", size=float("inf")),
        lambda: TextLine("l1", ()),
        lambda: Page(0),
        lambda: Page(1, width=612),
        lambda: Page(1, width=0, height=792),
        lambda: Content(PAPER.source, (Page(2),)),
        lambda: Content(PAPER.source, (Page(1), Page(1))),
        lambda: Content(
            PAPER.source,
            (Page(1, pictures=(Picture("x"),), drawings=(Drawing("x", Box(0, 0, 1, 1)),)),),
        ),
        lambda: Content(PAPER.source, (Page(1, pictures=(Picture(""),)),)),
        lambda: OutlineEntry("Introduction", 0),
        lambda: Content(PAPER.source, (Page(1),), outline=(OutlineEntry("Setup", 2, 1),)),
        lambda: Content(
            PAPER.source,
            (Page(1),),
            outline=(OutlineEntry("Methods", 1, 1), OutlineEntry("Data", 3, 1)),
        ),
        lambda: Content(  # back up a level, then two deeper
            PAPER.source,
            (Page(1),),
            outline=(
                OutlineEntry("A", 1, 1),
                OutlineEntry("A.1", 2, 1),
                OutlineEntry("B", 1, 1),
                OutlineEntry("B.1.1", 3, 1),
            ),
        ),
        lambda: Content(PAPER.source, (Page(1),), outline=(OutlineEntry("Methods", 1, 0),)),
        lambda: Content(PAPER.source, (Page(1),), outline=(OutlineEntry("Methods", 1, 2),)),
        lambda: Content(PAPER.source, (), outline=(OutlineEntry("Methods", 1, 1),)),
        lambda: Page(
            1, lines=(TextLine("l1", (TextRun("a"),)),), order=("l2",)
        ),  # an id not on the page
        lambda: Page(
            1, lines=(TextLine("l1", (TextRun("a"),)),), pictures=(Picture("i1"),), order=("l1",)
        ),  # one left out
        lambda: Page(1, lines=(TextLine("l1", (TextRun("a"),)),), order=("l1", "l1")),  # one twice
        lambda: Content(  # an item on another page
            PAPER.source,
            (Page(1, lines=(TextLine("l1", (TextRun("a"),)),)), Page(2)),
            outline=(OutlineEntry("Methods", 1, 2, item="l1"),),
        ),
        lambda: Content(  # an item without a page
            PAPER.source,
            (Page(1, lines=(TextLine("l1", (TextRun("a"),)),)),),
            outline=(OutlineEntry("Methods", 1, item="l1"),),
        ),
        lambda: Content(  # an item the content does not have
            PAPER.source,
            (Page(1, lines=(TextLine("l1", (TextRun("a"),)),)),),
            outline=(OutlineEntry("Methods", 1, 1, "l9"),),
        ),
    ],
)
def test_invalid_values_are_refused(make: object) -> None:
    with pytest.raises(ValueError):  # noqa: PT011 - each case has its own message
        make()  # type: ignore[operator]


def test_an_outline_keeps_its_nesting_in_its_levels() -> None:
    """Entries go deeper one level at a time and come back up any number of levels; titles
    stay as stored, an entry may point at no page, and a file without an outline has none."""
    outline = (
        OutlineEntry("A", 1, 1),
        OutlineEntry("A.1", 2, 1),
        OutlineEntry("A.1.1 ", 3),
        OutlineEntry("", 1, 1),
    )
    content = Content(PAPER.source, (Page(1),), outline=outline)
    assert content.outline == outline
    assert Content(PAPER.source, (Page(1),)).outline == ()


def test_a_page_without_positions_keeps_the_order_of_lines_and_pictures() -> None:
    """`order` places the picture between the heading and the paragraph (D-309); a page
    whose items have boxes needs none, and an outline entry can point at an item (D-311)."""
    page = EPUB.pages[0]
    assert page.order == ("c1-1", "c1-img1", "c1-2", "c1-3")
    assert PAPER.pages[1].order == ()
    assert EPUB.items()[EPUB.outline[1].item][1].text == "Part Two"  # type: ignore[union-attr]
    assert page.pictures[0].ref == "epub/images/map.png"


def test_an_outline_item_without_a_page_is_named_as_such() -> None:
    line = TextLine("l1", (TextRun("a"),))
    with pytest.raises(ValueError, match="points at item 'l1' but at no page"):
        Content(PAPER.source, (Page(1, lines=(line,)),), outline=(OutlineEntry("M", 1, item="l1"),))


@pytest.mark.timeout(10)
def test_many_anchors_into_one_long_page_are_checked_quickly() -> None:
    """One large chapter file with a long anchored table of contents (D-311): each page's
    ids are collected once, not once per entry (review of PR #140, finding 1)."""
    lines = tuple(TextLine(f"l{n}", (TextRun("a"),)) for n in range(50_000))
    outline = tuple(OutlineEntry(f"S{n}", 1, 1, item=f"l{n * 25}") for n in range(2_000))
    content = Content(PAPER.source, (Page(1, lines=lines),), outline=outline)
    assert len(content.outline) == 2_000


@pytest.mark.parametrize(
    "data",
    [
        {"x0": 0, "y0": 0, "x1": 1, "y1": 1, "extra": 1},
        {"x0": "0", "y0": 0, "x1": 1, "y1": 1},
        {"x0": True, "y0": 0, "x1": 1, "y1": 1},
        [0, 0, 1, 1],
    ],
)
def test_from_data_refuses_data_that_does_not_fit(data: object) -> None:
    with pytest.raises(ValueError):  # noqa: PT011
        from_data(Box, data)  # type: ignore[arg-type]


def test_export_golden_file(snapshot: SnapshotAssertion) -> None:
    assert {"pdf": to_data(PAPER), "epub": to_data(EPUB), "text": to_data(TEXT)} == snapshot


def test_a_source_says_how_its_text_was_read() -> None:
    """A text file names its encoding and whether it was a guess (D-346); PDF and EPUB bring
    their own, so their sources keep the defaults and export without the two fields."""
    assert (TEXT.source.encoding, TEXT.source.encoding_guessed) == ("windows-1252", True)
    assert Source("notes.md", SourceFormat.MARKDOWN, encoding="utf-8").encoding_guessed is False
    assert "encoding" not in to_data(PAPER.source)
    assert "encoding_guessed" not in to_data(EPUB.source)
    assert from_data(Content, to_data(TEXT)) == TEXT


@given(content=contents())
def test_content_round_trips_through_export(content: Content) -> None:
    data = to_data(content)
    assert from_data(Content, data) == content
    assert from_data(Content, json.loads(json.dumps(data))) == content


@given(content=contents())
def test_export_is_sorted_and_repeatable(content: Content) -> None:
    text = json.dumps(to_data(content))
    assert text == json.dumps(to_data(content), sort_keys=True)
    assert text == json.dumps(to_data(from_data(Content, json.loads(text))))


@given(content=contents())
def test_every_item_is_found_by_its_id(content: Content) -> None:
    found = content.items()
    total = sum(len(p.lines) + len(p.pictures) + len(p.drawings) for p in content.pages)
    assert len(found) == total
    for item_id, (page, item) in found.items():
        assert item.id == item_id
        assert item in (*page.lines, *page.pictures, *page.drawings)
