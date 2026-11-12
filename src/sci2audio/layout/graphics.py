"""Tables, figures and algorithms as placeholder blocks (Issue #21 step 3, PR D1, D-88 to
D-92; #38, #51).

A caption names the float next to it. The float is read from the caption's edge away from
it: an algorithm's lines below its caption; a table or figure on the side where something
stands within `caption_reach`, the side whose walk takes a graphic, else the nearer one.
The walk takes, by distance, the text lines and graphics that stand across the caption, or
across what it took so far (a table's rule is as wide as the table), each within
`float_gap` of the last, up to white, another caption, a footnote or furniture. A graphic
brings the graphics drawn close to it (the group read as one figure before this step), and
an item passed by because it stood beside what was taken is taken once the float grows
across it, so what a walk takes does not hang on the order items are met in. Until a
graphic shows how wide the float is, a line set smaller than the body text brings the small
lines on its row (the cells of a table without rules). Between two rules of the same width,
white up to `caption_reach` is a row's padding (D-92). A float met on the way is taken
whole: nowak's Figure 1 holds Algorithms 1 and 2, and its caption
and theirs all name one FIGURE block (D-89). The line just above an algorithm's caption is
the top of the algorithm's box.

The float is one block: a TABLE for a "Table" caption, else a FIGURE. Its text is its lines
read row by row (pieces of a row joined by a space, rows by a line break), each listing of
a merged float on its own, as found: a table row, or a numbered line of pseudocode with its
number first (#38). Its graphics stand among its parts where they are read.

The graphics no caption names:
- the same box on `repeat_pages` pages (a journal's logo) is FURNITURE, a RUNNING_HEAD
  (D-91);
- lines only (a rule, a frame, arrows), or a mark no taller than `mark_height` (an icon, a
  logo by the authors): part of the footnote just below it (a footnote rule, #51), else of
  the block read just before it (D-90), whose text stays as it was;
- anything else is a FIGURE, with the other such graphics within `float_gap` of it. It
  takes no text: without a caption, a frame or background around running text can't be
  told from a figure.
"""

from __future__ import annotations

import bisect
import heapq
import itertools
from collections.abc import Iterable
from dataclasses import dataclass, field, replace

from sci2audio.core import (
    Block,
    BlockKind,
    Box,
    Content,
    FurnitureRole,
    Page,
    Part,
    TextLine,
)
from sci2audio.layout.geometry import line_size, rows, same_row, union
from sci2audio.layout.settings import LayoutSettings

# what a float may take: running text and graphics. Anything else ends its walk
_TAKE = {BlockKind.PARAGRAPH, BlockKind.FIGURE}
_ALGORITHM = ("Algorithm", "ALGORITHM")
_TABLE = ("Table", "TABLE")


@dataclass(frozen=True)
class _Item:
    """A text line or graphic with a box, and the block it is read in."""

    id: str
    box: Box
    block: int
    page: int
    line: TextLine | None = None


@dataclass
class _Float:
    """A table or figure: its kind, the captions that name it, its items as listings (each
    read on its own), and whether a later float took it in."""

    kind: BlockKind
    captions: list[int] = field(default_factory=list)
    listings: list[list[_Item]] = field(default_factory=list)
    merged: bool = False


@dataclass(frozen=True)
class Links:
    """Which placeholder each caption names, by items: each item of a caption, and one item
    of its placeholder (block indices change as later steps cut blocks; items don't)."""

    named: dict[str, str]


@dataclass
class _State:
    blocks: list[Block]
    body: float
    settings: LayoutSettings
    floats: list[_Float] = field(default_factory=list)
    taken: dict[str, int] = field(default_factory=dict)  # item id: its float

    def kind(self, item: _Item) -> BlockKind:
        return self.blocks[item.block].kind

    def take(self, number: int, items: Iterable[_Item]) -> None:
        for item in items:
            self.taken[item.id] = number


def find_graphics(
    blocks: list[Block], content: Content, body: float, settings: LayoutSettings
) -> tuple[list[Block], Links]:
    """The blocks with tables, figures and algorithms as placeholders, and the graphics no
    caption names as furniture, figures or parts of the blocks next to them."""
    state = _State(blocks, body, settings)
    owner = {part.item: k for k, block in enumerate(blocks) for part in block.parts}
    pages = [_items(page, owner) for page in content.pages]
    read: set[int] = set()  # a caption over two pages names a float on its first page
    for items in pages:
        for k in sorted({i.block for i in items if state.kind(i) is BlockKind.CAPTION} - read):
            read.add(k)
            _read_float(k, items, state)
    actions = _repeated(pages, state)
    for items in pages:
        actions |= _loose(items, state, actions)
    return _assemble(state, actions)


def link_captions(blocks: list[Block], links: Links) -> list[Block]:
    """The blocks with each caption's `describes` set to its placeholder's index."""
    where = {part.item: k for k, block in enumerate(blocks) for part in block.parts}
    out = []
    for block in blocks:
        named = [links.named[p.item] for p in block.parts if p.item in links.named]
        if block.kind is BlockKind.CAPTION and named:
            block = replace(block, describes=where[named[0]])
        out.append(block)
    return out


def _items(page: Page, owner: dict[str, int]) -> list[_Item]:
    """The page's lines and graphics that have a box, each with its block."""
    found = [_Item(li.id, li.box, owner[li.id], page.number, li) for li in page.lines if li.box]
    graphics = (*page.pictures, *page.drawings)
    return found + [_Item(g.id, g.box, owner[g.id], page.number) for g in graphics if g.box]


def _read_float(k: int, items: list[_Item], state: _State) -> None:
    """Read the float that caption `k` names, if one stands next to it."""
    label = state.blocks[k].label
    caption = [i for i in items if i.block == k]
    if not caption:
        return
    box = union([i.box for i in caption])
    others = [i for i in items if i.block != k]
    if label.startswith(_ALGORITHM):
        found = _walk(box, True, others, state) + _box_top(box, others, state)
    else:
        found = _side(box, others, state)
    if not found:
        return
    met = sorted({state.taken[i.id] for i in found if i.id in state.taken})
    kind = BlockKind.TABLE if label.startswith(_TABLE) else BlockKind.FIGURE
    new = _Float(kind, [k])
    for m in met:
        state.floats[m].merged = True
        new.captions += state.floats[m].captions
        new.listings += state.floats[m].listings
    own = [i for i in found if i.id not in state.taken]
    new.listings += [own] if own else []
    new.captions.sort()
    state.floats.append(new)
    state.take(len(state.floats) - 1, (i for listing in new.listings for i in listing))


def _beyond(box: Box, down: bool, items: list[_Item]) -> list[_Item]:
    """The items below (or above) the box, nearest first."""
    if down:
        return sorted((i for i in items if i.box.y0 >= box.y1), key=lambda i: i.box.y0)
    return sorted((i for i in items if i.box.y1 <= box.y0), key=lambda i: -i.box.y1)


def _across(item: _Item, left: float, right: float) -> bool:
    return item.box.x0 < right and item.box.x1 > left


def _gap(box: Box | float, item: _Item, down: bool) -> float:
    edge = box if isinstance(box, float) else (box.y1 if down else box.y0)
    return item.box.y0 - edge if down else edge - item.box.y1


def _side(box: Box, others: list[_Item], state: _State) -> list[_Item]:
    """The walk on the side the caption reads toward (nothing if nothing stands near): the
    side whose walk takes a graphic, or else the side where something stands nearer."""
    found = []
    for down in (True, False):
        walk = _walk(box, down, others, state)
        if walk:
            graphic = any(i.line is None for i in walk)
            found.append((not graphic, min(_gap(box, i, down) for i in walk), down, walk))
    return min(found, key=lambda f: f[:3])[3] if found else []


def _walk(box: Box, down: bool, others: list[_Item], state: _State) -> list[_Item]:
    """What stands across the caption (or across what was taken), from its edge outward,
    each item within `float_gap` of the last (the first within `caption_reach`). An item
    passed by because it stood beside what was taken so far is taken once the float grows
    across it, so what is taken does not hang on the order items are met in. Until a
    graphic shows how wide the float is, a line set smaller than the body text brings the
    small lines on its row: the cells of a table without rules. Between two rules of the
    same width, white up to `caption_reach` is a row's padding (chi's Table 4)."""
    reach = state.settings.caption_reach * state.body
    gap = state.settings.float_gap * state.body
    walk = _Walk(box, down, others, state)
    ahead = _beyond(box, down, others)
    for n, item in enumerate(ahead):
        if item.id in walk.seen:
            continue
        if not _across(item, walk.left, walk.right):
            walk.pass_by(item)
            continue
        white = _gap(walk.edge, item, down)
        if state.kind(item) not in _TAKE or white > reach:
            break
        if white > gap and walk.found and not _ruled(walk, ahead[n:], state):
            break
        walk.take(item)
    return walk.found


class _Walk:
    """A caption's walk so far: what it took, how far and how wide that reaches, and the
    items it passed by on either side."""

    def __init__(self, box: Box, down: bool, others: list[_Item], state: _State) -> None:
        self.down, self.state = down, state
        self.left, self.right = box.x0, box.x1
        self.edge = box.y1 if down else box.y0
        self.found: list[_Item] = []
        self.seen: set[str] = set()
        self.west: list[tuple[float, int, _Item]] = []  # passed by on the left, by -x1
        self.east: list[tuple[float, int, _Item]] = []  # passed by on the right, by x0
        self.order = itertools.count()
        self.drawn: dict[int, list[_Item]] = {}  # the graphics of each figure block
        for i in others:
            if i.line is None and state.blocks[i.block].kind is BlockKind.FIGURE:
                self.drawn.setdefault(i.block, []).append(i)
        small = [i for i in others if _small(i, state) and state.kind(i) in _TAKE]
        self.small = sorted(small, key=lambda i: i.box.y0)
        self.tops = [i.box.y0 for i in self.small]

    def pass_by(self, item: _Item) -> None:
        """Keep an item the walk passes by, beside what it took, if a float may take it."""
        if self.state.kind(item) not in _TAKE:
            return
        if item.box.x1 <= self.left:
            heapq.heappush(self.west, (-item.box.x1, next(self.order), item))
        else:
            heapq.heappush(self.east, (item.box.x0, next(self.order), item))

    def take(self, item: _Item) -> None:
        """Take the item, the small lines on its row while no graphic shows the float's
        width, and every passed item the float grows across, until none is left."""
        todo = [item]
        while todo:
            taken = todo.pop()
            if taken.id in self.seen:
                continue
            self.seen.add(taken.id)
            self.found.append(taken)
            if self.down:
                self.edge = max(self.edge, taken.box.y1)
            else:
                self.edge = min(self.edge, taken.box.y0)
            self.left, self.right = min(self.left, taken.box.x0), max(self.right, taken.box.x1)
            if _small(taken, self.state) and all(i.line for i in self.found):
                todo += self._row(taken)
            if taken.line is None:  # the graphics drawn with it, whole
                todo += self.drawn.pop(taken.block, [])
            while self.west and -self.west[0][0] > self.left:
                todo.append(heapq.heappop(self.west)[2])
            while self.east and self.east[0][0] < self.right:
                todo.append(heapq.heappop(self.east)[2])

    def _row(self, item: _Item) -> list[_Item]:
        """The small lines on the item's row not yet taken."""
        overlap = self.state.settings.row_overlap
        last = bisect.bisect_left(self.tops, item.box.y1)
        return [
            i
            for i in self.small[:last]
            if i.box.y1 > item.box.y0
            and i.id not in self.seen
            and same_row(i.box, item.box, overlap)
        ]


def _ruled(walk: _Walk, ahead: list[_Item], state: _State) -> bool:
    """True if a rule as wide as one already taken lies ahead, with only what a float may
    take, nothing further than `caption_reach` apart, up to it: the white is inside a
    table whose rows the rules divide."""
    reach = state.settings.caption_reach * state.body
    slack = state.settings.float_gap * state.body
    down, found = walk.down, walk.found
    widths = [(i.box.x0, i.box.x1) for i in found if _is_line(i, state)]
    edge: float | None = None
    for item in (i for i in ahead if _across(i, walk.left, walk.right)):
        if state.kind(item) not in _TAKE or (edge is not None and _gap(edge, item, down) > reach):
            return False
        if _is_line(item, state) and any(
            abs(item.box.x0 - x0) <= slack and abs(item.box.x1 - x1) <= slack for x0, x1 in widths
        ):
            return True
        far = item.box.y1 if down else item.box.y0
        edge = far if edge is None else (max(edge, far) if down else min(edge, far))
    return False


def _small(item: _Item, state: _State) -> bool:
    """True for a text line set smaller than the body text."""
    smaller = (1 - state.settings.size_change) * state.body
    return item.line is not None and line_size(item.line) < smaller


def _box_top(box: Box, others: list[_Item], state: _State) -> list[_Item]:
    """The line just above an algorithm's caption: the top of the algorithm's box."""
    gap = state.settings.float_gap * state.body
    above = [i for i in _beyond(box, False, others) if _across(i, box.x0, box.x1)]
    if above and _is_line(above[0], state) and _gap(box, above[0], False) <= gap:
        return [] if above[0].id in state.taken else [above[0]]
    return []


def _is_line(item: _Item, state: _State) -> bool:
    """True for a drawing at most `line_width` thick: a rule, a frame's side, an arrow."""
    box, width = item.box, state.settings.line_width * state.body
    return item.line is None and min(box.x1 - box.x0, box.y1 - box.y0) <= width


def _groups(items: Iterable[_Item], state: _State) -> dict[int, list[_Item]]:
    """The graphics no caption took, by the block they are read in."""
    groups: dict[int, list[_Item]] = {}
    for item in items:
        if item.line is None and item.id not in state.taken:
            groups.setdefault(item.block, []).append(item)
    return groups


def _loose(items: list[_Item], state: _State, actions: dict[int, str]) -> dict[int, str]:
    """What becomes of the page's graphics no caption took: blocks to "join" a neighbour;
    the rest become figures (new floats)."""
    gap = state.settings.float_gap * state.body
    groups = {k: g for k, g in _groups(items, state).items() if k not in actions}
    found, figures = {}, []
    for k, group in groups.items():
        if _minor(group, state):
            found[k] = "join"
        else:
            figures.append(group)
    # figures this close are one; text stays as it is (it may be framed running text)
    merged: list[list[_Item]] = []
    for group in figures:
        box = _grown(union([i.box for i in group]), gap)
        near = [m for m in merged if _meets(box, union([i.box for i in m]))]
        merged = [m for m in merged if m not in near]
        merged.append([i for m in near for i in m] + group)
    for group in merged:
        state.floats.append(_Float(BlockKind.FIGURE, [], [group]))
        state.take(len(state.floats) - 1, group)
    return found


def _minor(group: list[_Item], state: _State) -> bool:
    """True for lines only (a rule, a frame, arrows) or a mark no taller than
    `mark_height` (an icon)."""
    box = union([i.box for i in group])
    mark = box.y1 - box.y0 <= state.settings.mark_height * state.body
    return mark or all(_is_line(i, state) for i in group)


def _repeated(pages: list[list[_Item]], state: _State) -> dict[int, str]:
    """The graphics no caption took whose box stands on `repeat_pages` pages (a journal's
    logo, not lines or a mark): their blocks become "furniture"."""
    drift = state.settings.head_drift * state.body
    groups = _groups((i for items in pages for i in items), state)
    boxes = {
        k: (group[0].page, union([i.box for i in group]))
        for k, group in groups.items()
        if not _minor(group, state)
    }
    found = {}
    for k, (_, box) in boxes.items():
        same = {
            page
            for page, other in boxes.values()
            if all(abs(a - b) <= drift for a, b in zip(_corners(box), _corners(other), strict=True))
        }
        if len(same) >= state.settings.repeat_pages:
            found[k] = "furniture"
    return found


def _corners(box: Box) -> tuple[float, float, float, float]:
    return box.x0, box.y0, box.x1, box.y1


def _grown(box: Box, by: float) -> Box:
    return Box(box.x0 - by, box.y0 - by, box.x1 + by, box.y1 + by)


def _meets(a: Box, b: Box) -> bool:
    return a.x0 <= b.x1 and b.x0 <= a.x1 and a.y0 <= b.y1 and b.y0 <= a.y1


def _assemble(state: _State, actions: dict[int, str]) -> tuple[list[Block], Links]:
    """The blocks with the taken items moved into their placeholders, each placeholder
    where its first line of text was read (an algorithm's box opens above its caption, its
    lines below it), and the loose graphics placed by `actions`."""
    floats = {n: f for n, f in enumerate(state.floats) if not f.merged}
    anchor: dict[int, list[int]] = {}
    for n, f in floats.items():
        items = [i for listing in f.listings for i in listing]
        text = [i for i in items if i.line]  # where its text is read, else its graphics
        first = min(i.block for i in (text or items))
        anchor.setdefault(first, []).append(n)
    taken = set(state.taken)
    placeholders = {n: _placeholder(f, state.settings) for n, f in floats.items()}
    out: list[tuple[Block, str]] = []  # each block, and what to do with it
    for k, block in enumerate(state.blocks):
        here = [(placeholders[n], "") for n in anchor.get(k, [])]
        rest = _without(block, taken)
        first_taken = bool(block.parts) and block.parts[0].item in state.taken
        kept = [(rest, actions.get(k, ""))] if rest else []
        out += here + kept if first_taken else kept + here
    blocks = _place(out)
    named = {
        part.item: placeholders[n].parts[0].item
        for n, f in floats.items()
        for c in f.captions
        for part in state.blocks[c].parts
        if placeholders[n].parts
    }
    return blocks, Links(named)


def _placeholder(f: _Float, settings: LayoutSettings) -> Block:
    """A float's block: each listing's lines row by row, its graphics where they are read."""
    text, parts = "", []
    for listing in f.listings:
        graphics = sorted((i for i in listing if i.line is None), key=lambda i: i.box.y0)
        lines = [i.line for i in listing if i.line]
        for row in rows(lines, settings.row_overlap):
            top = min(li.box.y0 for li in row if li.box)
            while graphics and graphics[0].box.y0 <= top:
                parts.append(Part(graphics.pop(0).id, len(text)))
            text += "\n" if text else ""
            for n, line in enumerate(row):
                text += " " if n else ""
                parts.append(Part(line.id, len(text)))
                text += line.text
        parts += [Part(g.id, len(text)) for g in graphics]
    return Block(f.kind, text, tuple(parts))


def _without(block: Block, taken: set[str]) -> Block | None:
    """The block without the taken items (None if nothing is left): each kept line's text
    as found, with the break or space that stood before it."""
    kept = [part for part in block.parts if part.item not in taken]
    if len(kept) == len(block.parts):
        return block
    if not kept:
        return None
    text, parts = "", []
    ends = {part.item: end for part, end in zip(block.parts, _ends(block), strict=True)}
    for part in kept:
        piece = block.text[part.start : ends[part.item]]
        text += block.text[part.start - 1] if text and part.start else ""
        parts.append(Part(part.item, len(text)))
        text += piece
    return replace(block, text=text, parts=tuple(parts))


def _ends(block: Block) -> list[int]:
    """Where each part's text ends: before the one break or space ahead of the next part
    that starts later, or at the end of the text."""
    out, end = [], len(block.text)
    for n in range(len(block.parts) - 1, -1, -1):
        after = block.parts[n + 1].start if n + 1 < len(block.parts) else None
        if after is not None and after > block.parts[n].start:
            end = after - 1
        out.append(end)
    return out[::-1]


def _place(out: list[tuple[Block, str]]) -> list[Block]:
    """The blocks, with each loose graphic made furniture or joined to its neighbour: the
    footnote just after it, else the block before it, else the one after it. Graphics that
    would join the block after them never pass it: before furniture, or with nothing after
    them, they stay a block of their own where they are read."""
    blocks: list[Block] = []
    pending: list[Part] = []  # graphics to join the next block (none before them)
    for n, (block, action) in enumerate(out):
        if action == "furniture":
            if pending:
                blocks.append(Block(BlockKind.FIGURE, "", tuple(Part(p.item) for p in pending)))
                pending = []
            head = FurnitureRole.RUNNING_HEAD
            blocks.append(Block(BlockKind.FURNITURE, "", block.parts, role=head))
            continue
        if action != "join":
            if pending:
                block = replace(block, parts=(*(Part(p.item) for p in pending), *block.parts))
                pending = []
            blocks.append(block)
            continue
        after = out[n + 1][0] if n + 1 < len(out) else None
        if (after is not None and after.kind is BlockKind.FOOTNOTE) or not blocks:
            pending += block.parts
        else:
            last = blocks[-1]
            blocks[-1] = replace(
                last, parts=(*last.parts, *(Part(p.item, len(last.text)) for p in block.parts))
            )
    if pending:  # nothing after them: they stay a block of their own
        blocks.append(Block(BlockKind.FIGURE, "", tuple(Part(p.item) for p in pending)))
    return blocks
