"""The bounded TrueType reader that letter recognition draws glyphs with (#618, AC-442.11).

A font program embedded in a PDF is untrusted input: every count and offset in it is
checked, and a damaged program gives no glyph rather than an error. The programs here are
written by the tests (`pdf_maker.font_program`), plus the Apache-2.0 subsets in
`tests/fixtures/fonts/`.
"""

from __future__ import annotations

import struct
from pathlib import Path

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st
from pdf_maker import composite_glyph, font_program, sfnt, simple_glyph, truetype_program

from sci2audio.extraction import glyphs
from sci2audio.extraction.glyphs import COLUMNS, ROWS, draw, read_font

FONTS = Path(__file__).resolve().parents[1] / "fixtures" / "fonts"
SQUARE = [(100, 0), (500, 0), (500, 400), (100, 400)]


def test_a_simple_glyph_is_read_with_its_points_and_advance() -> None:
    font = read_font(truetype_program(5))
    assert font is not None
    assert (font.units, font.count, font.metrics) == (1000, 5, 5)
    assert font.outline(1) == (((50.0, 0.0, True), (450.0, 0.0, True), (450.0, 600.0, True),
                                (50.0, 600.0, True)),)  # fmt: skip
    assert font.outline(0) == font.outline(3) == ()  # no ink: the .notdef and the space
    assert font.advance(1) == 500


def test_the_short_loca_format_is_read() -> None:
    program = font_program([b"", simple_glyph([SQUARE])], [0, 600], short_loca=True)
    font = read_font(program)
    assert font is not None
    assert font.outline(1) == (tuple((float(x), float(y), True) for x, y in SQUARE),)


def test_off_curve_points_are_kept() -> None:
    program = font_program([simple_glyph([[(0, 0), (200, 400, False), (400, 0)]])], [400])
    font = read_font(program)
    assert font is not None
    assert font.outline(0) == (((0.0, 0.0, True), (200.0, 400.0, False), (400.0, 0.0, True)),)


def test_a_composite_glyph_moves_and_scales_its_components() -> None:
    outlines = [
        simple_glyph([SQUARE]),
        composite_glyph([(0, 10, 20), (0, 0, 500, (0.5, 0.0, 0.0, 0.5))]),
    ]
    font = read_font(font_program(outlines, [600, 600]))
    assert font is not None
    moved, scaled = font.outline(1)
    assert moved == tuple((x + 10.0, y + 20.0, True) for x, y in SQUARE)
    assert scaled == tuple((x / 2, y / 2 + 500, True) for x, y in SQUARE)


def test_a_composite_that_holds_itself_gives_no_outline() -> None:
    outlines = [composite_glyph([(1, 0, 0)]), composite_glyph([(0, 0, 0)])]
    font = read_font(font_program(outlines, [500, 500]))
    assert font is not None
    assert font.outline(0) is None
    assert font.outline(1) is None


def test_composites_nested_past_the_limit_give_no_outline() -> None:
    depth = glyphs.MAX_DEPTH
    # glyph k holds glyph k - 1; glyph 0 is a square: glyph `depth` nests `depth` deep
    outlines = [simple_glyph([SQUARE])]
    outlines += [composite_glyph([(k, 0, 0)]) for k in range(depth + 1)]
    font = read_font(font_program(outlines, [500] * len(outlines)))
    assert font is not None
    assert font.outline(depth) == font.outline(0)
    assert font.outline(depth + 1) is None


def test_a_composite_of_too_many_components_gives_no_outline() -> None:
    many = glyphs.MAX_COMPONENTS + 1
    outlines = [simple_glyph([SQUARE]), composite_glyph([(0, k, 0) for k in range(many)])]
    font = read_font(font_program(outlines, [500, 500]))
    assert font is not None
    assert font.outline(1) is None


def test_a_glyph_of_too_many_contours_or_points_gives_no_outline() -> None:
    contours = [[(k, 0), (k + 1, 0), (k, 1)] for k in range(glyphs.MAX_CONTOURS + 1)]
    points = [[(k % 1000, k // 1000) for k in range(glyphs.MAX_POINTS + 1)]]
    outlines = [simple_glyph(contours), simple_glyph(points), simple_glyph([SQUARE])]
    font = read_font(font_program(outlines, [500] * 3))
    assert font is not None
    assert font.outline(0) is None
    assert font.outline(1) is None
    assert font.outline(2) is not None


def test_a_composite_whose_points_add_up_past_the_limit_gives_no_outline() -> None:
    half = [[(k % 1000, k // 1000) for k in range(glyphs.MAX_POINTS // 2 + 1)]]
    outlines = [simple_glyph(half), composite_glyph([(0, 0, 0), (0, 5, 0)])]
    font = read_font(font_program(outlines, [500, 500]))
    assert font is not None
    assert font.outline(0) is not None
    assert font.outline(1) is None


def test_a_glyph_whose_offsets_leave_the_glyf_table_gives_no_outline() -> None:
    program = font_program([simple_glyph([SQUARE])], [500])
    font = read_font(program)
    assert font is not None
    # loca says glyph 0 runs to byte 10,000 of glyf
    loca = struct.pack(">2I", 0, 10_000)
    broken = read_font(font_program([simple_glyph([SQUARE])], [500], tables={b"loca": loca}))
    assert broken is not None
    assert broken.outline(0) is None


def test_glyphs_past_the_loca_table_do_not_exist() -> None:
    loca = struct.pack(">2I", 0, 0)  # maxp says 3 glyphs, loca holds one
    font = read_font(font_program([b"", b"", b""], [500] * 3, tables={b"loca": loca}))
    assert font is not None
    assert font.count == 1
    assert font.outline(2) is None
    assert font.outline(-1) is None


def test_an_hmtx_table_cut_short_gives_no_advance_past_its_end() -> None:
    hmtx = struct.pack(">Hh", 300, 0)  # numberOfHMetrics says 3, the table holds one
    font = read_font(font_program([b""] * 3, [300, 400, 500], hmtx=hmtx))
    assert font is not None
    assert font.advance(0) == 300
    assert font.advance(1) is None
    assert font.advance(2) is None


def test_glyphs_past_the_metrics_have_no_advance_of_their_own() -> None:
    font = read_font(font_program([b""] * 4, [300, 400, 500, 600], metrics=2))
    assert font is not None
    assert (font.metrics, font.advance(1), font.advance(2)) == (2, 400, None)
    assert font.advance(2, shared=True) == 400  # as the format reads it: the last one


@pytest.mark.parametrize(
    "program",
    [
        b"",
        b"%!PS-AdobeFont-1.0: CMMI10",
        sfnt({b"CFF ": b"x"}, b"OTTO"),  # CFF outlines: out of scope (#618)
        b"ttcf" + bytes(100),  # a collection
        sfnt({b"glyf": b"", b"head": bytes(54)}),  # no loca, maxp
        font_program([b""], [500], units=1),  # units per em out of range
        font_program([b""], [500], tables={b"head": bytes(10)}),  # head cut short
    ],
    ids=["empty", "type1", "cff", "collection", "missing-tables", "units", "short-head"],
)
def test_a_program_that_is_not_a_readable_truetype_font_is_none(program: bytes) -> None:
    assert read_font(program) is None


def test_a_program_past_the_size_limit_is_not_read(monkeypatch: pytest.MonkeyPatch) -> None:
    program = truetype_program(5)
    monkeypatch.setattr(glyphs, "MAX_PROGRAM", len(program) - 1)
    assert read_font(program) is None


def test_a_table_running_past_the_program_is_missing() -> None:
    program = bytearray(truetype_program(5))
    for k in range(struct.unpack(">H", program[4:6])[0]):
        entry = 12 + 16 * k
        if program[entry : entry + 4] == b"glyf":
            program[entry + 12 : entry + 16] = struct.pack(">I", 1 << 30)
    assert read_font(bytes(program)) is None


# ---- drawing ---------------------------------------------------------------------------


def test_a_drawing_covers_the_glyph_where_it_stands_on_the_em() -> None:
    font = read_font(truetype_program(5))
    assert font is not None
    picture = draw(font.outline(1), font.units).reshape(ROWS, COLUMNS)
    assert picture.dtype == np.uint8
    assert picture.max() == 15
    rows, columns = np.nonzero(picture == 15)
    # the rectangle x 0.05..0.45 em, y 0..0.6 em: inside it fully covered, outside empty
    xs = glyphs.LEFT + (columns + 0.5) * glyphs.CELL_WIDTH
    ys = glyphs.TOP - (rows + 0.5) * glyphs.CELL_HEIGHT
    assert xs.min() > 0.05
    assert xs.max() < 0.45
    assert ys.min() > 0.0
    assert ys.max() < 0.6
    assert picture.sum() == pytest.approx(
        15 * 0.4 * 0.6 / (glyphs.CELL_WIDTH * glyphs.CELL_HEIGHT), rel=0.05
    )


def test_an_empty_outline_draws_nothing() -> None:
    assert not draw((), 1000).any()


def test_a_curve_is_drawn_inside_its_control_points() -> None:
    """A quadratic arc bulges towards its off-curve point but stays short of it."""
    arc = (((0.0, 0.0, True), (500.0, 1000.0, False), (1000.0, 0.0, True)),)
    picture = draw(arc, 1000).reshape(ROWS, COLUMNS)
    rows = np.nonzero(picture.any(axis=1))[0]
    top = glyphs.TOP - rows.min() * glyphs.CELL_HEIGHT
    assert 0.45 <= top <= 0.6  # the arc's top is at half the control point's height


def test_a_hole_is_left_empty_by_the_winding_rule() -> None:
    outer = [(0, 0), (800, 0), (800, 800), (0, 800)]
    inner = [(200, 200), (200, 600), (600, 600), (600, 200)]  # the other way round
    font = read_font(font_program([simple_glyph([outer, inner])], [800]))
    assert font is not None
    picture = draw(font.outline(0), font.units).reshape(ROWS, COLUMNS)
    middle_row = round((glyphs.TOP - 0.4) / glyphs.CELL_HEIGHT)
    middle_column = round((0.4 - glyphs.LEFT) / glyphs.CELL_WIDTH)
    assert picture[middle_row, middle_column] == 0
    assert picture[middle_row, round((0.1 - glyphs.LEFT) / glyphs.CELL_WIDTH)] == 15


def test_a_far_away_point_is_drawn_without_trouble() -> None:
    far = (((-30000.0, -30000.0, True), (30000.0, -30000.0, True), (0.0, 30000.0, True)),)
    picture = draw(far, 16)
    assert picture.shape == (ROWS * COLUMNS,)


# ---- damaged programs never fail (AC-442.11) -------------------------------------------


def every_glyph(program: bytes) -> None:
    """Read the program and draw every glyph it has, as recognition would."""
    font = read_font(program)
    if font is None:
        return
    for glyph in range(min(font.count, 64)):
        font.advance(glyph)
        font.advance(glyph, shared=True)
        outline = font.outline(glyph)
        if outline is not None:
            draw(outline, font.units)


def seed_programs() -> list[bytes]:
    outlines = [
        b"",
        simple_glyph([SQUARE, [(0, 0), (50, 80, False), (100, 0)]]),
        composite_glyph([(1, 10, 20), (1, 0, 300, (0.5, 0.2, -0.2, 0.5))]),
    ]
    found = [truetype_program(6), font_program(outlines, [500, 600, 700], short_loca=True)]
    found += [path.read_bytes() for path in sorted(FONTS.glob("*.ttf"))]
    return found


SEEDS = seed_programs()


@given(st.binary(max_size=2048))
def test_random_bytes_never_fail_the_reader(data: bytes) -> None:
    every_glyph(data)
    every_glyph(b"\x00\x01\x00\x00" + data)


@given(
    st.sampled_from(range(len(SEEDS))),
    st.lists(st.tuples(st.integers(0, 1 << 20), st.integers(0, 255)), min_size=1, max_size=24),
)
def test_a_damaged_program_never_fails_the_reader(
    seed: int, changes: list[tuple[int, int]]
) -> None:
    program = bytearray(SEEDS[seed])
    for at, value in changes:
        program[at % len(program)] = value
    every_glyph(bytes(program))


@given(st.sampled_from(range(len(SEEDS))), st.integers(0, 1 << 20))
def test_a_program_cut_short_never_fails_the_reader(seed: int, cut: int) -> None:
    program = SEEDS[seed]
    every_glyph(program[: cut % len(program)])
