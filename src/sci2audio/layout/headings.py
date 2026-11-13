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

A heading may also be marked by a rule drawn under it rather than by its style (#48, D-385
to D-391). In a document that numbers its headings, after the first of them, a block that
may be a heading, has no number and holds a rule under its last line is a level-1 heading,
also after a common title over the appendices, whose shift goes on for the numbered headings
after it ("ACL 2023 Responsible NLP Checklist", set like the subsections, with a rule under
it across the page). The rule is one of the block's own graphic parts, where the graphics
step put it (#58, D-90): at most `line_width` em thick, its top between the middle of the
line and `heading_rule_gap` em below the line, across the whole line and at least
`heading_rule_reach` em longer than its words at one end, so an underline of the words
themselves (a link) does not count.

The file's own outline (PDF bookmarks, #24) is a second signal, used after the font rules and
settled by these rules (D-270 to D-272):

1. The font rules go first and are never undone: every heading they find stays, with its
   level and printed number, whatever the outline says (outlines are often partial).
2. An outline entry adds a heading the font rules missed when exactly one paragraph block
   on the entry's page has the entry's title as its whole text: compared after NFKC, case
   folding and folding white space, with a printed number taken off the front of the block
   (and of the entry, if it has one). No match, or more than one, and the entry is ignored;
   so is an entry with no letters.
3. A single top entry with entries under it names the document, not a heading: it is
   skipped and the entries under it move up one level. An entry whose text is the file's
   own title is skipped too.
4. An added heading's level comes from its printed number when it has one, one level
   deeper after a common title over the appendices as for the font rules, else from the
   entry's level after rule 3; when both found a heading, the font rules' level stands.
   When two entries name the same block, the first one decides its level.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, replace

from sci2audio.core import Block, BlockKind, Box, Content, OutlineEntry, Section, TextLine
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
    drawings = {drawing.id: drawing.box for page in content.pages for drawing in page.drawings}
    rules = _Headings(texts, body, settings, lines, drawings)
    levels = rules.levels()
    levels |= _from_outline(texts, content, levels, rules)
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

    def __init__(
        self,
        texts: list[_Text],
        body: float,
        settings: LayoutSettings,
        lines: dict[str, TextLine],
        drawings: dict[str, Box],
    ) -> None:
        self.texts = texts
        self.body = body
        self.settings = settings
        self.lines = lines
        self.drawings = drawings
        self.short = [k for k, text in enumerate(texts) if self._short(text)]
        numbers = {
            k: found["label"]
            for k in self.short
            if (found := _NUMBER.match(texts[k].block.text.strip()))
        }
        # a capital letter is a number only where letters number headings ("A", "A.1",
        # "B"), not in a title that starts with a one-letter word ("A Note on Ethics")
        letters = {label for label in numbers.values() if label[0].isalpha()}
        self.lettered = len(letters) >= settings.heading_repeats
        # the block index of a common title over the appendices: numbered headings after it
        # are one level deeper (set by `levels`)
        self.shift_from: int | None = None
        if not self.lettered:
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
                if self.shift_from is None:  # the shift starts at the first such title
                    self.shift_from = self.texts[k].index
            elif label is None and started and self._ruled(k):
                found[k] = (1, "")  # a part of its own: no shift, which goes on after it
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

    def _ruled(self, k: int) -> bool:
        """True if the block holds a rule drawn under its last line (module docstring)."""
        block, em, settings = self.texts[k].block, self.body, self.settings
        boxes = [self.lines[part.item].box for part in block.parts if part.item in self.lines]
        line = boxes[-1] if boxes else None
        if line is None:
            return False
        rules = (self.drawings[part.item] for part in block.parts if part.item in self.drawings)
        return any(
            rule.y1 - rule.y0 <= settings.line_width * em
            and (line.y0 + line.y1) / 2 <= rule.y0 <= line.y1 + settings.heading_rule_gap * em
            and rule.x0 <= line.x0 + settings.align * em
            and rule.x1 >= line.x1 - settings.align * em
            and max(line.x0 - rule.x0, rule.x1 - line.x1) >= settings.heading_rule_reach * em
            for rule in rules
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


def _from_outline(
    texts: list[_Text], content: Content, found: dict[int, tuple[int, str]], rules: _Headings
) -> dict[int, tuple[int, str]]:
    """Headings the outline adds to those the font rules `found`, by block index, with their
    level and printed number (rules 2 to 4 in the module docstring)."""
    lettered = rules.lettered
    pages = {item.id: page.number for page in content.pages for item in page.lines}
    candidates: dict[tuple[int, str], list[tuple[int, str]]] = {}
    for text in texts:
        page = next((pages[p.item] for p in text.block.parts if p.item in pages), None)
        if page is None:
            continue
        label, rest = _printed_number(title(text.block.text), lettered)
        candidates.setdefault((page, _key(rest)), []).append((text.index, label))
    added: dict[int, tuple[int, str]] = {}
    for entry in _entries(content):
        if entry.page is None:
            continue
        keys = {_key(entry.title), _key(_printed_number(entry.title.strip(), lettered)[1])}
        matches = {m for key in keys for m in candidates.get((entry.page, key), [])}
        if len(matches) != 1:
            continue
        ((index, label),) = matches
        if index not in found and index not in added:
            shift = int(rules.shift_from is not None and index > rules.shift_from)
            added[index] = (_depth(label) + shift if label else entry.level, label)
    return added


def _entries(content: Content) -> list[OutlineEntry]:
    """The outline entries that may name a heading, with a title root taken off (rule 3)."""
    entries = list(content.outline)
    tops = [entry for entry in entries if entry.level == 1]
    if len(tops) == 1 and len(entries) > 1:
        entries = [replace(entry, level=entry.level - 1) for entry in entries[1:]]
    document = _key(content.metadata.title)
    return [
        entry
        for entry in entries
        if any(ch.isalpha() for ch in entry.title) and _key(entry.title) != document
    ]


def _printed_number(text: str, lettered: bool) -> tuple[str, str]:
    """The printed number at the front of a heading and the rest; ("", text) if it has none.
    A capital letter counts only where letters number the headings (`lettered`)."""
    found = _NUMBER.match(text)
    if found is None or (found["label"][0].isalpha() and not lettered):
        return "", text
    return found["label"], text[found.end() :]


def _key(text: str) -> str:
    """The text as outline titles and printed headings are compared: NFKC, case folded,
    white space folded."""
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


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
