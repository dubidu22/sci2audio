# ruff: noqa: RUF001, RUF002, RUF003
# (minus signs, dashes, primes and math letters are what these rules are about)
"""Numbers the voice reads wrong (TP-09, TP-13, #67): ranges, minus signs, counts, powers.

misaki, the voice's English front end, reads ordinary numbers, years and dates well and
they are left to it (D-54, D-176). This step proposes `replace` edits only where it reads a
number wrong; digits stay digits for the voice wherever it can read them, and each reason
quotes the printed text.

- N1: a minus sign (U+2212) before a number read "minus"; misaki loses the point of "−.32".
- N2 (D-183): ranges read "to": "3–5", "1.2–3.4", "2010–15", and "18-25" with a hyphen
  between plain numbers only.
- N3 (D-182): misaki reads every bare four-digit number as a year; one that the context
  marks as a count gets a thousands comma ("1234 participants" → "1,234").
- N4 (D-184): trailing zeros kept ("2.50" → "2 point 5 0"); misaki drops them.
- N5, N6 (D-187): powers: "10⁶", "10^-4", "× 10−4", "x²".
- N7, N8 (D-186): ratios "3:1" read "3 to 1"; fractions "1/2" read "1 half", "17/20" read
  "17 out of 20".
- N9 (D-188): ISO dates read "12 March 2019".
- N10 (D-189): digits grouped by thin or no-break spaces ("50 000") read as one number.
- R1 (D-185): Roman numerals after "Phase", "Type", "War" and similar read as numbers.

Units, %, ≈, ×, ° and µ are the units step's (#68, D-178).
"""

from __future__ import annotations

import calendar
import re

from sci2audio.core import Document, Edit
from sci2audio.textprep.notation import SKIPPED_KINDS, Candidate, fold, pick, to_edits
from sci2audio.textprep.steps import Category, Stage, StepContext, TextStep

_UNSIGNED = r"\d+(?:\.\d+)?"

# --- N1 minus sign ---------------------------------------------------------------------------
# U+2212 minus, and U+2012 figure dash where no number stands before it (between two numbers
# it is a range dash, N2); the ASCII hyphen-minus is read right by the voice
_MINUS = re.compile(r"(?<![\w.,])(?:\u2212|(?<!\d)(?<!\d\s)\u2012)(?P<space> ?)(?=\.?\d)")

# --- N2 ranges ------------------------------------------------------------------------------
# an en dash or figure dash, spaces allowed around it, or an em dash without spaces
_DASH_RANGE = re.compile(r"(?<=\d)(?P<dash>\s*[\u2013\u2012]\s*|\u2014)(?=[\u2212-]?\.?\d)")
# a hyphen between two plain numbers that are not part of a longer chain
_HYPHEN_RANGE = re.compile(
    r"(?<![\w.,/:-])(?<!-\n)(?P<a>\d{1,4}(?:\.\d+)?)(?P<dash>-\n?)(?P<b>\d{1,4}(?:\.\d+)?)"
    r"(?![\w/:-]|[.,]\d)"
)

# --- N3 four-digit counts -------------------------------------------------------------------
_FOUR_DIGITS = re.compile(r"(?<![\w.,/])[1-9]\d{3}(?![\w]|[.,]\d|\s+point\s+\d)")
_AFTER_OPERATOR = re.compile(r"[=<>\u2264\u2265\u2248~]\s*\Z")
_NEXT_WORD = re.compile(r"\s+(?P<word>[a-z][a-z'-]*)")
_PREVIOUS_WORD = re.compile(r"(?P<word>[A-Za-z]+)\.?\s+\Z")
# words ending in "s" that are not plural nouns: "ACL 2023 is", "in 2019 was"
_NOT_PLURAL = frozenset(
    {"is", "was", "has", "his", "its", "this", "thus", "as", "yes", "does", "goes", "whereas"}
    | {"versus", "plus", "minus", "less", "unless", "always", "perhaps", "towards", "besides"}
)
_PLURALS = frozenset({"people", "children", "men", "women", "mice", "data", "persons"})
_MONTHS = {name.lower() for name in calendar.month_name[1:] + calendar.month_abbr[1:]}
_YEAR_WORDS = frozenset(
    {"in", "since", "from", "until", "till", "to", "by", "during", "of", "before", "after"}
    | {"around", "circa", "c", "ca", "the", "this", "that", "these", "those"}
    | {"early", "mid", "late", "year", "years", "spring", "summer", "autumn", "fall"}
    | {"winter", "sept"}
    | _MONTHS
)

# --- N4 trailing zeros -----------------------------------------------------------------------
# at most four digits after the point, not inside an identifier such as "arXiv:2401.17620",
# and not over a slash ("2.50/3" has no fraction reading, so it is left as printed) or in an
# exponent ("10^22.50", "10−42.50")
_TRAILING_ZERO = re.compile(
    r"(?<![\w.,/^])(?<![^\W\d_]:)(?<!\d[\u2212-])(?P<whole>\d{1,3}(?:,\d{3})*|\d+)\.(?P<fraction>\d{0,3}0)"
    r"(?![\w]|[.,/]\d)"
)

# --- N5, N6 powers ---------------------------------------------------------------------------
_SUPERSCRIPTS = "⁰¹²³⁴⁵⁶⁷⁸⁹"
_SUPER_DIGIT = {char: str(n) for n, char in enumerate(_SUPERSCRIPTS)}
_SUPER = f"[⁺⁻]?[{_SUPERSCRIPTS}]+"
_POWER_OF_TEN = re.compile(r"(?<![\w.,])(?P<base>10)(?P<exp>" + _SUPER + ")")
_SIGNED_POWER = re.compile(
    r"(?<![\w.,])(?P<base>\d+(?:\.\d+)?)(?P<exp>[⁺⁻][" + _SUPERSCRIPTS + "]+)"
)
_CARET = re.compile(
    r"(?<![\w.,])(?P<base>\d+(?:\.\d+)?|[^\W\d_])"
    r"(?P<exp>\^(?:\{(?P<braced>[+\u2212-]?\d+)\}|\((?P<paren>[+\u2212-]?\d+)\)|(?P<bare>[+\u2212-]?\d+)))"
    r"(?![\w.])"
)
_TIMES_TEN = re.compile(r"\d\s*[×x]\s*(?P<base>10)(?P<exp>[\u2212-]\d{1,3})(?![\w.,])")
# not after a number and a space ("5 m²" is a unit, the units step's); a caret exponent before
# the space is no such number, since the caret rule may turn it into a word ("x^2 x⁶")
_LETTER_POWER = re.compile(
    r"(?<![\w/])(?<!(?<!\^)\d )(?<![.,] )(?P<base>[^\W\d_])(?P<exp>" + _SUPER + r")"
    r"(?![\w" + _SUPERSCRIPTS + "])"
)
_SQUARED_STATISTICS = frozenset("Rrηωεχ")  # read by the statistics step ("R squared")

# --- N7 ratios, N8 fractions -----------------------------------------------------------------
# a ratio not after a hyphen: "10-23:3" is a hyphenated pair, left as printed
_RATIO = re.compile(
    r"(?<![\w.:/,-])(?P<a>" + _UNSIGNED + r"):(?P<b>" + _UNSIGNED + r")(?![\w:/]|[.,]\d)"
)
_TIME_BEFORE = re.compile(
    r"(?i:\b(?:at|from|until|till|by|before|after|around|between|and|to)\s+)\Z"
)
_TIME_AFTER = re.compile(r"\s*(?:[ap]\.?m\b\.?|h\b|hrs?\b|hours?\b|o'clock)", re.IGNORECASE)
# a range after "8:64" makes it a volume and its pages; "to" is how this step reads that range
_RANGE_AFTER = re.compile(r"\s*(?:[\u2013\u2012\u2014-]|\s+to\s)\s*\d")
# not before a signed power, colon or hyphen ("3/3⁻⁴", "3/33:3", "3/33-53": no plain denominator)
_FRACTION = re.compile(r"(?<![\w.,/:\u2212-])(?P<n>\d{1,3})/(?P<d>\d{1,3})(?![\w/:⁺⁻-]|[.,]\d)")
_FRACTION_WORDS = {
    2: ("half", "halves"),
    3: ("third", "thirds"),
    4: ("quarter", "quarters"),
    5: ("fifth", "fifths"),
    6: ("sixth", "sixths"),
    7: ("seventh", "sevenths"),
    8: ("eighth", "eighths"),
    9: ("ninth", "ninths"),
    10: ("tenth", "tenths"),
}

# --- N9 ISO dates ----------------------------------------------------------------------------
_ISO_DATE = re.compile(
    r"(?<![\w.\u2013-])(?P<y>1[5-9]\d\d|20\d\d)-\n?(?P<m>0[1-9]|1[0-2])-\n?(?P<d>0[1-9]|[12]\d|3[01])"
    r"(?![\w⁺⁻-]|[.,]\d)"  # not before a power: "2019-03-12⁻⁴" is no date
)

# --- N10 grouped digits ----------------------------------------------------------------------
_GROUPED = re.compile(
    r"(?<![\w.,])\d{1,3}(?:[ \u00a0\u2009\u202f]\d{3})+(?![\w]|[.,]\d|[ \u00a0\u2009\u202f]\d)"
)
_NARROW = re.compile(r"[\u00a0\u2009\u202f]")

# --- R1 Roman numerals -----------------------------------------------------------------------
_KEYWORDS = frozenset(
    {"war", "phase", "type", "class", "stage", "grade", "level", "tier", "part", "chapter"}
    | {"volume", "book", "section", "appendix", "study", "experiment", "trial", "table"}
    | {"figure"}
)
_PLURAL_KEYWORDS = {"studies": "study", "classes": "class", "wars": "war"}
_ROMAN = r"[IVX]{1,6}"
_ROMAN_RUN = re.compile(
    r"\b(?P<keyword>[A-Za-z]+)\s+(?P<run>"
    + _ROMAN
    + r"(?:(?:\s*[/\u2013-]\s*|,\s*|\s+(?:and|or|&)\s+)"
    + _ROMAN
    + r")*)(?![\w⁺⁻])"  # "Phase II⁻⁴" is left as printed
)
_ROMAN_PART = re.compile(r"(?P<numeral>" + _ROMAN + r")|(?P<sep>\s*[/\u2013-]\s*)")
_VALID_ROMAN = re.compile(r"\A(?P<tens>X{0,3})(?P<units>IX|IV|V?I{0,3})\Z")
_UNITS = {"": 0, "I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8, "IX": 9}


class NumbersStep(TextStep):
    """Read the numbers the voice gets wrong; one edit per number or sign."""

    id = "numbers"
    languages = ("en",)
    category = Category.NUMBERS_AND_UNITS
    stage = Stage.INLINE

    def find(self, document: Document, context: StepContext) -> list[Edit]:
        edits = []
        for index, block in enumerate(document.blocks):
            if block.kind in SKIPPED_KINDS or not block.text:
                continue
            edits += to_edits(index, find_numbers(block.text), self.id)
        return edits


def find_numbers(text: str) -> list[Candidate]:
    """The number edits for one block's text, without overlap, in text order.

    Rules come most specific first, so a date is not also read as a range and a power's
    minus is not also read as a minus sign.
    """
    plain = fold(text)
    return pick(
        [
            *_iso_dates(text),
            *_unjoined(text, _roman_numerals(plain, text)),
            *_grouped_digits(text),
            *_unjoined(text, _powers(text, plain)),
            *_minus_signs(text),
            *_ranges(text),
            *_unjoined(text, _trailing_zeros(text)),
            *_counts(text),
            *_ratios(text),
            *_fractions(text),
        ]
    )


# a number joined to the next or the last one by a dash, colon or slash, by a space, or by
# the "to" this step reads a range or ratio with, or by nothing at all ("10⁶3")
_JOINED_AFTER = re.compile(r"\s*[\u2013\u2014\u2012:/-]\s*\.?\d|\.?\d|\s\d|\s+to\s+\.?\d")
_JOINED_BEFORE = re.compile(r"\d\s*(?:[\u2013\u2014\u2012:/-]|\sto\s)\s*\Z|\d\s\Z")


def _unjoined(text: str, candidates: list[Candidate]) -> list[Candidate]:
    """The candidates whose number stands on its own.

    These rules write digits next to words ("2 point 5 0", "Phase 3", "of 4"). Where the
    printed number is joined to another one ("3:2.50", "Phase I 395", "10⁻⁴–5"), that new
    reading would join differently on a second run, so such a number is left as printed:
    the step proposes nothing that a second run would change again.
    """
    return [
        c
        for c in candidates
        if not _JOINED_AFTER.match(text, c.end) and not _JOINED_BEFORE.search(text, 0, c.start)
    ]


def _iso_dates(text: str) -> list[Candidate]:
    found = []
    for match in _ISO_DATE.finditer(text):
        year, month, day = int(match["y"]), int(match["m"]), int(match["d"])
        if day > calendar.monthrange(year, month)[1]:
            continue
        words = f"{day} {calendar.month_name[month]} {year}"
        found.append(Candidate(*match.span(), words, f'date "{match.group()}" read as "{words}"'))
    return found


def _roman_value(numeral: str) -> int:
    match = _VALID_ROMAN.match(numeral)
    if not match or not numeral:
        return 0
    return 10 * len(match["tens"]) + _UNITS[match["units"]]


def _roman_numerals(plain: str, text: str) -> list[Candidate]:
    found = []
    for match in _ROMAN_RUN.finditer(plain):
        keyword = match["keyword"]
        base = keyword.lower()
        base = _PLURAL_KEYWORDS.get(base, base[:-1] if base.endswith("s") else base)
        if keyword.lower() not in _KEYWORDS and base not in _KEYWORDS:
            continue
        offset = match.start("run")
        parts = list(_ROMAN_PART.finditer(match["run"]))
        values = [_roman_value(p["numeral"]) for p in parts if p["numeral"]]
        if not all(values):
            continue  # "Type IIX": not a numeral, so nothing in the run is read as one
        if match["run"] == "I" and not keyword[0].isupper():
            continue  # "the part I think": a lone "I" after a lowercase word is the pronoun
        for part in parts:
            start, end = offset + part.start(), offset + part.end()
            if part["numeral"]:
                value = str(_roman_value(part["numeral"]))
                reason = f'Roman numeral "{part["numeral"]}" after "{keyword}" read as "{value}"'
                found.append(Candidate(start, end, value, reason))
            else:
                sep = part["sep"].strip()
                words = " and " if sep == "/" else " to "
                reason = f'"{sep}" between Roman numerals read as "{words.strip()}"'
                found.append(Candidate(start, end, words, reason))
    return found


def _grouped_digits(text: str) -> list[Candidate]:
    found = []
    for match in _GROUPED.finditer(text):
        number = match.group()
        groups = re.split(r"[ \u00a0\u2009\u202f]", number)
        if not _NARROW.search(number) and len(groups) < 3:
            continue  # "Table 2 000" could be two numbers; one plain-space group is not enough
        if _NARROW.search(number) and " " in number:
            continue  # mixed separators: not one grouped number
        words = ",".join(groups)
        found.append(
            Candidate(*match.span(), words, f'digits grouped as "{number}" read as "{words}"')
        )
    return found


def _exponent_words(exponent: str) -> str:
    digits = "".join(_SUPER_DIGIT.get(c, c) for c in exponent)
    sign = ""
    if digits[:1] in "⁻\u2212-":
        sign, digits = "minus ", digits[1:]
    elif digits[:1] in "⁺+":
        digits = digits[1:]
    return f"{sign}{digits}"


def _powers(text: str, plain: str) -> list[Candidate]:
    found: list[tuple[Candidate, int | None]] = []
    for pattern in (_POWER_OF_TEN, _SIGNED_POWER, _TIMES_TEN):
        for match in pattern.finditer(text):
            start, end = match.span("exp")
            words = f" to the power of {_exponent_words(match['exp'])}"
            found.append(
                (
                    Candidate(start, end, words, _power_reason(text, match, words)),
                    match.start("base"),
                )
            )
    for match in _CARET.finditer(plain):
        start, end = match.span("exp")
        exponent = match["braced"] or match["paren"] or match["bare"]
        words = _letter_power(exponent) if match["base"].isalpha() else None
        words = words or f" to the power of {_exponent_words(exponent)}"
        base = None if match["base"].isalpha() else match.start("base")
        found.append((Candidate(start, end, words, _power_reason(text, match, words)), base))
    for match in _LETTER_POWER.finditer(plain):
        if match["base"] in _SQUARED_STATISTICS and match["exp"] == "²":
            continue
        start, end = match.span("exp")
        exponent = "".join(_SUPER_DIGIT.get(c, c) for c in match["exp"])
        words = _letter_power(exponent) or f" to the power of {_exponent_words(match['exp'])}"
        found.append((Candidate(start, end, words, _power_reason(text, match, words)), None))
    # the base is the number whose reading changes: "3:10²" is left as printed (`_unjoined`);
    # a letter base (None) is read the same whatever stands before it
    return [c for c, base in found if base is None or not _JOINED_BEFORE.search(text, 0, base)]


def _letter_power(exponent: str) -> str | None:
    return {"2": " squared", "3": " cubed"}.get(exponent)


def _power_reason(text: str, match: re.Match[str], words: str) -> str:
    printed = text[match.start("base") : match.end("exp")]
    return f'power "{printed}" read with "{words.strip()}"'


def _minus_signs(text: str) -> list[Candidate]:
    return [
        Candidate(m.start(), m.end(), "minus ", '"\u2212" before a number read as "minus"')
        for m in _MINUS.finditer(text)
    ]


def _ranges(text: str) -> list[Candidate]:
    found = []
    for match in _DASH_RANGE.finditer(text):
        start, end = match.span("dash")
        found.append(Candidate(start, end, " to ", _range_reason(text, start, end)))
    for match in _HYPHEN_RANGE.finditer(text):
        if float(match["a"]) >= float(match["b"]):
            continue  # "3-1" is a score or a code, not a range
        start, end = match.span("dash")
        found.append(Candidate(start, end, " to ", _range_reason(text, start, end)))
    return found


def _range_reason(text: str, start: int, end: int) -> str:
    left = re.search(r"[\d.,]*\d\Z", text[:start])
    right = re.match(r"[\u2212-]?[\d.,]*\d", text[end:])
    printed = (left.group() if left else "") + text[start:end] + (right.group() if right else "")
    return f'range "{" ".join(printed.split())}" read with "to"'


def _counts(text: str) -> list[Candidate]:
    found = []
    for match in _FOUR_DIGITS.finditer(text):
        number = match.group()
        value = int(number)
        if value % 100 == 0:
            continue  # "1000", "1200": read right as a year and as a number
        before = text[: match.start()]
        if not _AFTER_OPERATOR.search(before) and not _counted(text, match.end(), before, value):
            continue
        words = f"{number[0]},{number[1:]}"
        found.append(Candidate(*match.span(), words, f'"{number}" read as a number, not a year'))
    return found


def _counted(text: str, end: int, before: str, value: int) -> bool:
    """True if a plural word follows and no word before makes the number a year."""
    following = _NEXT_WORD.match(text, end)
    if not following:
        return False
    word = following["word"]
    plural = word in _PLURALS or (
        word.endswith("s") and not word.endswith(("ss", "us", "'s")) and word not in _NOT_PLURAL
    )
    if not plural:
        return False
    if not 1500 <= value <= 2099:
        return True
    previous = _PREVIOUS_WORD.search(before)
    # "in 2019 studies", "the 2019 guidelines", "ACL 2023 papers": the number is a year
    return previous is None or not (
        previous["word"].lower() in _YEAR_WORDS or previous["word"][0].isupper()
    )


def _trailing_zeros(text: str) -> list[Candidate]:
    found = []
    for match in _TRAILING_ZERO.finditer(text):
        words = f"{match['whole']} point {' '.join(match['fraction'])}"
        found.append(
            Candidate(
                *match.span(),
                words,
                f'"{match.group()}" read with its trailing zeros as "{words}"',
            )
        )
    return found


def _ratios(text: str) -> list[Candidate]:
    found = []
    for match in _RATIO.finditer(text):
        if _RANGE_AFTER.match(text, match.end()):
            continue  # "8:64–77": a volume and its pages
        if _is_time(text, match):
            continue
        start = match.start() + len(match["a"])
        words = f"{match['a']} to {match['b']}"
        found.append(
            Candidate(start, start + 1, " to ", f'ratio "{match.group()}" read as "{words}"')
        )
    return found


def _is_time(text: str, match: re.Match[str]) -> bool:
    hours, minutes = match["a"], match["b"]
    if not (hours.isdigit() and minutes.isdigit() and len(minutes) == 2):
        return False
    if int(hours) > 24 or int(minutes) > 59:
        return False
    return bool(_TIME_BEFORE.search(text, 0, match.start()) or _TIME_AFTER.match(text, match.end()))


def _fractions(text: str) -> list[Candidate]:
    found = []
    for match in _FRACTION.finditer(text):
        n, d = int(match["n"]), int(match["d"])
        if n > d or d == 0:
            continue  # "24/7", "3/2": no reading that is right everywhere
        start = match.start("n") + len(match["n"])
        # a word for the denominator would part it from a number joined to it ("3/5 2.50")
        if d in _FRACTION_WORDS and 0 < n < d and not _JOINED_AFTER.match(text, match.end()):
            one, many = _FRACTION_WORDS[d]
            words = f" {one if n == 1 else many}"
        else:
            words = " out of "
            start, end = start, start + 1
            found.append(
                Candidate(start, end, words, f'"{match.group()}" read as "{n} out of {d}"')
            )
            continue
        found.append(
            Candidate(start, match.end(), words, f'fraction "{match.group()}" read as "{n}{words}"')
        )
    return found
