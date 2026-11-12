"""Reading order on one page: bands top to bottom, columns left to right inside each band.

Items wider than `wide` of the text area (a title, a full-width figure or table rule) cut the
page into bands. Inside a band, a gutter is a vertical strip of white that hardly any item
crosses (a centred author line may), with enough on both sides to be a column; the items that
do cross it cut the band once more. Each column is read from the top, row by row.
"""

from __future__ import annotations

from dataclasses import dataclass

from sci2audio.core import Box, Drawing, Picture, TextLine
from sci2audio.layout.furniture import boxed
from sci2audio.layout.settings import LayoutSettings

Cuts = list[tuple[float, float]]
COLUMN_TEXT = 0.2  # a band sets the page's columns if it holds this share of the page's text
COLUMN_FILL = 0.5  # and if a column has this share of its letters in full lines (not a table)
FULL_LINE = 0.8  # a line this wide of its column fills it


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
        Element(_union([boxed(g) for g in group]), graphics=tuple(group))
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
    wide = sorted(
        (e for e in elements if e.box.x1 - e.box.x0 > settings.wide * width),
        key=lambda e: e.box.y0,
    )
    ordered: list[Element] = []
    columns, total = 1, _text(elements)
    for band, spanner in _bands([e for e in elements if e not in wide], wide):
        cuts = gutters(band, width, size, settings)
        ordered += _read_band(band, cuts)
        if _text(band) >= COLUMN_TEXT * total and _filled(band, cuts):
            columns = max(columns, len(cuts) + 1)
        if spanner:
            ordered.append(spanner)
    return ordered, columns


def _text(elements: list[Element]) -> int:
    return sum(len(e.line.text) for e in elements if e.line)


def _filled(band: list[Element], cuts: Cuts) -> bool:
    """True if a column holds running text: most of its letters in lines that fill it.

    The cells of a table leave white between them, so a page of tables is not read as
    columns; an algorithm or a formula beside running text still is.
    """
    lines = [e for e in band if e.line]
    for column in filter(None, _columns(lines, cuts)):
        span = max(e.box.x1 for e in column) - min(e.box.x0 for e in column)
        full = [e for e in column if e.box.x1 - e.box.x0 >= FULL_LINE * span]
        if _text(full) >= COLUMN_FILL * _text(column):
            return True
    return False


def _bands(
    elements: list[Element], spanners: list[Element]
) -> list[tuple[list[Element], Element | None]]:
    """The elements between one spanner and the next, each band followed by its spanner."""
    bands: list[list[Element]] = [[] for _ in range(len(spanners) + 1)]
    for element in elements:
        middle = (element.box.y0 + element.box.y1) / 2
        bands[sum((s.box.y0 + s.box.y1) / 2 < middle for s in spanners)].append(element)
    return list(zip(bands, [*spanners, None], strict=True))


def gutters(elements: list[Element], width: float, size: float, settings: LayoutSettings) -> Cuts:
    """The white strips between columns in one band, left to right."""
    if not elements:
        return []
    left = min(e.box.x0 for e in elements)
    right = max(e.box.x1 for e in elements)
    crossings = int(settings.gutter_crossings * len(elements))
    found: Cuts = []
    opened = left  # where the column left of the next gutter starts
    for start, end in _strips(elements, left, right, crossings):
        if end - start < settings.gutter * size:
            continue
        # a line may end in the strip, as strips allow a few crossings
        column = [e for e in elements if e.box.x0 >= opened and e.box.x1 <= end]
        rest = [e for e in elements if e.box.x0 >= end]
        if _is_column(column, width, settings) and _is_column(rest, width, settings):
            found.append((start, end))
            opened = end
    return found


def _strips(elements: list[Element], left: float, right: float, crossings: int) -> Cuts:
    """Stretches between left and right that at most `crossings` elements cover.

    A strip at the edge of the band may hold a short column of its own (fewer lines than
    `crossings`): it ends where that column starts, or starts where it ends.
    """
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
    found = []
    for start, end in strips:
        inside = [e.box for e in elements if start <= e.box.x0 and e.box.x1 <= end]
        if start == left and inside:
            start = max(box.x1 for box in inside)
        if end == right and inside:
            end = min(box.x0 for box in inside)
        if left < start < end < right:
            found.append((start, end))
    return found


def _is_column(side: list[Element], width: float, settings: LayoutSettings) -> bool:
    """Enough items, spread wide enough to be text and not a margin of numbers."""
    if len(side) < settings.column_items:
        return False
    broad = max(e.box.x1 for e in side) - min(e.box.x0 for e in side)
    return broad >= settings.column_width * width


def _read_band(elements: list[Element], cuts: Cuts) -> list[Element]:
    """Columns left to right, cut again where an element crosses a gutter."""
    crossers = sorted((e for e in elements if _spans(e, cuts)), key=lambda e: e.box.y0)
    ordered: list[Element] = []
    for band, crosser in _bands([e for e in elements if e not in crossers], crossers):
        for column in _columns(band, cuts):
            ordered += by_rows(column)
        if crosser:
            ordered.append(crosser)
    return ordered


def by_rows(elements: list[Element]) -> list[Element]:
    """Top to bottom; elements side by side on one row, left to right."""
    rows: list[list[Element]] = []
    for element in sorted(elements, key=lambda e: e.box.y0):
        if rows and _overlap(rows[-1][-1].box, element.box):
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


def _overlap(a: Box, b: Box) -> bool:
    overlap = min(a.y1, b.y1) - max(a.y0, b.y0)
    return overlap > 0.5 * min(a.y1 - a.y0, b.y1 - b.y0)


def _union(boxes: list[Box]) -> Box:
    return Box(
        min(b.x0 for b in boxes),
        min(b.y0 for b in boxes),
        max(b.x1 for b in boxes),
        max(b.y1 for b in boxes),
    )
