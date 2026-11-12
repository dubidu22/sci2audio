"""Reading order on one page: bands top to bottom, columns left to right inside each band.

Items wider than `wide` of the text area (a title, a full-width figure or table rule) cut the
page into bands at their middle. A graphic around several items (a frame, a page background)
cuts at its top and bottom edges instead and is read before what it holds. Inside a band, a
gutter is a vertical strip of white that hardly any item crosses (a centred author line may),
with enough on both sides to be a column; the items that do cross it cut the band once more,
the same way. Each column is read from the top, row by row. The cut is not repeated inside a
column (no nested columns; Issue #32).
"""

from __future__ import annotations

from dataclasses import dataclass

from sci2audio.core import Box, Drawing, Picture, TextLine
from sci2audio.layout.geometry import boxed, same_row, union
from sci2audio.layout.settings import LayoutSettings

Cuts = list[tuple[float, float]]
Edges = list[tuple[float, "Element | None"]]  # where bands end, and what is read there


@dataclass(frozen=True)
class Element:
    """Something to put in order: one text line, or one figure (pictures and drawings)."""

    box: Box
    line: TextLine | None = None
    graphics: tuple[Picture | Drawing, ...] = ()


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


def reading_order(
    elements: list[Element], width: float, size: float, settings: LayoutSettings
) -> tuple[list[Element], int]:
    """The elements in reading order, and how many columns the page's running text has.

    A band counts for the columns if it holds a fair share of the page's text and a column
    of running text, so a table's cells don't. `width` is the width of the document's text
    area; `size` its body font size.
    """
    wide = [e for e in elements if e.box.x1 - e.box.x0 > settings.wide * width]
    taken = {id(e) for e in wide}
    ordered: list[Element] = []
    columns, total = 1, _text(elements)
    rest = [e for e in elements if id(e) not in taken]
    for band, after in _bands(rest, _edges(wide, elements, settings)):
        cuts = gutters(band, width, size, settings)
        ordered += _read_band(band, cuts, settings)
        if _text(band) >= settings.column_text * total and _filled(band, cuts, settings):
            columns = max(columns, len(cuts) + 1)
        if after:
            ordered.append(after)
    return ordered, columns


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
    opened = left  # where the column left of the next gutter starts

    def splits(start: float, end: float) -> bool:
        """True if the strip is wide enough, inside the band, and has a column on each side."""
        if end - start < settings.gutter * size or not left < start < end < right:
            return False
        # a line may end in the strip, as strips allow a few crossings
        column = [e for e in elements if e.box.x0 >= opened and e.box.x1 <= end]
        rest = [e for e in elements if e.box.x0 >= end]
        return _is_column(column, width, settings) and _is_column(rest, width, settings)

    for strip in _strips(elements, left, right, crossings):
        candidates = [strip] if splits(*strip) else _white(strip, elements)
        for start, end in candidates:
            if start >= opened and splits(start, end):
                found.append((start, end))
                opened = end
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


def _read_band(elements: list[Element], cuts: Cuts, settings: LayoutSettings) -> list[Element]:
    """Columns left to right, cut again where an element crosses a gutter."""
    crossers = [e for e in elements if _spans(e, cuts)]
    taken = {id(e) for e in crossers}
    rest = [e for e in elements if id(e) not in taken]
    ordered: list[Element] = []
    for band, after in _bands(rest, _edges(crossers, elements, settings)):
        for column in _columns(band, cuts):
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
    middle = (element.box.x0 + element.box.x1) / 2
    return sum(middle > start for start, _ in cuts)
