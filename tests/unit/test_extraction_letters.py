"""Letters of fonts with no Unicode source, recognised from their glyph shapes (#618, D-789).

A PDF whose TrueType fonts lost their ToUnicode map, cmap and post table holds only glyph
numbers (#442). The fixtures set text in Apache-2.0 subsets of Tinos and Arimo, the open
twins of Times New Roman and Arial (`tests/fixtures/fonts/`), as such a file holds them
(`pdf_maker.twin_pdf`): glyph order shuffled or the usual TrueType order, cmap and post
stripped, hmtx cut short, Identity-H, widths from the true advances.
"""

from __future__ import annotations

import struct
import time
from collections import Counter

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pdf_maker import (
    Twin,
    chained_twin_pdf,
    font_program,
    glyph_number_pdf,
    heavy_glyph_pdf,
    twin_pdf,
)

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
        patch.setattr(letters, "recognise", lambda *args: None)
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


TIMES_WIDTHS = (444, 500, 278, 333, 722, 389, 556, 611, 667, 250)  # Tinos letters' advances


def test_a_monospaced_font_behind_a_glyph_map_keeps_todays_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A Cousine subset whose codes go through a shuffled /CIDToGIDMap stream: every advance
    is the same, so the widths cannot show the codes are glyph numbers, and the shapes drawn
    are not the ones printed. The font is refused (#618)."""
    data = twin_pdf(ENGLISH, "courier", cid_map=True)
    content = read(data)
    assert content == unrecognised(data, monkeypatch)
    assert content.pages[0].recovered == 0


def test_a_monospaced_font_keeps_todays_text_even_in_glyph_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The same font with its codes its glyph numbers is refused too: nothing in the file
    tells the two apart (`IDENTITY_WIDTHS`)."""
    data = twin_pdf(ENGLISH, "courier")
    assert read(data) == unrecognised(data, monkeypatch)


def test_a_font_whose_characters_pdfium_partly_maps_keeps_todays_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Glyph numbers in the Arabic, Hebrew or Tamil ranges get no map error from PDFium, so
    those characters of the font are not counted as glyph numbers. A font whose characters
    on a page are not all accounted for is refused, and part B judges the page as before
    (#618)."""
    data = twin_pdf(GERMAN, "arial", spread=0xE00, seed=1, metrics="full")
    content = read(data)
    assert content == unrecognised(data, monkeypatch)
    page = content.pages[0]
    assert page.recovered == 0 < page.unmapped < page.characters


def test_fonts_refused_one_round_at_a_time_are_read_at_most_twice_more(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Five recognisable fonts on five pages, each page readable only while the font before
    it is recognised: page 1 refuses font 1, then page 2 refuses font 2, and so on. After
    the second round in which a page fails, every font left is refused: no page is read more
    than three times in all, where main reads each once, and the file keeps today's text."""
    data = chained_twin_pdf(ENGLISH, "the cases", 5)
    reads = []
    real = pdf._read_again

    def counted(document, first, found, sourceless):  # type: ignore[no-untyped-def]
        reads.append(first.number)
        return real(document, first, found, sourceless)

    monkeypatch.setattr(pdf, "_read_again", counted)
    content = read(data)
    assert len(content.pages) == 5
    assert len(content.pages) + len(reads) <= 3 * len(content.pages)
    assert max(reads.count(n) for n in set(reads)) <= 2
    monkeypatch.undo()
    assert content == unrecognised(data, monkeypatch)


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


def test_the_word_step_stops_at_its_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    """The close calls' work is counted against the read's budget: with none left, c and e
    drawn alike are not settled and the font is refused (#618)."""
    data = twin_pdf(ENGLISH, same=("c", "e"))
    monkeypatch.setattr(glyphs, "MAX_WORD_STEPS", 0)
    content = read(data)
    assert content.pages[0].recovered == 0
    assert content == unrecognised(data, monkeypatch)


def test_the_word_step_spends_at_most_its_budget() -> None:
    usage = many_glyphs(300)
    budget = glyphs.Budget(steps=5_000)
    letters.recognise(usage, budget)
    assert 0 <= budget.steps <= 5_000
    assert budget.steps < 5_000  # close calls were tried


@pytest.mark.parametrize(
    ("count", "widths"),
    [(20_000, (600,)), (2_000, (600,)), (20_000, TIMES_WIDTHS), (2_000, TIMES_WIDTHS)],
    ids=["20000-mono", "2000-mono", "20000-times", "2000-times"],
)
def test_a_font_of_heavy_glyphs_costs_little(count: int, widths: tuple[int, ...]) -> None:
    """Glyphs that each hold one 8,191-point glyph: within every limit of a glyph, but before
    the read's budget a page of 20,000 took over 60 s and 2,000 took 43 s to recognise
    (#618). No outline is parsed while the page is read; the monospaced font is
    refused before any glyph is drawn, the one with Times New Roman's widths when the
    read's points run out. The page keeps today's text; main reads it in about 1 s."""
    data = heavy_glyph_pdf(count, widths=widths)
    start = time.perf_counter()
    content = read(data)
    elapsed = time.perf_counter() - start
    assert content.pages[0].recovered == 0
    assert content.pages[0].unmapped == content.pages[0].characters == count
    # The budget's work took minutes before it; 10 s is ten times the M4's time.
    # clock-bound: unbounded font work, which ran past the reader's 60 s step clock
    assert elapsed < pdf.STEP_SECONDS / 6


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
