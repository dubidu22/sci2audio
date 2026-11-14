# ruff: noqa: RUF001, RUF003
# (minus signs, primes and Greek letters are what these rules are about)
"""German statistics read as words (TP-11, #130): the statistics step's German rules.

The German voice's front end says nothing for "<" and ">", drops the bracket of "t(34)" and
spells "KI" (plans/v11-german-measure-misaki.txt). These rules mirror the English ones in
statistics.py, which also reads the comparison signs with `OPERATORS_DE`:

- S-de-1 (D-177): comparison signs read as words ("p kleiner als 0 Komma 0 5").
- S-de-2 (D-477): a df bracket read "mit ... Freiheitsgraden" ("t mit 34 Freiheitsgraden",
  "F mit 2 und 57 Freiheitsgraden", "Chi-Quadrat mit 1 Freiheitsgrad").
- S-de-3: R², η², ηp², ω², ε² read "Quadrat" and χ² "Chi-Quadrat".
- S-de-4: "KI" and "CI" read "Konfidenzintervall"; the bracketed pair after it "1 Komma 2 bis 3
  Komma 4". German pairs are split by ";" or a comma and a space, since a comma alone is the
  decimal sign ("[1,2; 3,4]").
- S-de-5: "OR" before a comparison sign read "Odds Ratio".

The numbers inside a df bracket or an interval are read here, as German says them, since the
edit covers them; every other number is the numbers step's (numbers_de.py).
"""

from __future__ import annotations

import re
from collections.abc import Iterator

from sci2audio.textprep.notation import Candidate, padded, unit_follows

OPERATORS_DE = {
    "=": "gleich",
    "<": "kleiner als",
    ">": "größer als",
    "≤": "kleiner oder gleich",
    "⩽": "kleiner oder gleich",
    "≦": "kleiner oder gleich",
    "≥": "größer oder gleich",
    "⩾": "größer oder gleich",
    "≧": "größer oder gleich",
    "≠": "ungleich",
    "̸=": "ungleich",
    "≠": "ungleich",
    "±": "plus minus",
    "∓": "minus plus",
    "≪": "viel kleiner als",
    "≫": "viel größer als",
}

_OPERATOR_AHEAD = r"\s*(?:̸=|≠|[=<>≤⩽≦≥⩾≧≠≪≫])"
_THEN_OPERATOR = f"(?={_OPERATOR_AHEAD})"
# a German number: a decimal comma or point, or a thousands point ("1.234")
_NUMBER = r"\d+(?:[.,]\d+)*"
# two numbers in a bracket are parted by ";" or by a comma and a space: "F(2, 57)"; "t(34,5)"
# is one number
_PAIR = r"(?:\s*;\s*|,\s+)"

# S-de-2: a test statistic, its df in a bracket, then a comparison sign
_DF = re.compile(
    r"(?<![\w′'])(?:[tFrHUWzG]|χ[2²]?|X2)"
    r"(?P<paren>\(\s*(?P<a>" + _NUMBER + r")\s*"
    r"(?:"
    + _PAIR
    + r"(?:(?P<n>[Nn]\s*=\s*\d[\d.]*)|(?P<b>"
    + _NUMBER
    + r")))?\s*\))"
    + _THEN_OPERATOR
)

# S-de-3
_SQUARED_NAMES = {
    "R": "R Quadrat",
    "r": "r Quadrat",
    "η": "Eta-Quadrat",
    "ω": "Omega-Quadrat",
    "ε": "Epsilon-Quadrat",
    "χ": "Chi-Quadrat",
}
_SQUARED = re.compile(
    r"(?<![\w′'])(?P<name>[Rrηωεχ])(?P<p1>p)?(?:(?P<sup>²)|(?P<two>2))(?P<p2>p)?(?![\w²])"
)
_THEN_OPERATOR_OR_DF = re.compile(f"(?:{_OPERATOR_AHEAD}|\\s*\\()")

# S-de-4: confidence intervals; "95 %-KI" puts a hyphen between
_CI = re.compile(r"(?<![\w′'])(?P<name>KI|CI)(?P<plural>s)?(?![\w′'])")
_WINDOW = 64
_AFTER_PERCENT = re.compile(r"[\d⁰¹²³⁴⁵⁶⁷⁸⁹][\])]?\s?%\s*-?\Z")
_BEFORE_CI_THING = re.compile(r"\s*[\[(=:]")
_SIGNED = r"[−-]?(?:\d+(?:[.,]\d+)?|[.,]\d+)"
_INTERVAL = re.compile(
    r"\s*(?:[=:]\s*)?(?P<open>[\[(]\s*)(?P<a>" + _SIGNED + r")(?P<sep>" + _PAIR + r")"
    r"(?P<b>" + _SIGNED + r")(?P<close>\s*[\])])"
)
_JOIN = re.compile(r"\s*(?:,\s*)?(?:und|oder|bzw\.)(?=[\s\[(])|\s*[,;]")
MAX_JOINED_INTERVALS = 8
# and an x the units step may read "mal" ("[1; 2] x3")
_FULL_STOP = re.compile(r"\.(?:\s|\Z)")  # a full stop that ends a sentence
_JOINED_NUMBER = re.compile(r"\s*[\u2013\u2014\u2012:/-]\s*[\u2212-]?[.,]?\d|\s?[xX×]|[.,]\d")

# S-de-5
_ODDS_RATIO = re.compile(r"(?<![\w′'])OR(?![\w′'])" + _THEN_OPERATOR)


def say_decimal(number: str) -> str:
    """A number as German reads it: "2,45" and "2.45" are "2 Komma 4 5", ".05" "0 Komma 0 5"."""
    sign = number[0] if number[:1] in "\u2212-" else ""
    body = number[len(sign) :]
    if not re.fullmatch(r"\d*[.,]\d+", body):
        return number
    whole, fraction = re.split(r"[.,]", body, maxsplit=1)
    return f"{sign}{whole or '0'} Komma {' '.join(fraction)}"


def find_statistics_de(text: str, plain: str) -> list[Candidate]:
    """The German statistics rules but the comparison signs, most specific first."""
    return [
        *_degrees_of_freedom(text, plain),
        *_squared(text, plain),
        *_confidence_intervals(text, plain),
        *_odds_ratios(plain),
    ]


def _number(printed: str) -> str:
    """A number inside a df bracket as German reads it: "1.234" (a count) is "1234"."""
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", printed):
        return printed.replace(".", "")
    return say_decimal(printed)


def _degrees_of_freedom(text: str, plain: str) -> list[Candidate]:
    found = []
    for match in _DF.finditer(plain):
        start, end = match.span("paren")
        a = _number(match["a"])
        if match["n"]:
            n = re.sub(r"\s*=\s*", " gleich ", match["n"]).replace(".", "")
            words = f" mit {a} {_degrees(match['a'])}, {n}"
        elif match["b"]:
            words = f" mit {a} und {_number(match['b'])} Freiheitsgraden"
        else:
            words = f" mit {a} {_degrees(match['a'])}"
        found.append(
            Candidate(
                start,
                end,
                words,
                f'degrees of freedom "{text[start:end]}" read as "{words.strip()}"',
            )
        )
    return found


def _degrees(number: str) -> str:
    return "Freiheitsgrad" if number == "1" else "Freiheitsgraden"


def _squared(text: str, plain: str) -> list[Candidate]:
    found = []
    for match in _SQUARED.finditer(plain):
        if match["two"] and not _THEN_OPERATOR_OR_DF.match(plain, match.end()):
            continue
        partial = bool(match["p1"] or match["p2"])
        if partial and match["name"] != "η":
            continue
        words = ("partielles " if partial else "") + _SQUARED_NAMES[match["name"]]
        start, end = match.span()
        found.append(Candidate(start, end, words, f'"{text[start:end]}" read as "{words}"'))
    return found


def _confidence_intervals(text: str, plain: str) -> list[Candidate]:
    found = []
    for match, intervals in ci_runs_de(plain):
        start, end = match.span()
        if plain[start - 1 : start] == "-" and _AFTER_PERCENT.search(
            plain, max(0, start - _WINDOW), start
        ):
            start -= 1  # "95 %-KI" reads "95 % Konfidenzintervall"
        words = "Konfidenzintervalle" if match["plural"] else "Konfidenzintervall"
        reading = padded(text, start, end, words)
        if start == match.start():
            # "Jh.CI", "1 %KI", "1<CI": no space after a sign, which would have the
            # abbreviations step read "Jh.", the units step "1 %" or the "<" read on a second
            # run but not on the first
            reading = reading.lstrip()
        found.append(Candidate(start, end, reading, f'"{text[start:end]}" read as "{words}"'))
        found += [_interval(text, interval) for interval in intervals]
    return found


def ci_runs_de(plain: str) -> Iterator[tuple[re.Match[str], list[re.Match[str]]]]:
    """Each "KI" or "CI" read as words, with the intervals read after it (as `_ci_runs` in
    statistics.py, with German number pairs)."""
    for match in _CI.finditer(plain):
        start, end = match.span()
        after_percent = bool(_AFTER_PERCENT.search(plain, max(0, start - _WINDOW), start))
        if not after_percent and not _BEFORE_CI_THING.match(plain, end):
            continue
        intervals = []
        interval = _INTERVAL.match(plain, end)
        while interval is not None and len(intervals) < MAX_JOINED_INTERVALS:
            if unit_follows(plain, interval.end(), "de") or _JOINED_NUMBER.match(
                plain, interval.end()
            ):
                break  # "[1; 2] N", "[1; 2]–3": "1 bis 2 N" and "2 –3" would be read again
            intervals.append(interval)
            joined = _JOIN.match(plain, interval.end())
            interval = _INTERVAL.match(plain, joined.end()) if joined else None
        yield match, intervals


def _interval(text: str, interval: re.Match[str]) -> Candidate:
    """The whole bracket read as "1 Komma 2 bis 3 Komma 4"."""
    start, end = interval.start("open"), interval.end("close")
    words = f"{say_decimal(interval['a'])} bis {say_decimal(interval['b'])}"
    reading = padded(text, start, end, words)
    if _FULL_STOP.match(text, end):
        reading = reading.rstrip()  # "[1,1; 4,8]." reads "4 Komma 8.", no space before it
    return Candidate(
        start, end, reading, f'confidence interval "{text[start:end]}" read as "{words}"'
    )


def _odds_ratios(plain: str) -> list[Candidate]:
    return [
        Candidate(m.start(), m.end(), "Odds Ratio", '"OR" read as "Odds Ratio"')
        for m in _ODDS_RATIO.finditer(plain)
    ]
