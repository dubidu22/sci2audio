"""Footnotes: the notes printed below a short rule at the foot of a column (Issue #21
step 3, #37).

A footnote rule is a thin horizontal line in the lower part of a page that starts at the
left edge of a column and is much narrower than the column. The text below it in that
column, set smaller than the body text, is the column's notes; a column whose text below
the line has a line in body size is not (the line belongs to something else, a table).
The notes' lines are read again row by row and split where a row opens with a mark (a
number or a symbol such as an asterisk or a dagger, set smaller than the row's text). A
note's lines are joined into one block even where the paragraph step left them apart
(#37: a note in a narrow column, cut into pieces at its wide word gaps). Text below a
rule with no mark is one note without a label. A page without a rule has no footnotes.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from statistics import median

from sci2audio.core import Block, BlockKind, Box, Content, Page, Part, TextLine
from sci2audio.layout.geometry import rows
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
        for zone in _zones(page, text, body, settings):
            inside = _blocks_in(zone, page, blocks, owner, body, settings)
            if not inside:
                continue
            on_page = {line.id: line for line in page.lines}
            lines = [on_page[part.item] for k in inside for part in blocks[k].parts]
            replaced[inside[0]] = _notes(lines, settings)
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
    reach = settings.footnote_reach * body
    found = []
    for rule in page.drawings:
        box = rule.box
        if box is None or not _thin(box, page, settings):
            continue
        column = [li.box.x1 for li in text if li.box and abs(li.box.x0 - box.x0) <= reach]
        if not column:
            continue
        right = median(column)
        if not 2 * body <= box.x1 - box.x0 <= settings.footnote_rule_share * (right - box.x0):
            continue
        found.append(_Zone(box.y1, box.x0 - reach, right))
    return found


def _thin(box: Box, page: Page, settings: LayoutSettings) -> bool:
    """True for a thin horizontal line in the lower part of the page."""
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
    if any(_size(line) >= smaller for line in below):
        return []
    ids = {line.id for line in below}
    found = sorted({owner[line.id] for line in below})
    return [
        k
        for k in found
        if blocks[k].kind is BlockKind.PARAGRAPH
        and all(part.item in ids for part in blocks[k].parts)
    ]


def _size(line: TextLine) -> float:
    """The size most of the line's letters have."""
    letters: Counter[float] = Counter()
    for run in line.runs:
        letters[run.size] += len(run.text.strip())
    return letters.most_common(1)[0][0] if letters else 0.0


def _notes(lines: list[TextLine], settings: LayoutSettings) -> list[Block]:
    """The lines read again row by row, top to bottom and left to right, and split into
    notes where a row opens with a mark."""
    notes: list[tuple[str, list[list[TextLine]]]] = []
    for row in rows(lines, settings.row_overlap):
        mark = _mark(row[0], settings)
        if mark is not None or not notes:
            notes.append((mark or "", [row]))
        else:
            notes[-1][1].append(row)
    return [_note(label, found) for label, found in notes]


def _mark(line: TextLine, settings: LayoutSettings) -> str | None:
    """The mark a line opens with: its first run, a number or note symbols set smaller
    than the line's text."""
    first = line.runs[0]
    text = first.text.strip()
    smaller = first.size < (1 - settings.size_change) * _size(line)
    return text if smaller and _MARK.fullmatch(text) else None


def _note(label: str, lines: list[list[TextLine]]) -> Block:
    """A footnote block: rows joined by a line break, pieces of a row by a space."""
    text, parts = "", []
    for n, row in enumerate(lines):
        for k, piece in enumerate(row):
            text += "\n" if n and not k else " " if k else ""
            parts.append(Part(piece.id, len(text)))
            text += piece.text
    return Block(BlockKind.FOOTNOTE, text, tuple(parts), label=label)
