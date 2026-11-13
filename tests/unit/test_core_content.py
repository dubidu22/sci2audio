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

# The same idea from an EPUB: no positions, but the source's own tags.
EPUB = Content(
    source=Source("book.epub", SourceFormat.EPUB),
    pages=(
        Page(
            1,
            lines=(
                TextLine("c1-1", (TextRun("Chapter One", tags=("h2",)),)),
                TextLine("c1-2", (TextRun("It was "), TextRun("dark", italic=True, tags=("em",)))),
            ),
            pictures=(Picture("c1-img1", alt="A map of the island"),),
        ),
    ),
    outline=(OutlineEntry("Chapter One", 1, 1),),
)


def test_line_text_joins_its_runs() -> None:
    assert PAPER.pages[0].lines[1].text == "We study sound"


def test_items_by_id() -> None:
    page, item = PAPER.items()["p2-pic1"]
    assert page.number == 2
    assert isinstance(item, Picture)
    assert len(EPUB.items()) == 3


def test_objects_are_frozen() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        PAPER.pages[0].number = 5  # type: ignore[misc]


@pytest.mark.parametrize(
    "make",
    [
        lambda: Source("dir/paper.pdf", SourceFormat.PDF),
        lambda: Source("C:\\paper.pdf", SourceFormat.PDF),
        lambda: Source("", SourceFormat.PDF),
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
    assert {"pdf": to_data(PAPER), "epub": to_data(EPUB)} == snapshot


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
