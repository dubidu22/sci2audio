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

Some styles (IEEE) number their sections with Roman numerals and their subsections with
letters: "II. Method", then "A. Setup" (#49). A Roman number is a heading number only with
a dot after it, and only when the document's Roman numbers, in reading order, count up from
"I" without a gap or a repeat, at least `heading_repeats` of them, and Arabic numbers do not
number the document (fewer than `heading_repeats` of them, and no more than the Roman ones:
else "I." and "II." are a bold list inside an Arabic section). Then each is a level-1
number, kept as printed ("IV"); a letter written with a dot is one level deeper ("A" at
level 2, "A.1" at level 3), and an Arabic number is no heading number. A single letter that
is not the next Roman number in the count ("I" or "V" after "H" or "U") stays a letter. A
heading the outline adds (rule 4 below) is read the same way: a Roman number only when it
is the next after the Roman sections before it, a letter only with its dot, an Arabic
number not at all. In a document numbered in Arabic, a letter still numbers an appendix at
level 1. Under a lettered subsection, a number with a closing parenthesis ("1) Hardware") is
one level deeper than the letter, kept as printed ("1)", #798). The letter must be a heading
the font rules keep, in the same Roman section: before the first such letter of a Roman
section, and in a document that is not Roman, "1)" is no heading number, so a "1)" list item
stays a list item unless it is set like these headings. The outline reads it the same way.

A heading stands over text no larger than the body text, or over another heading: the
title, the authors and their affiliations at the top of a paper are not headings.

A heading may also be marked by a rule drawn under it rather than by its style (#48, D-385
to D-391). In a document that numbers its headings, after the first of them, a block that
may be a heading, has no number and holds a rule under its last line is a level-1 heading,
also after a common title over the appendices, whose shift goes on for the numbered headings
after it ("ACL 2023 Responsible NLP Checklist", set like the subsections, with a rule under
it across the page). The rule is one of the block's own graphic parts, where the graphics
step put it (#58, D-90): at most `line_width` em thick, its top between the middle of the
last row and `heading_rule_gap` em below it, across the whole row and at least
`heading_rule_reach` em longer than its words at one end, so an underline of the words
themselves (a link) does not count. The last row is the block's lines that stand at its
last line's height: a table's header row split into cells is measured as one row.

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
5. An entry that names the publisher's front matter ("Cover", "Impressum",
   "Inhaltsverzeichnis": `front_matter_names`) on a page without a heading starts a
   level-1 section marked as the publisher's (#456, D-755): a publisher section from the
   outline starts at its page's first block. It ends at the next heading or at the first
   block of the next page any outline entry points to, so the article's own title page
   after it stays out of it; with neither after it, it ends with its own page. Entries
   are taken in page order; the first such section, with no heading before it, starts at
   block 0, so a repository's cover sheet before it joins it. Front matter never holds the
   whole document, and is found only through the outline, never by the pages' looks.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, replace

from sci2audio.core import Block, BlockKind, Box, Content, OutlineEntry, Section, TextLine
from sci2audio.layout.geometry import union
from sci2audio.layout.settings import LayoutSettings

# a printed heading number: "2", "2.1", "A", "A.1", with an optional dot, before the title
_NUMBER = re.compile(r"(?P<label>(?:\d{1,2}|[A-Z])(?:\.\d{1,2})*)\.?\s+(?=\w)")


_ROMAN = r"(?=[IVXL])(?:XC|XL|L?X{0,3})(?:IX|IV|V?I{0,3})"

# a heading that is only a Roman numeral: "II", "IV.", "XII"
_NUMERAL = re.compile(_ROMAN + r"\.?")

# a printed Roman section number with its dot, before the title: "IV. Results" (#49)
_ROMAN_NUMBER = re.compile(rf"(?P<label>{_ROMAN})\.\s+(?=\w)")

# a letter numbering a subsection under a Roman section, with its dot: "A. Setup", "A.1."
_LETTER_NUMBER = re.compile(r"(?P<label>[A-Z](?:\.\d{1,2})*)\.\s+(?=\w)")

# a number under a lettered subsection, with its closing parenthesis: "1) Hardware" (#798)
_PAREN_NUMBER = re.compile(r"(?P<label>\d{1,2}\))\s+(?=\w)")

_ROMAN_VALUES = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}


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
        if (block.kind is BlockKind.PARAGRAPH or _numbered_item(block)) and block.text.strip()
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
    front = front_matter(blocks, content, sorted(levels), settings)
    heads += [(start, 1, name) for start, (_, name) in front.items()]
    tree = section_tree(sorted(heads), len(blocks))
    return out, _publisher(tree, {start: end for start, (end, _) in front.items()})


# a list item's label as `lists` gives it for a numbered marker: "1." or "1)"
_NUMBERED_ITEM = re.compile(r"\d{1,2}[.)]")


def _numbered_item(block: Block) -> bool:
    """True for a one-line list item numbered "1." or "1)": lists are found before headings,
    so a numbered heading set like a list marker ("1. Introduction" over "2. Related work")
    is a list item by now. The heading rules judge it as they judge a paragraph; one they
    don't take stays a list item (#54)."""
    return (
        block.kind is BlockKind.LIST_ITEM
        and _NUMBERED_ITEM.fullmatch(block.label or "") is not None
        and "\n" not in block.text.strip()
    )


def front_matter(
    blocks: list[Block], content: Content, heads: list[int], settings: LayoutSettings
) -> dict[int, tuple[int, str]]:
    """The publisher's front matter the outline names (#456, module docstring): by start
    block, its end and the entry's title. An entry whose title is one of
    `front_matter_names` starts at the first block of its page, when no heading stands on
    that page; it ends at the next heading or at the first block of the next page an
    outline entry points to, whichever comes first, or with neither at the end of its own
    page. Entries are taken in page order; the first of them, with no heading before it,
    starts at block 0: a repository's cover sheet before it joins it. When they would hold
    the whole document together, there is none. Nothing is found by the pages' looks, so a file
    without an outline has no front matter."""
    names = {title_key(name) for name in settings.front_matter_names}
    pages = {item.id: page.number for page in content.pages for item in page.lines}
    page_of = [next((pages[p.item] for p in b.parts if p.item in pages), None) for b in blocks]
    first: dict[int, int] = {}  # page number -> its first block
    for index, number in enumerate(page_of):
        if number is not None:
            first.setdefault(number, index)
    headed = {page_of[k] for k in heads}
    starts = [  # each outline entry that points at a page with blocks: its first block
        (first[entry.page], entry.title)
        for entry in content.outline
        if entry.page is not None and entry.page in first
    ]
    found: dict[int, tuple[int, str]] = {}
    for start, text in sorted(starts, key=lambda entry: entry[0]):  # by page (stable)
        if title_key(text).rstrip(".: ") not in names or page_of[start] in headed:
            continue
        later = [other for other, _ in starts if other > start]  # any entry, by page
        bounds = [*(h for h in heads if h > start), *later]
        # nothing bounds it: its own page only, never the rest of the document
        after = (k for k in range(start, len(blocks)) if page_of[k] not in (None, page_of[start]))
        end = min(bounds) if bounds else next(after, len(blocks))
        if not found and not any(h < start for h in heads):
            start = 0
        if not any(s <= start < e for s, (e, _) in found.items()):
            found[start] = (end, text.strip())
    if sum(end - start for start, (end, _) in found.items()) == len(blocks):
        return {}  # front matter never holds the whole document, in one section or many
    return found


def _publisher(tree: tuple[Section, ...], front: dict[int, int]) -> tuple[Section, ...]:
    """The tree with each front-matter section cut to its end and marked as the
    publisher's; the deeper headings it took in follow it at the top level."""
    out: list[Section] = []
    for section in tree:
        if section.start in front:
            out.append(replace(section, end=front[section.start], children=(), publisher=True))
            out += section.children
        else:
            out.append(section)
    return tuple(out)


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
        # each number's depth: one per part, or as in a Roman document (module docstring)
        self.depths = {k: _depth(label) for k, label in numbers.items()}
        # the Roman section numbers by block index, with their values (`_roman`)
        self.sections: dict[int, int] = {}
        # the lettered subsections of a Roman document kept as headings, by block index,
        # with their depths (set by `_numbered`)
        self.letters: dict[int, int] = {}
        arabic = sum(label[0].isdigit() for label in numbers.values())
        roman = self._roman(arabic)
        self.roman = roman is not None
        if roman is not None:
            self.lettered = True
            numbers, self.depths = roman
        self.numbers = numbers

    def _roman(self, arabic: int) -> tuple[dict[int, str], dict[int, int]] | None:
        """The numbers and depths of a document that numbers its sections in Roman, or None
        if it does not (module docstring); `arabic` is how many Arabic numbers it has."""
        numbers: dict[int, str] = {}
        depths: dict[int, int] = {}
        sections: dict[int, int] = {}
        # the depth of the last letter: a "1)" after it is a candidate number one deeper,
        # which `_numbered` keeps only under a letter heading of its own Roman section
        under: int | None = None
        for k in self.short:
            text = self.texts[k].block.text.strip()
            found = _ROMAN_NUMBER.match(text)
            if found is not None and _roman_value(found["label"]) == len(sections) + 1:
                numbers[k], depths[k] = found["label"], 1
                sections[self.texts[k].index] = len(sections) + 1
            elif found is not None and len(found["label"]) > 1:
                return None  # a Roman number out of sequence
            elif sections and (letter := _LETTER_NUMBER.match(text)):
                numbers[k], depths[k] = letter["label"], _depth(letter["label"]) + 1
                under = depths[k]
            elif under is not None and (item := _PAREN_NUMBER.match(text)):
                numbers[k], depths[k] = item["label"], under + 1
        count = len(sections)
        if count < self.settings.heading_repeats:
            return None
        if arabic >= self.settings.heading_repeats or arabic > count:
            return None  # Arabic numbers number the document; "I." and "II." are a list
        self.sections = sections
        return numbers, depths

    def depth(self, index: int, label: str) -> int | None:
        """A printed number's depth at block `index`, for a heading the outline adds: in a
        Roman document a Roman number is depth 1 when it is the next one after the Roman
        sections before the block, as the font rules count them; a number with a closing
        parenthesis is one deeper than the last letter after the last of those sections,
        and no number (None) without such a letter; any other number there is a letter, one
        level deeper than its parts."""
        if not self.roman:
            return _depth(label)
        if label.endswith(")"):
            section = max((at for at in self.sections if at < index), default=-1)
            letter = max((at for at in self.letters if section < at < index), default=None)
            return None if letter is None else self.letters[letter] + 1
        before = max((value for at, value in self.sections.items() if at < index), default=0)
        if _NUMERAL.fullmatch(label) and _roman_value(label) == before + 1:
            return 1
        return _depth(label) + 1

    def levels(self) -> dict[int, tuple[int, str]]:
        """Each heading's block index, with its level and printed number ("" if none)."""
        numbered = len(self.numbers) >= self.settings.heading_repeats
        found = self._numbered() if numbered else self._unnumbered()
        found |= self._numeral_one(found)
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
        for k in self.numbers:
            votes.setdefault(self.depths[k], Counter())[self.texts[k].style] += 1
        styles = {depth: vote.most_common(1)[0][0] for depth, vote in votes.items()}
        top = styles[min(styles)]
        found: dict[int, tuple[int, str]] = {}
        shift = 0  # one more level for each heading under a common title (appendices)
        started = False  # the first numbered heading has come
        under: int | None = None  # the depth of the last kept letter in this Roman section
        for k in self.short:
            style, label = self.texts[k].style, self.numbers.get(k)
            index = self.texts[k].index
            if index in self.sections:
                under = None
            if label is not None and label.endswith(")") and under is None:
                continue  # "1)" with no letter heading over it (#798)
            if label is not None and styles[self.depths[k]] == style:
                depth = under + 1 if label.endswith(")") and under is not None else self.depths[k]
                found[k] = (depth + shift, label)
                started = True
                if self.roman and label[0].isalpha() and index not in self.sections:
                    under = self.letters[index] = depth
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

    def _numeral_one(self, found: dict[int, tuple[int, str]]) -> dict[int, tuple[int, str]]:
        """A block that is only the Roman numeral "I", set like a heading that is only a Roman
        numeral ("II", "III"), at that heading's level (#459). It has one letter, too few for
        `_short`, which keeps a bold table number or a list label out. Found headings are
        all bold or larger than the body, so the style match is all the check it needs."""
        levels = {
            self.texts[k].style: level
            for k, (level, _) in found.items()
            if _NUMERAL.fullmatch(self.texts[k].block.text.strip())
        }
        return {
            k: (levels[text.style], "")
            for k, text in enumerate(self.texts)
            if k not in found
            and text.style in levels
            and text.block.text.strip().rstrip(".") == "I"
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
        """True if the block holds a rule drawn under its last row (module docstring)."""
        block, em, settings = self.texts[k].block, self.body, self.settings
        boxes = [self.lines[part.item].box for part in block.parts if part.item in self.lines]
        last = boxes[-1] if boxes else None
        if last is None:
            return False
        # the last row: the block's lines that stand at the last one's height (a table's
        # header split into cells is one row; #180)
        line = union([box for box in boxes if box and last.y0 <= (box.y0 + box.y1) / 2 <= last.y1])
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
    lettered, roman = rules.lettered, rules.roman
    pages = {item.id: page.number for page in content.pages for item in page.lines}
    candidates: dict[tuple[int, str], list[tuple[int, str]]] = {}
    for text in texts:
        page = next((pages[p.item] for p in text.block.parts if p.item in pages), None)
        if page is None:
            continue
        label, rest = printed_number(title(text.block.text), lettered, roman)
        candidates.setdefault((page, title_key(rest)), []).append((text.index, label))
    added: dict[int, tuple[int, str]] = {}
    for entry in outline_entries(content):
        if entry.page is None:
            continue
        number = printed_number(entry.title.strip(), lettered, roman)[1]
        keys = {title_key(entry.title), title_key(number)}
        matches = {m for key in keys for m in candidates.get((entry.page, key), [])}
        if len(matches) != 1:
            continue
        ((index, label),) = matches
        if index not in found and index not in added:
            shift = int(rules.shift_from is not None and index > rules.shift_from)
            depth = rules.depth(index, label) if label else None
            if depth is None:  # no number, or a "1)" with no letter over it: no number
                added[index] = (entry.level, "")
            else:
                added[index] = (depth + shift, label)
    return added


def outline_entries(content: Content) -> list[OutlineEntry]:
    """The outline entries that may name a heading, with a title root taken off (rule 3)."""
    entries = list(content.outline)
    tops = [entry for entry in entries if entry.level == 1]
    if len(tops) == 1 and len(entries) > 1:
        entries = [replace(entry, level=entry.level - 1) for entry in entries[1:]]
    document = title_key(content.metadata.title)
    return [
        entry
        for entry in entries
        if any(ch.isalpha() for ch in entry.title) and title_key(entry.title) != document
    ]


def printed_number(text: str, lettered: bool, roman: bool = False) -> tuple[str, str]:
    """The printed number at the front of a heading and the rest; ("", text) if it has none.
    A capital letter counts only where letters number the headings (`lettered`); a Roman
    number with its dot ("IV.") only where Roman numbers do (`roman`), and there only it,
    a letter with its dot or a number with a closing parenthesis ("1)") is a number, as for
    the font rules (module docstring; `_Headings.depth` says where "1)" counts)."""
    if roman:
        found = _ROMAN_NUMBER.match(text) or _LETTER_NUMBER.match(text) or _PAREN_NUMBER.match(text)
        return ("", text) if found is None else (found["label"], text[found.end() :])
    found = _NUMBER.match(text)
    if found is None or (found["label"][0].isalpha() and not lettered):
        return "", text
    return found["label"], text[found.end() :]


def title_key(text: str) -> str:
    """The text as outline titles and printed headings are compared: NFKC, case folded,
    white space folded."""
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def _depth(label: str) -> int:
    """A printed number's depth: one per part (`_Headings.depth` reads a Roman document)."""
    return label.count(".") + 1


def _roman_value(numeral: str) -> int:
    """The value of a Roman numeral as `_ROMAN` reads it: "XIV" is 14."""
    values = [_ROMAN_VALUES[ch] for ch in numeral]
    after = [*values[1:], 0]
    return sum(-v if v < next_one else v for v, next_one in zip(values, after, strict=True))


def section_tree(heads: list[tuple[int, int, str]], end: int) -> tuple[Section, ...]:
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
        out.append(Section(name, level, index, stop, section_tree(heads[k + 1 : j], stop)))
        k = j
    return tuple(out)
