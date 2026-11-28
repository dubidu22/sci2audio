"""A slash between words, read as "and" (#653, D-816).

"Menschen/Gruppen" reaches the voice as printed, which reads a pause or "Schrägstrich". This
step reads it "Menschen und Gruppen", "people/groups" "people and groups", with spaces around
the slash too; three words or more are a list ("Schulen, Vereine und Einrichtungen"). A short
list of opposites reads "oder" / "or" ("ja/nein", "yes/no"); a hyphen fragment keeps its
hyphen ("Sozial-/Kulturpädagogik" is "Sozial- und Kulturpädagogik"). English and German only:
another language keeps the slash.

Every part is a word as a second run reads it: two letters or more, one of them lower case and
one a vowel, glued to no other sign, no join word itself ("und/oder", "and/or",
"bzw./oder"), and no rate: no word of one after the first part ("Euro/Monat", "pro
Kopf/Jahr", "words/min"), and no pair after a number ("3 dollars/user", "5 Euro/Nutzer": a
quantity per something). An abbreviation or a unit the steps before this one read counts by
its words ("z. B./u. a." is "zum Beispiel/unter anderem" then, so "Beispiel" and "unter";
"€/Monat" is "Euro/Monat"). German gender forms stay as printed, in any case and doubled
("Lehrer/innen", "Lehrer/Innen", "Kolleg/inn/en"; "ein/e" and "Lehrer/-innen" have no word
after the slash). So are numbers, dates, units, links, paths and acronyms ("1998/2019",
"km/h", "docs/kb", "TCP/IP"); the steps that read them run first and win where they edit.
Names glued to a slash before a bracket the citations step takes for a narrative citation's
year stay as printed too ("Heydorn/Koneffke (1964)", "Smith/Jones (in press)", #455).
"""

from __future__ import annotations

import bisect
import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass

from sci2audio.core import Document, Edit, EditKind, Span
from sci2audio.textprep.citations import WORDS as CITATION_WORDS
from sci2audio.textprep.footnotes import unread_marks
from sci2audio.textprep.notation import edits_through_unread
from sci2audio.textprep.placeholders import read_as_prose
from sci2audio.textprep.readings import Reading, readings_of
from sci2audio.textprep.steps import Category, Stage, StepContext, TextStep


@dataclass(frozen=True)
class SlashWords:
    """The words of one language this step says and looks for, lower case."""

    joined: str  # what the last slash of a list reads as: "and"
    either: str  # what the slash of a pair of opposites reads as: "or"
    opposites: frozenset[frozenset[str]]  # pairs read with `either`, in either order
    joins: frozenset[str]  # a join word is no part: "and/or" stays
    signs: frozenset[str]  # nor a sign's name: "plus/minus" is "±", which the numbers step reads
    rates: frozenset[str]  # a rate's word after a slash is no part: "Euro/Monat" stays
    suffixes: frozenset[str] = frozenset()  # gender forms after a capital word: "Lehrer/innen"


WORDS = {
    "en": SlashWords(
        joined="and",
        either="or",
        opposites=frozenset({frozenset({"yes", "no"}), frozenset({"true", "false"})}),
        joins=frozenset({"and", "or", "nor", "either", "neither", "respectively"}),
        signs=frozenset({"plus", "minus"}),
        rates=frozenset({
            "second", "minute", "hour", "day", "week", "month", "quarter", "year", "semester",
            "sec", "secs", "min", "mins", "hr", "hrs", "wk", "wks", "mo", "yr", "yrs",
            "head", "capita", "person", "piece",
        }),
    ),
    "de": SlashWords(
        joined="und",
        either="oder",
        opposites=frozenset({
            frozenset({"ja", "nein"}), frozenset({"richtig", "falsch"}),
            frozenset({"wahr", "falsch"}),
        }),
        joins=frozenset({
            "und", "oder", "bzw", "beziehungsweise", "sowie", "entweder", "weder", "noch",
        }),
        signs=frozenset({"plus", "minus"}),
        rates=frozenset({
            "sekunde", "minute", "stunde", "tag", "woche", "monat", "quartal", "jahr",
            "semester", "sek", "min", "kopf", "person", "einwohner", "stück",
        }),
        suffixes=frozenset({"innen", "in", "inn"}),  # "inn" of a double form: "Kolleg/inn/en"
    ),
}  # fmt: skip

# a slash, maybe with one space on either side; a line break stays a line break
_SLASH = r"[ \u00a0]?/[ \u00a0]?"
_PART = r"[^\W\d_]{2,}"
# a list of parts joined by slashes, glued to no other sign at either end: not inside a path,
# an address or a code ("/usr/bin", "a.org/b", "C:\Daten/x"); a part before a slash may end in
# a hyphen ("Sozial-/")
_LIST = re.compile(rf"(?<![\w@\\/.:\-])(?:{_PART}-?{_SLASH})+{_PART}(?![\w@\\]|{_SLASH}|[.:]\w)")
_SEPARATOR = re.compile(_SLASH)
# names before a bracket of years are the citations step's ("Heydorn/Koneffke (1964)", #455):
# glued to the slash they are no name to it and the bracket stays; read "und", a second run
# would take "Heydorn und Koneffke (1964)" for a citation and drop the bracket. A stand-in for
# the year ("in press") and a possessive ("Jones's (2019)") count as they do for that step.
_CITED_AFTER = {
    language: re.compile(
        rf"(?:[\u2019']s?)?\s*\(\s*(?:(?:1[5-9]|20)\d\d|{CITATION_WORDS[language].undated})",
        re.IGNORECASE,
    )
    for language in WORDS
}
# a pair right after a number is a quantity per something: "3 dollars/user"
_NUMBER_BEFORE = re.compile(r"\d[ \u00a0]+\Z")
_VOWELS = frozenset("aeiouäöüàáâãåæèéêëìíîïòóôõøùúûœ")  # not "y": "jzy/Ex" is maths


class SlashStep(TextStep):
    """Read a slash between words as "and"."""

    id = "slashes"
    languages = ("en", "de")
    category = Category.CHARACTERS
    stage = Stage.INLINE

    def find(self, document: Document, context: StepContext) -> list[Edit]:
        language = context.language.split("-", 1)[0].lower()
        words = WORDS.get(language)
        if words is None:
            return []
        marks = unread_marks(document, context)  # read as a second run reads, without them
        edits = []
        for index, block in enumerate(document.blocks):
            if not read_as_prose(block, context) or "/" not in block.text:
                continue
            edits += edits_through_unread(
                index,
                block.text,
                lambda read, index=index: _found(index, read, words, language),
                self.id,
                marks.get(index, ()),
            )
        return edits


def _found(index: int, text: str, words: SlashWords, language: str) -> Iterator[Edit]:
    """The step's edits in one block's text, read past the readings before the slashes."""
    view = _View(text, language)
    for match in _LIST.finditer(view.text):
        shown = re.split(_SLASH, match.group())  # "Sozial-", "Kulturpädagogik"
        parts = [part.removesuffix("-") for part in shown]
        if not _a_list(parts, words) or _a_rate(view.text, match.start(), parts):
            continue
        # spaced ("Smith / Jones (2019)"), the name before the bracket stands alone, so the
        # bracket is a citation on both runs and the slash may be read
        glued = not _SEPARATOR.findall(match.group())[-1].endswith((" ", "\u00a0"))
        if glued and _CITED_AFTER[language].match(view.text, match.end()):
            continue
        said = _said(parts, words)
        printed = view.printed(match.start(), match.end())
        spoken = _spoken(shown, said)
        reason = f'slash between words "{printed}" read as "{spoken}"'
        for separator, replacement in zip(_SEPARATOR.finditer(match.group()), said, strict=True):
            start, end = (
                view.at(match.start() + separator.start()),
                view.at(match.start() + separator.end()),
            )
            if start is None or end is None:
                continue
            yield Edit(Span(index, start, end), EditKind.REPLACE, reason, SlashStep.id, replacement)


def _a_list(parts: Sequence[str], words: SlashWords) -> bool:
    """True if every part is a word a slash joins to the next as "and"."""
    for number, part in enumerate(parts):
        low = part.lower()
        if part == part.upper() or not _VOWELS & set(low) or low in words.joins | words.signs:
            return False  # "TCP/IP", "docs/kb", "und/oder", "plus/minus"
        if number and low in words.rates:
            return False  # "Euro/Monat": a rate, "Euro pro Monat"
        if number and low in words.suffixes and parts[number - 1][:1].isupper():
            return False  # "Lehrer/innen", "Lehrer/Innen": a gender form, out of scope (D-816)
    return True


def _a_rate(text: str, start: int, parts: Sequence[str]) -> bool:
    """True if a pair stands right after a number: "3 dollars/user", "5 Euro/Nutzer"."""
    return len(parts) == 2 and bool(_NUMBER_BEFORE.search(text, max(0, start - 4), start))


def _said(parts: Sequence[str], words: SlashWords) -> list[str]:
    """What each slash reads as: ", " between the parts of a list, then "and"."""
    if len(parts) == 2 and frozenset(part.lower() for part in parts) in words.opposites:
        return [f" {words.either} "]
    return [", "] * (len(parts) - 2) + [f" {words.joined} "]


def _spoken(parts: Sequence[str], said: Sequence[str]) -> str:
    return "".join(part + gap for part, gap in zip(parts, [*said, ""], strict=True))


class _View:
    """The block's text with what the units and abbreviations steps read there put in, as a
    second run sees it ("z. B./u. a." as "zum Beispiel/unter anderem"), and the way back to
    the printed text."""

    def __init__(self, text: str, language: str) -> None:
        pieces: list[str] = []
        # each piece: where it starts in the view, its length there, its printed span, and
        # whether it is printed text (as long in both) or a reading's words
        self._pieces: list[tuple[int, int, int, int, bool]] = []
        printed = view = 0
        for reading in [
            *_readings(text, language),
            Reading(len(text), len(text), "", Category.CHARACTERS),
        ]:
            kept = text[printed : reading.start]
            self._pieces.append((view, len(kept), printed, reading.start, True))
            view += len(kept)
            if reading.end > reading.start:
                self._pieces.append((view, len(reading.words), reading.start, reading.end, False))
                view += len(reading.words)
            pieces += [kept, reading.words]
            printed = reading.end
        self.text = "".join(pieces)
        self._printed = text

    def at(self, position: int) -> int | None:
        """The printed position of the view's `position`, or None inside a reading's words."""
        for view, length, start, _, kept in self._pieces:
            if kept and view <= position <= view + length:
                return start + position - view
        return None

    def printed(self, start: int, end: int) -> str:
        """The printed text the view's `start` to `end` comes from, whole readings included."""
        low = high = None
        for view, length, first, last, kept in self._pieces:
            if low is None and view <= start < view + length:
                low = first + start - view if kept else first
            if view < end <= view + length:
                high = first + end - view if kept else last
        return self._printed[low:high]


def _readings(text: str, language: str) -> list[Reading]:
    """The readings of the units and abbreviations steps, apart, the units step's where they
    overlap, as it runs first."""
    units = list(readings_of("units", text, language))
    starts = [reading.start for reading in units]
    taken = list(units)
    for reading in readings_of("abbreviations", text, language):
        at = bisect.bisect_right(starts, reading.start)
        if (at and units[at - 1].end > reading.start) or (
            at < len(units) and units[at].start < reading.end
        ):
            continue
        taken.append(reading)
    return sorted(taken, key=lambda reading: reading.start)
