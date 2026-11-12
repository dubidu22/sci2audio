"""Cutting a text block into blocks at the start of some of its lines (Issue #21 step 3)."""

from __future__ import annotations

from dataclasses import replace

from sci2audio.core import Block, Part


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
    the very start, is left out (`piece_starts`)."""
    edges = piece_starts(block, cuts)
    out = []
    for n, begin in enumerate(edges):
        end = edges[n + 1] if n + 1 < len(edges) else len(block.text) + 1
        parts = tuple(
            Part(part.item, part.start - begin) for part in block.parts if begin <= part.start < end
        )
        out.append(replace(block, text=block.text[begin:end].rstrip("\n"), parts=parts))
    return out
