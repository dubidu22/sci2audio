"""Fonts with no Unicode source, and how readable each page's text is (#442 part A, D-762).

A PDF whose TrueType fonts lost their ToUnicode map, cmap and post table (Acrobat Distiller
after a PDF organiser) holds only glyph numbers, and PDFium reads them as characters: "Das
Buch" becomes "'DV %XFK". Extraction counts such characters per page (`Page.unmapped`), and
`legibility` measures every page's text, so the app can stop before voicing nonsense
(#442 part B). The fixtures write their own font program: no real font, no licence.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from core_strategies import contents
from hypothesis import given
from pdf_maker import cropped, glyph_number_pdf, one_page_pdf

from sci2audio.core import Content, Page, TextLine
from sci2audio.extraction import (
    extract_epub,
    extract_markdown,
    extract_text,
    legibility,
    read_pdf,
)
from sci2audio.extraction.legibility import (
    FOREIGN_SHARE,
    MIN_LETTERS,
    MIN_PAIRS,
    RARE_PAIRS,
    RARE_SHARE,
    UNMAPPED_SHARE,
)

pytestmark = pytest.mark.timeout(120)

CORPUS = Path(__file__).resolve().parents[1] / "corpus"
GERMAN = [
    "Das Buch wurde in einer Zeit geschrieben, in der die Arbeit in den Quartieren",
    "neu gedacht werden musste. Die Menschen, die dort leben, kennen ihre Nachbarn,",
    "und sie wissen, was in ihrem Viertel fehlt. Wer mit ihnen arbeiten will, muss",
    "zuerst zuhoeren lernen und dann gemeinsam mit ihnen handeln, nicht an ihrer Stelle.",
]
ENGLISH = [
    "The book was written at a time when work in the neighbourhoods had to be thought",
    "anew. The people who live there know their neighbours, and they know what their",
    "district is missing. Anyone who wants to work with them must first learn to listen",
]


def read(data: bytes) -> Content:
    return read_pdf(data, "glyphs.pdf")


# ---- the font rule (AC-442.1) ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("lines", "read_as"),
    [(GERMAN, "'DV %XFK ZXUGH"), (ENGLISH, "7KH ERRN ZDV")],
    ids=["de", "en"],
)
def test_every_character_of_a_font_with_no_unicode_source_is_counted(
    lines: list[str], read_as: str
) -> None:
    (page,) = read(glyph_number_pdf(lines)).pages
    assert page.lines[0].text.startswith(read_as)  # as in the issue: "Das Buch wurde"
    assert page.characters > 150
    assert page.unmapped == page.characters


def test_only_the_glyph_numbers_of_a_page_are_counted() -> None:
    """A Helvetica line beside the glyph-number lines: its letters have a source."""
    (page,) = read(glyph_number_pdf(GERMAN[:1], plain=("Hello world",))).pages
    assert [line.text for line in page.lines][1] == "Hello world"
    assert page.unmapped == page.characters - len("Helloworld")


@pytest.mark.parametrize(
    ("source", "text"),
    [
        ({"to_unicode": True}, GERMAN[0]),  # the map gives the letters: nothing to count
        ({"cmap": True}, None),  # the program names its glyphs itself
        ({"post": True}, None),
    ],
    ids=["tounicode", "cmap", "post"],
)
def test_a_font_with_a_unicode_source_is_not_counted(
    source: dict[str, bool], text: str | None
) -> None:
    (page,) = read(glyph_number_pdf(GERMAN[:1], **source)).pages
    assert page.unmapped == 0
    if text is not None:
        assert page.lines[0].text == text


def test_glyph_numbers_the_crop_box_cuts_off_are_not_counted() -> None:
    """Only characters kept in the page's lines count: the first line (baseline 720 up) lies
    above the crop box, on the sheet."""
    data = cropped(glyph_number_pdf(GERMAN[:2]), (0, 0, 612, 710))
    (page,) = read(data).pages
    assert len(page.lines) == 1
    assert page.unmapped == page.characters > 0


def test_a_simple_font_with_glyph_names_pdfium_does_not_know_is_not_counted() -> None:
    """#187's example: Helvetica whose /Differences give unknown names reads the codes as
    letters ("ABC"). Such fonts set TeX's math symbols and matplotlib's text in the corpus,
    so they are left to the text check (D-762, the narrowing of AC-442.1)."""
    font = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica"
    font += b" /Encoding << /Type /Encoding /Differences [65 /g1 /g2 /g3] >> >>"
    data = one_page_pdf(b"BT /F1 12 Tf 72 720 Td (ABC) Tj ET", extra={6: font})
    data = data.replace(b"/F1 5 0 R", b"/F1 6 0 R")
    (page,) = read(data).pages
    assert page.lines[0].text == "ABC"
    assert page.unmapped == 0


# ---- the text check (AC-442.2) ---------------------------------------------------------------


def without_count(content: Content) -> Content:
    """The content as if no font had been counted: the text check alone."""
    pages = tuple(dataclasses.replace(page, unmapped=0) for page in content.pages)
    return dataclasses.replace(content, pages=pages)


def test_glyph_numbers_make_a_page_unreadable_by_their_count() -> None:
    (measured,) = legibility(read(glyph_number_pdf(GERMAN)))
    assert measured.unmapped == measured.characters
    assert measured.unreadable


@pytest.mark.parametrize("lines", [GERMAN, ENGLISH], ids=["de", "en"])
def test_glyph_numbers_in_the_usual_order_are_found_by_their_letter_pairs(
    lines: list[str],
) -> None:
    (measured,) = legibility(without_count(read(glyph_number_pdf(lines))))
    assert measured.pairs >= MIN_PAIRS
    assert measured.rare / measured.pairs >= RARE_SHARE
    assert measured.foreign == 0  # all plain ASCII: no script check would see it
    assert measured.unreadable


def test_glyph_numbers_far_from_unicode_are_found_by_their_foreign_letters() -> None:
    (measured,) = legibility(without_count(read(glyph_number_pdf(GERMAN, order="far"))))
    assert measured.letters >= MIN_LETTERS
    assert measured.foreign / measured.letters >= FOREIGN_SHARE
    assert measured.unreadable


def test_the_same_text_with_its_unicode_map_is_readable() -> None:
    (measured,) = legibility(read(glyph_number_pdf(GERMAN, to_unicode=True)))
    assert (measured.unmapped, measured.rare, measured.foreign) == (0, 0, 0)
    assert not measured.unreadable


def test_the_limits_are_the_decided_ones() -> None:
    assert (UNMAPPED_SHARE, MIN_PAIRS, RARE_SHARE) == (0.5, 100, 0.05)
    assert (MIN_LETTERS, FOREIGN_SHARE) == (50, 0.2)
    assert len(RARE_PAIRS) == 72
    assert all(len(pair) == 2 and pair.isascii() and pair.islower() for pair in RARE_PAIRS)


# ---- the corpus (AC-442.4) -------------------------------------------------------------------


def corpus() -> list[Content]:
    found = [read_pdf(path.read_bytes(), path.name) for path in sorted(CORPUS.glob("papers/*.pdf"))]
    found += [extract_epub(path) for path in sorted(CORPUS.glob("epub/*.epub"))]
    found += [extract_markdown(path) for path in sorted(CORPUS.glob("markdown/*.md"))]
    found += [extract_text(path) for path in sorted(CORPUS.glob("text/*.txt"))]
    return found


@pytest.fixture(scope="module")
def documents() -> list[Content]:
    return corpus()


def test_no_corpus_page_has_glyph_numbers_or_is_unreadable(documents: list[Content]) -> None:
    assert len(documents) == 13
    for content in documents:
        for page, measured in zip(content.pages, legibility(content), strict=True):
            assert page.unmapped == 0, (content.source.name, page.number)
            assert not measured.unreadable, (content.source.name, measured)


def shifted(text: str) -> str:
    """What a TrueType font in the usual glyph order without a Unicode source gives."""
    return "".join(chr(ord(c) - 29) if "!" <= c <= "~" else c for c in text)


def test_every_corpus_page_read_through_glyph_numbers_is_unreadable(
    documents: list[Content],
) -> None:
    """The letter pairs alone (no count): every page with enough of them."""
    checked = 0
    for content in documents:
        for page in content.pages:
            lines = tuple(
                TextLine(
                    line.id,
                    tuple(dataclasses.replace(run, text=shifted(run.text)) for run in line.runs),
                    line.box,
                )
                for line in page.lines
            )
            alone = Content(content.source, (Page(1, lines, width=page.width, height=page.height),))
            (measured,) = legibility(alone)
            if measured.pairs >= MIN_PAIRS:
                checked += 1
                assert measured.unreadable, (content.source.name, page.number, measured)
    assert checked >= 100


@given(content=contents())
def test_any_content_can_be_measured(content: Content) -> None:
    for page, measured in zip(content.pages, legibility(content), strict=True):
        assert measured.number == page.number
        assert measured.characters == page.characters
        assert 0 <= measured.rare <= measured.pairs
        assert 0 <= measured.foreign <= measured.letters <= measured.characters
