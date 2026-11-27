"""Reading order on one page: bands top to bottom, columns left to right inside each band.

Items wider than `wide` of the text area (a title, a full-width figure or table rule) cut the
page into bands at their middle. A graphic around several items (a frame, a page background)
cuts at its top and bottom edges instead and is read before what it holds. Inside a band, a
gutter is a vertical strip of white that hardly any item crosses (a centred author line may),
with enough on both sides to be a column; the items that do cross it cut the band once more,
the same way. Inside each column found, the same cut into bands and columns is tried again,
with "wide" now measured against that column, down to `column_depth` levels (#32, D-67): a
block of two short columns of running text inside one column of the page is read one column
after the other. A table's cells or a plot's labels inside a column leave a ragged edge and
are not cut there. A column with no columns inside it is read from the top, row by row.

A display formula set across both columns of a page leaves no white wide enough to cut it,
so a gutter would run through it (#34). An equation number at the right edge of the text
whose row of pieces runs across a gutter, with no white as wide as a gutter between them,
gathers that row, and the lines set in mathematics or smaller chained to it within
`float_gap`; if they are wider than `wide`, they are one element (a formula) read across
the page.
"""

from __future__ import annotations

import bisect
import math
from dataclasses import dataclass

from sci2audio.core import Box, Drawing, Picture, TextLine
from sci2audio.layout.geometry import boxed, line_size, minor, same_row, union
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
    """Pictures and drawings grouped into figures: those that touch or nearly touch (within
    `reach` across and down), each figure in the order of its first graphic, its graphics in
    their order."""
    placed = [g for g in graphics if g.box]
    found = touching([boxed(g) for g in placed], reach)
    groups: dict[int, list[Picture | Drawing]] = {}
    for graphic, group in zip(placed, found, strict=True):
        groups.setdefault(group, []).append(graphic)
    return [
        Element(union([boxed(g) for g in group]), graphics=tuple(group))
        for group in groups.values()
    ]


def touching(boxes: list[Box], reach: float) -> list[int]:
    """For each box, a number its group shares: boxes that touch or nearly touch, `reach`
    or less apart across and down, are in one group, and so are boxes touching one of those.

    A sweep from left to right, in time about n log n however the boxes lie and whatever
    their size in points (#354, #645). The boxes the sweep has passed whose right
    edge plus `reach` it has not yet passed are "open": they are near the new box across.
    Down the page each box stands for its span, from its top to its bottom plus `reach`,
    and two boxes are near each other down the page exactly when their spans meet (the
    same sums as comparing every pair, so the same answer to the last bit). Spans that meet
    hold the lower of their two tops, so the new box joins the open groups whose top lies
    in its span, and those whose span holds its top. A tree over the page's tops, in order,
    finds both in a few steps: each node keeps the groups whose span covers it and those
    with a top under it, with how far right their boxes there reach.
    """
    parent = list(range(len(boxes)))

    def root(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    tops = sorted({box.y0 for box in boxes})
    size = 1 << max(0, len(tops) - 1).bit_length()  # leaves: the tops, then empty ones
    leaf = {y: k + size for k, y in enumerate(tops)}
    # node -> {group: how far right its boxes filed there reach}, for the boxes whose span
    # covers the node, and for those whose top lies under it
    spans: list[dict[int, float] | None] = [None] * (2 * size)
    starts: list[dict[int, float] | None] = [None] * (2 * size)

    def look(table: list[dict[int, float] | None], node: int, x: float, found: list[int]) -> None:
        """Add the groups filed at the node that reach `x` (one key per group), and forget
        the others."""
        entries = table[node] or {}
        kept: dict[int, float] = {}
        for key, until in entries.items():
            if until >= x:
                group = root(key)
                kept[group] = max(until, kept.get(group, -math.inf))
        table[node] = kept or None
        found.extend(kept)

    def file(table: list[dict[int, float] | None], node: int, i: int, until: float) -> None:
        entries = table[node]
        if entries is None:
            table[node] = {i: until}
        else:
            entries[i] = until

    for i in sorted(range(len(boxes)), key=lambda k: boxes[k].x0):
        box = boxes[i]
        top = leaf[box.y0]
        end = bisect.bisect_right(tops, box.y1 + reach) + size
        cover = []  # the nodes that together hold leaves top up to (not including) end
        low, high = top, end
        while low < high:
            if low & 1:
                cover.append(low)
                low += 1
            if high & 1:
                high -= 1
                cover.append(high)
            low, high = low >> 1, high >> 1
        path = []  # the nodes above the box's top, from its leaf up
        node = top
        while node:
            path.append(node)
            node >>= 1
        found: list[int] = []
        for node in path:  # spans holding this box's top
            if spans[node] is not None:
                look(spans, node, box.x0, found)
        for node in cover:  # tops inside this box's span
            if starts[node] is not None:
                look(starts, node, box.x0, found)
        for group in found:  # roots, all joined to the box, a group of its own until now
            parent[group] = i
        until = box.x1 + reach
        for node in cover:
            file(spans, node, i, until)
        for node in path:
            file(starts, node, i, until)
    return [root(i) for i in range(len(boxes))]


@dataclass
class Reading:
    """A page read: its elements in order, its columns, and where each column ends.

    `sides` gives, for an element read inside a column, the gutter on its left and on its
    right (None at the text's edge); an element read across the page has no entry.

    `columns` counts the page's own columns, as the corpus truth gives them; `nested`
    counts the columns read side by side at the page's widest, a column cut again inside
    (#32) counting as the columns found in it (#866). Both judge the same bands.
    """

    ordered: list[Element]
    columns: int
    sides: Sides
    nested: int = 1


def reading_order(
    elements: list[Element],
    width: float,
    size: float,
    settings: LayoutSettings,
    uncounted: frozenset[str] = frozenset(),
) -> Reading:
    """The elements in reading order, and how many columns the page's running text has.

    A band counts for the columns if it holds a fair share of the page's text and a column
    of running text, so a table's cells don't. `width` is the width of the document's text
    area; `size` its body font size. Lines whose ids are `uncounted` (inside a captioned
    figure, #238) are read and find gutters like any other, but neither their text nor
    their fill counts for the columns.
    """
    wide = [e for e in elements if e.box.x1 - e.box.x0 > settings.wide * width]
    taken = {id(e) for e in wide}
    reading = Reading([], 1, {})

    def counted(group: list[Element]) -> list[Element]:
        return [e for e in group if e.line is None or e.line.id not in uncounted]

    total = _text(counted(elements))
    rest = [e for e in elements if id(e) not in taken]
    for band, after in _bands(rest, _edges(wide, elements, settings)):
        cuts = gutters(band, width, size, settings)
        band = across(band, cuts, width, size, settings)
        depth = settings.column_depth - 1
        ordered, breadth = _read_band(band, cuts, size, settings, reading.sides, depth)
        reading.ordered += ordered
        mine = counted(band)
        if _text(mine) >= settings.column_text * total and _filled(mine, cuts, settings):
            count = _text_columns(mine, cuts, width, size, settings)
            reading.columns = max(reading.columns, count)
            # what the cuts inside the page's columns add to their count
            reading.nested = max(reading.nested, count + breadth - (len(cuts) + 1))
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
        # a head always has a line (texts holds no other): the test only tells pyright so
        if (
            head.line is None
            or head.box.x1 < right - settings.number_reach * size
            or not number_alone(head.line)
        ):
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
                and e.line is not None  # always so in texts: the test only tells pyright
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


def _text_columns(
    band: list[Element], cuts: Cuts, width: float, size: float, settings: LayoutSettings
) -> int:
    """How many columns of text the band's gutters make.

    A figure in a wide gutter leaves white on each side of it, so it is read as a column of
    its own between its neighbours (#873), but it is no column of text (#895). A column
    between two others that holds a figure counts only if its lines, without its labels,
    are a column; a caption alone is not. A label is a line on the figure or within
    `float_gap` of it (a plot's ticks print just outside its frame) that does not fill the
    column (`full_line` of what it holds): running text set on a shaded box fills it
    (#916). Rules and marks
    (`geometry.minor`, an underline) are no figure. The first and last columns always
    count: a figure filling one of them still stands in a column of the page."""
    columns = _columns(band, cuts)
    reach = settings.float_gap * size
    mark, thin = settings.mark_height * size, settings.line_width * size
    count = 0
    for k, column in enumerate(columns):
        inner = 0 < k < len(columns) - 1
        shown = [
            _grown(e.box, reach)
            for e in column
            if inner and e.graphics and not minor([boxed(g) for g in e.graphics], mark, thin)
        ]
        if not shown:
            count += 1
            continue
        # what the column holds spans it: its gutters may start inside its lines (#873)
        span = max(e.box.x1 for e in column) - min(e.box.x0 for e in column)
        full = settings.full_line * span
        lines = [
            e
            for e in column
            if e.line and (e.box.x1 - e.box.x0 >= full or not any(_on(e.box, box) for box in shown))
        ]
        count += _is_column(lines, width, settings)
    return count


def _on(box: Box, figure: Box) -> bool:
    """True if the box overlaps the figure's box."""
    return box.x0 < figure.x1 and figure.x0 < box.x1 and box.y0 < figure.y1 and figure.y0 < box.y1


def _grown(box: Box, by: float) -> Box:
    return Box(box.x0 - by, box.y0 - by, box.x1 + by, box.y1 + by)


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
    """The white strips between columns in one band, left to right.

    A strip may be crossed by a tenth of the band's items (`gutter_crossings`), so a short
    column, one with no more lines than that, can stand wholly inside the strip between its
    neighbours. That strip still splits the band in two, which would read the short column
    row by row with the one on its left; so where a column stands inside a strip, the
    white on each side of it is looked at first and the whole strip only if neither splits
    (#873). A figure with a few lines under it, too few to be a column, stands in a strip
    the same way: if the white on each side of it splits the band, it is read as a column of
    its own between its neighbours (#938)."""
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

    def framed(strip: tuple[float, float], inside: list[Element]) -> Cuts:
        """The white on each side of a figure standing in the strip with a few lines under
        it, if each of the two splits the band: the figure's column is read between its
        neighbours, as a short column is (#938). Else nothing."""
        if not _figure_column(inside, width, size, settings):
            return []
        whites = _white(strip, elements)
        if len(whites) < 2 or whites[0][0] < opened:
            return []
        first, last = whites[0], whites[-1]
        if first[1] > min(e.box.x0 for e in inside) or last[0] < max(e.box.x1 for e in inside):
            return []
        rest = [e for e in elements if e.box.x0 >= last[1]]
        wide = last[1] - last[0] >= settings.gutter * size and last[1] < right
        return (
            [first, last] if splits(*first) and wide and _is_column(rest, width, settings) else []
        )

    for strip in _strips(elements, left, right, crossings):
        start, end = strip
        inside = [e for e in elements if e.box.x0 >= start and e.box.x1 <= end]
        if _is_column(inside, width, settings):  # a short column in the strip (#873)
            candidates = [*_white(strip, elements), strip]
        elif beside := framed(strip, inside):
            found += beside
            opened, after = beside[1][1], beside[1][0]
            continue
        else:
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


def _figure_column(
    side: list[Element], width: float, size: float, settings: LayoutSettings
) -> bool:
    """True if the elements are a figure (more than a rule or a mark) and the lines with it,
    spread as wide as a column."""
    mark, thin = settings.mark_height * size, settings.line_width * size
    shown = [
        e for e in side if e.graphics and not minor([boxed(g) for g in e.graphics], mark, thin)
    ]
    if not shown or len(shown) + sum(e.line is not None for e in side) < len(side):
        return False
    broad = max(e.box.x1 for e in side) - min(e.box.x0 for e in side)
    return broad >= settings.column_width * width


def _is_column(side: list[Element], width: float, settings: LayoutSettings) -> bool:
    """Enough items, spread wide enough to be text and not a margin of numbers."""
    if len(side) < settings.column_items:
        return False
    broad = max(e.box.x1 for e in side) - min(e.box.x0 for e in side)
    return broad >= settings.column_width * width


def _read_band(
    elements: list[Element],
    cuts: Cuts,
    size: float,
    settings: LayoutSettings,
    sides: Sides,
    depth: int,
) -> tuple[list[Element], int]:
    """Columns left to right, cut again where an element crosses a gutter; inside each
    column, columns of its own are looked for `depth` more levels down. Also how many
    columns are read side by side at the band's widest, counting those found inside."""
    crossers = [e for e in elements if _spans(e, cuts)]
    taken = {id(e) for e in crossers}
    rest = [e for e in elements if id(e) not in taken]
    ordered: list[Element] = []
    breadth = 1
    edges: list[float | None] = [None, *(x for cut in cuts for x in cut), None]
    for band, after in _bands(rest, _edges(crossers, elements, settings)):
        side_by_side = 0
        for index, column in enumerate(_columns(band, cuts)):
            if not cuts:
                ordered += by_rows(column, settings.row_overlap)
                side_by_side += 1
                continue
            outer = (edges[2 * index], edges[2 * index + 1])
            sides.update((id(e), outer) for e in column)
            found, inside = _read_column(column, outer, size, settings, sides, depth)
            ordered += found
            side_by_side += inside
        breadth = max(breadth, side_by_side)
        if after:
            ordered.append(after)
    return ordered, breadth


def _read_column(
    elements: list[Element],
    outer: tuple[float | None, float | None],
    size: float,
    settings: LayoutSettings,
    sides: Sides,
    depth: int,
) -> tuple[list[Element], int]:
    """One column found on the page, in reading order (#32, D-67), and how many columns
    it is read in side by side at its widest (1 if it is read row by row).

    The column is cut as a page is: what is wider than `wide` of the column cuts it into
    bands, and gutters cut each band into columns of running text. If no band has such a
    gutter, or `depth` is used up, the column is read row by row as it is. An element read in
    a column inside it takes that column's gutters as its sides, and the outer column's
    (`outer`) at its edges.
    """
    if depth <= 0 or len(elements) < 2 * settings.column_items:
        return by_rows(elements, settings.row_overlap), 1
    width = max(e.box.x1 for e in elements) - min(e.box.x0 for e in elements)
    wide = [e for e in elements if e.box.x1 - e.box.x0 > settings.wide * width]
    taken = {id(e) for e in wide}
    rest = [e for e in elements if id(e) not in taken]
    bands = []
    for band, after in _bands(rest, _edges(wide, elements, settings)):
        cuts = gutters(band, width, size, settings)
        bands.append((band, after, cuts if _running(band, cuts, size, settings) else []))
    if not any(cuts for _, _, cuts in bands):
        return by_rows(elements, settings.row_overlap), 1
    ordered: list[Element] = []
    breadth = 1
    inner: Sides = {}
    for band, after, cuts in bands:
        band = across(band, cuts, width, size, settings)
        found, wide_as = _read_band(band, cuts, size, settings, inner, depth - 1)
        ordered += found
        breadth = max(breadth, wide_as)
        if after:
            ordered.append(after)
    for key, (left, right) in inner.items():
        sides[key] = (outer[0] if left is None else left, outer[1] if right is None else right)
    return ordered, breadth


def _running(band: list[Element], cuts: Cuts, size: float, settings: LayoutSettings) -> bool:
    """True if each column the gutters (`cuts`) make in a band inside a column is running
    text: `column_fill` of its letters in lines that start and end within `fill_slack` of
    its edges (#32). The cells of a table, the labels of a plot and the words of one line
    set apart leave a ragged edge, so they are still read row by row."""
    slack = settings.fill_slack * size
    for column in _columns([e for e in band if e.line], cuts):
        left = min((e.box.x0 for e in column), default=0.0)
        right = max((e.box.x1 for e in column), default=0.0)
        full = [e for e in column if e.box.x0 <= left + slack and e.box.x1 >= right - slack]
        if not column or _text(full) < settings.column_fill * _text(column):
            return False
    return True


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
    """The column of an element that crosses no gutter: right of each gutter it reaches past.
    That is the split `gutters` found the gutter with (what ends inside it is left of it).
    A gutter may begin inside the longest lines of the column to its left (it allows a few to
    cross), so their middle can lie past its start; beside a short column it may even begin
    where its short lines end, left of where a centred or indented line of it starts (#679)."""
    return sum(element.box.x1 > end for _, end in cuts)
