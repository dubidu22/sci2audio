"""Headings and the section tree (Issue #21 step 3).

A heading is a short block set apart from the running text: bold, or set larger than the
body text. Its printed number ("2.1", "A.3") gives its level, one per part; numbered
headings of one level share one style, so a short bold line in another style (a table's
header row, a checklist entry) is not one of them. A heading without a number counts at
level 1 when it is set like the numbered level-1 headings ("References"), when its whole
text is a usual section name ("Abstract"), or when it is set more prominently than any
numbered heading after the first of them: a common title over the appendices, which then
move one level down. A document without numbered headings takes its heading styles from
the short, larger-than-body lines that stand over running text more than once; the most
prominent style is level 1.

A heading stands over text no larger than the body text, or over another heading: the
title, the authors and their affiliations at the top of a paper are not headings.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, replace

from sci2audio.core import Block, BlockKind, Content, Section, TextLine
from sci2audio.layout.settings import LayoutSettings

# a printed heading number: "2", "2.1", "A", "A.1", with an optional dot, before the title
_NUMBER = re.compile(r"(?P<label>(?:\d{1,2}|[A-Z])(?:\.\d{1,2})*)\.?\s+(?=\w)")


@dataclass(frozen=True, order=True)
class Style:
    """How a block's letters are set: the size most of them have, and if they are bold.
    Styles order by prominence: larger, then bold."""

    size: float
    bold: bool


@dataclass(frozen=True)
class _Text:
    """A text block in reading order, with its place among all blocks and its style."""

    index: int
    block: Block
    style: Style


def find_headings(
    blocks: list[Block], content: Content, body: float, settings: LayoutSettings
) -> tuple[list[Block], tuple[Section, ...]]:
    """The blocks with their headings marked (kind, printed number as label), and the
    section tree the headings make."""
    lines = {line.id: line for page in content.pages for line in page.lines}
    found = [
        (index, block, _style(block, lines, settings))
        for index, block in enumerate(blocks)
        if block.kind is BlockKind.PARAGRAPH and block.text.strip()
    ]
    sizes = _same_sizes([style.size for _, _, style in found], settings.same_size)
    texts = [
        _Text(index, block, Style(sizes[style.size], style.bold)) for index, block, style in found
    ]
    levels = _Headings(texts, body, settings).levels()
    out = list(blocks)
    heads = []
    for index, (level, label) in sorted(levels.items()):
        out[index] = replace(blocks[index], kind=BlockKind.HEADING, label=label)
        heads.append((index, level, title(blocks[index].text)))
    return out, _sections(heads, len(blocks))


def title(text: str) -> str:
    """A heading's lines as one line. After a hyphen at a line's end the next line goes on
    without a space; the hyphen goes too if the next line starts in lower case (it only
    split a word), as the corpus truth writes headings."""
    found = ""
    for line in text.strip().split("\n"):
        line = line.strip()
        if found[-2:-1].isalpha() and found.endswith("-"):
            found = (found[:-1] if line[:1].islower() else found) + line
        else:
            found = f"{found} {line}" if found else line
    return found


def _style(block: Block, lines: dict[str, TextLine], settings: LayoutSettings) -> Style:
    """The size most of the block's letters have; bold if nearly all letters in that size
    are (a footnote mark in another size doesn't count)."""
    runs = [run for part in block.parts if part.item in lines for run in lines[part.item].runs]
    letters: Counter[float] = Counter()
    for run in runs:
        letters[run.size] += len(run.text.strip())
    if not letters:
        return Style(0.0, False)
    size = letters.most_common(1)[0][0]
    total = sum(len(run.text.strip()) for run in runs if run.size == size)
    bold = sum(len(run.text.strip()) for run in runs if run.size == size and run.bold)
    return Style(size, bool(total) and bold >= settings.heading_bold * total)


def _same_sizes(sizes: list[float], share: float) -> dict[float, float]:
    """Each size mapped to the smallest size of its group: sizes less than `share` apart
    (11.94 and 12.0 point) are one size, so they make one style."""
    found: dict[float, float] = {}
    first = None
    for size in sorted(set(sizes)):
        if first is None or size - first >= share * size:
            first = size
        found[size] = first
    return found


class _Headings:
    """Decides which text blocks are headings, and their levels."""

    def __init__(self, texts: list[_Text], body: float, settings: LayoutSettings) -> None:
        self.texts = texts
        self.body = body
        self.settings = settings
        self.short = [k for k, text in enumerate(texts) if self._short(text)]
        numbers = {
            k: found["label"]
            for k in self.short
            if (found := _NUMBER.match(texts[k].block.text.strip()))
        }
        # a capital letter is a number only where letters number headings ("A", "A.1",
        # "B"), not in a title that starts with a one-letter word ("A Note on Ethics")
        letters = {label for label in numbers.values() if label[0].isalpha()}
        if len(letters) < settings.heading_repeats:
            numbers = {k: label for k, label in numbers.items() if not label[0].isalpha()}
        self.numbers = numbers

    def levels(self) -> dict[int, tuple[int, str]]:
        """Each heading's block index, with its level and printed number ("" if none)."""
        numbered = len(self.numbers) >= self.settings.heading_repeats
        found = self._numbered() if numbered else self._unnumbered()
        # from the end: a heading stands over body text or another heading
        kept: dict[int, tuple[int, str]] = {}
        for k in sorted(found, reverse=True):
            after = k + 1
            if after < len(self.texts) and after not in kept and self._larger(self.texts[after]):
                continue
            kept[k] = found[k]
        return {self.texts[k].index: level for k, level in kept.items()}

    def _numbered(self) -> dict[int, tuple[int, str]]:
        """Headings in a document that numbers them: each depth of number in one style."""
        votes: dict[int, Counter[Style]] = {}
        for k, label in self.numbers.items():
            votes.setdefault(_depth(label), Counter())[self.texts[k].style] += 1
        styles = {depth: vote.most_common(1)[0][0] for depth, vote in votes.items()}
        top = styles[min(styles)]
        found: dict[int, tuple[int, str]] = {}
        shift = 0  # one more level for each heading under a common title (appendices)
        started = False  # the first numbered heading has come
        for k in self.short:
            style, label = self.texts[k].style, self.numbers.get(k)
            if label is not None and styles[_depth(label)] == style:
                found[k] = (_depth(label) + shift, label)
                started = True
            elif label is None and started and style > max(styles.values()):
                found[k], shift = (1, ""), 1
            elif label is None and (style == top or self._named(k)):
                found[k] = (1 + shift, "")
        return found

    def _unnumbered(self) -> dict[int, tuple[int, str]]:
        """Headings in a document that numbers none: the larger-than-body styles that stand
        over running text more than once, the most prominent at level 1."""
        over_text = Counter(
            self.texts[k].style
            for k in self.short
            if self._larger(self.texts[k]) and not self._over_larger(k)
        )
        styles = sorted(
            (s for s, n in over_text.items() if n >= self.settings.heading_repeats), reverse=True
        )
        level = {style: n for n, style in enumerate(styles, start=1)}
        return {
            k: (level.get(self.texts[k].style, 1), self.numbers.get(k, ""))
            for k in self.short
            if self.texts[k].style in level or self._named(k)
        }

    def _short(self, text: _Text) -> bool:
        """True if the block may be a heading: a few short lines with at least two letters,
        bold or larger than the body text, not ending as a sentence or a lead-in does."""
        words = text.block.text.strip()
        return (
            words.count("\n") < self.settings.heading_lines
            and len(words.split()) <= self.settings.heading_words
            and sum(ch.isalpha() for ch in words) >= self.settings.heading_letters
            and (text.style.bold or self._larger(text))
            and not words.endswith((".", ":", ";", ","))
        )

    def _larger(self, text: _Text) -> bool:
        return text.style.size > (1 + self.settings.size_change) * self.body

    def _over_larger(self, k: int) -> bool:
        """True if the next text block is set larger than the body text."""
        return k + 1 < len(self.texts) and self._larger(self.texts[k + 1])

    def _named(self, k: int) -> bool:
        """True if the block's whole text is a usual section name ("Abstract")."""
        name = title(self.texts[k].block.text).casefold()
        return name in {n.casefold() for n in self.settings.section_names}


def _depth(label: str) -> int:
    return label.count(".") + 1


def _sections(heads: list[tuple[int, int, str]], end: int) -> tuple[Section, ...]:
    """The section tree: a heading's section runs to the next heading of its level or
    above (or `end`), and holds the deeper ones in between."""
    out = []
    k = 0
    while k < len(heads):
        index, level, name = heads[k]
        j = k + 1
        while j < len(heads) and heads[j][1] > level:
            j += 1
        stop = heads[j][0] if j < len(heads) else end
        out.append(Section(name, level, index, stop, _sections(heads[k + 1 : j], stop)))
        k = j
    return tuple(out)
