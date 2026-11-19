"""Footnotes: the notes printed below a short rule at the foot of a column (Issue #21
step 3, #37).

A footnote rule is a thin horizontal line in the lower half of a page that starts at the
left edge of a column and is much narrower than the column. The text below it in that
column, set smaller than the body text, is the column's notes; a column whose text below
the line has a line in body size is not (the line belongs to something else, a table).
The notes' lines are read again row by row and split where a row opens with a mark (a
number or a symbol such as an asterisk or a dagger, set smaller than the row's text, or
raised, or in the text's size as a line of its own before the note's indented text when
the page's text above prints that mark, #457). A
note's lines are joined into one block even where the paragraph step left them apart
(#37: a note in a narrow column, cut into pieces at its wide word gaps). Text below a
rule with no mark is one note without a label. A page without a rule has no footnotes.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from statistics import median

from sci2audio.core import Block, BlockKind, Box, Content, Page, Part, TextLine, TextRun
from sci2audio.layout.geometry import Bars, letter_size, page_bars, rows, separators, union
from sci2audio.layout.settings import LayoutSettings

# a footnote mark as printed: a number or a run of note symbols
_MARK = re.compile(r"\d{1,3}|[*∗†‡§¶]+")  # noqa: RUF001 (the asterisk operator is meant)


@dataclass(frozen=True)
class _Zone:
    """The notes area of one column: below the rule, between the column's edges."""

    top: float
    left: float
    right: float


def find_footnotes(
    blocks: list[Block], content: Content, body: float, settings: LayoutSettings
) -> list[Block]:
    """The blocks with each column's notes as footnote blocks (the mark as label), in the
    place of the first block the notes were read in."""
    owner = {part.item: k for k, block in enumerate(blocks) for part in block.parts}
    text = [
        line
        for page in content.pages
        for line in page.lines
        if line.box and line.id in owner and blocks[owner[line.id]].kind is not BlockKind.FURNITURE
    ]
    replaced: dict[int, list[Block]] = {}
    dropped: set[int] = set()
    for page in content.pages:
        on_page = {line.id: line for line in page.lines}
        # from the highest rule down: a block below two rules belongs to the upper one
        for zone in sorted(_zones(page, text, body, settings), key=lambda z: z.top):
            inside = [
                k
                for k in _blocks_in(zone, page, blocks, owner, body, settings)
                if k not in replaced and k not in dropped
            ]
            if not inside:
                continue
            lines = [on_page[part.item] for k in inside for part in blocks[k].parts]
            marks = _body_marks(page, zone, settings)
            replaced[inside[0]] = _notes(lines, settings, page_bars(page, settings), marks)
            dropped.update(inside[1:])
    out: list[Block] = []
    for k, block in enumerate(blocks):
        if k in replaced:
            out += replaced[k]
        elif k not in dropped:
            out.append(block)
    return out


def _zones(page: Page, text: list[TextLine], body: float, settings: LayoutSettings) -> list[_Zone]:
    """The notes areas of the page: one below each footnote rule. A rule's column is that
    of the document's lines that start at its left end: they reach, most of them, as far
    as the column's right edge (`text` holds the document's lines that are not furniture)."""
    reach, share = settings.footnote_reach * body, settings.footnote_rule_share
    found = []
    for rule in page.drawings:
        box = rule.box
        if box is None or not _thin(box, page, settings):
            continue
        column = [li.box.x1 for li in text if li.box and abs(li.box.x0 - box.x0) <= reach]
        if not column:
            continue
        right = median(column)
        width = box.x1 - box.x0
        if not settings.footnote_rule_width * body <= width <= share * (right - box.x0):
            continue
        found.append(_Zone(box.y1, box.x0 - reach, right))
    return found


def _thin(box: Box, page: Page, settings: LayoutSettings) -> bool:
    """True for a thin horizontal line in the lower half of the page."""
    return box.y1 - box.y0 <= settings.footnote_rule_height and box.y0 >= settings.footnote_band * (
        page.height or 0.0
    )


def _blocks_in(
    zone: _Zone,
    page: Page,
    blocks: list[Block],
    owner: dict[str, int],
    body: float,
    settings: LayoutSettings,
) -> list[int]:
    """The paragraph blocks that lie wholly in the zone, in reading order; none if the zone
    holds a line in body size (the rule is not a footnote rule)."""
    smaller = (1 - settings.size_change) * body
    below = [
        line
        for line in page.lines
        if line.box
        and line.box.y0 >= zone.top
        and zone.left <= line.box.x0 < zone.right
        and line.id in owner
        and blocks[owner[line.id]].kind is not BlockKind.FURNITURE
    ]
    if any(_size(line.runs) >= smaller for line in below):
        return []
    ids = {line.id for line in below}
    found = sorted({owner[line.id] for line in below})
    return [
        k
        for k in found
        if blocks[k].kind is BlockKind.PARAGRAPH
        and all(part.item in ids for part in blocks[k].parts)
    ]


def _size(runs: Iterable[TextRun]) -> float:
    """The size most of the runs' letters have."""
    letters: Counter[float] = Counter()
    for run in runs:
        letters[run.size] += len(run.text.strip())
    return letters.most_common(1)[0][0] if letters else 0.0


def _body_marks(page: Page, zone: _Zone, settings: LayoutSettings) -> frozenset[str]:
    """The note marks the page prints in its text above the zone: numbers or note symbols
    set smaller than the line around them (#457)."""
    found = set()
    for line in page.lines:
        if not line.box or line.box.y0 >= zone.top or len(line.runs) < 2:
            continue
        size = _size(line.runs)
        for run in line.runs:
            text = run.text.strip()
            if run.size < (1 - settings.size_change) * size and _MARK.fullmatch(text):
                found.add(text)
    return frozenset(found)


def _notes(
    lines: list[TextLine], settings: LayoutSettings, bars: Bars, marks: frozenset[str] = frozenset()
) -> list[Block]:
    """The lines read again row by row, top to bottom and left to right, and split into
    notes where a row opens with a mark; `bars` are the page's drawings (a fraction bar
    keeps a space between its parts, #202), `marks` the marks printed in the text above."""
    notes: list[tuple[str, list[list[TextLine]]]] = []
    for row in rows(lines, settings.row_overlap):
        mark = _mark(row, settings, marks)
        if mark is not None or not notes:
            notes.append((mark or "", [row]))
        else:
            notes[-1][1].append(row)
    return [_note(label, found, settings, bars) for label, found in notes]


def _bars_of(row: list[TextLine], bars: Bars) -> tuple[Box, ...]:
    """The page's possible fraction bars that meet the row (#202)."""
    boxes = [piece.box for piece in row if piece.box]
    return bars.meeting(union(boxes)) if boxes else ()


def _mark(
    row: list[TextLine], settings: LayoutSettings, marks: frozenset[str] = frozenset()
) -> str | None:
    """The mark a row opens with: its first run, a number or note symbols set smaller
    than the row's text (the mark may be a line of its own), or set in the text's size but
    raised, as superior figures are: its box ends `footnote_mark_rise` em or more above the
    next run's (#235, D-507; boxes are loose, so the next run's letters don't matter).

    A mark in the text's size on the same baseline counts too where it is a line of its
    own, `footnote_mark_gap` em or more before the note's text, and the page's text above
    prints that mark (`marks`) as a smaller mark (#457): so a note that opens with a year
    ("1999 erschien ...") is not cut there."""
    first = row[0].runs[0]
    text = first.text.strip()
    size = _size(run for line in row for run in line.runs)
    smaller = first.size < (1 - settings.size_change) * size
    after = row[0].runs[1] if len(row[0].runs) > 1 else None
    raised = bool(
        first.box
        and after is not None
        and after.box
        and first.box.y1 <= after.box.y1 - settings.footnote_mark_rise * size
    )
    own, text_after = row[0].box, row[1].box if len(row) > 1 else None
    hanging = bool(
        text in marks
        and row[0].text.strip() == text
        and own
        and text_after
        and text_after.x0 - own.x1 >= settings.footnote_mark_gap * size
    )
    return text if (smaller or raised or hanging) and _MARK.fullmatch(text) else None


def _note(label: str, lines: list[list[TextLine]], settings: LayoutSettings, bars: Bars) -> Block:
    """A footnote block: rows joined by a line break, pieces of a row by a space where the
    page prints one (`separators`), each piece's text as found (white at its ends included,
    as in any block)."""
    text, parts = "", []
    for n, row in enumerate(lines):
        size = letter_size(run for piece in row for run in piece.runs)
        joins = separators(
            row,
            size,
            settings.word_space,
            settings.stack_reach,
            _bars_of(row, bars),
            settings.fraction_bar,
            settings.fraction_reach,
        )
        for k, piece in enumerate(row):
            text += "\n" if n and not k else joins[k]
            parts.append(Part(piece.id, len(text)))
            text += piece.text
    return Block(BlockKind.FOOTNOTE, text, tuple(parts), label=label)
