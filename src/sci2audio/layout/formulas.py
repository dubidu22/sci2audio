"""Display formulas as placeholder blocks with their printed numbers (Issue #21 step 3, PR
D2, D-93).

A display formula stands apart from the running text of its column. It is found from its
equation number: a line "(N)" ("(12)", "(16a)", "(A.2)") ending within `number_reach` of the
column's right edge, or a line starting at least `formula_indent` in that ends so. What
stands on the number's row in its column is the formula's, and so is each line chained to
it within `float_gap` that starts at least `formula_indent` in and does not fill the column:
the other rows of the formula, the limits of a sum set smaller. A line of running text ends
the chain. Each number makes one formula: aligned rows with a number each (nowak's 16a to
16f) are one formula each, each row going to the number nearest it. A chain without a
number is an unnumbered formula if at least `math_share` of its letters are set in a math
font (`math_fonts`) or are math symbols, and one of its lines is set at body size (a lone
subscript is not one).

A formula holds the graphics drawn inside it (a fraction bar, an arrow), taken from the
blocks they joined, and a figure no caption names that stands on its number's row
(arsiwalla's Eq. (4) is a picture). Only lines of paragraphs are taken: text in a caption,
footnote, table or figure stays where it is.

The formula is one FORMULA block, labelled with its number as printed ("16a"; "" if it has
none). Its text is its lines read row by row, each as found, the number with them. It
stands where its first line was read: a paragraph that holds it is cut there, the text
before it staying that paragraph and the text after it becoming a new one, each line's
text unchanged. A formula the reading order already read across both columns of a page
(#34) is cut into one block per number the same way.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace

from sci2audio.core import Block, BlockKind, Box, Content, Page, Part, TextLine
from sci2audio.layout.geometry import line_size, same_row, union
from sci2audio.layout.maths import math_letters, number_alone, number_at_end
from sci2audio.layout.settings import LayoutSettings
from sci2audio.layout.split import kept, read_rows

Edges = tuple[float, float]
_LIST_MARK = re.compile(
    r"[\N{BULLET}\N{WHITE BULLET}\N{BLACK SMALL SQUARE}\N{TRIANGULAR BULLET}]\s"
)


@dataclass
class _Formula:
    label: str
    lines: list[TextLine] = field(default_factory=list)
    graphics: list[tuple[str, Box]] = field(default_factory=list)


@dataclass
class _State:
    blocks: list[Block]
    owner: dict[str, int]  # item id: the block it is read in
    columns: dict[str, Edges]  # line id: its column's left and right edge
    named: set[str]  # first items of the placeholders a caption names
    boxes: dict[str, Box]  # graphic id: its box
    body: float
    settings: LayoutSettings
    taken: set[str] = field(default_factory=set)

    def kind(self, item: str) -> BlockKind:
        return self.blocks[self.owner[item]].kind


def find_formulas(
    blocks: list[Block],
    content: Content,
    columns: dict[str, Edges],
    named: set[str],
    body: float,
    settings: LayoutSettings,
) -> list[Block]:
    """The blocks with each display formula as a FORMULA block labelled with its number.

    `columns` gives each line of running text its column's edges; `named` the first item of
    each table or figure a caption names (never taken)."""
    owner = {part.item: k for k, block in enumerate(blocks) for part in block.parts}
    boxes = {
        graphic.id: graphic.box
        for page in content.pages
        for graphic in (*page.pictures, *page.drawings)
        if graphic.box
    }
    state = _State(blocks, owner, columns, named, boxes, body, settings)
    lines = {line.id: line for page in content.pages for line in page.lines}
    found: list[_Formula] = []
    for block in blocks:  # read across both columns by the reading order (#34)
        if block.kind is BlockKind.FORMULA:
            held = [lines[p.item] for p in block.parts if p.item in lines]
            graphics = [(p.item, boxes[p.item]) for p in block.parts if p.item in boxes]
            numbers = {li.id: n for li in held if (n := number_alone(li) or number_at_end(li))}
            found += _split(held, graphics, numbers) or [_Formula("", held, graphics)]
            state.taken |= {p.item for p in block.parts}
    for page in content.pages:
        found += _on_page(page, state)
    return _assemble(blocks, found, set(lines), settings)


def _on_page(page: Page, state: _State) -> list[_Formula]:
    """The display formulas in the page's columns."""
    by_column: dict[Edges, list[TextLine]] = {}
    for line in page.lines:
        known = line.id in state.columns and line.id in state.owner
        if line.box and known and line.id not in state.taken:
            by_column.setdefault(state.columns[line.id], []).append(line)
    found: list[_Formula] = []
    for edges, members in by_column.items():
        numbers = _numbers(members, edges, state)
        for group in _grown(_chains(members, edges, numbers, state), page, edges, state):
            graphics = _graphics(group, numbers, page, edges, state)
            formulas = [f for f in _split(group, graphics, numbers) if _holds_more(f)]
            if not formulas and not numbers.keys() & {li.id for li in group}:
                alone = _unnumbered(group, members, state)
                formulas = [_Formula("", group, graphics)] if alone else []
            for formula in formulas:
                state.taken |= {li.id for li in formula.lines} | {g for g, _ in formula.graphics}
            found += formulas
    return found


def _holds_more(formula: _Formula) -> bool:
    """True if the formula holds more than a number standing alone."""
    return bool(formula.graphics) or len(formula.lines) > 1 or not number_alone(formula.lines[0])


def _numbers(members: list[TextLine], edges: Edges, state: _State) -> dict[str, str]:
    """The column's equation numbers, by the line that prints them."""
    left, right = edges
    reach = state.settings.number_reach * state.body
    indent = state.settings.formula_indent * state.body
    found = {}
    for line in members:
        if state.kind(line.id) is not BlockKind.PARAGRAPH or line.box.x1 < right - reach:
            continue
        number = number_alone(line)
        if number is None and line.box.x0 >= left + indent:
            number = number_at_end(line)
        if number is not None:
            found[line.id] = number
    return found


def _chains(
    members: list[TextLine], edges: Edges, numbers: dict[str, str], state: _State
) -> list[list[TextLine]]:
    """The column's runs of display lines, top to bottom, each line within `float_gap` of
    the run so far; a line of running text ends a run."""
    left, right = edges
    settings = state.settings
    indent, gap = settings.formula_indent * state.body, settings.float_gap * state.body
    slack = settings.fill_slack * state.body
    heads = [line for line in members if line.id in numbers]
    paragraph = [line for line in members if state.kind(line.id) is BlockKind.PARAGRAPH]
    display = {
        line.id
        for line in paragraph
        if line.id in numbers
        or any(same_row(line.box, head.box, settings.row_overlap) for head in heads)
        or (line.box.x0 >= left + indent and line.box.x1 <= right - slack)
    }
    # the rest of a display line's row, unless it is running text: running text starts at
    # the column's edge or one paragraph indent in, and fills the column. A piece that
    # starts a formula's indent in is no running text even if it reaches the edge
    # (the second row of nowak's Eq. (14))
    start = settings.indent * state.body
    shown = [line for line in paragraph if line.id in display]
    display |= {
        line.id
        for line in paragraph
        if line.box.x0 > left + start
        and (line.box.x1 <= right - slack or line.box.x0 >= left + indent)
        and any(same_row(line.box, other.box, settings.row_overlap) for other in shown)
    }
    # a piece on a row of running text is inline maths, never a display line
    running = [li for li in paragraph if li.id not in display and li.box.x0 <= left + start]
    display -= {
        line.id
        for line in paragraph
        if line.id in display
        and line.id not in numbers
        and any(same_row(line.box, other.box, settings.row_overlap) for other in running)
    }
    chains: list[list[TextLine]] = []
    current: list[TextLine] = []
    bottom = 0.0
    for line in sorted(members, key=lambda li: li.box.y0):
        box = line.box
        if line.id not in display:
            chains += [current] if current else []
            current = []
            continue
        if current and box.y0 > bottom + gap:
            chains.append(current)
            current = []
        current.append(line)
        bottom = max(bottom, box.y1) if len(current) > 1 else box.y1
    return chains + ([current] if current else [])


def _grown(
    chains: list[list[TextLine]], page: Page, edges: Edges, state: _State
) -> list[list[TextLine]]:
    """The chains, each grown by the loose graphics that reach into it (a diagram's arrows,
    arsiwalla Eq. (2)) and by the chains of maths those graphics reach in turn, until none
    is left. A graphic as wide as the column is a rule or a frame, no connector; a chain of
    plain text (a quotation in a framed box) never joins (review of PR #61)."""
    settings = state.settings
    gap = settings.float_gap * state.body
    width = settings.full_line * (edges[1] - edges[0])
    loose = [
        graphic.box
        for graphic in (*page.pictures, *page.drawings)
        if graphic.box
        and graphic.id in state.owner
        and graphic.id not in state.taken
        and state.kind(graphic.id) not in (BlockKind.FIGURE, BlockKind.TABLE)
        and edges[0] - gap <= graphic.box.x0
        and graphic.box.x1 <= edges[1] + gap
        and graphic.box.x1 - graphic.box.x0 < width
    ]
    small = (1 - settings.size_change) * state.body
    maths = [
        math_letters(chain, settings.math_fonts) >= settings.math_share
        or all(line_size(li) < small for li in chain)
        for chain in chains
    ]
    out: list[list[TextLine]] = []
    rest = [union([li.box for li in chain]) for chain in chains]
    waiting = list(range(len(chains)))
    while waiting:
        group, area = list(chains[waiting[0]]), rest[waiting[0]]
        waiting.pop(0)
        unused = list(loose)
        while True:
            near = _grow(area, gap)
            reached = [box for box in unused if _meets(box, near)]
            unused = [box for box in unused if not _meets(box, near)]
            area = union([area, *reached])
            near = _grow(area, gap)
            joined = [k for k in waiting if maths[k] and _meets(rest[k], near)]
            if not reached and not joined:
                break
            for k in joined:
                group += chains[k]
                area = union([area, rest[k]])
            waiting = [k for k in waiting if k not in joined]
        out.append(sorted(group, key=lambda li: li.box.y0) if len(group) > 1 else group)
    return out


def _grow(box: Box, by: float) -> Box:
    return Box(box.x0 - by, box.y0 - by, box.x1 + by, box.y1 + by)


def _meets(a: Box, b: Box) -> bool:
    return a.x0 <= b.x1 and b.x0 <= a.x1 and a.y0 <= b.y1 and b.y0 <= a.y1


def _graphics(
    group: list[TextLine], numbers: dict[str, str], page: Page, edges: Edges, state: _State
) -> list[tuple[str, Box]]:
    """The graphics a formula holds: those drawn inside it, from the blocks they joined, and
    a figure no caption names standing on one of its numbers' rows."""
    gap = state.settings.float_gap * state.body
    area = union([li.box for li in group])
    area = Box(area.x0 - gap, area.y0 - gap, area.x1 + gap, area.y1 + gap)
    heads = [li for li in group if li.id in numbers]
    found: list[tuple[str, Box]] = []
    figures: dict[int, list[str]] = {}
    for graphic in (*page.pictures, *page.drawings):
        if not graphic.box or graphic.id not in state.owner or graphic.id in state.taken:
            continue
        kind = state.kind(graphic.id)
        if kind is BlockKind.FIGURE:
            figures.setdefault(state.owner[graphic.id], []).append(graphic.id)
        elif kind is not BlockKind.TABLE and _inside(graphic.box, area):
            found.append((graphic.id, graphic.box))
    for k, items in figures.items():
        block = state.blocks[k]
        if block.parts[0].item in state.named or len(items) < len(block.parts):
            continue
        box = union([state.boxes[i] for i in items])
        in_column = edges[0] - gap <= box.x0 and box.x1 <= edges[1] + gap
        on_row = any(same_row(box, h.box, state.settings.row_overlap) for h in heads)
        if in_column and (_inside(box, area) or on_row):
            found += [(i, state.boxes[i]) for i in items]
    return found


def _inside(box: Box, area: Box) -> bool:
    return area.x0 <= box.x0 and box.x1 <= area.x1 and area.y0 <= box.y0 and box.y1 <= area.y1


def _split(
    lines: list[TextLine], graphics: list[tuple[str, Box]], numbers: dict[str, str]
) -> list[_Formula]:
    """One formula per number, each line and graphic going to the number nearest it (by
    the middle of its height); none if no line prints a number."""
    heads = sorted((li for li in lines if li.id in numbers), key=lambda li: li.box.y0)
    formulas = [_Formula(numbers[head.id], [head]) for head in heads]
    if not heads:
        return []

    def nearest(box: Box) -> _Formula:
        middle = (box.y0 + box.y1) / 2
        k = min(
            range(len(heads)), key=lambda n: abs(middle - (heads[n].box.y0 + heads[n].box.y1) / 2)
        )
        return formulas[k]

    for line in lines:
        if line.id not in numbers:
            nearest(line.box).lines.append(line)
    for graphic in graphics:
        nearest(graphic[1]).graphics.append(graphic)
    return formulas


def _unnumbered(group: list[TextLine], members: list[TextLine], state: _State) -> bool:
    """True if the run is a display of mathematics: set in mathematics, not only in letters
    set smaller, alone on its rows, further in than the running text above it, and no list
    entry."""
    settings = state.settings
    smaller = (1 - settings.size_change) * state.body
    if not any(line_size(line) >= smaller for line in group):
        return False
    if math_letters(group, settings.math_fonts) < settings.math_share:
        return False
    if any(_LIST_MARK.match(line.text) for line in group):
        return False
    box = union([line.box for line in group])
    ids = {line.id for line in group}
    others = [line for line in members if line.id not in ids]
    if any(line.box.y0 < box.y1 and line.box.y1 > box.y0 for line in others):
        return False  # inline: running text on its rows
    above = [line for line in others if line.box.y1 <= box.y0]
    if above:
        last = max(above, key=lambda line: line.box.y1)
        return box.x0 >= last.box.x0 + settings.indent * state.body
    return True


def _assemble(
    blocks: list[Block], found: list[_Formula], lines: set[str], settings: LayoutSettings
) -> list[Block]:
    """The blocks with each formula where its first line is read: a block that holds a
    formula's line is cut there, the text on either side of it kept as found."""
    formula_of: dict[str, int] = {}
    for n, formula in enumerate(found):
        formula_of |= {li.id: n for li in formula.lines} | {g: n for g, _ in formula.graphics}
    placeholders = [_placeholder(f, settings) for f in found]
    out: list[Block] = []
    placed: set[int] = set()
    for block in blocks:
        if not any(part.item in formula_of for part in block.parts):
            out.append(block)
            continue
        segment: list[Part] = []
        for part in block.parts:
            n = formula_of.get(part.item)
            if n is None:
                segment.append(part)
            elif part.item in lines:  # a formula's line: the text so far ends here
                _flush(block, segment, lines, out)
                segment = []
                if n not in placed:
                    out.append(placeholders[n])
                    placed.add(n)
        _flush(block, segment, lines, out)
    out += [placeholders[n] for n in range(len(found)) if n not in placed]  # graphics only
    return out


def _flush(block: Block, segment: list[Part], lines: set[str], out: list[Block]) -> None:
    """Put out the block's parts kept so far: as a block if they hold text, else as parts
    of the block before them (a graphic joins the block read before it, D-90)."""
    if not segment:
        return
    if any(part.item in lines for part in segment) or not out:
        out.append(kept(block, segment, lines))
        return
    last = out[-1]
    more = tuple(Part(part.item, len(last.text)) for part in segment)
    out[-1] = replace(last, parts=(*last.parts, *more))


def _placeholder(formula: _Formula, settings: LayoutSettings) -> Block:
    text, parts = read_rows(formula.lines, formula.graphics, settings.row_overlap)
    return Block(BlockKind.FORMULA, text, tuple(parts), label=formula.label)
