# ruff: noqa: RUF002
# (minus signs, dashes, primes and math letters are what these rules are about)
"""Shared helpers for the number and statistics steps (#67): candidate edits and folding.

Each of those steps runs several small rules over a block's text. A rule proposes
`Candidate`s; `pick` keeps them in rule order and drops any that overlaps one already kept,
so a step never returns two edits on the same text (the conformance suite checks that).
`fold` maps mathematical and letterlike letters to their plain letter without changing the
length, so a rule written for "p < .05" also finds "𝑝 < .05"; the edit then covers the
original characters.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass

from sci2audio.core import BlockKind, Edit, EditKind, Span

# blocks the number and statistics steps do not read: furniture is removed whole and tables,
# formulas and figures get notices (#64), so an edit there could only be set aside
SKIPPED_KINDS = frozenset(
    {BlockKind.FURNITURE, BlockKind.TABLE, BlockKind.FORMULA, BlockKind.FIGURE}
)


@dataclass(frozen=True)
class Candidate:
    """A replacement one rule proposes: the span in the block, what to read, and why."""

    start: int
    end: int
    replacement: str
    reason: str


def pick(candidates: Iterable[Candidate]) -> list[Candidate]:
    """The candidates that do not overlap an earlier one, in text order.

    Candidates come in rule order (the more specific rule first); a later candidate that
    shares a character with a kept one is dropped.
    """
    kept: list[Candidate] = []
    for candidate in candidates:
        if all(candidate.end <= k.start or candidate.start >= k.end for k in kept):
            kept.append(candidate)
    return sorted(kept, key=lambda c: c.start)


def to_edits(block: int, candidates: Iterable[Candidate], step: str) -> list[Edit]:
    """One `replace` edit per candidate (a candidate with no replacement removes its span)."""
    return [
        Edit(
            Span(block, c.start, c.end),
            EditKind.REPLACE if c.replacement else EditKind.REMOVE,
            reason=c.reason,
            step=step,
            replacement=c.replacement,
        )
        for c in candidates
    ]


def _plain(char: str) -> str:
    code = ord(char)
    if 0x1D400 <= code <= 0x1D7FF or 0x2100 <= code <= 0x214F:
        folded = unicodedata.normalize("NFKC", char)
        if len(folded) == 1:
            return folded
    return char


def fold(text: str) -> str:
    """The text with math and letterlike letters as plain letters; same length, same digits."""
    if text.isascii():
        return text
    return "".join(_plain(char) for char in text)


def padded(text: str, start: int, end: int, words: str) -> str:
    """`words` with a space on each side where a word would otherwise touch it.

    The span has taken the spaces around the sign, so "p < .05" and "p<.05" both read
    "p less than .05"; no space goes after an opening or before a closing bracket.
    """
    before = text[start - 1] if start > 0 else " "
    after = text[end] if end < len(text) else " "
    lead = "" if before.isspace() or before in "([{" else " "
    trail = "" if after.isspace() or after in ")]},;:" else " "
    return f"{lead}{words}{trail}"
