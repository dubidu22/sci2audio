"""The reference list is not read (TP-06, D-146).

A section whose title is a usual name of a reference list in the job's language
(`REFERENCE_NAMES`; English names count in every language, since a German paper may head its
list "References"), after a printed number if there is one ("7 References", "7 Literatur"),
is left out one block at a time,
its heading included, at any level of the section tree. The "Reference list" switch keeps
it. Footnotes inside the section are kept, since their marks stand in the body text (a note
at the foot of the page where the list starts), and furniture is the furniture step's.

A reference list printed without a heading (PRL and revtex style, #92, D-646) is found only
in a document with no reference-list section: the last run of text blocks that starts with
the entry "[1] …", counts its entries up ("[N]" at a line start, a step of 1 to 3, since
layout may merge or split an entry's lines), holds at least five entries, at least half of
them with a year and an author ("N. Nagaosa", "Fahl, S.", #377), and ends at
the document's end or at a heading (an appendix after it is read). A run right after a
heading that names no reference list ("Notes", "Anmerkungen") has a heading, so it is read.
A short block with a year between two entries ("(2020).") is an entry's last
line; after the last entry it is not.
Furniture, footnotes and placeholders between the entries are skipped; a note printed as an
entry of the list (revtex "footinbib") goes with the list.
"""

from __future__ import annotations

import re
from collections.abc import Iterator

from sci2audio.core import Block, BlockKind, Document, Edit, EditKind, Section, Span
from sci2audio.textprep.steps import Category, Stage, StepContext, TextStep

# the usual names of a reference list in English: D-83's two and the rest of D-132's English
# list, so the step and the app's chapter choice (#70) agree (layout keeps its own list in its
# settings; textprep may not import layout)
REFERENCE_TITLES = (
    "References",
    "Bibliography",
    "Reference list",
    "Works cited",
    "Literature cited",
)
# German (#221, D-481): the app's four German chapter names, the two spellings of
# "Bibliographie", the counterparts of "Works cited" and "Literature cited", and the
# combined titles of German theses (#222)
GERMAN_REFERENCE_TITLES = (
    "Literatur",
    "Literaturverzeichnis",
    "Quellen",
    "Quellenverzeichnis",
    "Bibliographie",
    "Bibliografie",
    "Literaturliste",
    "Verwendete Literatur",
    "Zitierte Literatur",
    "Quellen- und Literaturverzeichnis",
    "Literatur- und Quellenverzeichnis",
)
# by primary language tag; the app's chapter choice takes its names from here
REFERENCE_NAMES: dict[str, tuple[str, ...]] = {
    "en": REFERENCE_TITLES,
    "de": GERMAN_REFERENCE_TITLES,
}

# Matched as the app matches a chapter title (`app.chapters.is_reference_title`, D-132), so
# the step and the chapter choice agree; a test keeps the two equal: white space read as one
# space, an optional printed number ("7", "7.", "8.1", "A", "A.1", "IV.") taken off, then the
# name without case and without a closing "." or ":" ("REFERENCES", "References:").
_NUMBER = re.compile(r"\A(?:\d{1,2}|[A-Z]|[IVX]{1,5})(?:\.\d{1,2})*\.?\s+")
_NAMES = {
    language: frozenset(name.casefold() for name in (*REFERENCE_TITLES, *names))
    for language, names in REFERENCE_NAMES.items()
}


def is_reference_title(title: str, language: str = "en") -> bool:
    """True if a section title names a reference list ("7 References", "Bibliography:") in
    the language ("de-AT" uses "de"; English names count in every language)."""
    names = _NAMES.get(language.split("-", 1)[0].lower(), _NAMES["en"])
    name = _NUMBER.sub("", " ".join(title.split()), count=1)
    return name.casefold().rstrip(".:") in names


_KEPT = frozenset({BlockKind.FOOTNOTE, BlockKind.FURNITURE})

# a list printed without a heading (#92, D-646)
_ENTRY = re.compile(r"^\[([1-9]\d{0,3})\][ \t]", re.MULTILINE)  # an entry's number, line start
_ENTRY_YEAR = re.compile(r"(?<!\d)(?:1[5-9]\d\d|20\d\d)(?!\d)")
# an author as reference lists print one: initials before a surname ("N. Nagaosa", "Y.-G.
# Choi") or a surname before its initial ("Fahl, S.")
_ENTRY_AUTHOR = re.compile(
    r"(?<![^\W\d_])[A-Z]\.(?:\s?-?[A-Z]\.)*\s?[A-Z][^\W\d_]|[A-Z][^\W\d_]+,\s[A-Z]\."
)
_MIN_ENTRIES = 5
_MAX_STEP = 3  # how far one entry's number may jump past the one before it
_LAST_LINE = 120  # characters; a longer block without an entry number ends the list
# passed over between entries: furniture, footnotes, placeholders and their captions
_PASSED = _KEPT | {
    BlockKind.TABLE,
    BlockKind.FORMULA,
    BlockKind.FIGURE,
    BlockKind.CODE,
    BlockKind.CAPTION,
}
_UNHEADED_REASON = "the reference list is not read (printed without a heading)"


class ReferenceListStep(TextStep):
    """Remove every block of a reference-list section, one edit per block."""

    id = "reference-list"
    languages = ("en", "de")
    category = Category.REFERENCES
    stage = Stage.BLOCK

    def find(self, document: Document, context: StepContext) -> list[Edit]:
        edits = []
        indexes: set[int] = set()
        for section in _sections(document.sections):
            if is_reference_title(section.title, context.language):
                indexes.update(range(section.start, section.end))
        reason = "the reference list is not read"
        if not indexes:
            indexes.update(unheaded_list(document.blocks, context.language))
            reason = _UNHEADED_REASON
        for index in sorted(indexes):
            block = document.blocks[index]
            if block.text and block.kind not in _KEPT:
                edits.append(
                    Edit(Span(index, 0, len(block.text)), EditKind.REMOVE, reason, self.id)
                )
        return edits


def unheaded_list(blocks: tuple[Block, ...], language: str = "en") -> list[int]:
    """The indexes of the text blocks of a reference list printed without a heading, or []
    (see the module's text; #92, D-646)."""
    found: list[int] = []
    run = _Run()
    headed = False  # a heading that names no reference list stands right before
    for index, block in enumerate(blocks):
        if block.kind in _PASSED:
            continue
        if block.kind is BlockKind.HEADING:
            found = run.list() or found
            run = _Run()
            headed = not is_reference_title(block.text, language)
            continue
        numbers = [int(match.group(1)) for match in _ENTRY.finditer(block.text)]
        if block.text.startswith("[") and numbers and _ENTRY.match(block.text):
            if not run.takes(numbers):
                run = _Run()
                if not run.takes(numbers):
                    headed = False
                    continue
            if not run.blocks:
                run.headed = headed
            run.add(index, block.text)
        elif run.blocks and len(block.text.strip()) < _LAST_LINE and _ENTRY_YEAR.search(block.text):
            run.last_lines.append(index)
        else:
            run = _Run()
        headed = False
    return run.list() or found


class _Run:
    """The entries of a list read so far, and the short blocks after the last entry."""

    def __init__(self) -> None:
        self.blocks: list[int] = []
        self.last_lines: list[int] = []
        self.last = 0
        self.entries = 0
        self.cited = 0  # entries with a year and an author
        self.headed = False

    def takes(self, numbers: list[int]) -> bool:
        """True if these entry numbers count on from the run's (the first entry is 1)."""
        last = self.last
        for number in numbers:
            if not (number == 1 if last == 0 else 0 < number - last <= _MAX_STEP):
                return False
            last = number
        return True

    def add(self, index: int, text: str) -> None:
        self.blocks += [*self.last_lines, index]
        self.last_lines = []
        starts = [match.start() for match in _ENTRY.finditer(text)]
        for start, end in zip(starts, [*starts[1:], len(text)], strict=True):
            self.entries += 1
            self.cited += bool(
                _ENTRY_YEAR.search(text, start, end) and _ENTRY_AUTHOR.search(text, start, end)
            )
        self.last = int(_ENTRY.findall(text)[-1])

    def list(self) -> list[int]:
        """The run's blocks up to its last entry, if it is a reference list."""
        if self.headed or self.entries < _MIN_ENTRIES or 2 * self.cited < self.entries:
            return []
        return list(self.blocks)


def _sections(sections: tuple[Section, ...]) -> Iterator[Section]:
    for section in sections:
        yield section
        yield from _sections(section.children)
