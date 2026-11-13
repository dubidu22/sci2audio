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

import bisect
import unicodedata
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from sci2audio.core import BlockKind, Edit, EditKind, Span
from sci2audio.textprep.characters import ACCENTS, INVISIBLE, SOFT_HYPHEN

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
    # the kept candidates never overlap, so sorted by start their ends are in order too, and
    # only the neighbours of a new candidate's place can overlap it (linear on long blocks)
    starts: list[int] = []
    kept: list[Candidate] = []
    for candidate in candidates:
        at = bisect.bisect_right(starts, candidate.start)
        if at and _overlap(kept[at - 1], candidate):
            continue
        following = at
        while following < len(kept) and kept[following].start < candidate.end:
            if _overlap(kept[following], candidate):
                break
            following += 1
        else:
            starts.insert(at, candidate.start)
            kept.insert(at, candidate)
    return kept


def _overlap(a: Candidate, b: Candidate) -> bool:
    return not (b.end <= a.start or b.start >= a.end)


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


def through_unread(text: str, rules: Callable[[str], list[Candidate]]) -> list[Candidate]:
    """`rules` run on the text as it is read: without the characters the Unicode step (#65)
    removes, which runs last (D-150). A soft hyphen or a zero-width space inside "3:\u00ad4",
    or a stray accent in "x <¯ 3", would otherwise hide a ratio or a sign that a second run,
    after the clean-up, finds. The candidates' spans are mapped back onto the printed text,
    taking in any unread characters inside."""
    kept: list[int] = []
    at = 0
    while at < len(text):
        char = text[at]
        if char in INVISIBLE:
            at += 1
        elif char == SOFT_HYPHEN:
            at += 2 if text[at + 1 : at + 2] == "\n" else 1
        else:
            kept.append(at)
            at += 1
    kept = [at for n, at in enumerate(kept) if not _stray_accent(text, kept, n)]
    if len(kept) == len(text):
        return rules(text)
    read = "".join(text[i] for i in kept)
    kept.append(len(text))
    return [
        Candidate(
            kept[c.start],
            kept[c.end - 1] + 1 if c.end > c.start else kept[c.start],
            c.replacement,
            c.reason,
        )
        for c in rules(read)
    ]


def _stray_accent(text: str, kept: list[int], n: int) -> bool:
    """True for an accent the Unicode step drops: no letter, digit or accent on either side,
    looking past unread characters (as `characters._accent` does)."""
    if text[kept[n]] not in ACCENTS:
        return False
    before = text[kept[n - 1]] if n else ""
    after = text[kept[n + 1]] if n + 1 < len(kept) else ""
    return all(not c.isalnum() and c not in ACCENTS for c in (before, after))
