"""Fonts with no Unicode source, and how readable each page's text is (#442 part A, D-762).

A PDF whose TrueType fonts lost their ToUnicode map, cmap and post table (Acrobat Distiller
after a PDF organiser) holds only glyph numbers, and PDFium reads them as characters: "Das
Buch" becomes "'DV %XFK". Extraction counts such characters per page (`Page.unmapped`), and
`legibility` measures every page's text, so the app can stop before voicing nonsense
(#442 part B). The fixtures write their own font program: no real font, no licence.
"""

from __future__ import annotations

import dataclasses
import struct
from collections.abc import Callable
from pathlib import Path

import pytest
from core_strategies import contents
from hypothesis import given
from pdf_maker import cropped, glyph_number_pdf, one_page_pdf, turned

from sci2audio.core import Content, Page, Source, SourceFormat, TextLine, TextRun
from sci2audio.extraction import (
    PageLegibility,
    extract_epub,
    extract_markdown,
    extract_text,
    legibility,
    pdf,
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
    "data",
    [
        lambda: glyph_number_pdf(GERMAN),
        lambda: glyph_number_pdf(ENGLISH, order="far"),
        lambda: glyph_number_pdf(GERMAN[:2], plain=("Hello world", "Table 2: What it shows.")),
        lambda: cropped(glyph_number_pdf(GERMAN[:2]), (0, 0, 612, 710)),
        lambda: turned(glyph_number_pdf(GERMAN[:2], plain=("Hello world",)), 90),
    ],
    ids=["de", "en-far", "mixed", "cropped", "turned"],
)
def test_no_page_extraction_makes_counts_more_glyph_numbers_than_it_holds(
    data: Callable[[], bytes],
) -> None:
    """The bound core no longer checks (#574): on every page extraction makes, the count is
    at most the characters of the page's lines, and a page with glyph numbers counts some."""
    for page in read(data()).pages:
        assert 0 < page.unmapped <= page.characters, (page.number, page.unmapped)


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


def test_a_page_whose_characters_pdfium_maps_never_looks_at_a_font_program(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The map error is asked first: a font's program (megabytes for some fonts) is copied
    only for a character PDFium could not map (#562)."""

    def refuse(textpage: object, index: int) -> bool:
        raise AssertionError("a font was looked at for a character PDFium mapped")

    monkeypatch.setattr(pdf, "_sourceless", refuse)
    data = glyph_number_pdf(GERMAN[:1], to_unicode=True, plain=("Hello world",))
    (page,) = read(data).pages
    assert [line.text for line in page.lines] == [GERMAN[0], "Hello world"]
    assert page.unmapped == 0


def directory(version: bytes, tags: list[bytes]) -> bytes:
    """The start of a font program: its version tag and a table directory naming `tags`."""
    entries = b"".join(struct.pack(">4sIII", tag, 0, 0, 0) for tag in tags)
    return version + struct.pack(">HHHH", len(tags), 0, 0, 0) + entries


TRUETYPE = b"\x00\x01\x00\x00"


@pytest.mark.parametrize(
    ("program", "names_no_glyph"),
    [
        (directory(TRUETYPE, [b"glyf", b"head"]), True),
        (directory(TRUETYPE, [b"glyf", b"head", b"cmap"]), False),
        (directory(TRUETYPE, [b"glyf", b"head", b"post"]), False),
        (directory(b"true", [b"glyf", b"head"]), True),
        (directory(b"OTTO", [b"CFF ", b"head"]), True),
        (directory(b"ttcf", [b"glyf"]), False),  # a collection: not read
        (directory(TRUETYPE, []), False),  # no tables
        (TRUETYPE + struct.pack(">HHHH", 3, 0, 0, 0) + bytes(8), False),  # cut short
        (b"%!PS-AdobeFont-1.0: CMMI10", False),  # Type 1
        (b"", False),
    ],
    ids=[
        "truetype",
        "cmap",
        "post",
        "true",
        "otto",
        "collection",
        "no-tables",
        "cut-short",
        "type1",
        "empty",
    ],
)
def test_only_a_truetype_or_opentype_program_without_cmap_or_post_names_no_glyph(
    program: bytes, names_no_glyph: bool
) -> None:
    assert pdf._names_no_glyph(program) is names_no_glyph


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


def measured(
    characters: int = 0,
    unmapped: int = 0,
    pairs: int = 0,
    rare: int = 0,
    letters: int = 0,
    foreign: int = 0,
) -> PageLegibility:
    return PageLegibility(1, characters, unmapped, pairs, rare, letters, foreign)


@pytest.mark.parametrize(
    ("page", "unreadable"),
    [
        (measured(characters=100, unmapped=50), False),  # half: not more than half
        (measured(characters=100, unmapped=51), True),
        (measured(pairs=99, rare=99), False),  # too few pairs to judge
        (measured(pairs=100, rare=5), True),
        (measured(pairs=100, rare=4), False),
        (measured(letters=49, foreign=49), False),  # too few letters to judge
        (measured(letters=50, foreign=10), True),
        (measured(letters=50, foreign=9), False),
        (measured(), False),  # an empty page
    ],
    ids=[
        "unmapped-half",
        "unmapped-more",
        "pairs-99",
        "pairs-5-of-100",
        "pairs-4-of-100",
        "letters-49",
        "letters-10-of-50",
        "letters-9-of-50",
        "empty",
    ],
)
def test_the_limits_hold_at_their_boundaries(page: PageLegibility, unreadable: bool) -> None:
    assert page.unreadable is unreadable


@pytest.mark.parametrize(
    "text",
    ["".join(chr(0xE000 + n) for n in range(60)), "\ufffd" * 60],
    ids=["private-use", "replacement"],
)
def test_private_use_and_replacement_characters_are_foreign_letters(text: str) -> None:
    """A glyph PDFium could not map at all (U+FFFD) and a private-use character are counted
    as letters and as foreign ones (#187's measure)."""
    page = Page(1, lines=(TextLine("p1-l1", (TextRun(text),)),))
    content = Content(Source("broken.pdf", SourceFormat.PDF), (page,))
    (found,) = legibility(content)
    assert found.letters == found.foreign == 60
    assert found.unreadable


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
