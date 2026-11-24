"""Read the outlines of a TrueType font program and draw them, bounded (#618, D-789).

A PDF whose fonts have no Unicode source holds only glyph numbers (#442); the letters can be
recognised from the glyphs' shapes (`extraction.letters`). This module reads what that
needs from the embedded program: units per em, advance widths, and each glyph's outline,
simple or composite. It reads nothing else (no hinting, no cmap: such a font has none).

The program comes from a user's file, so it is untrusted: every count and offset is checked
against the table it points into, and the limits below bound the work a glyph can cause. A
damaged program never raises: `read_font` gives None for a program it cannot read, and
`Font.outline` None for a glyph it cannot read. fontTools is not used here on purpose: it is
not a run-time dependency, and its lazy, permissive parsing is not bounded for hostile input.

`draw` puts an outline on a fixed grid over the em, the same for every glyph and font, so a
letter's drawing keeps where it stands (a comma low, an apostrophe high): the drawings of
the reference fonts (`scripts/letter_shapes.py`) are made by this same code.
"""

from __future__ import annotations

import itertools
import math
import struct
from dataclasses import dataclass

import numpy as np

# Limits against hostile programs (AC-442.11). The fonts sci2audio recognises are a few
# hundred KB; their largest glyph has under 20 contours and 300 points, and composites nest
# at most twice. A glyph past a limit is not drawn, so it is not recognised.
MAX_PROGRAM = 16 * 1024**2  # bytes of a program read at all
MAX_CONTOURS = 512  # contours of one simple glyph
MAX_POINTS = 8192  # points of one glyph, its components' added up
MAX_COMPONENTS = 64  # components of one composite glyph, those of its components added up
MAX_DEPTH = 4  # composites inside composites
_UNITS = (16, 16384)  # units per em the format allows

# The grid a glyph is drawn on, in em: 24 columns from -0.05 to 1.05 em across, 30 rows
# from 1.05 em above the baseline to 0.3 em below it, each cell sampled 4 x 4 times and
# given its covered share as 0 to 15. A cell is about a stroke wide: a comma, a crossbar or
# a dot over a letter fills cells of its own, while a twin font's other serifs fall in the
# same cells, and the drawings of 20 styles stay at 240 KB.
COLUMNS, ROWS = 24, 30
LEFT, RIGHT = -0.05, 1.05
TOP, BOTTOM = 1.05, -0.3
CELL_WIDTH = (RIGHT - LEFT) / COLUMNS
CELL_HEIGHT = (TOP - BOTTOM) / ROWS
_SAMPLES = 4  # per cell, each way
_CURVE_STEPS = 6  # lines a quadratic curve is drawn with

Point = tuple[float, float, bool]  # x, y in font units, on the curve
Outline = tuple[tuple[Point, ...], ...]  # contours

_ON_CURVE, _X_SHORT, _Y_SHORT, _REPEAT, _X_SAME, _Y_SAME = 0x01, 0x02, 0x04, 0x08, 0x10, 0x20
_WORDS, _XY_VALUES, _SCALE, _MORE = 0x0001, 0x0002, 0x0008, 0x0020
_XY_SCALE, _TWO_BY_TWO = 0x0040, 0x0080


class _Damaged(Exception):
    """A glyph or table the reader cannot read; never leaves this module."""


@dataclass(frozen=True)
class Font:
    """A TrueType program's outlines and advances, read on demand."""

    units: int  # units per em
    count: int  # glyphs, as far as both maxp and loca hold them
    metrics: int  # glyphs with an advance of their own (hhea's numberOfHMetrics)
    _program: bytes
    _glyf: tuple[int, int]  # start and end of the glyf table in the program
    _loca: tuple[int, ...]  # each glyph's start in glyf, and the end of the last
    _hmtx: tuple[int, int]

    def advance(self, glyph: int, *, shared: bool = False) -> int | None:
        """The glyph's advance width in font units, or None. A glyph past `metrics` has none
        of its own; the format gives it the last one, which `shared` asks for (a font
        cut short can hold a wrong one there)."""
        if not 0 <= glyph < self.count:
            return None
        if glyph >= self.metrics:
            if not shared or self.metrics == 0:
                return None
            glyph = self.metrics - 1
        start, end = self._hmtx
        at = start + 4 * glyph
        if at + 2 > end:
            return None
        return int.from_bytes(self._program[at : at + 2], "big")

    def outline(self, glyph: int) -> Outline | None:
        """The glyph's contours in font units, () for a glyph without ink, None for a glyph
        the font does not have or that cannot be read within the limits."""
        try:
            return self._outline(glyph, (), [0, 0])
        except (_Damaged, struct.error, IndexError, ValueError, OverflowError):
            return None

    def _outline(self, glyph: int, holders: tuple[int, ...], spent: list[int]) -> Outline:
        """`spent` counts the points and components drawn so far for the glyph asked for:
        composites of empty glyphs add no points, but each component is work."""
        if not 0 <= glyph < self.count or glyph in holders:
            raise _Damaged  # a glyph the font lacks, or a composite that holds itself
        start, end = self._loca[glyph], self._loca[glyph + 1]
        if start == end:
            return ()
        base = self._glyf[0]
        if not start < end <= self._glyf[1] - base:
            raise _Damaged
        data = memoryview(self._program)[base + start : base + end]
        contours = struct.unpack_from(">h", data)[0]
        if contours >= 0:
            outline = _simple(data, contours)
            spent[0] += sum(len(c) for c in outline)
            if spent[0] > MAX_POINTS:
                raise _Damaged
            return outline
        if len(holders) >= MAX_DEPTH:
            raise _Damaged
        return self._composite(data, (*holders, glyph), spent)

    def _composite(self, data: memoryview, holders: tuple[int, ...], spent: list[int]) -> Outline:
        outline: list[tuple[Point, ...]] = []
        at = 10
        while spent[1] < MAX_COMPONENTS:
            spent[1] += 1
            flags, child = struct.unpack_from(">HH", data, at)
            at += 4
            if flags & _WORDS:
                arg1, arg2 = struct.unpack_from(">hh" if flags & _XY_VALUES else ">HH", data, at)
                at += 4
            else:
                arg1, arg2 = struct.unpack_from(">bb" if flags & _XY_VALUES else ">BB", data, at)
                at += 2
            a, b, c, d = 1.0, 0.0, 0.0, 1.0
            if flags & _SCALE:
                a = d = _f2dot14(data, at)
                at += 2
            elif flags & _XY_SCALE:
                a, d = _f2dot14(data, at), _f2dot14(data, at + 2)
                at += 4
            elif flags & _TWO_BY_TWO:
                a, b, c, d = (_f2dot14(data, at + 2 * k) for k in range(4))
                at += 8
            part = self._outline(child, holders, spent)
            if flags & _XY_VALUES:
                dx, dy = float(arg1), float(arg2)
            else:  # matched points: the child's point arg2 lands on the parent's point arg1
                dx, dy = _matched(outline, part, arg1, arg2, (a, b, c, d))
            outline.extend(
                tuple((a * x + c * y + dx, b * x + d * y + dy, on) for x, y, on in contour)
                for contour in part
            )
            if not flags & _MORE:
                return tuple(outline)
        raise _Damaged  # more components than the limit


def _f2dot14(data: memoryview, at: int) -> float:
    return struct.unpack_from(">h", data, at)[0] / 16384


def _matched(
    parent: list[tuple[Point, ...]],
    child: Outline,
    parent_point: int,
    child_point: int,
    matrix: tuple[float, float, float, float],
) -> tuple[float, float]:
    """The offset that puts the child's point onto the parent's point (both counted over
    all contours, the parent's so far)."""
    ours = [p for contour in parent for p in contour]
    theirs = [p for contour in child for p in contour]
    if not (0 <= parent_point < len(ours) and 0 <= child_point < len(theirs)):
        raise _Damaged
    a, b, c, d = matrix
    x, y, _ = theirs[child_point]
    return ours[parent_point][0] - (a * x + c * y), ours[parent_point][1] - (b * x + d * y)


def _simple(data: memoryview, contours: int) -> Outline:
    if contours > MAX_CONTOURS:
        raise _Damaged
    if contours == 0:
        return ()
    ends = struct.unpack_from(f">{contours}H", data, 10)
    if any(later <= earlier for earlier, later in itertools.pairwise(ends)):
        raise _Damaged
    count = ends[-1] + 1
    if count > MAX_POINTS:
        raise _Damaged
    at = 10 + 2 * contours
    at += 2 + struct.unpack_from(">H", data, at)[0]  # past the hinting instructions
    flags: list[int] = []
    while len(flags) < count:
        flag = data[at]
        at += 1
        repeat = 1
        if flag & _REPEAT:
            repeat += data[at]
            at += 1
        flags.extend([flag] * repeat)
    del flags[count:]
    xs, at = _coordinates(data, at, flags, _X_SHORT, _X_SAME)
    ys, _ = _coordinates(data, at, flags, _Y_SHORT, _Y_SAME)
    found: list[tuple[Point, ...]] = []
    start = 0
    for end in ends:
        found.append(
            tuple((xs[k], ys[k], bool(flags[k] & _ON_CURVE)) for k in range(start, end + 1))
        )
        start = end + 1
    return tuple(found)


def _coordinates(
    data: memoryview, at: int, flags: list[int], short: int, same: int
) -> tuple[list[float], int]:
    values: list[float] = []
    value = 0
    for flag in flags:
        if flag & short:
            step = data[at]
            at += 1
            value += step if flag & same else -step
        elif not flag & same:
            value += struct.unpack_from(">h", data, at)[0]
            at += 2
        values.append(float(value))
    return values, at


def read_font(program: bytes) -> Font | None:
    """The font of a TrueType program, or None if it is not one this reader can read: too
    large, not TrueType outlines (CFF, a collection, Type 1), or a needed table missing,
    cut short or out of range."""
    if len(program) > MAX_PROGRAM or program[:4] not in (b"\x00\x01\x00\x00", b"true"):
        return None
    try:
        return _font(program)
    except (_Damaged, struct.error, IndexError, ValueError):
        return None


def _font(program: bytes) -> Font:
    tables = _tables(program)
    head, maxp, hhea = tables.get(b"head"), tables.get(b"maxp"), tables.get(b"hhea")
    loca, glyf = tables.get(b"loca"), tables.get(b"glyf")
    if not (head and maxp and loca and glyf):
        raise _Damaged
    if head[1] - head[0] < 54 or maxp[1] - maxp[0] < 6:
        raise _Damaged
    (units,) = struct.unpack_from(">H", program, head[0] + 18)
    (long_offsets,) = struct.unpack_from(">h", program, head[0] + 50)
    (count,) = struct.unpack_from(">H", program, maxp[0] + 4)
    if not _UNITS[0] <= units <= _UNITS[1] or long_offsets not in (0, 1):
        raise _Damaged
    size = 4 if long_offsets else 2
    count = min(count, (loca[1] - loca[0]) // size - 1)
    if count < 1:
        raise _Damaged
    raw = struct.unpack_from(f">{count + 1}{'I' if long_offsets else 'H'}", program, loca[0])
    offsets = raw if long_offsets else tuple(2 * o for o in raw)
    metrics = 0
    hmtx = tables.get(b"hmtx", (0, 0))
    if hhea and hhea[1] - hhea[0] >= 36 and hmtx[1] > hmtx[0]:
        (metrics,) = struct.unpack_from(">H", program, hhea[0] + 34)
        metrics = min(metrics, count)
    else:
        hmtx = (0, 0)
    return Font(units, count, metrics, program, glyf, offsets, hmtx)


def _tables(program: bytes) -> dict[bytes, tuple[int, int]]:
    """Each table's start and end, for the tables that lie wholly inside the program."""
    (count,) = struct.unpack_from(">H", program, 4)
    found: dict[bytes, tuple[int, int]] = {}
    for k in range(count):
        tag, _, offset, length = struct.unpack_from(">4sIII", program, 12 + 16 * k)
        if offset + length <= len(program):
            found.setdefault(tag, (offset, offset + length))
    return found


# ---- drawing --------------------------------------------------------------------------

_XS = LEFT + (np.arange(COLUMNS * _SAMPLES) + 0.5) * (CELL_WIDTH / _SAMPLES)
_YS = TOP - (np.arange(ROWS * _SAMPLES) + 0.5) * (CELL_HEIGHT / _SAMPLES)


def draw(outline: Outline, units: int) -> np.ndarray:
    """The outline on the em grid: `ROWS` x `COLUMNS` cells, row by row from the top, each
    0 (empty) to 15 (covered), filled by the non-zero winding rule as TrueType fills."""
    edges = _edges(outline, units)
    if not len(edges):
        return np.zeros(ROWS * COLUMNS, np.uint8)
    x0, y0, x1, y1 = edges.T
    ys = _YS[:, None]
    crossing = ((y0 <= ys) & (ys < y1)) | ((y1 <= ys) & (ys < y0))
    rows, which = np.nonzero(crossing)
    t = (_YS[rows] - y0[which]) / (y1[which] - y0[which])
    xs = x0[which] + t * (x1[which] - x0[which])
    # a crossing at xs turns the winding for every sample to its right
    first = np.floor((xs - LEFT) / (CELL_WIDTH / _SAMPLES) - 0.5).astype(np.int64) + 1
    first = np.clip(first, 0, COLUMNS * _SAMPLES)
    turn = np.where(y1[which] > y0[which], 1, -1)
    winding = np.zeros((ROWS * _SAMPLES, COLUMNS * _SAMPLES + 1), np.int32)
    np.add.at(winding, (rows, first), turn)
    inside = np.cumsum(winding[:, :-1], axis=1) != 0
    covered = inside.reshape(ROWS, _SAMPLES, COLUMNS, _SAMPLES).sum(axis=(1, 3))
    return ((covered * 15 + 8) // (_SAMPLES * _SAMPLES)).astype(np.uint8).reshape(-1)


def _edges(outline: Outline, units: int) -> np.ndarray:
    """The outline's contours as straight edges (x0, y0, x1, y1) in em, curves split into
    `_CURVE_STEPS` lines; flat edges are left out (they cross no row)."""
    edges: list[tuple[float, float, float, float]] = []
    scale = 1 / units
    for contour in outline:
        for start, control, end in _segments(contour):
            if control is None:
                edges.append((start[0], start[1], end[0], end[1]))
                continue
            last = start
            for step in range(1, _CURVE_STEPS + 1):
                t = step / _CURVE_STEPS
                u = 1 - t
                point = (
                    u * u * start[0] + 2 * u * t * control[0] + t * t * end[0],
                    u * u * start[1] + 2 * u * t * control[1] + t * t * end[1],
                )
                edges.append((last[0], last[1], point[0], point[1]))
                last = point
    found = np.array(edges, np.float64).reshape(-1, 4) * scale
    found = found[np.isfinite(found).all(axis=1)]
    return found[found[:, 1] != found[:, 3]]


_Pair = tuple[float, float]


def _segments(contour: tuple[Point, ...]) -> list[tuple[_Pair, _Pair | None, _Pair]]:
    """The contour as lines (no control point) and quadratic curves, closed; two off-curve
    points in a row have an on-curve point midway between them, as TrueType reads them."""
    if len(contour) < 2:
        return []
    count = len(contour)
    first = next((k for k, p in enumerate(contour) if p[2]), None)
    if first is None:  # all off the curve: start midway between the last and the first
        a, b = contour[-1], contour[0]
        start: _Pair = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        order = list(contour)
    else:
        start = (contour[first][0], contour[first][1])
        order = [contour[(first + k) % count] for k in range(1, count)]
    segments: list[tuple[_Pair, _Pair | None, _Pair]] = []
    current, control = start, None
    for x, y, on in order:
        if on:
            segments.append((current, control, (x, y)))
            current, control = (x, y), None
        elif control is None:
            control = (x, y)
        else:
            middle = ((control[0] + x) / 2, (control[1] + y) / 2)
            segments.append((current, control, middle))
            current, control = middle, (x, y)
    segments.append((current, control, start))
    return [s for s in segments if all(map(math.isfinite, (*s[0], *s[2])))]
