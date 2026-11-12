"""List items: the entries of a bulleted, numbered or lettered list (Issue #21 step 3, D-85).

A list is two or more text blocks in a row that open with markers of one style in
sequence: the same bullet (•, ◦, ▪, ‣ or an en dash), or "1." "2.", "(1)" "(2)", "1)" "2)",
"(a)" "(b)", "a)" "b)", "(i)" "(ii)". It starts at the first marker ("1.", "(a)", "(i)" or
a bullet). Furniture, figures, captions and footnotes between two items don't end a list (a page
break, a float); a heading or a block without a marker does. A list inside an item (the
bullets under "(iii)") is a list of its own and doesn't end the outer one. A block that
holds several items, one per line ("1. First Party\\n2. Third Party"), is cut into one
block per item; a block whose marker lines make no list stays whole.

The items of one list are set alike: their markers all stand apart from their text (a
gap, as in a hanging indent) or none do. This keeps a paragraph that opens by naming an
example ("(1) is understood as …") out of the list of numbered examples set apart around
it. Each item is a LIST_ITEM block labelled by its marker as printed.
"""

from __future__ import annotations

import itertools
import re
from dataclasses import dataclass, replace

from sci2audio.core import Block, BlockKind, Content, TextLine
from sci2audio.layout.split import line_starts, piece_starts, split_at

_ROMAN = ["i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x", "xi", "xii"]
_BULLETS = "•◦▪‣–"  # noqa: RUF001 (the en dash is meant)

# marker styles: a name, and a pattern whose group "n" is the ordinal as printed
_STYLES = [
    ("bullet", rf"(?P<n>[{_BULLETS}])"),
    ("1.", r"(?P<n>\d{1,2})\."),
    ("(1)", r"\((?P<n>\d{1,2})\)"),
    ("1)", r"(?P<n>\d{1,2})\)"),
    ("(i)", rf"\((?P<n>{'|'.join(_ROMAN)})\)"),
    ("i)", rf"(?P<n>{'|'.join(_ROMAN)})\)"),
    ("(a)", r"\((?P<n>[a-z])\)"),
    ("a)", r"(?P<n>[a-z])\)"),
]
_MARKERS = [(style, re.compile(rf"{pattern}(?=[^\S\n]+\S)")) for style, pattern in _STYLES]
# blocks that may stand between two items of a list: they float or sit at the page edge
_BETWEEN = {BlockKind.FURNITURE, BlockKind.FIGURE, BlockKind.CAPTION, BlockKind.FOOTNOTE}


@dataclass(frozen=True)
class _Marker:
    """A marker a block opens with: its text, and each reading of it (style, ordinal):
    "(i)" reads as the first roman numeral and as the ninth letter."""

    text: str
    readings: tuple[tuple[str, int], ...]

    def first(self) -> tuple[str, int] | None:
        return next((r for r in self.readings if r[1] == 1), None)


def find_lists(blocks: list[Block], content: Content) -> list[Block]:
    """The blocks with each list's items as LIST_ITEM blocks (the marker as label)."""
    lines = {line.id: line for page in content.pages for line in page.lines}
    # each block tried cut at its marker lines: (the block's index, the piece's start, piece)
    tried = []
    for n, block in enumerate(blocks):
        starts = _cuts(block)
        tried += [(n, k, piece) for k, piece in zip(starts, split_at(block, starts), strict=True)]
    cut = [piece for _, _, piece in tried]
    markers = [_marker(block.text) if block.kind is BlockKind.PARAGRAPH else None for block in cut]
    items: set[int] = set()
    for start, marker in enumerate(markers):
        reading = marker.first() if marker and start not in items else None
        if reading is None:
            continue
        found = _list_from(start, reading, cut, markers)
        apart = {_apart(cut[k], markers[k], lines) for k in found}
        if len(found) >= 2 and len(apart) == 1:
            items.update(found)
    # a block is cut only next to an item: pieces that make no list stay together
    item_at = {(n, k): markers[i] for i, (n, k, _) in enumerate(tried) if i in items}
    out: list[Block] = []
    for n, block in enumerate(blocks):
        starts = [k for m, k, _ in tried if m == n]
        keep = [
            k
            for before, k in itertools.pairwise(starts)
            if (n, before) in item_at or (n, k) in item_at
        ]
        for k, piece in zip([0, *keep], split_at(block, keep), strict=True):
            marker = item_at.get((n, k))
            out.append(
                replace(piece, kind=BlockKind.LIST_ITEM, label=marker.text) if marker else piece
            )
    return out


def _cuts(block: Block) -> list[int]:
    """Where a paragraph whose lines open with the markers of one list, in sequence, would
    be cut into one block per item: the start of each piece (only 0 for any other block)."""
    first = _marker(block.text) if block.kind is BlockKind.PARAGRAPH else None
    if first is None:
        return [0]
    readings, cuts = set(first.readings), []
    for start in line_starts(block)[1:]:
        found = _marker(block.text[start:])
        hit = {r for r in found.readings if _next(r, readings)} if found else set()
        if hit:
            readings, cuts = hit, [*cuts, start]
    return piece_starts(block, cuts)


def _list_from(
    start: int, reading: tuple[str, int], blocks: list[Block], markers: list[_Marker | None]
) -> list[int]:
    """The items of the list that starts at block `start`, in order."""
    style, found, readings = reading[0], [start], {reading}
    for k in range(start + 1, len(blocks)):
        marker = markers[k]
        if marker is None:
            if blocks[k].kind in _BETWEEN:
                continue
            break
        hit = {r for r in marker.readings if _next(r, readings)}
        if hit:
            found.append(k)
            readings = hit
        elif all(s != style for s, _ in marker.readings):
            continue  # an item of a list inside this one
        else:
            break
    return found


def _next(reading: tuple[str, int], before: set[tuple[str, int]]) -> bool:
    """True if `reading` follows one of `before` in its list (any bullet follows the same
    bullet)."""
    style, n = reading
    return any(s == style and (s.startswith("bullet") or n == m + 1) for s, m in before)


def _marker(text: str) -> _Marker | None:
    """The marker the text opens with, if any, with each reading of it."""
    readings, printed = [], ""
    for style, pattern in _MARKERS:
        found = pattern.match(text)
        if found:
            name = f"{style}{found['n']}" if style == "bullet" else style
            readings.append((name, _ordinal(style, found["n"])))
            printed = printed or found.group(0)
    return _Marker(printed, tuple(readings)) if readings else None


def _ordinal(style: str, n: str) -> int:
    if style == "bullet":
        return 1
    if n.isdigit():
        return int(n)
    if style in ("(i)", "i)"):
        return _ROMAN.index(n) + 1
    return ord(n) - ord("a") + 1


def _apart(block: Block, marker: _Marker | None, lines: dict[str, TextLine]) -> bool:
    """True if the marker is a piece of its own: white stands between it and its text."""
    first = lines.get(block.parts[0].item) if block.parts else None
    return bool(marker and first and first.text.strip() == marker.text)
