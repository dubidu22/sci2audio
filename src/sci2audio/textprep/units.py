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
  ("441K apps").
- **Symbols:** "≈" reads "approximately" and "×" "times" (D-242: explicit, though espeak-ng
  says the same); "~" and "∼" read "about" right before a number; a letter "x" reads "times"
  between two numbers or glued after one ("10x speedup"); the micro sign "µ" that is not a
  unit prefix becomes the Greek "μ", which the voice reads "mu". "%" is left to the voice.

Edits cover the unit or symbol only, never the number, so they never overlap the number
steps (#67). Furniture and placeholder blocks are claimed whole by other steps and skipped.
"""
# ruff: noqa: RUF002 (the docstrings name the symbols this step reads)

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterator
from dataclasses import dataclass
from functools import cache

from sci2audio.core import Block, BlockKind, Document, Edit, EditKind, Span
from sci2audio.textprep.notation import FILE_NUMBER_DE, edits_through_unread
from sci2audio.textprep.statistics_de import OPERATORS_DE
from sci2audio.textprep.steps import Category, Stage, StepContext, TextStep
from sci2audio.textprep.wordlists import Unit, UnitList, units

MICRO_SIGN = "\u00b5"
GREEK_MU = "\u03bc"
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
    r"(?P<exponent>[\u207b\u2212]?[\u2070\u00b9\u00b2\u00b3\u2074-\u2079]+"
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


_TILDE = re.compile(r"[~\u223c](?=[ \u00a0]{0,2}[+\-\u2212]?\.?\d)")
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
    # "2x" ("gleich 2x" as "=2x"); English keeps only the printed signs, as it did before #130
    said_operators: re.Pattern[str] = re.compile(r"(?!)")
    # text the step leaves as printed: a German court's file number ("13 W 17/12", #243)
    kept: re.Pattern[str] = re.compile(r"(?!)")


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
        edits = []
        for index, block in enumerate(document.blocks):
            if _skipped(block):
                continue
            edits += edits_through_unread(
                index,
                block.text,
                lambda read: _without_overlaps(self._edits(index, read, table)),  # noqa: B023
                self.id,
            )
        return edits

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
        unit_ends = {end for _, end in units_found}
        for match in _TILDE.finditer(text):
            # "5~10" stays; after a unit, its power included ("5 m3~5", "Å³~5"), "~" is "about"
            head = text[max(0, match.start() - 3) : match.start()].rstrip(" \u00a0")
            after_number = head[-1:].isascii() and head[-1:].isdigit()
            if not after_number or max(0, match.start() - 3) + len(head) in unit_ends:
                yield self._symbol(index, text, match.start(), words["about"], before_number=True)
        for match in _LETTER_X.finditer(text):
            if _times_x(text, match, words["times"], table.said_operators, table.words.decimal):
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
        return Edit(
            Span(index, start, end),
            EditKind.REPLACE,
            reason=f'"{shown}" read as "{reads.strip()}"',
            step=self.id,
            replacement=reads,
        )


_POINT_NUMBER = re.compile(r" \.\d")
_HYPHEN_LINE_END = re.compile("[-\u2010\u2011]\n\\Z")


def _skipped(block: Block) -> bool:
    return block.kind is BlockKind.FURNITURE or block.is_placeholder


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
        else r"(?!)"
    )
    kept = re.compile(FILE_NUMBER_DE if german else r"(?!)")
    return _Table(
        listed, by_form, pattern, magnitude, number, _label_list(listed.label_joins), said, kept
    )


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
    parsed = _expression(text, start, table)
    if parsed is not None:
        terms, stop = parsed
        first = terms[0].unit
        single = _single_letter(text[start:stop], first)
        glued = start == end
        if (single and glued) or _word_not_unit(text, terms, stop):
            parsed = None
        else:
            attributive = (hyphen and table.words.hyphen_singular) or _after_article(
                text, number.start(), table
            )
            one = _exactly_one(text, number)
            plural = not attributive and not one
            if text[stop - 1] == "." and not text[stop:].strip():
                stop -= 1  # "nach 2 Std." at the end of a block keeps its full stop
            reads = _reading(terms, plural, table)
            shown = " ".join(text[start:stop].split())
            gender = first.gender if one and not terms[0].per else ""
            if hyphen and gender and text[stop : stop + 1] == "-":
                # "1-kg-Packung": "Ein-Kilogramm-Packung"; "1-m" alone starts no compound
                gender = _COMPOUND
            return start, stop, (" " if glued else "") + reads, shown, gender
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


def _reading(terms: list[_Term], plural: bool, table: _Table) -> str:
    words = table.words.words
    above = [term for term in terms if not term.per]
    below = [term for term in terms if term.per]
    joined = table.words.joined_powers
    said = [
        _said(term, plural and position == len(above) - 1, words, joined)
        for position, term in enumerate(above)
    ]
    said += [f"{words['per']} {_said(term, False, words, joined)}" for term in below]
    return " ".join(said)


def _said(term: _Term, plural: bool, words: dict[str, str], joined: bool = False) -> str:
    name = term.unit.plural if plural else term.unit.singular
    if term.power == 1:
        return name
    if term.unit.length:
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
        and _times_x(text, match, times, table.said_operators, table.words.decimal)
        for match in _LETTER_X.finditer(text, max(0, end - 64), end + 2)
    )


def _times_x(
    text: str,
    match: re.Match[str],
    times: str,
    said: re.Pattern[str] | None = None,
    decimal: str = ".",
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
        text, match.start("number"), after, times, said
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
    text: str, start: int, end: int, times: str, said: re.Pattern[str] | None = None
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
    before = head[-1:]
    after = text[end : end + 3].lstrip(" ")[:1]
    return (before != "" and before in _OPERATORS) or (after != "" and after in _OPERATORS + "(")
