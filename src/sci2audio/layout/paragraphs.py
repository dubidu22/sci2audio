"""Paragraphs: the lines of the reading order joined into blocks (Issue #21 step 2, #27).

Extraction ends a line at a wide gap (#27), so one printed line may come as several pieces
on one baseline. Pieces next to each other in one column are one line again, unless the
white between them lines up with white in the row above or below: then they are the cells
of a table or a list and stay apart; a list's dash or bullet printed apart from its words
is no cell, but opens its item's line (#856).

A line's size is the size most of its letters have, so a footnote mark or a subscript does
not change it; it is bold if nearly all its letters are and it ends in bold words, so a bold
run-in head ("Definition 1.") does not make it bold. A paragraph ends where the next line
is set in another size or weight, where the line before it stops short of its column's
edge, where the next line is indented as a first line (or, in a list with hanging indents,
starts further out), or where more white than the usual line spacing stands between the
two; never inside a word split by a hyphen at a line's end, and not at a short line that
ends inside a sentence when the line right under it goes on in lower case (#454). Lines set
flush right or centred (a motto, a title page's affiliation) start at many places: there a
ragged left edge is no indent or outdent, in centred lines a short line ends nothing, and a
change between italic and upright ends the paragraph (#454).
A paragraph goes on across a column or page break when its last line fills the column and
the next column starts with a line in the same style that is not indented. Figures and
furniture met while a paragraph is open wait until it closes, and so does text that
interrupts it (`Paragraphs`): a paragraph is never cut by a footnote or a float. Text under
a float's caption in a column printed between the paragraph's column and the one it would
go on in is no float's but that column's: the paragraph ends before it, and the columns are
read in their order (#966). Of what waited, the marks drawn in the paragraph's own lines (a
fraction bar) come out first, right after it (#648). A figure in a wide gutter is read as a
column of its own between two columns of text (#873, #938): the rows read in that column
right after it, if they are its labels (on it or close by it, #945; a row of ticks may span
it, #933) and caption (under them, or above the figure and read before it, #933) and no
running text, interrupt a paragraph and never go on with one, nor set one aside (#905); the
paragraph open there ends at the figure, its labels are read into its block (#932) and its
caption is a block of its own. If the row before the figure ends no sentence (an
abbreviation's full stop ends none), its labels must lie on it, and its rows are the
figure's only where the paragraph read before them would not be set aside to go on after
them (#958); its labels are then read into its block all the same (#1017). The rows lying
on a figure at a column's top (its labels, set in any size) neither go on with a paragraph
nor it with them: they may interrupt it, and are read as blocks of their own after the
figure (#932).
A listing starts a block of its own (#599): a line set wholly in a typewriter font, after a
line of the paragraph that is not, with another such line right under it on the line
pitch, ends the paragraph, so code printed right under a full line is not read as prose.
A single such line is the paragraph's: a code name wrapped onto a line of its own, with
prose or more white under it (a caption's last line, #603), unless it starts at a code
indent (#787): further in than the prose line right above it and the one under it, by a
paragraph indent or more. A wrapped code name starts at the paragraph's left edge, so the
indent tells the two apart; such a line is a block of its own, and the prose under it
starts the next one. Links are no listing, and in a document set mostly in a typewriter
font (a typed memo) nothing is. Whether a document is typed and its body size are the one
judgement `code.find_code` uses too (`code.body_text`, #794).
A row that opens with a heading run into its paragraph, cut off its printed line by
extraction ("1) Hardware:" then "The board …", `geometry.run_in_head`, #963), starts a
paragraph: the headings step may take the heading out of it.
"""

from __future__ import annotations

import itertools
import re
from dataclasses import dataclass, replace
from statistics import median

from sci2audio.core import Block, BlockKind, Box, Part, TextLine, TextRun
from sci2audio.layout.captions import opens_caption
from sci2audio.layout.code import BodyText, body_text, monospace, monospace_line, only_links
from sci2audio.layout.geometry import (
    Bars,
    boxed,
    fraction_bar,
    holds,
    letter_size,
    minor,
    run_in_head,
    same_row,
    separators,
    union,
)
from sci2audio.layout.order import Element
from sci2audio.layout.settings import LayoutSettings

# a list item lettered "i." to "viii." or "a." to "z." (`lists` knows "i)", "(i)", "a)", "(a)")
_LETTERED_ITEM = re.compile(r"(?:[ivxl]{1,4}|[a-z])[.)]\s")
# a list item's dash or bullet, printed apart from its words (#856)
_ITEM_MARKS = frozenset("-\u2010\u2012\u2013\u2014\u2022\u25e6\u25aa\u2023\u2043\u00b7\u2219")
# what besides a letter may open the words after it: a quote, an opening bracket, a digit
_ITEM_OPENS = frozenset("\"'\u201c\u201e\u2018\u201a\u00ab\u00bb\u2039\u203a([{0123456789")
# a table cell a dash leads as a minus (#985): a number, then only numbers, signs and units
# of up to three letters ("3 ms", "0.5 (0.1)", "1.5 ± 0.2"), where an item goes on in words;
# a short English or German word that joins numbers ("2 of 5", "3 bis 5") is no unit (#1002);
# matched as printed, since a unit may be spelled as a word in capitals ("A", the ampere)
_JOINING = (
    "a|an|and|as|at|by|for|in|of|on|or|per|the|to"
    "|als|am|auf|aus|bei|bis|im|je|mit|pro|um|und|von|vor|zu|zum|zur"
)
_NUMBER = re.compile(
    r"\d[\d.,]*(?:\s*(?:[\d.,()\[\]%±/+-]"
    rf"|(?<![^\W\d_])(?!(?:{_JOINING})\b)[^\W\d_]{{1,3}}\b))*"
)
# what may close a sentence after its full stop: quotes (English and German, #958),
# guillemets either way round, brackets
_CLOSING = "\"'\u201c\u201d\u2018\u2019\u00ab\u00bb\u2039\u203a)]"
# a full stop that ends a common abbreviation or a number, not a sentence (#945)
_ABBREVIATION = re.compile(
    r"(?:^|[\s(\[\u201e\u201c\"'])"
    r"(?:z\.\s?B|d\.\s?h|u\.\s?a|et\s+al|e\.\s?g|i\.\s?e|vgl|bzw|sog|ca|cf|vs"
    r"|Fig|Figs|Abb|Tab|Eq|Eqs|Ref|Refs|Nr|No|Sec|Abschn|Kap|S|p|pp|\d+)\.$"
)


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
    bars: tuple[Box, ...] = ()  # drawings meeting the row's box: fraction bars (#202)

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
    box: Box | None = None  # where a figure is drawn: its labels lie on it or by it (#945)
    # each of its graphics' boxes: one that holds all the text on it is a background (D-840)
    graphics: tuple[Box, ...] = ()
    # those of them that are pictures: an image is no fill set behind text (#1017)
    pictures: tuple[Box, ...] = ()


Unit = Row | Held


def rows_of(
    ordered: list[Element],
    edges: dict[int, tuple[float, float]],
    settings: LayoutSettings,
    size: float,
    bars: Bars | None = None,
) -> list[list[Element]]:
    """The page's text lines grouped into printed lines: neighbours in the reading order on
    one baseline in one column (`edges` gives each element's column edges). A loose line or
    mark read between two pieces of one printed line, inside that line (a fraction bar, an
    icon by a name), does not end the line: it is read just after it (#163, D-438). The
    line is the piece before the mark and the pieces read after it on one line with that
    piece: two fraction bars side by side, read as one graphic, reach past the first
    numerator (liu p4, #648). The denominator of a fraction in the line, under one of the
    page's `bars`, is in the line too, and is read right after its numerator (#322).
    `size` is the body text's size."""
    bars = bars or Bars()
    found: list[list[Element]] = []
    after: list[Element] = []  # marks drawn inside the printed line being read
    following = _following_lines(ordered)
    for element in ordered:
        last = found[-1] if found else None
        latest = last[-1] if last and last[-1].line is not None else None
        if element.line is None:
            ahead = following[id(element)]
            rest = (
                _rest_of_line(ordered, ahead, latest, edges, settings)
                if latest is not None and ahead is not None
                else []
            )
            if (
                latest is not None
                and rest
                and holds(union([latest.box, *(e.box for e in rest)]), element.box)
                and inline_mark(element, size, settings)
            ):
                after.append(element)
                continue
        elif latest is not None and (
            (_one_line(latest, element, edges, settings) and _on_row(found[-1], element, settings))
            or _denominator(found[-1], element, edges, settings, size, bars)
        ):
            found[-1].append(element)
            continue
        found += [[mark] for mark in after]
        after = []
        found.append([element])
    found += [[mark] for mark in after]
    return [_fractions_in_order(group, settings, size, bars) for group in found]


def _over(bar: Box, upper: Element, lower: Element, settings: LayoutSettings, size: float) -> bool:
    """True if the bar is a fraction bar over the first letters of `lower` with `upper`
    over it (#202), and those first letters start inside the bar's width: a word under a
    brace drawn as two short rules starts beside them (Nowak p10, #322)."""
    if upper.line is None or lower.line is None:
        return False
    first = _first_letters(lower.line)
    reach = settings.fraction_inside * size
    return (
        bar.x0 - reach <= first.x0
        and first.x1 <= bar.x1 + reach
        and fraction_bar(
            bar, upper.line, lower.line, size, settings.fraction_bar, settings.fraction_reach
        )
    )


def _first_letters(piece: TextLine) -> Box:
    boxes = [run.box for run in piece.runs if run.box is not None and run.text.strip()]
    return boxes[0] if boxes else boxed(piece)


def _denominator(
    group: list[Element],
    element: Element,
    edges: dict[int, tuple[float, float]],
    settings: LayoutSettings,
    size: float,
    bars: Bars,
) -> bool:
    """True if the text piece read after the printed line `group` is the denominator of a
    fraction whose numerator is in it (#322, liu p2 "e gs g over 12 pi"): under a bar that
    stands inside the height of the line read so far. A table's rule stands under its line,
    not inside it."""
    texts = [e for e in group if e.line is not None]
    if element.line is None or not texts or edges[id(texts[-1])] != edges[id(element)]:
        return False
    line = union([e.box for e in texts])
    inside = [b for b in bars.meeting(line) if line.y0 < (b.y0 + b.y1) / 2 < line.y1]
    return any(_over(bar, upper, element, settings, size) for bar in inside for upper in texts)


def _fractions_in_order(
    group: list[Element], settings: LayoutSettings, size: float, bars: Bars
) -> list[Element]:
    """The printed line's pieces from left to right, except that a numerator is read just
    before its denominator when it starts further right (liu p2 "me over m*", #322)."""
    pieces = sorted(group, key=lambda e: e.box.x0)
    near = bars.meeting(union([e.box for e in pieces])) if len(pieces) > 1 else ()
    if not near:
        return pieces
    placed: set[int] = set()
    found: list[Element] = []
    for k, lower in enumerate(pieces):
        if id(lower) in placed:
            continue
        for upper in pieces[k + 1 :]:
            if id(upper) not in placed and any(
                _over(bar, upper, lower, settings, size) for bar in near
            ):
                found.append(upper)
                placed.add(id(upper))
                break
        found.append(lower)  # never looked at again: numerators are sought to its right
    return found


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


def _on_row(row: list[Element], piece: Element, settings: LayoutSettings) -> bool:
    """True if the text piece's base letters overlap those of the row's pieces so far
    (`_band`). A piece on one line with the piece before it joins the row only if this
    holds too: measured against the row as a whole and by its letters, not its box, a
    piece reaching into the line below (a brace whose box hangs 7 pt under the baseline,
    a tall accent) does not take that line into the row (#126)."""
    pieces = [e for e in row if e.line is not None]
    return same_row(_band(pieces, settings), _band([piece], settings), settings.row_overlap)


def _band(pieces: list[Element], settings: LayoutSettings) -> Box:
    """Where the pieces' base letters stand across the line: the median top and bottom, by
    letters, of the runs set within `same_size` of their largest size (a script is smaller,
    and in "0[n(-1)" outnumbers the base letters); a piece whose runs have no box counts as
    one run with the piece's box."""
    found: list[tuple[float, Box, int]] = []  # size, box, letters
    for piece in pieces:
        if piece.line is None:
            continue
        runs = [r for r in piece.line.runs if r.box is not None and r.text.strip()]
        if runs:
            found += [(r.size, r.box, len(r.text.strip())) for r in runs]
        else:
            letters = len(piece.line.text.strip()) or 1
            found.append((letter_size(piece.line.runs), piece.box, letters))
    largest = max(size for size, _, _ in found)
    base = [(box, n) for size, box, n in found if size >= (1 - settings.same_size) * largest]
    weights = [n for _, n in base]
    top = _weighted_median([box.y0 for box, _ in base], weights)
    bottom = _weighted_median([box.y1 for box, _ in base], weights)
    return Box(min(p.box.x0 for p in pieces), top, max(p.box.x1 for p in pieces), bottom)


def _weighted_median(values: list[float], weights: list[int]) -> float:
    pairs = sorted(zip(values, weights, strict=True))
    half, total = sum(weights) / 2, 0
    for value, weight in pairs:
        total += weight
        if total >= half:
            return value
    return pairs[-1][0]


def _following_lines(ordered: list[Element]) -> dict[int, int | None]:
    """Where in the reading order the text line read next after each element stands, if
    there is one."""
    found: dict[int, int | None] = {}
    ahead: int | None = None
    for k in range(len(ordered) - 1, -1, -1):
        found[id(ordered[k])] = ahead
        if ordered[k].line is not None:
            ahead = k
    return found


def _rest_of_line(
    ordered: list[Element],
    start: int,
    latest: Element,
    edges: dict[int, tuple[float, float]],
    settings: LayoutSettings,
) -> list[Element]:
    """The text pieces read from `start` on that stand on one printed line with `latest`,
    up to the first element that does not (a mark, the next line)."""
    found: list[Element] = []
    k = start
    while k < len(ordered) and ordered[k].line is not None:
        if not _one_line(latest, ordered[k], edges, settings):
            break
        found.append(ordered[k])
        k += 1
    return found


def split_cells(
    groups: list[list[Element]], edges: dict[int, tuple[float, float]]
) -> list[list[Element]]:
    """Pieces of one baseline with white between them that lines up with white between the
    pieces of the printed line above or below (in the same column, close by) are cells of a
    table or a list: each stays a line of its own. A wide gap in running text has letters
    above and below it. A list's dash or bullet printed apart from its words is no cell
    but opens its item (#856), unless a line of its column is no such item (#985)."""
    text = [g for g in groups if g[0].line is not None]
    position = {id(g): k for k, g in enumerate(text)}
    cuts: dict[int, list[int]] = {}
    # the lines whose white lines up with the white after a line's first piece
    after_first: dict[int, list[int]] = {}
    for group in groups:
        if len(group) < 2:
            continue
        index = position[id(group)]
        near = [
            other
            for other in (_nearest(text, index, -1, edges), _nearest(text, index, 1, edges))
            if other and _close(other, group)
        ]
        cuts[index], reach = [], group[0].box.x1
        for k, piece in enumerate(group[1:], start=1):
            # the white starts where the letters so far end (a subscript may stand below
            # the end of the piece before it)
            middle = (reach + piece.box.x0) / 2
            lined_up = [position[id(other)] for other in near if _white(other, middle)]
            if piece.box.x0 > reach and lined_up:
                cuts[index].append(k)
                if k == 1:
                    after_first[index] = lined_up
            reach = max(reach, piece.box.x1)
    items = _dash_items(
        {index for index in after_first if _dash_item(text[index], cuts[index])}, after_first
    )
    out: list[list[Element]] = []
    for group in groups:
        index = position.get(id(group), -1)
        found = cuts.get(index, [])[1 if index in items else 0 :]
        out += [group[a:b] for a, b in itertools.pairwise([0, *found, len(group)])]
    return out


def _dash_item(group: list[Element], cuts: list[int]) -> bool:
    """True if the printed line is a list dash or bullet, white, and its item's words as one
    cell that opens with a letter, a quote, a bracket or a digit (#856, #985): a dash before
    a bare number, or before more than one cell, is a table's."""
    mark = group[0].line
    words = " ".join(e.line.text for e in group[1:] if e.line is not None).strip()
    return (
        cuts == [1]
        and mark is not None
        and mark.text.strip() in _ITEM_MARKS
        and (words[:1].isalpha() or words[:1] in _ITEM_OPENS)
        and not _NUMBER.fullmatch(words)
    )


def _dash_items(dashed: set[int], lined_up: dict[int, list[int]]) -> set[int]:
    """The lines of `dashed` whose dash opens their item: the lines whose white after the
    first piece lines up, read from row to row, make a column, and the column is a list's
    only if each of its lines is dash-led. One line that is not (a table's head, a "+" among
    the dashes) makes it a table's, and every dash in it a cell (#985)."""
    items: set[int] = set()
    seen: set[int] = set()
    for start in sorted(dashed):
        if start in seen:
            continue
        column: set[int] = set()
        stack = [start]
        while stack:
            index = stack.pop()
            if index not in column:
                column.add(index)
                stack += lined_up.get(index, []) if index in dashed else []
        seen |= column
        if column <= dashed:
            items |= column
    return items


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
    group: list[Element],
    edges: tuple[float, float],
    page: int,
    settings: LayoutSettings,
    bars: Bars | None = None,
) -> Row:
    """The printed line these pieces make, in the column with these edges, and those of
    the page's `bars` that meet its box (a fraction bar between its pieces, #202)."""
    pieces = tuple(e.line for e in group if e.line is not None)
    runs = [run for piece in pieces for run in piece.runs]
    box = union([e.box for e in group])
    return Row(
        pieces,
        box,
        edges[0],
        edges[1],
        page,
        letter_size(runs) or settings.body_size,
        _bold(runs, settings),
        bars.meeting(box) if bars is not None else (),
    )


def _bold(runs: list[TextRun], settings: LayoutSettings) -> bool:
    """True if nearly all the letters are bold and the line ends in bold words: a line that
    opens with a bold run-in head ("Definition 1.") and goes on in regular words is not."""
    letters = sum(len(run.text) for run in runs)
    bold = sum(len(run.text) for run in runs if run.bold)
    worded = [run for run in runs if any(ch.isalpha() for ch in run.text)]
    ends_bold = not worded or worded[-1].bold
    return bool(letters) and bold > settings.bold_share * letters and ends_bold


def paragraphs(
    units: list[Unit], settings: LayoutSettings, body: BodyText | None = None
) -> list[Block]:
    """The document's rows joined into paragraphs, with the other blocks in their places;
    `body` is the document's judgement of its text (`code.body_text`; if not given, judged
    from the rows)."""
    return Paragraphs(units, settings, body).blocks()


class Paragraphs:
    """Joins rows into paragraph blocks, holding figures and furniture while one is open.

    A paragraph whose last line fills its column may be interrupted at a column or page
    break, a figure or a wider white space: by a footnote, a table, a caption or a display
    formula. It is then set aside and goes on with the first row in its own style that
    continues it after the interruption; the interruption follows the paragraph. Running
    text in the paragraph's size, or a heading, ends the wait.
    """

    def __init__(
        self, units: list[Unit], settings: LayoutSettings, body: BodyText | None = None
    ) -> None:
        self.settings = settings
        self.units = units
        self.out: list[Block] = []
        self.open: list[Row] = []  # the paragraph being read
        self.waiting: list[Block] = []  # figures and furniture met while it is open
        self.aside: list[Row] = []  # an interrupted paragraph
        self.held: list[Block] = []  # the interruption, in order: it follows the paragraph
        self.marks: set[int] = set()  # marks drawn in a waiting paragraph's lines, by id
        self.figure = False  # a figure came since the last row
        self.marked = False  # the interruption holds a figure or smaller letters
        self.caption: Row | None = None  # the caption that opened the interruption
        rows = [unit for unit in units if isinstance(unit, Row)]
        self.pitch = _pitch(rows, settings) or settings.line_pitch
        judged = body or body_text(piece for row in rows for piece in row.pieces)
        self.body, self.typed = judged.size, judged.typed
        self.rows = rows
        self._neighbours(rows)
        self.gutter: set[int] = set()  # (`continues` reads it while it is being found)
        # the labels of figures at a column's top: they neither go on with running text nor
        # it with them, so they may interrupt it (#932)
        self.apart: set[int] = set()
        # a figure's rows in a gutter read after a row that ends no sentence, by the id of
        # the first: they join `gutter` when it is read, if it sets no paragraph aside
        self.pending: dict[int, list[Row]] = {}
        # of those, the figure and its labels, read into its block if the run joins (#1017)
        self.late: dict[int, tuple[Held, list[Row]]] = {}
        # the labels read into a figure's block, by the id of its unit (#932)
        self.labels: dict[int, list[Row]] = {}
        # figures in a gutter read between two paragraphs, by the id of their unit: the
        # paragraph open there ends at them, as it would at their labels (#905, #932)
        self.between: set[int] = set()
        self.gutter = self._gutter_figures(units)
        self.apart = self._column_tops(units)
        self.folded = {id(row) for found in self.labels.values() for row in found}
        if self.folded:  # the rows read on either side of a figure's labels meet
            self._neighbours([row for row in rows if id(row) not in self.folded])

    def _join_gutter(self, row: Row) -> None:
        """The figure's rows in a gutter waiting in `pending` from `row` on join `gutter` if
        `row`, read as any other, would set no paragraph aside (#958). Its labels are then
        read into its block, as after a sentence end, and the paragraph open there ends at
        the figure, as it would at the first of them (#1017)."""
        run = self.pending.pop(id(row), None)
        if run is None or self._sets_aside(row, self.figure and opens_caption(row.pieces[0])):
            return
        figure, labels = self.late.get(id(row), (None, []))
        folded = {id(label) for label in labels}
        self.gutter |= {id(r) for r in run if id(r) not in folded}
        if figure is None or not labels:
            return
        self.labels[id(figure)] = labels
        self.folded |= folded
        self._neighbours([r for r in self.rows if id(r) not in self.folded])
        held = _with_labels(figure, labels, self.settings).block
        # the figure came before its labels, so it has gone out or waits already
        for blocks in (self.waiting, self.held, self.out):
            blocks[:] = [held if b is figure.block else b for b in blocks]
        self._finish()

    def _neighbours(self, rows: list[Row]) -> None:
        self.earlier = {id(b): a for a, b in itertools.pairwise(rows)}  # the row read before
        self.later = {id(a): b for a, b in itertools.pairwise(rows)}  # the row read after

    def _gutter_figures(self, units: list[Unit]) -> set[int]:
        """The rows of figures read in a column of their own between two columns of text,
        by id: the rows in one column read right after a figure, and perhaps its caption
        read right before it (printed above it, #933), with the row read before them in a
        column to their left and the row read after them in a column to their right, all on
        one page. They are fewer than `column_items`, so `order` counts no column of text
        there, and they are the figure's labels and caption (`_figure_rows`): running text
        there is never taken out of its paragraph. After a row that ends a sentence the
        labels are read into the figure's block (`labels`, #932) and the caption rows join
        `gutter`; after a row that ends none all of them wait in `pending` (#958)."""
        found: set[int] = set()
        before: Unit | None = None  # the last unit read that is no figure
        for k, unit in enumerate(units):
            if not _figure(unit):
                before = unit
                continue
            above = self._above(units, k)
            if above:
                before = units[k - len(above) - 1] if k > len(above) else None
            first = units[k + 1] if k + 1 < len(units) else None
            column = _column(above[0]) if above else _column(first)
            end = k + 1  # each row is in one run at most: the scan stays linear
            while end < len(units) and column is not None and _column(units[end]) == column:
                end += 1
            run = [u for u in units[k + 1 : end] if isinstance(u, Row)]
            after = units[end] if end < len(units) else None
            rows = above + run
            if not rows or not isinstance(before, Row) or not isinstance(after, Row):
                continue
            if not (
                before.page == rows[0].page == after.page
                and before.right <= rows[0].left
                and rows[0].right <= after.left
                and len(rows) < self.settings.column_items
            ):
                continue
            box = unit.box if isinstance(unit, Held) else None
            labels = self._figure_rows(before, above, run, box)
            if labels is None:
                continue
            if _sentence_end(before):
                folded = {id(row) for row in labels}
                found |= {id(row) for row in rows if id(row) not in folded}
                self.between.add(id(unit))
                if labels:
                    self.labels[id(unit)] = labels
            else:
                self.pending[id(rows[0])] = rows
                if isinstance(unit, Held):
                    self.late[id(rows[0])] = (unit, labels)
        return found

    def _above(self, units: list[Unit], k: int) -> list[Row]:
        """The rows read right before the figure `units[k]` in one column that stands over
        it, fewer than `column_items`: its caption printed above it in a gutter (#933), if
        `_figure_rows` finds they are one. None if the rows before it stand in a column
        beside it (the figure opens its column) or are more."""
        unit = units[k]
        box = unit.box if isinstance(unit, Held) else None
        last = units[k - 1] if k else None
        if box is None or not isinstance(last, Row) or not _spans(last, box):
            return []
        column = _column(last)
        start = k - 1
        while start > 0 and _column(units[start - 1]) == column:
            start -= 1
            if k - start >= self.settings.column_items:
                return []
        return [u for u in units[start:k] if isinstance(u, Row)]

    def _figure_rows(
        self, before: Row, above: list[Row], run: list[Row], figure: Box | None
    ) -> list[Row] | None:
        """The figure's labels if the rows are its labels and its caption and nothing else,
        else None. The labels are rows read after the figure, the caption the rows above it
        (`above`) or else the rows after the labels. A label does not fill its column,
        unless its pieces stand apart as a plot's ticks do (`_ticks`), and lies on the
        figure or within `float_gap` of it or of the label before it, as a plot's ticks and
        its axis's name do: running text under a figure stands further off (#945). Ragged
        lines that go on with a sentence start in any case and after any last character (a
        German noun, a name, "im Jahr 2023"), so if the row read before the figure ends no
        sentence (`_sentence_end`), each label must lie on the figure itself (#958). The
        caption is a row that opens one and the rows that go on with it."""
        ended = _sentence_end(before)
        reach = self.settings.float_gap * self.body if ended else 0.0
        near = [figure] if figure is not None else []
        labels = 0
        while labels < len(run) and self._label(run[labels], near, reach):
            if ended:
                near.append(run[labels].box)
            labels += 1
        caption = run[labels:]
        if above:
            if caption:
                return None
            caption = above
        elif not caption:
            return run if labels else None
        named = opens_caption(caption[0].pieces[0]) and all(
            self.continues(caption[:n], caption[n]) for n in range(1, len(caption))
        )
        return run[:labels] if named else None

    def _column_tops(self, units: list[Unit]) -> set[int]:
        """The labels of each figure that opens its column, by id: the rows read right after
        it in the column under it that lie on it (`_label` with no reach). Not if the next
        row read in that column lies on it too (running text on a shaded box), a single
        drawing of it holds them all (a background or a frame, D-840; a picture holding them
        is a chart printed as an image, #1017) or it is lines or a mark only
        (`geometry.minor`). Without this, the paragraph of the column before goes
        on in them (#932). They stay text: without a caption, a figure at a column's top is
        not told from a table with a shaded head, whose cells are read. A figure whose rows
        the gutter's rule judged (`_gutter_figures`) is left as that rule has it."""
        mark, thin = self.settings.mark_height * self.body, self.settings.line_width * self.body
        judged = self.gutter | {id(row) for rows in self.pending.values() for row in rows}
        found: set[int] = set()
        last: Row | None = None  # the last row read
        for k, unit in enumerate(units):
            if isinstance(unit, Row):
                last = unit
                continue
            first = units[k + 1] if k + 1 < len(units) else None
            if (
                not _figure(unit)
                or unit.box is None
                or id(unit) in self.between
                or not unit.graphics
                or minor(unit.graphics, mark, thin)
                or last is None
                or not isinstance(first, Row)
                or id(first) in judged
                or _column(first) == _column(last)
                or not _spans(first, unit.box)
            ):
                continue
            box, column, end = unit.box, _column(first), k + 1
            while end < len(units) and _column(units[end]) == column:
                row = units[end]
                if not isinstance(row, Row) or not self._label(row, [box], 0.0):
                    break
                end += 1
            labels = [u for u in units[k + 1 : end] if isinstance(u, Row)]
            rest = units[end] if end < len(units) else None
            if isinstance(rest, Row) and _column(rest) == column and _meets(rest.box, box):
                continue
            fills = [g for g in unit.graphics if g not in unit.pictures]
            if not any(all(holds(g, r.box) for r in labels) for g in fills):
                found |= {id(row) for row in labels}
        return found

    def _label(self, row: Row, near: list[Box], reach: float) -> bool:
        """True if the row may be a label (`_figure_rows`): it does not fill its column,
        unless its pieces stand apart as ticks do (`_ticks`), opens no caption, and lies
        within `reach` of one of the boxes `near`."""
        if (self._runs_on(row) and not self._ticks(row)) or opens_caption(row.pieces[0]):
            return False
        box = row.box
        return any(
            box.x0 < b.x1 + reach
            and b.x0 - reach < box.x1
            and box.y0 < b.y1 + reach
            and b.y0 - reach < box.y1
            for b in near
        )

    def _ticks(self, row: Row) -> bool:
        """True if the row is two or more pieces, each apart from the next by white at least
        a `gutter` wide: a plot's ticks across it, not running text, whose words stand a
        space apart (#933)."""
        white = self.settings.gutter * row.size
        pieces = [boxed(piece) for piece in row.pieces]
        return len(pieces) > 1 and all(b.x0 - a.x1 >= white for a, b in itertools.pairwise(pieces))

    def blocks(self) -> list[Block]:
        for unit in self.units:
            if isinstance(unit, Held):
                if id(unit) in self.between:
                    self._finish()
                    if self.aside:
                        self._release()
                self._hold(self._with_labels(unit))
                continue
            self._join_gutter(unit)
            if id(unit) in self.folded:
                continue
            self._take(unit)
            self.figure = False
        self._finish()
        if self.aside:
            self._release()
        return self.out

    def _with_labels(self, unit: Held) -> Held:
        labels = self.labels.get(id(unit))
        return _with_labels(unit, labels, self.settings) if labels else unit

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

    def _sets_aside(self, row: Row, after_float: bool) -> bool:
        """True if a paragraph is set aside, or the row, read as any other, would set the
        open one aside to go on after it. A figure's rows in a gutter after a row that ends
        no sentence (`pending`) are the figure's only if not (#958): they set no paragraph
        aside, so where it would have gone on after them, they would move its end before
        them."""
        if self.aside:
            return True
        joins = bool(self.open) and not after_float and self.continues(self.open, row)
        return bool(self.open) and not joins and self._pauses(row)

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
            self.marks.add(id(block))
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
            self._emit([_paragraph(self.open, self.settings), *self._after(self.waiting)])
        self.open, self.waiting = [], []

    def _release(self) -> None:
        """The set-aside paragraph won't go on: it comes out, then what interrupted it."""
        self.out += [_paragraph(self.aside, self.settings), *self._after(self.held)]
        self.aside, self.held = [], []
        self.caption = None

    def _after(self, blocks: list[Block]) -> list[Block]:
        """What waited for a paragraph, the marks drawn in its own lines first: they are
        read just after their line (#163), so a page number or a float that waited for the
        paragraph does not come between it and them and take them (liu p4, #648)."""
        ours = {id(block) for block in blocks} & self.marks
        self.marks -= ours
        return [b for b in blocks if id(b) in ours] + [b for b in blocks if id(b) not in ours]

    def _pauses(self, row: Row) -> bool:
        """True if the open paragraph is running text that could go on and the row interrupts
        it after a figure or a column or page break (a footnote, a float at a page's top)."""
        last = self.open[-1]
        if len(self.open) < 2 or last.bold or not self._runs_on(last) or _ends(last):
            return False
        if id(row) in self.gutter or id(last) in self.gutter:
            return False  # (a figure's rows in a gutter neither set aside nor are, #958)
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
            and not self._column_between(row)
        )

    def _column_between(self, row: Row) -> bool:
        """True if the lines read under the caption that interrupted the set-aside paragraph
        stand in a column between the paragraph's and the row's: the text of a middle
        column under a figure, printed between its neighbours. Read after the row, it would
        leave the page's order (#966). A float's own lines under its caption (an algorithm's,
        a note's) stand in the column the paragraph runs on from or goes on in (nowak p5:
        on the next page, left of where it goes on), and still wait for it, as does the
        caption alone (#61, #958). A word split by a hyphen over the break is never cut:
        the hyphen step rejoins it only inside one block."""
        last, first = self.aside[-1], self.open[0] if self.open else None
        return (
            first is not None
            and not _split_word(last, row)
            and first is not self.caption
            and self._float(first)
            and last.right <= first.left
            and first.right <= row.left
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
        no bigger that is not running text (a table cell, a formula), or a row of a figure in
        a wide gutter."""
        if self._smaller(row, paragraph) or id(row) in self.gutter:
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
        if (id(last) in self.gutter) != (id(next_row) in self.gutter):
            return False  # (a figure's labels and caption are not running text, #905)
        if id(next_row) in self.gutter and opens_caption(next_row.pieces[0]):
            return False  # (its labels do not go on in its caption, #933)
        if (id(last) in self.apart) != (id(next_row) in self.apart):
            return False  # (nor at a column's top, #932)
        size = max(last.size, next_row.size)
        if abs(last.size - next_row.size) > self.settings.size_change * size:
            return False
        if not _split_word(last, next_row) and self._breaks(rows, next_row):
            return False  # (a paragraph does not end inside a word)
        if self._listing(last, next_row) or self._code_line(last) or self._code_line(next_row):
            return False
        if run_in_head(next_row.pieces[0]) and len(next_row.pieces) > 1:
            return False  # (a heading run into its paragraph starts one, #963)
        return (
            not spacing
            or not _below(last, next_row, self.settings)
            or self._close_by(last, next_row)
        )

    def _listing(self, last: Row, row: Row) -> bool:
        """True if a listing starts at the row (#599): it is set wholly in a typewriter font
        and the paragraph's last row is not, and another such row stands right under it. A
        lone such row is the paragraph's (a code name wrapped onto a line of its own, #603),
        and so are links and any row of a typed document."""
        if self.typed or not self._monospace(row) or self._monospace(last):
            return False
        after = self.later.get(id(row))
        return (
            after is not None
            and self._stacked(row, after)
            and self._monospace(after)
            and not only_links(f"{row.text}\n{after.text}")
        )

    def _code_line(self, row: Row) -> bool:
        """True if the row is a lone code line set at a code indent (#787): wholly in a
        typewriter font, right under a row that does not end in one, stopping short of its
        column's right edge, and further in than the row above it and the row under it (if any)
        by a paragraph indent or more (a listing's next line, at the same indent, is not; it is
        `_listing`'s). A code name wrapped onto a line of its own starts at the paragraph's
        left edge (#603); a paragraph's first line at its indent, wholly in a typewriter
        font, runs on to the column's edge and is read with it (PR #831). The rest of a
        link or a code name the row above ends in is no code line (a reference's URL
        broken onto its hanging indent), nor are links, nor any row of a typed document."""
        if self.typed or not self._monospace(row) or only_links(row.text):
            return False
        earlier, after = self.earlier.get(id(row)), self.later.get(id(row))
        if earlier is None or not self._stacked(earlier, row):
            return False
        if row.right - row.box.x1 <= self.settings.fill_slack * row.size:
            return False  # (a paragraph's indented first line runs to the edge: it is read)
        shown = [run for piece in earlier.pieces for run in piece.runs if run.text.strip()]
        if shown and monospace(shown[-1].font):
            return False  # (inline code or a link broken over the line's end, or a listing's row)
        step = self.settings.indent * row.size
        inset = row.box.x0 - row.left
        return all(inset - (r.box.x0 - r.left) >= step for r in (earlier, after) if r)

    def _monospace(self, row: Row) -> bool:
        return all(monospace_line(piece, self.body) for piece in row.pieces)

    def _breaks(self, rows: list[Row], next_row: Row) -> bool:
        """True if a change of weight, a short line, an indent or an outdent ends the
        paragraph before the next row. A short row that ends inside a sentence, with a row
        right under it that goes on in lower case, is no paragraph's end (#454, D-719); an
        indent or an outdent still is. In lines set flush right or centred, a ragged left
        edge is no indent or outdent, in centred lines a short line is no paragraph's end,
        and a change between italic and upright ends the paragraph (#454)."""
        last = rows[-1]
        if last.bold != next_row.bold:
            return True
        if self._display(last):
            return False
        shape = self._aligned(last, next_row)
        if shape is not None and _italic(last) != _italic(next_row):
            return True  # (an italic affiliation, then an upright date under it)
        short = (
            shape != "centred" and not self._goes_on(rows, next_row) and self._short(last, next_row)
        )
        return short or (
            shape is None and (self._indented(rows, next_row) or self._outdented(rows, next_row))
        )

    def _goes_on(self, rows: list[Row], next_row: Row) -> bool:
        """True if the next row stands right under the last and goes on with its sentence in
        lower case (`_inside`), and the paragraph is no caption: under a caption's last line
        a float's own lines start (an algorithm's "for" or "return"). Then a short last row
        does not end the paragraph."""
        last = rows[-1]
        return (
            _inside(last, next_row)
            and self._stacked(last, next_row)
            and not opens_caption(rows[0].pieces[0])
        )

    def _aligned(self, last: Row, next_row: Row) -> str | None:
        """The rows' shape around the break (the two before it and the one after it, standing
        under each other): "right" if they end at one edge and start at three or more places, and
        none of them fills its column: lines set flush right, as a motto. "centred" if
        instead their middles line up. None otherwise: a paragraph's first-line indent or a
        hanging indent starts its rows at two places only, and justified rows fill their
        column."""
        if not self._stacked(last, next_row):
            return None
        window = [last, next_row]
        before, after = self.earlier.get(id(last)), self.later.get(id(next_row))
        if before is not None and self._stacked(before, last):
            window.insert(0, before)
        if after is not None and self._stacked(next_row, after):
            window.append(after)
        reach = self.settings.align * max(row.size for row in window)
        if len(window) < 3 or any(self._runs_on(row) for row in window):
            return None  # (justified rows fill their column: a list's entries)
        if len(_places([row.box.x0 for row in window], reach)) < 3:
            return None
        if len(_places([row.box.x1 for row in window], reach)) == 1:
            return "right"
        middles = [(row.box.x0 + row.box.x1) / 2 for row in window]
        return "centred" if len(_places(middles, reach)) == 1 else None

    def _stacked(self, upper: Row, lower: Row) -> bool:
        """True if the lower row stands right under the upper one, with no more white
        between them than the usual line spacing."""
        return _below(upper, lower, self.settings) and self._close_by(upper, lower)

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


def _sentence_end(row: Row) -> bool:
    """True if the row ends a sentence: in ".", "!", "?" or ":", or in closing quotes,
    guillemets or brackets right after one (`_CLOSING`, #958). A full stop after a common
    abbreviation or a number ("z. B.", "et al.", "Fig.", "3.") ends none (#945)."""
    text = row.text.rstrip().rstrip(_CLOSING)
    return text.endswith((".", "!", "?", ":")) and not _ABBREVIATION.search(text)


def _inside(row: Row, next_row: Row) -> bool:
    """True if the row ends inside a sentence, in a letter, a comma, a semicolon, an open
    bracket or a slash (a link broken at a line's end), and the next row goes on with it in
    lower case: a break there is a line of a motto or a poem, not a new paragraph (#454,
    D-719). A heading, a caption or a list entry starts upper case, a figure or a mark, so it
    is not joined this way; nor is a row ending in a digit (a table's cell, a number), nor
    a list item lettered "i." or "a." ("e.g." and "i.e." go on)."""
    end, start = row.text.rstrip()[-1:], next_row.text.lstrip()
    return (
        (end.isalpha() or end in ",;(/") and start[:1].islower() and not _LETTERED_ITEM.match(start)
    )


def _italic(row: Row) -> bool:
    """True if most of the row's letters are set in italic (a leading upright mark, as an
    affiliation's "1", does not make it upright)."""
    runs = [run for piece in row.pieces for run in piece.runs]
    letters = sum(len(run.text) for run in runs)
    return 2 * sum(len(run.text) for run in runs if run.italic) > letters


def _places(edges: list[float], reach: float) -> list[float]:
    """The distinct places among these edges: edges closer than `reach` to the one before
    them, in order, are one place."""
    found: list[float] = []
    for edge in sorted(edges):
        if not found or edge - found[-1] > reach:
            found.append(edge)
    return found


def _ends(row: Row) -> bool:
    """True if the row ends a sentence or a proof, or announces what follows (a colon)."""
    return (
        row.text.rstrip()
        .rstrip(_CLOSING)
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


def _pitch(rows: list[Row], settings: LayoutSettings) -> float:
    """The usual distance from one line to the next, in units of their size."""
    found = [
        min(b.box.y0 - a.box.y0, b.box.y1 - a.box.y1) / a.size
        for a, b in itertools.pairwise(rows)
        if a.size and _below(a, b, settings) and abs(a.size - b.size) < settings.same_size * a.size
    ]
    return median(found) if found else 0.0


def _column(unit: Unit | None) -> tuple[int, float, float] | None:
    """The page and the column's edges of a row (None for anything else)."""
    return (unit.page, unit.left, unit.right) if isinstance(unit, Row) else None


def _spans(row: Row, box: Box) -> bool:
    """True if the row's column reaches across part of the box."""
    return row.left < box.x1 and box.x0 < row.right


def _meets(a: Box, b: Box) -> bool:
    return a.x0 < b.x1 and b.x0 < a.x1 and a.y0 < b.y1 and b.y0 < a.y1


def _figure(unit: Unit) -> bool:
    """True for a figure in the reading order (not a mark drawn in a line)."""
    return isinstance(unit, Held) and not unit.inline and unit.block.kind is BlockKind.FIGURE


def _with_labels(unit: Held, labels: list[Row], settings: LayoutSettings) -> Held:
    """The figure with its labels read into its block: their text, and its graphics at its
    start (#932)."""
    text = _paragraph(labels, settings)
    graphics = tuple(Part(p.item) for p in unit.block.parts)
    return replace(unit, block=Block(BlockKind.FIGURE, text.text, graphics + text.parts))


def _paragraph(rows: list[Row], settings: LayoutSettings) -> Block:
    """The rows' text, lines joined by a line break and the pieces of a line by a space
    where the page prints one (`separators`)."""
    text, parts = "", []
    for n, row in enumerate(rows):
        joins = separators(
            row.pieces,
            row.size,
            settings.word_space,
            settings.stack_reach,
            row.bars,
            settings.fraction_bar,
            settings.fraction_reach,
        )
        for k, piece in enumerate(row.pieces):
            text += "\n" if n and not k else joins[k]
            parts.append(Part(piece.id, len(text)))
            text += piece.text
    return Block(BlockKind.PARAGRAPH, text, tuple(parts))
