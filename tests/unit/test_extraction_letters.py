"""Letters of fonts with no Unicode source, recognised from their glyph shapes (#618, D-789).

A PDF whose TrueType fonts lost their ToUnicode map, cmap and post table holds only glyph
numbers (#442). The fixtures set text in Apache-2.0 subsets of Tinos and Arimo, the open
twins of Times New Roman and Arial (`tests/fixtures/fonts/`), as such a file holds them
(`pdf_maker.twin_pdf`): glyph order shuffled or the usual TrueType order, cmap and post
stripped, hmtx cut short, Identity-H, widths from the true advances.
"""

from __future__ import annotations

import struct
from collections import Counter

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pdf_maker import Twin, font_program, glyph_number_pdf, twin_pdf

from sci2audio.core import Content
from sci2audio.extraction import glyphs, legibility, letters, pdf, read_pdf

pytestmark = pytest.mark.timeout(120)
UNKNOWN = "�"  # a glyph read as no letter

# Written for these tests. Digits and , . - / : ( ) ü ß are what the usual TrueType order
# puts on control codes, which PDFium gives as white space (AC-442.7).
GERMAN = [
    "Das Buch „Gemeinwesenarbeit“ wurde 1980 geschrieben, für Menschen im Quartier.",
    "Die Arbeit (S. 12\u201314) zeigt: Wer mit ihnen arbeiten will, muss zuerst zuhören.",
    "Größere Städte, kleine Dörfer: 3/4 der Befragten äußern sich über die Nachbarschaft.",
    "Über 50 % der Älteren leben seit 1975 dort; sie wissen, was ihrem Viertel fehlt!",
]
ENGLISH = [
    "The book was written in 1980, at a time when the work in the neighbourhoods had to be",
    "thought anew (see pages 12-14). The people who live there know what is missing: 3/4 of",
    "them said so. Each one of these cases was seen at the centre, since the effect was clear.",
    "We expect that the evidence will be checked once more; the science is sound, they agree.",
]


def read(data: bytes) -> Content:
    return read_pdf(data, "twin.pdf")


def texts(content: Content) -> list[str]:
    return [line.text for page in content.pages for line in page.lines]


def unrecognised(data: bytes, monkeypatch: pytest.MonkeyPatch) -> Content:
    """The file read as before #618: no font's letters recognised."""
    with monkeypatch.context() as patch:
        patch.setattr(letters, "recognise", lambda usage: None)
        return read(data)


# ---- AC-442.5: twins are read exactly ----------------------------------------------------


@pytest.mark.parametrize("twin", ["times", "arial"])
@pytest.mark.parametrize("lines", [GERMAN, ENGLISH], ids=["de", "en"])
def test_a_font_with_no_unicode_source_is_read_from_its_glyph_shapes(
    twin: str, lines: list[str]
) -> None:
    """Shuffled glyph order and an hmtx cut short: the text equals the source."""
    content = read(twin_pdf(lines, twin))
    assert texts(content) == lines
    (page,) = content.pages
    assert page.recovered == page.unmapped == page.characters  # AC-442.8
    (measured,) = legibility(content)
    assert not measured.unreadable


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_every_shuffled_order_reads_the_same(seed: int) -> None:
    assert texts(read(twin_pdf(GERMAN, seed=seed, metrics="full"))) == GERMAN


def test_another_font_on_the_page_keeps_its_glyph_numbers() -> None:
    """Only the twin font's characters are recognised: a line in a font of rectangles on
    the same page keeps the glyph numbers it reads as today."""
    data = twin_pdf(ENGLISH, rectangles=("Hello",))
    lines = texts(read(data))
    assert lines[:-1] == ENGLISH
    assert lines[-1] == "+HOOR"  # the rectangles: no letter shapes, today's text


# ---- AC-442.6: refuse rather than guess --------------------------------------------------


def test_a_font_whose_shapes_match_no_letter_keeps_todays_text() -> None:
    (page,) = read(glyph_number_pdf(ENGLISH)).pages
    assert page.lines[0].text.startswith("7KH ERRN ZDV")
    assert page.recovered == 0
    assert page.unmapped == page.characters


def test_codes_that_are_not_glyph_numbers_keep_todays_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A /CIDToGIDMap stream: the PDF's widths disagree with the program's advances of the
    glyphs the codes name, so the shapes drawn would not be the ones printed."""
    data = twin_pdf(GERMAN, cid_map=True)
    content = read(data)
    assert content == unrecognised(data, monkeypatch)
    assert content.pages[0].recovered == 0
    assert texts(content) != GERMAN


def test_a_page_still_unreadable_keeps_todays_text(monkeypatch: pytest.MonkeyPatch) -> None:
    """The twin's line is recognised, but the page is mostly glyph numbers of a font
    without letter shapes: it stays unreadable, so nothing is recovered on it."""
    data = twin_pdf(GERMAN[:1], rectangles=tuple(ENGLISH))
    content = read(data)
    assert content == unrecognised(data, monkeypatch)
    assert content.pages[0].recovered == 0
    (measured,) = legibility(content)
    assert measured.unreadable


def test_a_font_past_the_glyph_budget_keeps_todays_text(monkeypatch: pytest.MonkeyPatch) -> None:
    data = twin_pdf(ENGLISH)
    monkeypatch.setattr(pdf, "MAX_DRAWN_GLYPHS", 10)
    content = read(data)
    assert content == unrecognised(data, monkeypatch)
    assert content.pages[0].recovered == 0


# ---- the close call (D-789 condition) ----------------------------------------------------


def test_c_and_e_drawn_alike_are_told_apart_by_the_words() -> None:
    """The font draws "e" exactly as "c" (and both are as wide in Times): only the words
    ("the", "each", "these", "once", "since") say which glyph is which."""
    content = read(twin_pdf(ENGLISH, same=("c", "e")))
    assert texts(content) == ENGLISH


def test_without_the_word_step_c_and_e_drawn_alike_are_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The proof the word step settles c and e: without it neither letter is recognised,
    "e" alone is far more than the font may leave out, and the font is refused."""
    monkeypatch.setattr(letters, "_by_words", lambda *args: None)
    data = twin_pdf(ENGLISH, same=("c", "e"))
    content = read(data)
    assert texts(content) != ENGLISH
    assert content.pages[0].recovered == 0
    assert content == unrecognised(data, monkeypatch)


# ---- AC-442.7: characters on control codes are no longer dropped -------------------------


@pytest.mark.parametrize("lines", [GERMAN, ENGLISH], ids=["de", "en"])
def test_digits_and_marks_on_control_codes_are_recovered(lines: list[str]) -> None:
    """The usual TrueType order puts the digits, , . - / : ( ), ü and ß on codes PDFium
    gives as white space or control codes: they are read like every other letter."""
    content = read(twin_pdf(lines, order="mac", metrics="full"))
    assert texts(content) == lines
    (page,) = content.pages
    assert page.recovered == page.unmapped == page.characters


def shifted(text: str) -> str:
    """What PDFium gives for the rectangle font of `glyph_number_pdf`, and what extraction
    keeps: printable codes as they are, white space and control codes of a glyph with ink
    as U+FFFD, the space (glyph 3, no ink) as a space."""
    found = ""
    for c in text:
        code = chr(ord(c) - 29)
        kept = code.isprintable() and not code.isspace()
        found += " " if c == " " else code if kept else UNKNOWN
    return found


def test_unrecognised_marks_on_control_codes_are_kept_and_counted() -> None:
    line = "Seite 70, Zeile 3 (oben)."
    (page,) = read(glyph_number_pdf([line])).pages
    assert page.lines[0].text == shifted(line)
    assert page.lines[0].text.count(UNKNOWN) == 7  # 7 0 , 3 ( ) .
    assert page.unmapped == page.characters
    assert page.recovered == 0


# ---- AC-442.11: a damaged program never fails the file -----------------------------------


@settings(max_examples=30, deadline=None)
@given(st.lists(st.tuples(st.integers(0, 1 << 16), st.integers(0, 255)), min_size=1, max_size=40))
def test_a_damaged_font_program_never_fails_the_file(damage: list[tuple[int, int]]) -> None:
    content = read(twin_pdf(ENGLISH[:2], damage=tuple(damage)))
    for page in content.pages:
        assert 0 <= page.recovered <= page.unmapped <= page.characters


def test_a_program_cut_in_its_glyphs_recognises_what_it_can_or_nothing() -> None:
    content = read(twin_pdf(ENGLISH, damage=tuple((k, 0xFF) for k in range(3000, 3400))))
    (page,) = content.pages
    assert page.recovered in (0, page.unmapped)  # a whole font, or none of it


# ---- the reference data (AC-442.12) ------------------------------------------------------


def test_the_reference_drawings_are_the_five_twins_in_four_styles() -> None:
    styles = letters.references()
    families = ("Tinos", "Arimo", "Cousine", "Caladea", "Carlito")
    kinds = ("Regular", "Bold", "Italic", "BoldItalic")
    assert [s.name for s in styles] == [f"{f} {k}" for f in families for k in kinds]
    for style in styles:
        assert len(style.letters) == len(style.widths) == len(style.shapes) == 216
        assert {"a", "ä", "ß", "0", ",", "„"} <= set(style.letters)
        assert np.allclose(style.shapes.sum(axis=1), 1)


def test_each_reference_letter_is_nearest_to_itself() -> None:
    for style in letters.references():
        for k in range(len(style.letters)):
            assert letters.distances(style.shapes[k], style.shapes)[k] == 0


def test_a_drawing_on_another_grid_gives_no_references(monkeypatch: pytest.MonkeyPatch) -> None:
    letters.references.cache_clear()
    monkeypatch.setattr(glyphs, "COLUMNS", glyphs.COLUMNS + 1)
    try:
        assert letters.references() == ()
    finally:
        monkeypatch.undo()
        letters.references.cache_clear()


@pytest.mark.parametrize(
    ("text", "known"),
    [("the", True), ("The,", True), ("„Das", True), ("1980,", True), ("3/4", True),
     ("thc", False), ("19ß0", False), ("", False)],
)  # fmt: skip
def test_a_word_counts_when_common_or_a_number(text: str, known: bool) -> None:
    assert letters._known(text) is known


# ---- recognition speed (AC-442.11) -------------------------------------------------------


def many_glyphs(count: int) -> letters.Usage:
    """A font of `count` glyphs, the Tinos subset's drawings over and over, each used."""
    twin = Twin.load("times")
    inked = [g for g in range(1, len(twin.glyphs)) if twin.glyphs[g]]
    order = [inked[k % len(inked)] for k in range(count)]
    program = font_program(
        [
            twin.glyphs[g] if struct.unpack_from(">h", twin.glyphs[g])[0] >= 0 else b""
            for g in order
        ],
        [twin.advances[g] for g in order],
        units=twin.units,
    )
    font = glyphs.read_font(program)
    assert font is not None
    usage = letters.Usage(font)
    for glyph, old in enumerate(order):
        usage.counts[glyph] = 1 + glyph % 7
        usage.widths[glyph] = 1000 * twin.advances[old] / twin.units
    usage.words.update(Counter(tuple(range(k, k + 5)) for k in range(0, count - 5, 3)))
    return usage


def test_recognition_of_many_glyphs_ends() -> None:
    """Glyphs drawn alike many times over: every one a close call no word settles, and the
    font refused, in bounded time (the benchmark below times 2,000)."""
    assert letters.recognise(many_glyphs(300)) is None


@pytest.mark.benchmark
def test_benchmark_recognising_2000_glyphs(benchmark) -> None:  # type: ignore[no-untyped-def]
    usage = many_glyphs(2000)
    benchmark.pedantic(lambda: letters.recognise(usage), rounds=1, iterations=1)
    assert benchmark.stats.stats.max < pdf.STEP_SECONDS / 4
