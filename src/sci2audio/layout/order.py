"""Reading order on one page: bands top to bottom, columns left to right inside each band.

Items wider than `wide` of the text area (a title, a full-width figure or table rule) cut the
page into bands at their middle. A graphic around several items (a frame, a page background)
cuts at its top and bottom edges instead and is read before what it holds. Inside a band, a
gutter is a vertical strip of white that hardly any item crosses (a centred author line may),
with enough on both sides to be a column; the items that do cross it cut the band once more,
the same way. Each column is read from the top, row by row. The cut is not repeated inside a
column (no nested columns; Issue #32).

A display formula set across both columns of a page leaves no white wide enough to cut it,
so a gutter would run through it (#34). An equation number at the right edge of the text
whose row of pieces runs across a gutter, with no white as wide as a gutter between them,
gathers that row, and the lines set in mathematics or smaller chained to it within
`float_gap`; if they are wider than `wide`, they are one element (a formula) read across
the page.
"""

from __future__ import annotations

from dataclasses import dataclass

from sci2audio.core import Box, Drawing, Picture, TextLine
from sci2audio.layout.geometry import boxed, line_size, same_row, union
from sci2audio.layout.maths import math_letters, number_alone
from sci2audio.layout.settings import LayoutSettings

Cuts = list[tuple[float, float]]
Edges = list[tuple[float, "Element | None"]]  # where bands end, and what is read there
Sides = dict[int, tuple[float | None, float | None]]  # id(element): its column's gutters


@dataclass(frozen=True)
class Element:
    """Something to put in order: one text line, one figure (pictures and drawings), or one
    formula read across the page (its lines)."""

    box: Box
    line: TextLine | None = None
    graphics: tuple[Picture | Drawing, ...] = ()
    lines: tuple[TextLine, ...] = ()


def figures(graphics: list[Picture | Drawing], reach: float) -> list[Element]:
    """Pictures and drawings grouped into figures: those that touch or nearly touch."""
    placed = [g for g in graphics if g.box]
    parent = list(range(len(placed)))

    def root(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    by_left = sorted(range(len(placed)), key=lambda i: boxed(placed[i]).x0)
    for n, i in enumerate(by_left):
        a = boxed(placed[i])
        for j in by_left[n + 1 :]:
            b = boxed(placed[j])
            if b.x0 > a.x1 + reach:
                break
            if b.y0 <= a.y1 + reach and a.y0 <= b.y1 + reach:
                parent[root(i)] = root(j)
    groups: dict[int, list[Picture | Drawing]] = {}
    for i, graphic in enumerate(placed):
        groups.setdefault(root(i), []).append(graphic)
    return [
        Element(union([boxed(g) for g in group]), graphics=tuple(group))
        for group in groups.values()
    ]


@dataclass
class Reading:
    """A page read: its elements in order, its columns, and where each column ends.

    `sides` gives, for an element read inside a column, the gutter on its left and on its
    right (None at the text's edge); an element read across the page has no entry.
    """

    ordered: list[Element]
    columns: int
    sides: Sides


def reading_order(
    elements: list[Element], width: float, size: float, settings: LayoutSettings
) -> Reading:
    """The elements in reading order, and how many columns the page's running text has.

    A band counts for the columns if it holds a fair share of the page's text and a column
    of running text, so a table's cells don't. `width` is the width of the document's text
    area; `size` its body font size.
    """
    wide = [e for e in elements if e.box.x1 - e.box.x0 > settings.wide * width]
    taken = {id(e) for e in wide}
    reading = Reading([], 1, {})
    total = _text(elements)
    rest = [e for e in elements if id(e) not in taken]
    for band, after in _bands(rest, _edges(wide, elements, settings)):
        cuts = gutters(band, width, size, settings)
        band = across(band, cuts, width, size, settings)
        reading.ordered += _read_band(band, cuts, settings, reading.sides)
        if _text(band) >= settings.column_text * total and _filled(band, cuts, settings):
            reading.columns = max(reading.columns, len(cuts) + 1)
        if after:
            reading.ordered.append(after)
    return reading


def across(
    elements: list[Element], cuts: Cuts, width: float, size: float, settings: LayoutSettings
) -> list[Element]:
    """The band's elements with each display formula set across one of its gutters (`cuts`)
    as one element (#34)."""
    texts = [e for e in elements if e.line]
    if not texts or not cuts:
        return elements
    left, right = min(e.box.x0 for e in texts), max(e.box.x1 for e in texts)
    indent, gap = settings.formula_indent * size, settings.float_gap * size
    groups: list[list[Element]] = []
    for head in texts:
        if head.box.x1 < right - settings.number_reach * size or not number_alone(head.line):
            continue
        row = [
            e
            for e in texts
            if e is not head
            and same_row(e.box, head.box, settings.row_overlap)
            and e.box.x1 <= head.box.x0
        ]
        if (
            row
            and min(e.box.x0 for e in row) >= left + indent
            and _bridges(row, head, cuts, settings.gutter * size)
        ):
            groups.append([head, *row])
    if not groups:
        return elements
    found = _merged(groups, gap)
    taken = {id(e) for group in found for e in group}
    smaller = (1 - settings.size_change) * size
    for group in found:  # the rows above and below: limits of a sum, more of the formula
        while True:
            box = union([e.box for e in group])
            near = [
                e
                for e in texts
                if id(e) not in taken
                and e.box.x0 >= max(left + indent, box.x0 - gap)
                and e.box.x1 <= min(right - settings.fill_slack * size, box.x1)
                and e.box.y0 <= box.y1 + gap
                and e.box.y1 >= box.y0 - gap
                and (
                    line_size(e.line) < smaller
                    or math_letters([e.line], settings.math_fonts) >= settings.math_share
                )
            ]
            if not near:
                break
            group += near
            taken |= {id(e) for e in near}
    found = _merged(found, gap)  # the limits taken may bring two formulas together
    formulas = [
        g
        for g in found
        if max(e.box.x1 for e in g) - min(e.box.x0 for e in g) > settings.wide * width
    ]
    merged = {id(e) for g in formulas for e in g}
    return [e for e in elements if id(e) not in merged] + [
        Element(union([e.box for e in g]), lines=tuple(e.line for e in g if e.line))
        for g in formulas
    ]


def _bridges(row: list[Element], head: Element, cuts: Cuts, most: float) -> bool:
    """True if the row's pieces run across a gutter with no white wider than `most`, the
    last of them reaching on to the number at its end."""
    spans: list[list[float]] = []
    for e in sorted(row, key=lambda e: e.box.x0):
        if spans and e.box.x0 - spans[-1][1] <= most:
            spans[-1][1] = max(spans[-1][1], e.box.x1)
        else:
            spans.append([e.box.x0, e.box.x1])
    spans[-1][1] = head.box.x1
    return any(x0 < start and x1 > end for x0, x1 in spans for start, end in cuts)


def _merged(groups: list[list[Element]], gap: float) -> list[list[Element]]:
    """Groups whose boxes stand within `gap` of each other, one above the other, merged."""
    out: list[list[Element]] = []
    for group in sorted(groups, key=lambda g: min(e.box.y0 for e in g)):
        top = min(e.box.y0 for e in group)
        if out and top <= max(e.box.y1 for e in out[-1]) + gap:
            out[-1] += [e for e in group if all(e is not f for f in out[-1])]
        else:
            out.append(list(group))
    return out


def _text(elements: list[Element]) -> int:
    return sum(len(e.line.text) for e in elements if e.line)


def _filled(band: list[Element], cuts: Cuts, settings: LayoutSettings) -> bool:
    """True if a column holds running text: most of its letters in lines that fill it.

    The cells of a table leave white between them, so a page of tables is not read as
    columns; an algorithm or a formula beside running text still is.
    """
    lines = [e for e in band if e.line]
    for column in filter(None, _columns(lines, cuts)):
        span = max(e.box.x1 for e in column) - min(e.box.x0 for e in column)
        full = [e for e in column if e.box.x1 - e.box.x0 >= settings.full_line * span]
        if _text(full) >= settings.column_fill * _text(column):
            return True
    return False


def _edges(spanning: list[Element], elements: list[Element], settings: LayoutSettings) -> Edges:
    """Where the spanning elements cut: at their middle, or around what a frame holds."""
    edges: Edges = []
    for element in spanning:
        box = element.box
        if _holds(element, elements) >= settings.frame_items:
            edges += [(box.y0, element), (box.y1, None)]
        else:
            edges.append(((box.y0 + box.y1) / 2, element))
    return sorted(edges, key=lambda edge: edge[0])


def _holds(frame: Element, elements: list[Element]) -> int:
    """How many other elements lie inside the frame's box."""
    box = frame.box
    return sum(
        e is not frame
        and box.x0 <= e.box.x0
        and e.box.x1 <= box.x1
        and box.y0 <= e.box.y0
        and e.box.y1 <= box.y1
        for e in elements
    )


def _bands(elements: list[Element], edges: Edges) -> list[tuple[list[Element], Element | None]]:
    """The elements between one edge and the next, each band followed by its edge's element."""
    bands: list[list[Element]] = [[] for _ in range(len(edges) + 1)]
    for element in elements:
        middle = (element.box.y0 + element.box.y1) / 2
        bands[sum(y < middle for y, _ in edges)].append(element)
    return list(zip(bands, [after for _, after in edges] + [None], strict=True))


def gutters(elements: list[Element], width: float, size: float, settings: LayoutSettings) -> Cuts:
    """The white strips between columns in one band, left to right."""
    if not elements:
        return []
    left = min(e.box.x0 for e in elements)
    right = max(e.box.x1 for e in elements)
    crossings = int(settings.gutter_crossings * len(elements))
    found: Cuts = []
    opened = left  # where the last gutter ends
    after = left  # where it starts: what starts from here on is right of it

    def splits(start: float, end: float) -> bool:
        """True if the strip is wide enough, inside the band, and has a column on each side.
        A line may end inside a strip, as strips allow a few crossings."""
        if end - start < settings.gutter * size or not left < start < end < right:
            return False
        column = [e for e in elements if e.box.x0 >= after and e.box.x1 <= end]
        rest = [e for e in elements if e.box.x0 >= end]
        return _is_column(column, width, settings) and _is_column(rest, width, settings)

    for strip in _strips(elements, left, right, crossings):
        candidates = [strip] if splits(*strip) else _white(strip, elements)
        for start, end in candidates:
            if start >= opened and splits(start, end):
                found.append((start, end))
                opened, after = end, start
    return found


def _strips(elements: list[Element], left: float, right: float, crossings: int) -> Cuts:
    """Stretches between left and right that at most `crossings` elements cover."""
    events = sorted([(e.box.x0, 1) for e in elements] + [(e.box.x1, -1) for e in elements])
    strips: Cuts = []
    count, opened = 0, left
    for x, step in events:
        before = count
        count += step
        if before <= crossings < count and x > opened:  # a strip closes
            strips.append((opened, x))
        elif count <= crossings < before:  # a strip opens
            opened = x
    if count <= crossings and opened < right:
        strips.append((opened, right))
    return strips


def _white(strip: tuple[float, float], elements: list[Element]) -> Cuts:
    """The truly white parts of a strip, left to right: what no element covers except those
    that cross it from side to side. A short column (fewer lines than the crossings a strip
    allows) stands inside a strip; the gutter beside it is one of these parts."""
    start, end = strip
    covers = sorted(
        (max(e.box.x0, start), min(e.box.x1, end))
        for e in elements
        if e.box.x0 < end and e.box.x1 > start and not (e.box.x0 < start and e.box.x1 > end)
    )
    found: Cuts = []
    at = start
    for x0, x1 in [*covers, (end, end)]:
        if x0 > at:
            found.append((at, x0))
        at = max(at, x1)
    return found


def _is_column(side: list[Element], width: float, settings: LayoutSettings) -> bool:
    """Enough items, spread wide enough to be text and not a margin of numbers."""
    if len(side) < settings.column_items:
        return False
    broad = max(e.box.x1 for e in side) - min(e.box.x0 for e in side)
    return broad >= settings.column_width * width


def _read_band(
    elements: list[Element], cuts: Cuts, settings: LayoutSettings, sides: Sides
) -> list[Element]:
    """Columns left to right, cut again where an element crosses a gutter."""
    crossers = [e for e in elements if _spans(e, cuts)]
    taken = {id(e) for e in crossers}
    rest = [e for e in elements if id(e) not in taken]
    ordered: list[Element] = []
    edges: list[float | None] = [None, *(x for cut in cuts for x in cut), None]
    for band, after in _bands(rest, _edges(crossers, elements, settings)):
        for index, column in enumerate(_columns(band, cuts)):
            if cuts:
                sides.update((id(e), (edges[2 * index], edges[2 * index + 1])) for e in column)
            ordered += by_rows(column, settings.row_overlap)
        if after:
            ordered.append(after)
    return ordered


def by_rows(elements: list[Element], overlap: float) -> list[Element]:
    """Top to bottom; elements side by side on one row, left to right."""
    rows: list[list[Element]] = []
    for element in sorted(elements, key=lambda e: e.box.y0):
        if rows and same_row(rows[-1][-1].box, element.box, overlap):
            rows[-1].append(element)
        else:
            rows.append([element])
    return [e for row in rows for e in sorted(row, key=lambda e: e.box.x0)]


def _columns(elements: list[Element], cuts: Cuts) -> list[list[Element]]:
    """The elements that don't cross a gutter, by the column their middle stands in."""
    columns: list[list[Element]] = [[] for _ in range(len(cuts) + 1)]
    for element in elements:
        if not _spans(element, cuts):
            columns[_column(element, cuts)].append(element)
    return columns


def _spans(element: Element, cuts: Cuts) -> bool:
    """True if the element reaches across a gutter, not just into its edge."""
    return any(element.box.x0 < start and element.box.x1 > end for start, end in cuts)


def _column(element: Element, cuts: Cuts) -> int:
    """The column the element starts in. A gutter may begin inside the longest lines of the
    column to its left (it allows a few to cross), so their middle can lie past its start."""
    return sum(element.box.x0 >= start for start, _ in cuts)
