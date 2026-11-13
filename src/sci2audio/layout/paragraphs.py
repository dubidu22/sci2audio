"""Paragraphs: the lines of the reading order joined into blocks (Issue #21 step 2, #27).

Extraction ends a line at a wide gap (#27), so one printed line may come as several pieces
on one baseline. Pieces next to each other in one column are one line again, unless the
white between them lines up with white in the row above or below: then they are the cells
of a table or a list and stay apart.

A line's size is the size most of its letters have, so a footnote mark or a subscript does
not change it; it is bold if nearly all its letters are and it ends in bold words, so a bold
run-in head ("Definition 1.") does not make it bold. A paragraph ends where the next line
is set in another size or weight, where the line before it stops short of its column's
edge, where the next line is indented as a first line (or, in a list with hanging indents,
starts further out), or where more white than the usual line spacing stands between the
two; never inside a word split by a hyphen at a line's end. A paragraph goes on across a
column or page break when its last line fills the column and the next column starts with a
line in the same style that is not indented. Figures and furniture met while a paragraph
is open wait until it closes, and so does text that interrupts it (`Paragraphs`): a
paragraph is never cut by a footnote or a float.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from statistics import median

from sci2audio.core import Block, BlockKind, Box, Part, TextLine, TextRun
from sci2audio.layout.captions import opens_caption
from sci2audio.layout.geometry import holds, letter_size, minor, same_row, separators, union
from sci2audio.layout.order import Element
from sci2audio.layout.settings import LayoutSettings


@dataclass(frozen=True)
class Row:
    """One printed line of running text: its pieces left to right, and its column's edges."""

    pieces: tuple[TextLine, ...]
    box: Box
    left: float
    right: float
    page: int
    size: float
    bold: bool

    @property
    def text(self) -> str:
        return " ".join(piece.text for piece in self.pieces)


@dataclass(frozen=True)
class Held:
    """A block that is not joined with others (a figure, furniture, a line without a
    position), in its place in the reading order, and the page it is printed on if known."""

    block: Block
    page: int | None = None
    # a loose line or mark drawn in a printed line: it waits for the open paragraph without
    # counting as a figure, so the paragraph reads as it would without it (#163, D-439)
    inline: bool = False


Unit = Row | Held


def rows_of(
    ordered: list[Element],
    edges: dict[int, tuple[float, float]],
    settings: LayoutSettings,
    size: float,
) -> list[list[Element]]:
    """The page's text lines grouped into printed lines: neighbours in the reading order on
    one baseline in one column (`edges` gives each element's column edges). A loose line or
    mark read between two pieces of one printed line, inside the two together (a fraction
    bar, an icon by a name), does not end the line: it is read just after it (#163, D-438).
    `size` is the body text's size."""
    found: list[list[Element]] = []
    after: list[Element] = []  # marks drawn inside the printed line being read
    following = _following_lines(ordered)
    for element in ordered:
        last = found[-1] if found else None
        latest = last[-1] if last and last[-1].line is not None else None
        if element.line is None:
            ahead = following[id(element)]
            if (
                latest is not None
                and ahead is not None
                and _one_line(latest, ahead, edges, settings)
                and holds(union([latest.box, ahead.box]), element.box)
                and inline_mark(element, size, settings)
            ):
                after.append(element)
                continue
        elif latest is not None and _one_line(latest, element, edges, settings):
            found[-1].append(element)
            continue
        found += [[mark] for mark in after]
        after = []
        found.append([element])
    found += [[mark] for mark in after]
    return [sorted(group, key=lambda e: e.box.x0) for group in found]


def inline_mark(element: Element, size: float, settings: LayoutSettings) -> bool:
    """True for graphics read as one that are a loose line or mark (`geometry.minor`), the
    kind that stands in a line of text."""
    boxes = [g.box for g in element.graphics if g.box]
    mark, width = settings.mark_height * size, settings.line_width * size
    return bool(boxes) and minor(boxes, mark, width)


def _one_line(
    a: Element, b: Element, edges: dict[int, tuple[float, float]], settings: LayoutSettings
) -> bool:
    """True if two text pieces read one after the other are one printed line."""
    return edges[id(a)] == edges[id(b)] and same_row(a.box, b.box, settings.row_overlap)


def _following_lines(ordered: list[Element]) -> dict[int, Element | None]:
    """The text line read next after each element, if any."""
    found: dict[int, Element | None] = {}
    ahead: Element | None = None
    for element in reversed(ordered):
        found[id(element)] = ahead
        if element.line is not None:
            ahead = element
    return found


def split_cells(
    groups: list[list[Element]], edges: dict[int, tuple[float, float]]
) -> list[list[Element]]:
    """Pieces of one baseline with white between them that lines up with white between the
    pieces of the printed line above or below (in the same column, close by) are cells of a
    table or a list: each stays a line of its own. A wide gap in running text has letters
    above and below it."""
    text = [g for g in groups if g[0].line is not None]
    position = {id(g): k for k, g in enumerate(text)}
    out: list[list[Element]] = []
    for group in groups:
        if len(group) < 2:
            out.append(group)
            continue
        index = position[id(group)]
        near = [
            other
            for other in (_nearest(text, index, -1, edges), _nearest(text, index, 1, edges))
            if other and _close(other, group)
        ]
        current, reach = [group[0]], group[0].box.x1
        for piece in group[1:]:
            # the white starts where the letters so far end (a subscript may stand below
            # the end of the piece before it)
            middle = (reach + piece.box.x0) / 2
            if piece.box.x0 > reach and any(_white(other, middle) for other in near):
                out.append(current)
                current = []
            current.append(piece)
            reach = max(reach, piece.box.x1)
        out.append(current)
    return out


def _nearest(
    groups: list[list[Element]], index: int, step: int, edges: dict[int, tuple[float, float]]
) -> list[Element] | None:
    """The next printed line in the same column, up (`step` -1) or down (+1)."""
    column = edges[id(groups[index][0])]
    k = index + step
    while 0 <= k < len(groups):
        if edges[id(groups[k][0])] == column:
            return groups[k]
        k += step
    return None


def _close(a: list[Element], b: list[Element]) -> bool:
    """True if the two printed lines are at most about one line apart."""
    top_a, top_b = min(e.box.y0 for e in a), min(e.box.y0 for e in b)
    bottom_a, bottom_b = max(e.box.y1 for e in a), max(e.box.y1 for e in b)
    height = max(bottom_a - top_a, bottom_b - top_b)
    return max(top_a, top_b) - min(bottom_a, bottom_b) <= height


def _white(group: list[Element], x: float) -> bool:
    """True if x falls in white between two pieces of the printed line."""
    inside = group[0].box.x0 < x < group[-1].box.x1
    return inside and not any(e.box.x0 <= x <= e.box.x1 for e in group)


def make_row(
    group: list[Element], edges: tuple[float, float], page: int, settings: LayoutSettings
) -> Row:
    """The printed line these pieces make, in the column with these edges."""
    pieces = tuple(e.line for e in group if e.line is not None)
    runs = [run for piece in pieces for run in piece.runs]
    return Row(
        pieces,
        union([e.box for e in group]),
        edges[0],
        edges[1],
        page,
        letter_size(runs) or settings.body_size,
        _bold(runs, settings),
    )


def _bold(runs: list[TextRun], settings: LayoutSettings) -> bool:
    """True if nearly all the letters are bold and the line ends in bold words: a line that
    opens with a bold run-in head ("Definition 1.") and goes on in regular words is not."""
    letters = sum(len(run.text) for run in runs)
    bold = sum(len(run.text) for run in runs if run.bold)
    worded = [run for run in runs if any(ch.isalpha() for ch in run.text)]
    ends_bold = not worded or worded[-1].bold
    return bool(letters) and bold > settings.bold_share * letters and ends_bold


def paragraphs(units: list[Unit], settings: LayoutSettings) -> list[Block]:
    """The document's rows joined into paragraphs, with the other blocks in their places."""
    return Paragraphs(units, settings).blocks()


class Paragraphs:
    """Joins rows into paragraph blocks, holding figures and furniture while one is open.

    A paragraph whose last line fills its column may be interrupted at a column or page
    break, a figure or a wider white space: by a footnote, a table, a caption or a display
    formula. It is then set aside and goes on with the first row in its own style that
    continues it after the interruption; the interruption follows the paragraph. Running
    text in the paragraph's size, or a heading, ends the wait.
    """

    def __init__(self, units: list[Unit], settings: LayoutSettings) -> None:
        self.settings = settings
        self.units = units
        self.out: list[Block] = []
        self.open: list[Row] = []  # the paragraph being read
        self.waiting: list[Block] = []  # figures and furniture met while it is open
        self.aside: list[Row] = []  # an interrupted paragraph
        self.held: list[Block] = []  # the interruption, in order: it follows the paragraph
        self.figure = False  # a figure came since the last row
        self.marked = False  # the interruption holds a figure or smaller letters
        self.caption: Row | None = None  # the caption that opened the interruption
        rows = [unit for unit in units if isinstance(unit, Row)]
        self.pitch = _pitch(rows, settings) or settings.line_pitch
        self.body = _body_size(rows)
        self.earlier = {id(b): a for a, b in itertools.pairwise(rows)}  # the row read before
        self.later = {id(a): b for a, b in itertools.pairwise(rows)}  # the row read after

    def blocks(self) -> list[Block]:
        for unit in self.units:
            if isinstance(unit, Held):
                self._hold(unit)
                continue
            self._take(unit)
            self.figure = False
        self._finish()
        if self.aside:
            self._release()
        return self.out

    def _take(self, row: Row) -> None:
        # a caption right after a float (a formula across the page, #34) starts afresh
        after_float = self.figure and opens_caption(row.pieces[0])
        if self.open and not after_float and self.continues(self.open, row):
            self.open.append(row)
            if self.aside and not self._interrupts(row, self.aside[-1]) and not self._float(row):
                self._release()  # running text in the paragraph's style: it won't go on
            elif self.aside:
                self.marked |= self._smaller(row, self.aside[-1])
        elif self.aside and self._resumes(row):
            self._finish()
            self.open, self.waiting = [*self.aside, row], self.held
            self.aside, self.held = [], []
            self.caption = None
        elif self.aside and self._interrupts(row, self.aside[-1]):
            self._finish()
            self.open = [row]
            self.marked |= self._smaller(row, self.aside[-1])
        elif self.open and not self.aside and self._pauses(row):
            self.aside, self.held = self.open, self.waiting
            self.open, self.waiting = [row], []
            self.marked = self.figure or self._smaller(row, self.aside[-1])
            self.caption = row if after_float else None
        elif self.aside and self._float(row):
            self._finish()
            self.open = [row]
        else:
            self._finish()
            if self.aside:
                self._release()
            self.open = [row]

    def _float(self, row: Row) -> bool:
        """True if the row belongs to the float whose caption interrupted the paragraph
        (an algorithm's lines under its caption): the rest of the caption's column on its
        page."""
        caption = self.caption
        return caption is not None and row.page == caption.page and row.left == caption.left

    def _hold(self, unit: Held) -> None:
        """A figure or furniture waits for the open paragraph. A formula stands where it is
        printed: it ends the open paragraph, unless the paragraph runs on from an earlier
        page and the formula stands at this page's top (#34). A mark drawn in a line waits
        too, but is no figure (#163)."""
        block = unit.block
        if unit.inline and self.open:
            self.waiting.append(block)
            return
        if self.open and block.kind is BlockKind.FORMULA and unit.page == self.open[-1].page:
            self._finish()
            self._emit([block])
        elif self.open:
            self.waiting.append(block)
            floats = (BlockKind.FIGURE, BlockKind.FORMULA)
            self.figure |= block.kind in floats
            self.marked |= bool(self.aside) and block.kind in floats
        else:
            self._emit([block])

    def _emit(self, blocks: list[Block]) -> None:
        (self.held if self.aside else self.out).extend(blocks)

    def _finish(self) -> None:
        """The open paragraph ends: it comes out, then what waited for it."""
        if self.open:
            self._emit([_paragraph(self.open, self.settings), *self.waiting])
        self.open, self.waiting = [], []

    def _release(self) -> None:
        """The set-aside paragraph won't go on: it comes out, then what interrupted it."""
        self.out += [_paragraph(self.aside, self.settings), *self.held]
        self.aside, self.held = [], []
        self.caption = None

    def _pauses(self, row: Row) -> bool:
        """True if the open paragraph is running text that could go on and the row interrupts
        it after a figure or a column or page break (a footnote, a float at a page's top)."""
        last = self.open[-1]
        if len(self.open) < 2 or last.bold or not self._runs_on(last) or _ends(last):
            return False
        if not self._interrupts(row, last):
            return False
        return self.figure or not _below(last, row, self.settings)

    def _resumes(self, row: Row) -> bool:
        """True if the row goes on with the set-aside paragraph as running text (it fills its
        column, and the next row goes on with it), apart from an interruption that held a
        figure or smaller letters, on the same page or the next, and not under a bold heading."""
        last = self.aside[-1]
        earlier, after = self.earlier.get(id(row)), self.later.get(id(row))
        return (
            self.marked
            and row.page <= last.page + 1
            and self._runs_on(row)
            and (after is None or self.continues([row], after))  # not a formula's full row
            and (earlier is None or (not earlier.bold and self._apart(earlier, row)))
            and self.continues(self.aside, row, spacing=False)
        )

    def _apart(self, upper: Row, lower: Row) -> bool:
        """True if a figure, a column or page break or more white than usual parts them."""
        return (
            self.figure
            or not _below(upper, lower, self.settings)
            or not self._close_by(upper, lower)
        )

    def _interrupts(self, row: Row, paragraph: Row) -> bool:
        """True if the row may stand inside the paragraph's text: smaller letters, or a row
        no bigger that is not running text (a table cell, a formula)."""
        if self._smaller(row, paragraph):
            return True
        bigger = row.size > (1 + self.settings.size_change) * paragraph.size
        return not bigger and not self._runs_on(row)

    def _runs_on(self, row: Row) -> bool:
        """True if the row fills its column from edge to edge, as running text does."""
        slack = self.settings.fill_slack * row.size
        return row.box.x0 - row.left <= slack and row.right - row.box.x1 <= slack

    def _smaller(self, row: Row, than: Row) -> bool:
        return row.size < (1 - self.settings.size_change) * than.size

    def _short(self, row: Row, next_row: Row) -> bool:
        """True if the row ends short of the right edge of its text: the column's, or the
        edge that it and a row next to it end at (a narrower block, as an abstract)."""
        window = [r for r in (self.earlier.get(id(row)), row, next_row) if r]
        slack = [r.right - r.box.x1 for r in window]
        reach = self.settings.align * row.size
        aligned = [
            a
            for i, a in enumerate(slack)
            for j, b in enumerate(slack)
            if i != j and abs(a - b) <= reach
        ]
        edge = min(aligned, default=0.0)
        return row.right - row.box.x1 - edge > self.settings.short_line * row.size

    def continues(self, rows: list[Row], next_row: Row, spacing: bool = True) -> bool:
        """True if the next row goes on with the paragraph whose rows these are; `spacing`:
        also check the white between them if the next row stands right under the last."""
        last = rows[-1]
        size = max(last.size, next_row.size)
        if abs(last.size - next_row.size) > self.settings.size_change * size:
            return False
        if not _split_word(last, next_row) and self._breaks(rows, next_row):
            return False  # (a paragraph does not end inside a word)
        return (
            not spacing
            or not _below(last, next_row, self.settings)
            or self._close_by(last, next_row)
        )

    def _breaks(self, rows: list[Row], next_row: Row) -> bool:
        """True if a change of weight, a short line, an indent or an outdent ends the
        paragraph before the next row."""
        last = rows[-1]
        if last.bold != next_row.bold:
            return True
        return not self._display(last) and (
            self._short(last, next_row)
            or self._indented(rows, next_row)
            or self._outdented(rows, next_row)
        )

    def _display(self, row: Row) -> bool:
        """True for a title or heading line: bigger than the body text, or bold. Its lines
        are often centred or ragged, so only a change of style or white ends it."""
        return row.bold or row.size > (1 + self.settings.size_change) * self.body

    def _close_by(self, upper: Row, lower: Row) -> bool:
        """True if no more white than the usual line spacing stands between the rows."""
        pitch = min(lower.box.y0 - upper.box.y0, lower.box.y1 - upper.box.y1)
        return pitch <= (self.pitch + self.settings.paragraph_space) * max(upper.size, lower.size)

    def _outdented(self, rows: list[Row], row: Row) -> bool:
        """True if the row starts further out than the paragraph's last row, and that row is
        not its first: a new entry of a list with hanging indents (as references)."""
        last = rows[-1]
        step = self.settings.indent * row.size
        return len(rows) > 1 and (last.box.x0 - last.left) - (row.box.x0 - row.left) >= step

    def _indented(self, rows: list[Row], row: Row) -> bool:
        """True if the row is the indented first line of a paragraph: it starts further in
        than the two rows before it, and the row after it is back at the left. In a list
        with hanging indents, only the first line of an entry stands out. A paragraph of one
        line at the left is the first line of such an entry: the row further in goes on
        with it. The paragraph's own first line may be indented too, so it is not one of
        the rows compared with."""
        last = rows[-1]
        if len(rows) < 2:
            return False
        step = self.settings.indent * row.size
        inset = row.box.x0 - row.left
        two_back = self.earlier.get(id(last))
        before = [r for r in (last, two_back) if r and r is not rows[0]]
        after = self.later.get(id(row))
        return all(inset - (r.box.x0 - r.left) >= step for r in before) and (
            after is None or inset - (after.box.x0 - after.left) >= step
        )


def _split_word(row: Row, next_row: Row) -> bool:
    """True if the row ends in a word split by a hyphen ("gram-") that the next row goes on
    with in lower case ("mar")."""
    end, start = row.text.rstrip(), next_row.text.lstrip()
    return end[-2:-1].isalpha() and end.endswith("-") and start[:1].islower()


def _ends(row: Row) -> bool:
    """True if the row ends a sentence or a proof, or announces what follows (a colon)."""
    return (
        row.text.rstrip()
        .rstrip("\"'\u201d\u2019)]")
        .endswith((".", "!", "?", ":", "\u25a0", "\u220e", "\u25a1"))
    )


def _below(upper: Row, lower: Row, settings: LayoutSettings) -> bool:
    """True if the lower row stands under the upper one in the same column of one page."""
    return (
        upper.page == lower.page
        and (upper.left, upper.right) == (lower.left, lower.right)
        and lower.box.y0 > upper.box.y0
        and not same_row(upper.box, lower.box, settings.row_overlap)
    )


def _body_size(rows: list[Row]) -> float:
    """The size most letters of the running text are set in."""
    letters: dict[float, int] = {}
    for row in rows:
        letters[row.size] = letters.get(row.size, 0) + len(row.text)
    return max(letters, key=lambda size: letters[size]) if letters else 0.0


def _pitch(rows: list[Row], settings: LayoutSettings) -> float:
    """The usual distance from one line to the next, in units of their size."""
    found = [
        min(b.box.y0 - a.box.y0, b.box.y1 - a.box.y1) / a.size
        for a, b in itertools.pairwise(rows)
        if a.size and _below(a, b, settings) and abs(a.size - b.size) < settings.same_size * a.size
    ]
    return median(found) if found else 0.0


def _paragraph(rows: list[Row], settings: LayoutSettings) -> Block:
    """The rows' text, lines joined by a line break and the pieces of a line by a space
    where the page prints one (`separators`)."""
    text, parts = "", []
    for n, row in enumerate(rows):
        joins = separators(row.pieces, row.size, settings.word_space, settings.stack_reach)
        for k, piece in enumerate(row.pieces):
            text += "\n" if n and not k else joins[k]
            parts.append(Part(piece.id, len(text)))
            text += piece.text
    return Block(BlockKind.PARAGRAPH, text, tuple(parts))
