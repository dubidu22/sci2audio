"""Cutting a text block into blocks at the start of some of its lines, keeping some of its
parts, and reading lines into a placeholder's text (Issue #21 step 3)."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace

from sci2audio.core import Block, Box, Part, TextLine
from sci2audio.layout.geometry import rows


def line_starts(block: Block) -> list[int]:
    """Where each of the block's printed lines starts in its text."""
    return [0, *(k + 1 for k, ch in enumerate(block.text) if ch == "\n")]


def piece_starts(block: Block, cuts: list[int]) -> list[int]:
    """Where the pieces of the block cut before each of `cuts` start: 0, then each cut
    inside the text where a part starts (no part is ever cut in two)."""
    starts = {part.start for part in block.parts}
    return [0, *sorted({c for c in cuts if 0 < c < len(block.text) and c in starts})]


def split_at(block: Block, cuts: list[int]) -> list[Block]:
    """The block cut before each of `cuts` (places in its text), each piece keeping the
    block's kind and the parts whose text starts in it. A cut where no part starts, or at
    the very start, is left out (`piece_starts`). Each piece's text is the block's text
    from its start up to the one break or space before the next piece, kept as found."""
    edges = piece_starts(block, cuts)
    out = []
    for n, begin in enumerate(edges):
        end = edges[n + 1] if n + 1 < len(edges) else len(block.text) + 1
        parts = tuple(
            Part(part.item, part.start - begin) for part in block.parts if begin <= part.start < end
        )
        out.append(replace(block, text=block.text[begin : end - 1], parts=parts))
    return out


def part_ends(block: Block) -> list[int]:
    """Where each part's text ends: before the one break or space ahead of the next part
    that starts later, or at the end of the text."""
    out, end = [], len(block.text)
    for n in range(len(block.parts) - 1, -1, -1):
        after = block.parts[n + 1].start if n + 1 < len(block.parts) else None
        if after is not None and after > block.parts[n].start:
            end = after - 1
        out.append(end)
    return out[::-1]


def kept(block: Block, parts: Iterable[Part], lines: set[str]) -> Block:
    """The block holding only these of its parts, in its order: each kept line's text as
    found, with the break or space that stood before it. A part that is no line (a graphic)
    holds no text; it stands where the text read before it ends."""
    ends = {part.item: end for part, end in zip(block.parts, part_ends(block), strict=True)}
    text, out = "", []
    for part in parts:
        if part.item not in lines:
            out.append(Part(part.item, len(text)))
            continue
        text += block.text[part.start - 1] if text and part.start else ""
        out.append(Part(part.item, len(text)))
        text += block.text[part.start : ends[part.item]]
    return replace(block, text=text, parts=tuple(out))


def read_rows(
    lines: list[TextLine], graphics: list[tuple[str, Box]], overlap: float
) -> tuple[str, list[Part]]:
    """Lines read row by row (pieces of a row joined by a space, rows by a line break), each
    as found, and the graphics among them where they are read (by their top)."""
    waiting = sorted(graphics, key=lambda g: g[1].y0)
    text, parts = "", []
    for row in rows(lines, overlap):
        top = min(li.box.y0 for li in row if li.box)
        while waiting and waiting[0][1].y0 <= top:
            parts.append(Part(waiting.pop(0)[0], len(text)))
        text += "\n" if text else ""
        for n, line in enumerate(row):
            text += " " if n else ""
            parts.append(Part(line.id, len(text)))
            text += line.text
    parts += [Part(g[0], len(text)) for g in waiting]
    return text, parts
