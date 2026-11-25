"""Units after a number, and the symbols around numbers, read as words (TP-10, K8).

D-236 to D-242. The voice spells nearly every unit symbol ("mg/kg" as "M G slash K G", "m²"
as "M two") and reads "~" as "tilde". This step proposes one `replace` edit per unit
expression, magnitude letter or symbol, with the words of `data/<language>/units.toml`:

- **Units** only right after a number (digits, maybe a decimal part, a range "1–2" or an
  exponent "10⁸"): "3.5 mg/kg" reads "3.5 milligrams per kilogram". A unit of one ASCII
  letter needs a space after the number ("5 m", never "1990s" or "2D"); longer units may be
  glued ("9kg" reads "9 kilograms"). No unit is read after a label word ("Figure 2 A").
- **Plural agreement:** singular after exactly "1", plural otherwise; singular when the
  number and unit are joined by a hyphen or follow "a"/"an" ("a 5-km race" reads "a
  5-kilometre race"); every unit after "per" is singular.
- **Compounds:** "/" and negative exponents read "per" ("m s⁻¹" reads "metres per second",
  "J/(kg·K)" "joules per kilogram per kelvin"); a power 2 or 3 reads "square"/"cubic" before
  a length and "squared"/"cubed" after anything else; units joined by "·" or a space are one
  compound when each is in the table ("N m" reads "newton metres"), except that a single
  capital letter after a space is not joined unless it has an exponent ("5 m A" stays apart).
- **Degrees:** "°" after a number reads "degree(s)", "°C" "degree(s) Celsius", a spaced "K"
  "kelvin".
- **Magnitudes:** a glued "K"/"k", "M", "B"/"bn" reads "thousand", "million", "billion"
  ("441K apps"); so does plain "40K", which nothing tells from "a 40K run". After a mass
  number set small and raised ("⁴⁰K" as a `sup` run, `footnotes.raised_numbers`) the letter is
  an element symbol: the raised digits are written as superscript digits, which is how they
  are printed and which no step reads as a number, so the letter stays as printed on both
  runs (#449). The voice reads "⁴⁰K" as it reads "40K". After a power printed in
  superscripts the letter is no magnitude either (#576): a one-letter unit glued to it reads
  as with a space ("10⁴K" as "10⁴ K", "kelvin"; German too, #815), and "M" or "B" is set apart
  ("10⁶M" reads "10⁶ M"), so a second run does not read "6M" as "6 million".
- **Raised exponents:** an exponent whose raise only its run shows ("10" and a raised "4",
  `footnotes.raised_exponents`) is read as if printed in superscripts (#576, #589).
- **Symbols:** "≈" reads "approximately" and "×" "times" (D-242: explicit, though espeak-ng
  says the same); "~" and "∼" read "about" right before a number; a letter "x" reads "times"
  between two numbers or glued after one ("10x speedup"); the micro sign "µ" that is not a
  unit prefix becomes the Greek "μ", which the voice reads "mu". "%" is left to the voice.

Edits cover the unit or symbol only, never the number, so they never overlap the number
steps (#67); the one exception is a raised mass number of one to three digits, which no
number rule reads (#449). Furniture and placeholder blocks are claimed whole by other steps
and skipped.
"""
# ruff: noqa: RUF002 (the docstrings name the symbols this step reads)

from __future__ import annotations

import re
import unicodedata
from collections.abc import Collection, Iterator
from dataclasses import dataclass
from functools import cache

from sci2audio.core import Document, Edit, EditKind, Span
from sci2audio.textprep.footnotes import (
    as_superscripts,
    raised_exponents,
    raised_numbers,
    unread_marks,
)
from sci2audio.textprep.notation import (
    DOUBLE_ARROW,
    FILE_NUMBER_DE,
    LEFT_ARROW_TAIL,
    edits_through_unread,
    fold,
    in_ascii_run,
)
from sci2audio.textprep.placeholders import read_as_prose
from sci2audio.textprep.statistics import comparisons_read_alone
from sci2audio.textprep.statistics_de import OPERATORS_DE
from sci2audio.textprep.steps import Category, Stage, StepContext, TextStep
from sci2audio.textprep.wordlists import Unit, UnitList, opens_sentence, units

MICRO_SIGN = "\u00b5"
GREEK_MU = "\u03bc"
_SUPERSCRIPT = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")
_MINUS = "-\u2212"
_DASHES = "-\u2013\u2014\u2012"
_GAP = " \u00a0\u2009\u202f\u2007\n"  # what may stand between a number and its unit
# a number as printed: digits with "," groups or a leading point, a decimal part, an exponent
# not inside a power ("^-1", "^{2}", "^{-1}"), but after the x of "5x86mg" or "5 x86K"
# (the x reads "times" either way, so a second run finds the same number, #160)
_NUMBER_START = (
    r"(?:(?<![\w.,:/^\u2070-\u209f])(?<!\^[-\u2212{])(?<!\^\{[-\u2212])"
    r"|(?<=[\d⁰¹²³⁴⁵⁶⁷⁸⁹][xX])|(?<=[\d⁰¹²³⁴⁵⁶⁷⁸⁹] [xX]))"  # after a power's x too (#253)
)
_EXPONENT = (
    r"(?P<exponent>[\u207a\u207b\u2212]?[\u2070\u00b9\u00b2\u00b3\u2074-\u2079]+"
    r"|\^[-\u2212]?\d+|\^\{[-\u2212]?\d+\})?"
)
_NUMBER = re.compile(
    _NUMBER_START + r"(?:\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?|\.\d+)" + _EXPONENT
)
# German (#113): a decimal comma and a thousands point ("2,5 km", "1.500 m"); a decimal point
# too, as statistics in German texts often print it ("2.5 s")
_NUMBER_DECIMAL_COMMA = re.compile(
    _NUMBER_START + r"(?:\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:[.,]\d+)?|[.,]\d+)" + _EXPONENT
)
_SIGNS = "+-\u2212\u00b1"  # a sign before "1": "-1 °C" is "minus 1", not "minus ein"
_POWERS = {
    "\u00b2": 2,
    "\u00b3": 3,
    "^2": 2,
    "^3": 3,
    "^{2}": 2,
    "^{3}": 3,
    "\u207b\u00b9": -1,
    "\u207b\u00b2": -2,
    "\u207b\u00b3": -3,
    **{f"^{m}{n}": -n for m in _MINUS for n in (1, 2, 3)},
    **{f"^{{{m}{n}}}": -n for m in _MINUS for n in (1, 2, 3)},
}
_POWER = re.compile("|".join(sorted(map(re.escape, _POWERS), key=len, reverse=True)))
_PLAIN_POWER = re.compile(r"[23]")  # "5 m2": a superscript the PDF gave as a plain digit
_PLAIN_NEGATIVE = re.compile(rf"[{_MINUS}]([123])")  # "m s-1", after another unit only
_WORD_BEFORE = re.compile(r"([^\W\d_][\w.]*)\s+\Z")  # the word right before a number
# a label word, then labels joined by ",", "and", "or", "&" or a dash, right before a number
_ONE_LABEL = r"(?:\d+[A-Za-z]{0,2}|[A-Z]{1,2}|[ivxlIVXL]+)"
_LABEL_JOIN = r"(?:\s*(?:,|&|[-\u2013\u2014])\s*|\s+(?:and|or)\s+|,\s*(?:and|or)\s+)"
_LABEL_LIST = re.compile(
    rf"(?<![\w.])([^\W\d_][\w.]*)\s+{_ONE_LABEL}(?:{_LABEL_JOIN}{_ONE_LABEL})*{_LABEL_JOIN}\Z"
)


def _label_list(joins: tuple[str, ...]) -> re.Pattern[str]:
    """`_LABEL_LIST` with the language's own joining words too ("bzw.", "sowie")."""
    if not joins:
        return _LABEL_LIST
    words = "|".join(map(re.escape, sorted(joins, key=len, reverse=True)))
    join = rf"(?:{_LABEL_JOIN}|\s+(?:{words})\s+|,\s*(?:{words})\s+)"
    return re.compile(rf"(?<![\w.])([^\W\d_][\w.]*)\s+{_ONE_LABEL}(?:{join}{_ONE_LABEL})*{join}\Z")


# a hyphen at a line end before a digit counts too: the line-end hyphen step keeps it, so a
# second run sees "~-0" (#304); so does a minus sign at a line end, which the numbers step
# reads "minus" (#336)
_TILDE = re.compile(r"[~\u223c](?=[ \u00a0]{0,2}(?:[+\u2212]\n?|-\n?)?\.?\d)")
# a number, then x; the number may follow another "x" of a chain ("5x86x86")
# and may end in a power the numbers step reads ("10⁶ x1" is "10 hoch 6 x1" after it, #253)
_LETTER_X = re.compile(
    r"(?:(?<![\w.,/-])|(?<=[\d⁰¹²³⁴⁵⁶⁷⁸⁹][xX])|(?<=[\d⁰¹²³⁴⁵⁶⁷⁸⁹] [xX]))"
    r"(?P<number>\d+(?:[.,]\d+)*(?:[⁺⁻]?[⁰¹²³⁴⁵⁶⁷⁸⁹]+)?)(?P<space> ?)(?P<x>[xX])"
)
_UNIT_JOINTS = "/^\u00b7\u22c5\u207b\u00b2\u00b3"  # after these, a letter is a unit: "5K/s"
_GLUED_JOINT = "\u02da\u00c5\u212b"  # a unit glued after another: only the angstrom forms
_HEX = frozenset("0123456789abcdefABCDEF")
_OPERATORS = "=+-\u2212\u00d7\u00b7/^<>\u2264\u2265"  # around "2x", it is a variable
_LOGIC_ARROW = re.compile(DOUBLE_ARROW)
# minus signs and a right arrow: one arrow to the numbers step (`notation.arrows`)
_PIECED_RIGHT_ARROW = re.compile("\u2212+\u2192")
_LOGIC_ARROW_BEFORE = re.compile(f"(?:{DOUBLE_ARROW}) *\\Z")
# the statistics step's English readings of those signs, which count as the signs around "2x"
# ("equals 4x" as "= 4x", #320); a bare "less than" or "greater than" does not, as prose says
# "less than 2x slower" (D-605). Longest first.
_SAID_OPERATORS_EN = ("less than or equal to", "greater than or equal to", "equals")
# ... and a bare "less than" / "greater than" counts after a one-letter variable or a closing
# bracket: "y less than 2x" is the reading of "y < 2x" (#358, D-646). Not after "a", "A", "I"
# (words) nor a letter the list has as a unit ("2 s less than 2x" is "2 seconds less than"
# after the first run), filled in by `_compiled`
_COMPARED_EN = r"(?:(?<![\w.])(?![aAI{units}]\b)[A-Za-z]|\)) +(?:less|greater) than *\Z"
# the characters that join a "<" or ">" to the sign before it ("<<", "=<", "->"): the
# statistics step then leaves it as printed (its `_ARROW`), so it stays a sign on a second run
_JOINED_TO_SIGN = frozenset("<>=-\u2212!:~|\u21d0")
# the numbers step's English reading of a minus sign before a number: it counts as the sign
# before "2x", so a minus sign before "3x" and its reading "minus 3x" agree (#997), as the
# times sign and "times" do (#253); white space between them is joined to one space by then
_MINUS_SAID_EN = re.compile(r"(?<![\w-])minus\s*\Z")
# ... but not after "plus or" or "plus/", in any case and with any white space: "plus or minus"
# is the reading of "±", which is no such sign ("± 3x" is "plus or minus 3 times"), and a
# second run sees its white space joined ("plus or\nminus" is "plus or minus" then); nor after
# "plus" and a glued dash or Unicode hyphen, which is "plus-minus" as typeset (#1021)
_PLUS_OR_BEFORE_EN = re.compile(
    r"plus(?:\s+or\s+|\s*/\s*|[\u2010\u2011\u2013\u2014])\Z", re.IGNORECASE
)
# after "Nx", the numbers step's reading of a minus sign before a number counts as that sign,
# as before it: "3x", a minus sign and "2" read "3x minus 2" on both runs (#1010); "minus the
# rest" is no such reading
_MINUS_SAID_AFTER_EN = re.compile(r"\s+minus\s+\.?\d")
# after "Nx", a bare "less than" / "greater than" counts as the sign before a one-letter
# variable (not "a", "A", "I", which are words) or an opening bracket, mirroring
# `_COMPARED_EN`: "3x greater than y" is the reading of "3x > y" (#1010, D-646)
_COMPARED_AFTER_EN = re.compile(r"\s*(?:less|greater) than\s+(?:(?![aAI]\b)[A-Za-z](?!\w|\.\w)|\()")
# the reading of a power ("A⁻¹" is "A to the power of minus 1", "5 A²" "5 Ampere hoch 2"): its
# number is an exponent, no unit's number, so a second run reads "A⁻¹ K" as the first did (#816)
_POWER_SAID = {
    "en": re.compile(r"(?<![\w-])to the power of (?:minus )?\Z"),
    "de": re.compile(r"(?<![\w-])hoch (?:minus )?\Z"),
}
# the numbers step's reading of a fraction it has no word for ("17/20" is "17 out of 20"): the
# second number is no unit's number, as the printed denominator is not (#335, D-605)
_OUT_OF = re.compile(r"(?<![\w.,])\d{1,3} out of \Z")
# the words after which a unit is read with no number before it: "per m²", "pro m²", "je kg"
# (#230, D-646)
_PER_WORDS = {"en": ("per",), "de": ("pro", "je")}
_OPENING = "([{\u201c\u2018\"'"
_CLOSING = ".,;:!?)]}\u201d\u2019\"'"


@dataclass(frozen=True)
class _Term:
    """One unit of an expression, with its power, and whether it stands after "per"."""

    unit: Unit
    power: int  # 1, 2 or 3; a negative exponent makes the term a denominator
    per: bool


@dataclass(frozen=True)
class _Table:
    """The unit list compiled for matching."""

    words: UnitList
    by_form: dict[str, Unit]
    pattern: re.Pattern[str]
    magnitude: re.Pattern[str]
    number: re.Pattern[str]  # a number as the language prints it
    label_list: re.Pattern[str]  # labels in a list, right before a number
    # the comparison signs as the statistics step reads them, which count as signs around
    # "2x" ("gleich 2x" as "=2x"; English "equals 4x" as "= 4x", #320)
    said_operators: re.Pattern[str] = re.compile(r"(?!)")
    # text the step leaves as printed: a German court's file number ("13 W 17/12", #243)
    kept: re.Pattern[str] = re.compile(r"(?!)")
    language: str = "en"
    # a bare comparison word after a variable, which counts as the sign before "2x" (#358)
    compared: re.Pattern[str] = re.compile(r"(?!)")
    # "per", "pro", "je" before a unit with no number (#230, D-646)
    per_word: re.Pattern[str] = re.compile(r"(?!)")


class UnitStep(TextStep):
    """Read units after numbers, magnitude letters and number symbols as words."""

    id = "units"
    languages = ("en", "de")
    category = Category.NUMBERS_AND_UNITS
    stage = Stage.INLINE

    def find(self, document: Document, context: StepContext) -> list[Edit]:
        table = _compiled(context.language)
        if table is None:
            return []
        marks = unread_marks(document, context)  # read as a second run reads, without them
        raised = raised_numbers(document) if table.words.magnitudes else {}
        exponents = raised_exponents(document)
        edits = []
        for index, block in enumerate(document.blocks):
            if not read_as_prose(block, context):
                continue
            # maths letters as the plain letters the characters step makes of them last
            # (D-150): a bold "1 s" is "1 s" to a second run, which reads "eine Sekunde" (#1082)
            found = edits_through_unread(
                index,
                as_superscripts(block.text, exponents.get(index, ())),  # as printed (#576)
                lambda read: _without_overlaps(self._edits(index, fold(read), table)),  # noqa: B023
                self.id,
                marks.get(index, ()),
            )
            edits += self._mass_numbers(block.text, found, raised.get(index, ()), table)
        return edits

    def _mass_numbers(
        self, text: str, edits: list[Edit], raised: Collection[tuple[int, int]], table: _Table
    ) -> list[Edit]:
        """A magnitude letter after a raised mass number is no "thousand": "⁴⁰K" is
        potassium-40 (#449). Its magnitude edit becomes a `replace` of the raised digits with
        superscript digits, so the letter stays as printed and a second run, which sees no
        run tags, reads "⁴⁰K" the same. A mass number begins a word: a raised run glued after
        a letter or a digit ("10⁴K", an exponent) keeps its magnitude edit (#572)."""
        ends = {end: start for start, end in raised}
        kept = []
        for edit in edits:
            start = ends.get(edit.span.start)
            letter = text[edit.span.start : edit.span.end]
            if (
                start is None
                or (start > 0 and text[start - 1].isalnum())
                or table.magnitude.fullmatch(letter) is None
            ):
                kept.append(edit)
                continue
            digits = text[start : edit.span.start]
            kept.append(
                Edit(
                    Span(edit.span.block, start, edit.span.start),
                    EditKind.REPLACE,
                    reason=f'raised "{digits}" before "{letter}" kept as printed, not "thousand"',
                    step=self.id,
                    replacement=digits.translate(_SUPERSCRIPT),
                )
            )
        return kept

    def _edits(self, index: int, text: str, table: _Table) -> Iterator[Edit]:
        units_found: list[tuple[int, int]] = []
        kept = [found.span() for found in table.kept.finditer(text)]  # in order, apart
        k = 0
        for match in table.number.finditer(text):
            while k < len(kept) and kept[k][1] <= match.start():
                k += 1  # numbers come in text order: one walk over the spans (linear)
            if k < len(kept) and kept[k][0] <= match.start():
                continue  # "Az. 13 W 17/12": a court's file number, no "13 Watt" (#243)
            found = _unit_after(text, match, table)
            if found is None:
                continue
            start, end, reads, shown, gender = found
            units_found.append((start, end))
            yield self._edit(index, start, end, reads, shown)
            if gender and (one := _one(text, match, table, gender)) is not None:
                yield self._edit(index, match.start(), match.end(), one, match.group())
        words = table.words.words
        for position, char in enumerate(text):
            if char == "\u00d7" and _single(text, position, "\u00d7"):
                yield self._symbol(index, text, position, words["times"])
            elif char == "\u2248" and _single(text, position, "\u2248"):
                yield self._symbol(index, text, position, words["approximately"])
            elif char == MICRO_SIGN and not any(s <= position < e for s, e in units_found):
                yield Edit(
                    Span(index, position, position + 1),
                    EditKind.REPLACE,
                    reason=f'micro sign "{MICRO_SIGN}" read as the Greek letter "{GREEK_MU}"',
                    step=self.id,
                    replacement=GREEK_MU,
                )
        for match in table.per_word.finditer(text):
            found_per = _unit_after_per(text, match.end(), table)
            if found_per is not None:
                start, end, reads, shown = found_per
                yield self._edit(index, start, end, reads, shown)
        unit_ends = {end for _, end in units_found}
        for match in _TILDE.finditer(text):
            # "5~10" stays; after a unit, its power included ("5 m3~5", "Å³~5"), "~" is "about"
            head = text[max(0, match.start() - 3) : match.start()].rstrip(" \u00a0")
            after_number = head[-1:].isascii() and head[-1:].isdigit()
            if not after_number or max(0, match.start() - 3) + len(head) in unit_ends:
                yield self._symbol(index, text, match.start(), words["about"], before_number=True)
        for match in _LETTER_X.finditer(text):
            if _times_x(
                text,
                match,
                words["times"],
                table.said_operators,
                table.words.decimal,
                table.compared,
                english=table.language == "en",
            ):
                yield self._symbol(index, text, match.start("x"), words["times"])

    def _symbol(
        self, index: int, text: str, position: int, word: str, *, before_number: bool = False
    ) -> Edit:
        """One symbol read as a word, with a space on each side where it is glued; before a
        number ("~.5") the space after it is always put in."""
        before = text[position - 1 : position]
        after = text[position + 1 : position + 2]
        lead = " " if before and not before.isspace() and before not in _OPENING else ""
        closing = "" if before_number else _CLOSING
        trail = " " if after and not after.isspace() and after not in closing else ""
        if _HYPHEN_LINE_END.match(text, max(0, position - 2), position):
            # a symbol after a line-end hyphen ("11-", a break, then the times sign): the line
            # break goes with it, read as a space, so the line-end hyphen step does not find
            # "11-\nmal" on a second run and join it
            return self._edit(index, position - 1, position + 1, f" {word}{trail}", text[position])
        return self._edit(index, position, position + 1, lead + word + trail, text[position])

    def _edit(self, index: int, start: int, end: int, reads: str, shown: str) -> Edit:
        said = f'"{shown}" read as "{reads.strip()}"'
        if reads.strip() == shown:  # "10⁶M": the letter set apart from the power (#576)
            said = f'"{shown}" after a power is no magnitude: set apart, kept as printed'
        return Edit(
            Span(index, start, end),
            EditKind.REPLACE,
            reason=said,
            step=self.id,
            replacement=reads,
        )


_POINT_NUMBER = re.compile(r" \.\d")
_HYPHEN_LINE_END = re.compile("[-\u2010\u2011]\n\\Z")


def _single(text: str, position: int, char: str) -> bool:
    """True unless the symbol is doubled ("××"), which is not one operator."""
    return text[position - 1 : position] != char and text[position + 1 : position + 2] != char


def _without_overlaps(edits: Iterator[Edit]) -> list[Edit]:
    """The edits in order, each that overlaps an earlier one left out (a guard: the rules
    above do not overlap, but one bad edit would cost the step every edit of the run)."""
    kept: list[Edit] = []
    for edit in sorted(edits, key=lambda e: (e.span.start, e.span.end)):
        if not kept or kept[-1].span.end <= edit.span.start:
            kept.append(edit)
    return kept


@cache
def _compiled(language: str) -> _Table | None:
    """The language's unit list compiled for matching, or None if it has none."""
    listed = units(language)
    if listed is None:
        return None
    by_form = {form: unit for unit in listed.units for form in unit.printed}
    forms = sorted(by_form, key=len, reverse=True)
    pattern = re.compile("|".join(map(re.escape, forms)))
    magnitudes = sorted(listed.magnitudes, key=len, reverse=True)
    magnitude = re.compile("|".join(map(re.escape, magnitudes)) or r"(?!)")
    number = _NUMBER_DECIMAL_COMMA if listed.decimal == "," else _NUMBER
    german = language.split("-", 1)[0].lower() == "de"
    said = re.compile(
        "|".join(map(re.escape, sorted(set(OPERATORS_DE.values()), key=len, reverse=True)))
        if german
        else "|".join(map(re.escape, _SAID_OPERATORS_EN))
    )
    kept = re.compile(FILE_NUMBER_DE if german else r"(?!)")
    per_words = _PER_WORDS.get(language.split("-", 1)[0].lower(), ())
    per_word = re.compile(rf"(?<![\w-])(?:{'|'.join(per_words)}) " if per_words else r"(?!)")
    return _Table(
        listed,
        by_form,
        pattern,
        magnitude,
        number,
        _label_list(listed.label_joins),
        said,
        kept,
        language.split("-", 1)[0].lower(),
        per_word=per_word,
        compared=re.compile(r"(?!)") if german else _compared_en(by_form),
    )


def _compared_en(by_form: dict[str, Unit]) -> re.Pattern[str]:
    letters = "".join(sorted(f for f in by_form if len(f) == 1 and f.isascii() and f.isalpha()))
    return re.compile(_COMPARED_EN.replace("{units}", letters))


def _boundary(text: str, position: int) -> bool:
    """True at the end of the text or before a character that cannot go on a word."""
    if position >= len(text):
        return True
    char = text[position]
    if char == "\u0338":
        return True  # the slash of "≠" written as two characters: the statistics step's sign
    return not (char.isalnum() or char == "_" or unicodedata.category(char).startswith("M"))


def _unit_after(
    text: str, number: re.Match[str], table: _Table
) -> tuple[int, int, str, str, str] | None:
    """The unit expression right after a number: its span, reading and printed text, and
    the gender of the unit "1" is read with ("" if "1" stays as printed)."""
    end = number.end()
    gap = end
    while gap < len(text) and gap - end < 2 and text[gap] in _GAP:
        gap += 1
    hyphen = gap == end and text[end : end + 1] == "-"
    start = end + 1 if hyphen else gap
    if _is_label(text, number.start(), table) or _in_name(text, number.start()):
        return None
    if table.language == "en" and _OUT_OF.search(text, max(0, number.start() - 16), number.start()):
        return None  # the numbers step's "17 out of 20" for "17/20", whose "20" no unit follows
    power_said = _POWER_SAID.get(table.language)
    if power_said and power_said.search(text, max(0, number.start() - 24), number.start()):
        return None
    # after a power printed in superscripts ("10⁴K") a glued letter reads as it does with a
    # space ("10⁴ K"), where the numbers step reads the power before it (#576; German, #815)
    exponent = number["exponent"] or ""
    powered = exponent[:1] not in ("", "^")
    parsed = _expression(text, start, table)
    if parsed is not None:
        terms, stop = parsed
        first = terms[0].unit
        single = _single_letter(text[start:stop], first)
        glued = start == end
        if (single and glued and not powered) or _word_not_unit(text, terms, stop):
            parsed = None
        else:
            attributive = (hyphen and table.words.hyphen_singular) or _after_article(
                text, number.start(), table
            )
            one = _exactly_one(text, number)
            plural = not attributive and not one
            if text[stop - 1] == "." and (
                not text[stop:].strip() or opens_sentence(text, stop, table.language)
            ):
                # "nach 2 Std." at the end of a block keeps its full stop, and so does "2 Std.
                # Danach" before a sentence opener (#229); "2 Std. Fahrt" is one sentence
                stop -= 1
            reads = _reading(terms, plural, table)
            shown = " ".join(text[start:stop].split())
            gender = first.gender if one and not terms[0].per else ""
            compound = text[stop : stop + 1] == "-" and text[stop + 1 : stop + 2].isalpha()
            if hyphen and gender and text[stop : stop + 1] == "-":
                # "1-kg-Packung": "Ein-Kilogramm-Packung"; "1-m" alone starts no compound
                gender = _COMPOUND
            elif gender and compound and start > end:
                # "1 %-Hürde" as "1-%-Hürde": "Ein-Prozent-Hürde"; the space (a no-break
                # space too) becomes the compound's hyphen, so the edit starts at it (#233)
                return end, stop, f"-{reads}", shown, _COMPOUND
            return start, stop, (" " if glued else "") + reads, shown, gender
    if powered and gap == end:
        magnitude = table.magnitude.match(text, end)
        if magnitude and _boundary(text, magnitude.end()):
            # "10⁶M": after a power the letter is no "million"; set apart, it stays as printed
            # and a second run does not read "6M" as "6 million" (#576)
            return end, magnitude.end(), f" {magnitude.group()}", magnitude.group(), ""
    if gap == end and not number["exponent"]:
        magnitude = table.magnitude.match(text, end)
        if (
            magnitude
            and _boundary(text, magnitude.end())
            and not _starts_with_joint(text, magnitude.end())
        ):
            words = table.words.magnitudes[magnitude.group()]
            return end, magnitude.end(), f" {words}", magnitude.group(), ""
    return None


def _unit_after_per(text: str, start: int, table: _Table) -> tuple[int, int, str, str] | None:
    """A unit right after "per" / "pro" / "je" with no number before it, read in the singular:
    "per m²" is "per square metre", "je kg" "je Kilogramm" (#230, D-646). A single capital
    letter ("pro A") and a unit that starts a hyphenated word ("pro A-Gruppe") stay."""
    parsed = _expression(text, start, table)
    if parsed is None:
        return None
    terms, stop = parsed
    # a single capital ("pro A") is never read here, so neither is "A" as a word ("1 A note")
    if _capital(text, start, stop) or text[stop : stop + 1] == "-":
        return None
    if text[stop - 1] == "." and (
        not text[stop:].strip() or opens_sentence(text, stop, table.language)
    ):
        stop -= 1  # "pro Std." at a sentence end keeps its full stop
    return (
        start,
        stop,
        _reading(terms, False, table, after_per=True),
        " ".join(text[start:stop].split()),
    )


_COMPOUND = "compound"  # instead of a gender: "1" starts a hyphenated compound


def _one(text: str, number: re.Match[str], table: _Table, gender: str) -> str | None:
    """The word read for a "1" before a unit in a language that says it by gender: "ein
    Kilogramm", "eine Sekunde", "nach einer Stunde", "für einen Meter"; None without a sign
    rule ("−1 °C" stays "minus 1") or a list of such words."""
    ones = table.words.ones
    sign = text[number.start() - 1 : number.start()]
    if not ones or (sign and sign in _SIGNS):
        return None
    if gender == _COMPOUND:  # the uninflected word, with a capital as it starts the compound
        word = ones["nominative"]["n"]
        return word[:1].upper() + word[1:]
    word = _WORD_BEFORE.search(text, max(0, number.start() - 24), number.start())
    before = word.group(1).lower() if word else ""
    case = "nominative"
    if before in table.words.dative:
        case = "dative"
    elif before in table.words.accusative:
        case = "accusative"
    return ones.get(case, ones["nominative"])[gender]


def _starts_with_joint(text: str, at: int) -> bool:
    """True if a unit joint follows ("5K/s" is a unit, not "5 thousand"); False at the end."""
    return at < len(text) and text[at] in _UNIT_JOINTS


def _in_name(text: str, start: int) -> bool:
    """True for a number that ends a name joined by a hyphen ("COVID-19", "GPT-3")."""
    return text[start - 1 : start] == "-" and text[start - 2 : start - 1].isalpha()


def _word_not_unit(text: str, terms: list[_Term], stop: int) -> bool:
    """True for a lone unit that is also a word, before a word in lower case ("1 A note")."""
    return (
        len(terms) == 1
        and terms[0].unit.not_before_word
        and terms[0].power == 1
        and text[stop : stop + 1] == " "
        and text[stop + 1 : stop + 2].islower()
    )


def _single_letter(printed: str, unit: Unit) -> bool:
    """True if the expression starts with a unit of one ASCII letter ("m", "K")."""
    return any(
        len(form) == 1 and form.isascii() and printed.startswith(form) for form in unit.printed
    )


def _is_label(text: str, start: int, table: _Table) -> bool:
    """True for a number after a label word, or in a list of labels after one: "Fig. 3B",
    "Figures 2B and 3B", "panels A, 2C or 3B"."""
    word = table.label_list.search(text, max(0, start - 64), start)
    if word is None:
        word = _WORD_BEFORE.search(text, max(0, start - 24), start)
    if word is None:
        return False
    # what follows a full stop inside the word counts too: a times sign, ".Figure 5", and
    # its reading "times.Figure 5" both hold the label "Figure" (#253)
    lowered = word.group(1).lower()
    return lowered in table.words.labels or _AFTER_INNER_STOP.sub("", lowered) in table.words.labels


_AFTER_INNER_STOP = re.compile(r"\A.*\.(?=[^\W\d_])")


def _after_article(text: str, start: int, table: _Table) -> bool:
    word = _WORD_BEFORE.search(text, max(0, start - 24), start)
    return word is not None and word.group(1).lower() in table.words.articles


def _exactly_one(text: str, number: re.Match[str]) -> bool:
    """True for a number printed "1" (a sign may stand before it), not the end of a range."""
    if number.group() != "1":
        return False
    before = text[max(0, number.start() - 3) : number.start()].rstrip(" ")
    return not (before[-1:] in _DASHES and before[-2:-1].isdigit())


def _term(
    text: str, position: int, table: _Table, *, first: bool, per: bool
) -> tuple[_Term, int] | None:
    """One unit and its power at `position`: (term, end), or None."""
    match = table.pattern.match(text, position)
    if match is None:
        return None
    unit = table.by_form[match.group()]
    end = match.end()
    power = 1
    if found := _POWER.match(text, end):
        power, end = _POWERS[found.group()], found.end()
    elif not first and (found := _PLAIN_NEGATIVE.match(text, end)):
        power, end = -int(found.group(1)), found.end()
    elif (unit.length or (per and match.group() == "s")) and (
        found := _PLAIN_POWER.match(text, end)
    ):
        power, end = int(found.group()), found.end()
    if not _boundary(text, end):
        return None
    term = _Term(unit, -power, per=not per) if power < 0 else _Term(unit, power, per=per)
    if unit.per_only and not term.per:
        return None  # "5 day" is left as printed
    return term, end


def _expression(text: str, start: int, table: _Table) -> tuple[list[_Term], int] | None:
    """Units joined by "/", "·", a space or negative exponents, from `start`."""
    found = _term(text, start, table, first=True, per=False)
    if found is None:
        return None
    term, end = found
    terms = [term]
    while end < len(text):
        joint = text[end]
        if joint == "/" and text[end + 1 : end + 2] == "(":
            group = _group(text, end + 2, table)
            if group is None:
                break
            more, end = group
            terms += more
            continue
        if joint in _GLUED_JOINT:  # "3.6eV\u02daA": eV times angstrom, printed glued
            found = _term(text, end, table, first=False, per=False)
            if found is None:
                break
            term, end = found
            terms.append(term)
            continue
        if joint not in "/\u00b7\u22c5 ":
            break
        found = _term(text, end + 1, table, first=False, per=joint == "/")
        if found is None:
            break
        term, after = found
        if joint == " " and term.power == 1 and not term.per and _capital(text, end + 1, after):
            break  # "5 m A": a capital letter after a space is not joined
        terms.append(term)
        end = after
    return terms, end


def _group(text: str, start: int, table: _Table) -> tuple[list[_Term], int] | None:
    """The units inside "/(kg·K)", all after "per", and the end after ")"."""
    terms = []
    position = start
    while True:
        found = _term(text, position, table, first=not terms, per=True)
        if found is None:
            return None
        term, position = found
        terms.append(term)
        if text[position : position + 1] == ")":
            return terms, position + 1
        if text[position : position + 1] not in ("\u00b7", "\u22c5", " "):
            return None
        position += 1


def _capital(text: str, start: int, end: int) -> bool:
    return end - start == 1 and text[start].isascii() and text[start].isupper()


def _reading(terms: list[_Term], plural: bool, table: _Table, after_per: bool = False) -> str:
    """The words of a unit expression; `after_per` when it follows a printed "pro" / "je",
    so its first unit is said as one after "per" ("pro s²" is "pro Quadratsekunde")."""
    words = table.words.words
    above = [term for term in terms if not term.per]
    below = [term for term in terms if term.per]
    joined = table.words.joined_powers
    said = [
        _said(
            term,
            plural and position == len(above) - 1,
            words,
            joined,
            per=after_per and position == 0,
        )
        for position, term in enumerate(above)
    ]
    said += [f"{words['per']} {_said(term, False, words, joined)}" for term in below]
    return " ".join(said)


def _said(
    term: _Term, plural: bool, words: dict[str, str], joined: bool = False, per: bool = False
) -> str:
    name = term.unit.plural if plural else term.unit.singular
    if term.power == 1:
        return name
    if term.unit.length or (
        joined and (term.per or per) and term.power == 2 and term.unit.square_after_per
    ):  # "pro Quadratsekunde" (#250, D-646)
        power = words["square" if term.power == 2 else "cubic"]
        # German writes it into one word: "Quadrat" + "Meter" is "Quadratmeter"
        return f"{power}{name[:1].lower()}{name[1:]}" if joined else f"{power} {name}"
    return f"{name} {words['squared' if term.power == 2 else 'cubed']}"


def reads_unit_after(text: str, end: int, language: str) -> bool:
    """True if the step reads a unit after the number that ends at `end` ("2,55 m"; not
    after a label, "Kapitel 2,55 m"). The numbers step asks before it splits the number's
    digits into words ("2 Komma 5 5 m"), after which a second run would read the unit."""
    table = _compiled(language)
    if table is None:
        return False
    return any(
        match.end() == end and _unit_after(text, match, table) is not None
        for match in table.number.finditer(text, max(0, end - 64), end)
    )


def reads_one_as_word(text: str, start: int, language: str) -> bool:
    """True if the step reads the number that starts at `start` as a word before its unit
    ("1 N" as "ein Newton"). The numbers step asks: a second run sees that word after a date
    or an ordinal before the "1" ("am 3.4. 1 N", #970). Court file numbers are looked for
    near `start` only, so long blocks stay linear."""
    table = _compiled(language)
    if table is None:
        return False
    low = max(0, start - _PER_LOOK_BACK)
    if any(
        a <= start < b
        for a, b in (m.span() for m in table.kept.finditer(text, low, start + _PER_LOOK_BACK))
    ):
        return False  # "Az. 1 N 1/12": a court's file number, no unit (#243)
    number = table.number.match(text, start)
    if number is None:
        return False
    found = _unit_after(text, number, table)
    return found is not None and bool(found[4]) and _one(text, number, table, found[4]) is not None


def symbol_word_at(text: str, position: int, language: str) -> str | None:
    """The word the step reads for the "×", "≈" or "~" at `position`, or None. The numbers
    step asks after an ordinal's full stop ("am 3. × 5" is "am 3. mal 5" after the first run,
    whose "3." a second run reads "dritten", #970). A "~" after a number is left to the step
    (None): after a full stop it never stands there."""
    table = _compiled(language)
    char = text[position : position + 1]
    if table is None or not char:
        return None
    words = table.words.words
    if char == "\u00d7" and _single(text, position, char):
        return words["times"]
    if char == "\u2248" and _single(text, position, char):
        return words["approximately"]
    if _TILDE.match(text, position):
        head = text[max(0, position - 3) : position].rstrip(" \u00a0")
        if not (head[-1:].isascii() and head[-1:].isdigit()):
            return words["about"]
    return None


def tilde_after(text: str, end: int) -> bool:
    """True if a "~" before a number follows `end`, after at most two spaces: the step reads
    it "about" after a word but leaves it after a number ("5 ~ 10"). The numbers step asks
    after a number it reads into a word ("1/2 ~ 2" would be "ein halb etwa 2" on a second
    run, #1082)."""
    at = end
    while at < len(text) and at - end < 2 and text[at] in " \u00a0":
        at += 1
    return _TILDE.match(text, at) is not None


def unit_spans(text: str, language: str) -> list[tuple[int, int]]:
    """What the step reads in `text`, as spans: the numbers step writes a raised exponent as
    printed only where this step does not read it ("5 mL⁻¹" is "per millilitre", #589)."""
    table = _compiled(language)
    if table is None:
        return []
    found = _without_overlaps(UnitStep()._edits(0, text, table))
    return [(edit.span.start, edit.span.end) for edit in found]


def reads_unit_after_per(text: str, position: int, language: str) -> bool:
    """True if `position` lies in a unit expression the step reads right after "per" / "pro"
    / "je" ("per m³" as "per cubic metre", "per m² s⁻¹", #230): the numbers step then leaves
    its powers, or a second run would read "per metre cubed"."""
    table = _compiled(language)
    if table is None:
        return False
    for match in table.per_word.finditer(text, max(0, position - _PER_LOOK_BACK), position + 1):
        found = _unit_after_per(text, match.end(), table)
        if found is not None and found[0] <= position < found[1]:
            return True
    return False


_PER_LOOK_BACK = 64  # characters; longer than any unit expression the step reads


def reads_x_after(text: str, end: int, language: str) -> bool:
    """True if the step reads an "x" right after the number that ends at `end` as "times"
    ("2,5x"). The numbers step asks, so it reads such a number exactly when this step reads
    the x (#130): a second run, on "2,5 mal", then finds nothing new."""
    table = _compiled(language)
    if table is None:
        return False
    times = table.words.words["times"]
    return any(
        match.end("number") == end
        and _times_x(
            text,
            match,
            times,
            table.said_operators,
            table.words.decimal,
            table.compared,
            english=table.language == "en",
        )
        for match in _LETTER_X.finditer(text, max(0, end - 64), end + 2)
    )


def _times_x(
    text: str,
    match: re.Match[str],
    times: str,
    said: re.Pattern[str] | None = None,
    decimal: str = ".",
    compared: re.Pattern[str] | None = None,
    *,
    english: bool = False,
) -> bool:
    """True if the letter x stands for "times": between numbers, or glued after one."""
    after = match.end("x")
    rest = text[after : after + 2]
    # a decimal digit, not a superscript: "1x⁶" is "1 x⁶", not "1 times ⁶"
    if match["space"]:
        # where the decimal sign is a comma, ".45" is a number the numbers step reads in
        # the same run ("0 Komma 4 5"): "2019 x .45" reads "mal" then too (#253)
        point = decimal == "," and _POINT_NUMBER.match(text, after) is not None
        return rest[:1].isdecimal() or (rest[:1] == " " and rest[1:2].isdecimal()) or point
    if match["number"] == "0" and rest[:1] in _HEX and rest[:1] != "":
        return False  # "0x1F"
    if rest[:1].isdecimal():
        return True
    if len(rest) == 2 and rest[0] in "⁺⁻" and rest[1] in "⁰¹²³⁴⁵⁶⁷⁸⁹":
        return False  # "3x⁻²" is "3 x⁻²", as "1x⁶" is
    return _boundary(text, after) and not _in_algebra(
        text, match.start("number"), after, times, said, compared, english=english
    )


def _said_around(text: str, start: int, end: int, said: re.Pattern[str]) -> bool:
    """True if a comparison sign as the statistics step reads it stands right before the
    number or right after the x ("gleich 2x", "2x kleiner als 3"): a second run then sees
    "2x" just as the first saw it in "=2x"."""
    before, after = _said_patterns(said.pattern)
    return bool(before.search(text, max(0, start - 32), start) or after.match(text, end))


@cache
def _said_patterns(words: str) -> tuple[re.Pattern[str], re.Pattern[str]]:
    return re.compile(rf"(?<!\w)(?:{words}) *\Z"), re.compile(rf" *(?:{words})(?!\w)")


def _in_algebra(
    text: str,
    start: int,
    end: int,
    times: str,
    said: re.Pattern[str] | None = None,
    compared: re.Pattern[str] | None = None,
    *,
    english: bool = False,
) -> bool:
    """True for "2x" in a formula: an operator right before the number or after the x
    ("y = 2x + 1", "3x^2", "= 4x."), so the x is the variable, not "times". The word this
    step reads for "×" counts as that operator, on either side, so "×5x" and its reading
    "times 5x" agree, and "5x×" and "5x times" (#253)."""
    head = text[max(0, start - len(times) - 3) : start].rstrip(" ")
    if head.endswith(times) and not head[: -len(times)][-1:].isalnum():
        return True
    tail = text[end : end + len(times) + 3].lstrip(" ")
    if tail.startswith(times) and not tail[len(times) : len(times) + 1].isalnum():
        return True
    if said is not None and _said_around(text, start, end, said):
        return True
    if compared is not None and compared.search(text, max(0, start - 24), start):
        return True  # "y less than 2x" (#358, D-646)
    if english and _minus_said_before(text, start):
        return True  # "minus 3x", the reading of a minus sign before "3x" (#997)
    if english and (_MINUS_SAID_AFTER_EN.match(text, end) or _COMPARED_AFTER_EN.match(text, end)):
        return True  # "3x minus 2", "3x greater than y": the readings of signs after "3x"
    before = head[-1:]
    before_at = max(0, start - len(times) - 3) + len(head) - 1
    ahead = text[end : end + 3]
    after = ahead.lstrip(" ")[:1]
    after_at = end + len(ahead) - len(ahead.lstrip(" "))
    # the "=" or ">" of an arrow of logic is no operator: the statistics step reads "=>" as
    # "implies", and "3x" before that word is "3 times" on a second run, as "3x ⇒" is (#843)
    # ... nor, in English, a "<" or ">" right after such an arrow: its reading follows the
    # arrow's words ("is implied by greater than 3x"), where a bare "greater than" is prose
    # and a second run reads "3 times" (D-605, #984)
    # ... nor, in English, any bare "<" or ">" the statistics step reads as words, unless its
    # words are the sign on a second run: "y > 3x", "(a) > 3x", but not "A > 3x" (#988, D-646)
    # ... nor a minus sign that is a piece of an arrow printed in pieces, a left arrow and
    # minus signs before "3x" or minus signs and a right arrow after it: the numbers step
    # reads the pieces as one arrow, which a second run sees next to "3x" (#970)
    if (
        before != ""
        and before in _OPERATORS
        and not _arrow_before(text, start)
        and not LEFT_ARROW_TAIL.search(text, max(0, before_at - 16), before_at + 1)
        and not (english and before in "<>" and _arrow_before(text, before_at))
        and not (english and _bare_comparison(text, before, before_at, compared))
    ):
        return True
    # ... and, in English, a bare "<" or ">" after "Nx" counts only where its words do on a
    # second run (`_COMPARED_AFTER_EN`): "3x > 2" is "3 times greater than 2", as "2 < 3x" is
    return (
        after != ""
        and after in _OPERATORS + "("
        and not _arrow_of_logic(_LOGIC_ARROW.match(text, after_at), text)
        and not _PIECED_RIGHT_ARROW.match(text, after_at)
        and not (english and _bare_comparison_after(text, after, after_at))
    )


def _bare_comparison_after(text: str, sign: str, at: int) -> bool:
    """True if the `sign` at `at`, after "Nx", is a "<" or ">" the statistics step reads alone
    as "less than" or "greater than", and those words before what follows are prose on a
    second run (`_COMPARED_AFTER_EN`)."""
    if sign not in ("<", ">") or at not in comparisons_read_alone(text):
        return False
    said_after = " less than " + text[at + 1 : at + 33].lstrip()
    return _COMPARED_AFTER_EN.match(said_after) is None


def _minus_said_before(text: str, start: int) -> bool:
    """True if "minus" stands right before the number at `start` as the reading of a minus
    sign, not as the end of "plus or minus" ("±")."""
    minus = _MINUS_SAID_EN.search(text, max(0, start - 24), start)
    return minus is not None and not _PLUS_OR_BEFORE_EN.search(
        text, max(0, minus.start() - 24), minus.start()
    )


def _bare_comparison(text: str, sign: str, at: int, compared: re.Pattern[str] | None) -> bool:
    """True if the `sign` at `at` is a "<" or ">" the statistics step reads alone as "less
    than" or "greater than", and those words after what stands before it are prose on a second
    run (`_COMPARED_EN`): then the sign makes no variable of the "Nx" after it either."""
    if sign not in ("<", ">") or compared is None:
        return False
    joined = at > 0 and text[at - 1] in _JOINED_TO_SIGN
    if joined and not LEFT_ARROW_TAIL.search(text, max(0, at - 16), at):
        return False  # "A << 3x", "A -> 3x": left as printed, a sign on both runs
    said_before = text[max(0, at - 32) : at].rstrip(" ") + " less than "
    return compared.search(said_before) is None


def _arrow_before(text: str, at: int) -> bool:
    """True if an arrow of logic ends right before `at`, maybe with spaces between: one the
    statistics step reads whole there, not the start of a longer run ("=>" in "=>>")."""
    found = _LOGIC_ARROW_BEFORE.search(text, max(0, at - 16), at)
    if found is None:
        return False
    whole = _LOGIC_ARROW.match(text, found.start())
    if whole is None or whole.end() != found.start() + len(found.group().rstrip(" ")):
        return False
    return _arrow_of_logic(found, text)


def _arrow_of_logic(found: re.Match[str] | None, text: str) -> bool:
    """True if `found` is an arrow the statistics step reads as one: not the end of a longer
    ASCII run ("==>", ">=>"), whose signs stay operators as there (#843)."""
    return found is not None and not in_ascii_run(text, found.start(), found.group().rstrip(" "))
