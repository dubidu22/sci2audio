"""Cutting a text block into blocks at the start of some of its lines, keeping some of its
parts, and reading lines into a placeholder's text (Issue #21 step 3)."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import replace

from sci2audio.core import Block, Box, Part, TextLine
from sci2audio.layout.geometry import letter_size, rows, separators
from sci2audio.layout.settings import LayoutSettings


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
    block's kind and the parts whose text starts in it, in their order: a part that starts
    exactly at a cut but comes before the part the next piece opens with (a graphic standing
    where the line before ends, with no separator, #58) stays with the piece before. A cut
    where no part starts, or at the very start, is left out (`piece_starts`). Each piece's
    text is the block's text from its start up to the next piece, without the one break or
    space before it (pieces of a printed line set close together have none, #36), kept as
    found."""
    edges = piece_starts(block, cuts)
    # where each piece's parts begin: at the last part that starts at its edge, so a graphic
    # standing where the line before ends, with no separator, stays with that line (#58)
    firsts = [0] + [
        max(k for k, part in enumerate(block.parts) if part.start == edge) for edge in edges[1:]
    ]
    out = []
    for n, begin in enumerate(edges):
        last = n + 1 == len(edges)
        stop = len(block.text) + 1 if last else edges[n + 1]  # where the next piece starts
        end = len(block.text) if last else _before(block.text, stop)
        held = block.parts[firsts[n] : None if last else firsts[n + 1]]
        parts = tuple(Part(p.item, p.start - begin) for p in held)
        out.append(replace(block, text=block.text[begin:end], parts=parts))
    return out


def _before(text: str, start: int) -> int:
    """Where the text before a part that starts at `start` ends: before the one break or
    space that joins them, if there is one (pieces of a printed line set close together
    have none, #36; a line's own text never ends in white space when it comes from a PDF)."""
    return start - 1 if 0 < start <= len(text) and text[start - 1].isspace() else start


def part_ends(block: Block, lines: Mapping[str, int]) -> dict[str, int]:
    """Where each line part's text ends: its start plus the length of the line's text
    (`lines` maps each text line's id to that length), at most the end of the block's text.
    Parts that are no line (a graphic) hold no text, so they never end a line, wherever
    they stand."""
    return {
        part.item: min(part.start + lines[part.item], len(block.text))
        for part in block.parts
        if part.item in lines
    }


def kept(block: Block, parts: Iterable[Part], lines: Mapping[str, int]) -> Block:
    """The block holding only these of its parts, in its order: each kept line's text as
    found, with the break or space that stood before it in the block (none where none
    stood, #36). A part that is no line (a graphic) holds no text; it stands where the text
    read before it ends. `lines` maps each text line's id to the length of its text."""
    ends = part_ends(block, lines)
    joins, end = {}, 0  # what stood before each line part: the text since the line before
    for part in block.parts:
        if part.item in lines:
            joins[part.item] = block.text[min(end, part.start) : part.start][-1:]
            end = max(end, ends[part.item])
    text, out = "", []
    for part in parts:
        if part.item not in lines:
            out.append(Part(part.item, len(text)))
            continue
        text += joins[part.item] if text else ""
        out.append(Part(part.item, len(text)))
        text += block.text[part.start : ends[part.item]]
    return replace(block, text=text, parts=tuple(out))


def read_rows(
    lines: list[TextLine], graphics: list[tuple[str, Box]], settings: LayoutSettings
) -> tuple[str, list[Part]]:
    """Lines read row by row (pieces of a row joined by a space where the page prints one,
    `separators`; rows by a line break), each as found, and the graphics among them where
    they are read (by their top)."""
    waiting = sorted(graphics, key=lambda g: g[1].y0)
    text, parts = "", []
    for row in rows(lines, settings.row_overlap):
        top = min(li.box.y0 for li in row if li.box)
        while waiting and waiting[0][1].y0 <= top:
            parts.append(Part(waiting.pop(0)[0], len(text)))
        text += "\n" if text else ""
        size = letter_size(run for line in row for run in line.runs)
        joins = separators(row, size, settings.word_space, settings.stack_reach)
        for n, line in enumerate(row):
            text += joins[n]
            parts.append(Part(line.id, len(text)))
            text += line.text
    parts += [Part(g[0], len(text)) for g in waiting]
    return text, parts
