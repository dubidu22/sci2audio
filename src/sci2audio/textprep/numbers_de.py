# ruff: noqa: RUF001, RUF002, RUF003
# (minus signs, dashes and superscripts are what these rules are about)
"""German numbers the voice reads wrong (TP-09, TP-13, #130): the numbers step's German rules.

The German voice's front end (espeak-ng German, through misaki) reads plain whole numbers
well, "2019" and "10 000" too, but loses the decimal comma ("2,5" is "zwei fünf"), reads the
years 1100 to 1999 as counts, says nothing for ranges, ordinals, fractions, ratios and powers,
and breaks "1.234" (plans/v11-german-measure-misaki.txt). `find_numbers_de` proposes a
`replace` edit only for those; digits stay digits wherever the voice reads them, and each
reason quotes the printed text (in English, as every reason in the report).

- N-de-1 (D-478): decimals "2,45" read "2 Komma 4 5", the digits after the comma one by one;
  a point decimal after a comparison sign, or with a leading point ("r = .45"), the same; a
  point after a label word ("Abschnitt 2.5") reads "Punkt". Any other point is left as printed.
- N-de-2: thousands points "1.234" read "1234".
- N-de-3 (D-479): 1100 to 1999 read as a year, "19 hundert 98", after a year word; "1990er".
- N-de-4: ranges read "bis".
- N-de-5, N-de-6: ordinals and dates with the ending the word before asks for ("am 3. Mai" is
  "am dritten Mai", "12.03.2019" "zwölfter März 2019", "2019-03-12" the same).
- N-de-7: fractions "1/2" "ein halb", "2/3" "2 Drittel", "17/20" "17 von 20".
- N-de-8: ratios "3:1" "3 zu 1"; times "13:30 Uhr" "13 Uhr 30".
- N-de-9: powers "10⁶" "10 hoch 6", "x²" "x Quadrat".
- N-de-10: Roman numerals after a keyword ("Kapitel IV" is "Kapitel 4").

The statistics step reads the comparison signs (statistics_de.py); units, %, ×, ≈ and µ are
the units step's (#113).

Every rule decides the same on the printed text and on the script a run made of it, so a second
run changes nothing. Where a reading would give another rule or step something new to read, the
number is left as printed: before a unit or an "x" the units step leaves alone
(`_unit_left_alone`, `_x_left_alone`), before a dash, colon or slash that joins it to another
number, and in a label's run that is left as printed. A full stop that ends a word counts as a
space (`_STOP`), since the abbreviations step reads "Abb.1:1" as "Abbildung 1:1".
"""

from __future__ import annotations

import calendar
import re

from sci2audio.textprep.notation import Candidate, fold, pick, unit_follows, unit_starts_at
from sci2audio.textprep.statistics_de import OPERATORS_DE
from sci2audio.textprep.units import reads_unit_after, reads_x_after

# every look back before a match reads at most this many characters (linear on long blocks)
WINDOW = 64

# --- number words ----------------------------------------------------------------------------
_ONES = ("", "ein", "zwei", "drei", "vier", "fünf", "sechs", "sieben", "acht", "neun")
_TEENS = (
    "zehn",
    "elf",
    "zwölf",
    "dreizehn",
    "vierzehn",
    "fünfzehn",
    "sechzehn",
    "siebzehn",
    "achtzehn",
    "neunzehn",
)
_TENS = ("", "", "zwanzig", "dreißig", "vierzig", "fünfzig", "sechzig", "siebzig", "achtzig")
_TENS += ("neunzig",)
# the ordinal stems that are not the number word and "st"
_ORDINAL_STEMS = {1: "erst", 3: "dritt", 7: "siebt", 8: "acht"}
MAX_ORDINAL = 999_999

MONTHS = (
    "Januar",
    "Februar",
    "März",
    "April",
    "Mai",
    "Juni",
    "Juli",
    "August",
    "September",
    "Oktober",
    "November",
    "Dezember",
)
_MONTH_FORMS = frozenset(
    {*MONTHS, "Jänner", "Jan", "Feb", "Febr", "Mär", "Apr", "Jun", "Jul", "Aug", "Sep"}
    | {"Sept", "Okt", "Nov", "Dez"}
)


def _below_hundred(n: int) -> str:
    if n < 10:
        return _ONES[n]
    if n < 20:
        return _TEENS[n - 10]
    tens, ones = divmod(n, 10)
    return f"{_ONES[ones]}und{_TENS[tens]}" if ones else _TENS[tens]


def _below_thousand(n: int) -> str:
    hundreds, rest = divmod(n, 100)
    head = f"{_ONES[hundreds] if hundreds > 1 else ''}hundert" if hundreds else ""
    return head + _below_hundred(rest)


def _cardinal(n: int) -> str:
    """The number word of 0 < n < 1 000 000 as it starts a compound ("ein", not "eins")."""
    thousands, rest = divmod(n, 1000)
    head = f"{_below_thousand(thousands) if thousands > 1 else ''}tausend" if thousands else ""
    return head + _below_thousand(rest)


def ordinal(n: int, ending: str) -> str:
    """The ordinal word of 1 to 999 999 with its ending: ordinal(3, "en") is "dritten"."""
    if not 0 < n <= MAX_ORDINAL:
        raise ValueError(f"no German ordinal for {n}")
    last = n % 100
    head = _cardinal(n - last) if n - last else ""
    if last == 0:
        stem = head + "st"
    elif last < 20:
        stem = head + _ORDINAL_STEMS.get(last, (_ONES + _TEENS)[last] + "t")
    else:
        stem = head + _below_hundred(last) + "st"
    return stem + ending


def year_words(year: int) -> str:
    """A year as German says it: 1100 to 1999 in hundreds ("19 hundert 98"), else digits."""
    if 1100 <= year <= 1999:
        hundreds, rest = divmod(year, 100)
        return f"{hundreds} hundert {rest}" if rest else f"{hundreds} hundert"
    return str(year)


# --- context words ---------------------------------------------------------------------------
_PREVIOUS_WORD = re.compile(r"(?P<word>[^\W\d_]+)(?P<dot>\.)?\s+\Z")
_NEXT_WORD = re.compile(r"\s+(?P<word>[^\W\d_]+)(?P<dot>\.)?")
# words before a number that make it a year whatever follows (D-479)
_YEAR_WORDS = frozenset(
    {"jahr", "jahre", "jahres", "jahren", "jahrs", "frühjahr", "frühling", "sommer", "herbst"}
    | {"winter", "wintersemester", "sommersemester", "ws", "ss", "wise", "sose"}
    | {month.lower() for month in _MONTH_FORMS}
)
# words before a number that make it a year unless a noun follows ("seit 1998 gibt es", but
# "um 1500 Teilnehmer")
_MAYBE_YEAR_WORDS = frozenset(
    {"seit", "bis", "ab", "um", "von", "zwischen", "im", "anfang", "mitte", "ende"}
)
# "zwischen 1990 und 1995": a number joined on to a year is a year too
_DIGIT_BEFORE = re.compile(r"\d\s*\Z")
# a "bis" a range made: after a number, or after "Uhr" ("13 Uhr–1234")
_RANGE_BEFORE = re.compile(r"(?:\d|\bUhr)\s*\Z")
_JOINED_YEAR = re.compile(r"(?:\s*[\u2013\u2012-]\s*|\s+(?:und|oder|bis|bzw\.)\s+)\Z")
_JOINED_NEXT = re.compile(
    r"(?:\s*[\u2013\u2012-]\s*|\s+(?:und|oder|bis|bzw\.)\s+)(?:1[1-9]\d\d|\d{1,2}\.\d{3})(?![\d.,])"
)


def _before(text: str, at: int) -> str:
    return text[max(0, at - WINDOW) : at]


def _is_year(text: str, start: int, end: int, years: list[tuple[int, int]]) -> bool:
    """True if the number at start:end is read as a year (N-de-3)."""
    before = _before(text, start)
    joined = [end_ for _, end_ in years if end_ <= start]
    if joined and _JOINED_YEAR.fullmatch(text, joined[-1], start):
        return True
    previous = _PREVIOUS_WORD.search(before)
    if previous is None:
        return False
    word = previous["word"].lower()
    if word in _YEAR_WORDS:
        return True
    if word not in _MAYBE_YEAR_WORDS or previous["dot"]:
        return False
    if word == "bis" and _RANGE_BEFORE.search(before, 0, previous.start()):
        return False  # "1 bis 1234": a range ("1–1234" on the first run), not "bis 1998"
    # "zwischen 1234 und 1567 Probanden": the word after the last number of a joined run
    # decides for the whole run, as on a second run, where "1234 und" has no year before it
    while joined_next := _JOINED_NEXT.match(text, end):
        end = joined_next.end()
    if unit_follows(text, end, "de"):
        return False  # "seit 1998 %": the units step's ("1998 Prozent", a capital after it)
    following = _NEXT_WORD.match(text, end)
    # "seit 1998x" is "seit 1998 mal" after the units step, which a second run reads alike
    return following is None or not (following["word"][0].isupper() or following["word"] == "mal")


# not after a full stop, but for one that ends a word: the abbreviations step reads "Abb.1:1"
# as "Abbildung 1:1", so a second run must decide as the first ("x.5" is the variable x).
# Rules that look for a letter before a number let an "x" stand there ("1x1:1"), since the
# units step may read it "mal".
_STOP = (
    r"(?:(?<!\.)|(?<=[^\W\d_xX]\.)|(?<=[^\W\d_][xX]\.)"
    # after a power too: "5 m^2.45:1" is "5 Quadratmeter.45:1" after the units step
    r"|(?<=\^\d\.)|(?<=\^\d\d\.)|(?<=\}\.)|(?<=[⁰¹²³⁴⁵⁶⁷⁸⁹]\.)"
    # and after "×", which the units step reads "mal"
    r"|(?<=×\.))"
)

# --- N-de-1, N-de-2 decimals and thousands ---------------------------------------------------
_COMMA_DECIMAL = re.compile(
    r"(?<![,/^])"
    + _STOP
    + r"(?<![^\WxX])(?P<whole>\d{1,3}(?:\.\d{3})+|\d+),(?P<fraction>\d+)(?![\d_]|[⁺⁻^]|[.,/]\d)"
)
# a point decimal after a comparison sign (a minus may stand between) or a leading point; the
# sign as the statistics step reads it counts too, so a second run decides the same
_SIGN_BEFORE = re.compile(
    "(?:["
    + re.escape("".join({key[0] for key in OPERATORS_DE} | {"\u0338"}))
    + "]|"
    + "|".join(
        sorted(
            (rf"\b{re.escape(words)}" for words in set(OPERATORS_DE.values())),
            key=len,
            reverse=True,
        )
    )
    + r")\s*[\u2212-]?\Z"
)
# not before a ratio or fraction: ".5:1" read "0 Komma 5:1" would be a ratio on a second run
_POINT_DECIMAL = re.compile(
    r"(?<![.,/:^])(?<![^\WxX])(?P<whole>\d*)\.(?P<fraction>\d+)"
    r"(?![^\WxX]|[⁺⁻^]|[.,:/]\d|-\n?\d)"
)
_X_AFTER = re.compile(r" ?[xX]")
_LINE_END_HYPHEN = re.compile(r"[-\u2010\u2011]\n\Z")
_COUNT_LETTER = re.compile(r"(?<![\w′'])[Nn]\s*(?:=|gleich)\s*\Z")
# a letter after the number does not stop these: "1.234x" and "1.234Å" are read when the units
# step reads the "x" or the unit, and left as printed when it does not
_THOUSANDS = re.compile(
    r"(?<![,/:^])" + _STOP + r"(?<![^\WxX])\d{1,3}(?:\.\d{3})+(?![\d_]|[⁺⁻^]|[.,:/]\d)"
)

# words after which a point between numbers is read "Punkt": "Abschnitt 2.5", "Abb. 3.1"
_LABELS = frozenset(
    {"abschnitt", "abschnitte", "abschnitten", "kapitel", "kapiteln", "version", "tabelle"}
    | {"tabellen", "abbildung", "abbildungen", "gleichung", "gleichungen", "formel", "anhang"}
    | {"hypothese", "hypothesen", "studie", "experiment", "teil", "schritt", "unterkapitel"}
    | {"ziffer", "nummer", "punkt", "satz", "regel", "definition", "beispiel", "modell"}
)
_SHORT_LABELS = frozenset({"abb", "tab", "kap", "abschn", "gl", "nr", "anh", "bsp", "def"})
_LABEL_RUN = re.compile(
    r"(?<!\w)(?P<label>[^\W\d_]+)(?P<dot>\.)?(?(dot)\s*|\s+)(?P<run>\d+(?:\.\d+)+"
    r"(?:\s*(?:und|oder|bis|[\u2013-])\s*\d+(?:\.\d+)+)*)(?![^\WxX]|[.,]\d)"
)
_POINT = re.compile(r"\.")
# a number joined after a label's number by a colon, slash or hyphen (an en dash is a range,
# read "bis" in the same run), by a digit or by a power
_LABEL_JOINED_AFTER = re.compile(r"\s*[:/-]\s*[.,]?\d|[.,]?\d|[⁺⁻^⁰¹²³⁴⁵⁶⁷⁸⁹]")


def _decimals(text: str) -> list[Candidate]:
    found = []
    for match in _COMMA_DECIMAL.finditer(text):
        if _x_left_alone(text, match.end()) or _unit_left_alone(text, match.end()):
            continue
        if _GLUED_MINUS.match(text, max(0, match.start() - 2), match.start()):
            continue  # "10−412,5": an exponent or a sum, not "minus 412 Komma 5" on its own
        ratio = _RATIO_BEFORE.search(text, max(0, match.start() - 16), match.start())
        if ratio is not None and not _ratio_at(text, ratio.start()):
            continue  # "1:2,5:", "11:2,5 N": the ratio is left as printed, so is its number
        if _HYPHEN_AFTER.match(text, match.end()) and not _hyphen_range_at(text, match.start()):
            continue  # "1,0-1" is no range ("3-1" is a score); "1 Komma 0-1" would be one
        if re.match(r":[.,]?\d", text[match.end() : match.end() + 3]) and not _ratio_at(
            text, match.start()
        ):
            continue  # "2,51:1" after "1:": no ratio is read there, so the number stays too
        whole = match["whole"].replace(".", "")
        words = f"{whole} Komma {' '.join(match['fraction'])}"
        found.append(Candidate(*match.span(), words, _decimal_reason(match.group(), words)))
    for match in _POINT_DECIMAL.finditer(text):
        if _x_left_alone(text, match.end()) or _unit_left_alone(text, match.end()):
            continue
        whole, fraction = match["whole"], match["fraction"]
        before = _before(text, match.start())
        if whole and not _SIGN_BEFORE.search(before):
            continue  # "2.5" in running text: a decimal, a date or a version; left as printed
        if not whole and _LINE_END_HYPHEN.search(before):
            continue  # "1-\n.45": the hyphen step decides by the "." after the line break
        if whole and whole != "0" and len(fraction) == 3 and _COUNT_LETTER.search(before):
            continue  # "N = 1.234": a count with a thousands point (N-de-2)
        words = f"{whole or '0'} Komma {' '.join(fraction)}"
        found.append(Candidate(*match.span(), words, _decimal_reason(match.group(), words)))
    return found


def _x_left_alone(text: str, end: int) -> bool:
    """True if an "x" follows the number that the units step leaves as printed: then so is
    the number ("2,5x" is read "2 Komma 5 mal" only when the units step reads the x)."""
    return _X_AFTER.match(text, end) is not None and not reads_x_after(text, end, "de")


def _unit_left_alone(text: str, end: int) -> bool:
    """True if a unit follows the number that the units step leaves as printed ("Kapitel
    2,55 m"): read "2 Komma 5 5 m", a second run would read "5 m" as "5 Meter"."""
    return (
        unit_follows(text, end, "de")
        and not reads_unit_after(text, end, "de")
        and not reads_x_after(text, end, "de")  # "12,5x": the x is "mal", no unit
    )


_RATIO_BEFORE = re.compile(r"(?<![\d,])\d+(?:,\d+)?:\Z")
_HYPHEN_AFTER = re.compile(r"-\n?\d")


def _hyphen_range_at(text: str, start: int) -> bool:
    """True if `_ranges` reads the hyphen range that starts at `start`."""
    match = _HYPHEN_RANGE.match(text, start)
    if match is None or _x_left_alone(text, match.end()):
        return False
    if match["a"].count(".") == 1 and _SIGN_BEFORE.search(_before(text, start)):
        return False  # "= 1.234-1998": a point decimal, left as printed with what joins it
    return _value(match["a"]) < _value(match["b"])


def _ratio_at(text: str, start: int) -> bool:
    """True if `_ratios` reads the ratio that starts at `start`."""
    match = _RATIO.match(text, start)
    return match is not None and not _unit_left_alone(text, match.end())


def _decimal_reason(printed: str, words: str) -> str:
    return f'decimal "{printed}" read as "{words}"'


def _labelled(text: str) -> tuple[list[Candidate], list[tuple[int, int]]]:
    """The points of a label's numbers read "Punkt", and the label runs left as printed."""
    found = []
    kept = []
    for match in _LABEL_RUN.finditer(text):
        label = match["label"].lower()
        if not (label in _SHORT_LABELS if match["dot"] else label in _LABELS):
            continue
        end = match.end("run")
        if (
            _LABEL_JOINED_AFTER.match(text, end)
            or _x_left_alone(text, end)
            or _unit_left_alone(text, end)
        ):
            kept.append(match.span("run"))
            continue  # "Abschnitt 2.51:1": the new digits would join differently next time
        offset = match.start("run")
        for point in _POINT.finditer(match["run"]):
            start = offset + point.start()
            found.append(
                Candidate(
                    start,
                    start + 1,
                    " Punkt ",
                    f'"." in "{match["run"]}" after "{match["label"]}" read as "Punkt"',
                )
            )
    return found, kept


def _thousands(text: str) -> list[Candidate]:
    found = []
    for match in _THOUSANDS.finditer(text):
        if _x_left_alone(text, match.end()) or _unit_left_alone(text, match.end()):
            continue  # "1.234abc"; "1.234Å" is read, as the units step reads the unit
        number = match.group()
        value = int(number.replace(".", ""))
        # a year word before it, not a year joined by a dash: "im 1234–1.234" reads "12 hundert
        # 34 bis 1234", where a second run sees no year before "1234" either
        if 1100 <= value <= 1999 and _is_year(text, *match.span(), []):
            # "von 1.500 auf", "um 1.200": read as "15 hundert", which a second run leaves
            # alone; read "1500", a second run would see a year there (D-479)
            words = year_words(value)
            found.append(
                Candidate(*match.span(), words, f'"{number}" read as "{words}" after a year word')
            )
            continue
        before = _before(text, match.start())
        if (
            number.count(".") == 1
            and _SIGN_BEFORE.search(before)
            and not _COUNT_LETTER.search(before)
        ):
            continue  # "M = 2.345": a point decimal, read by N-de-1 (or left as printed)
        words = number.replace(".", "")
        found.append(Candidate(*match.span(), words, f'"{number}" read as the number "{words}"'))
    return found


# --- N-de-3 years ----------------------------------------------------------------------------
# not before a ratio, printed or read ("1234:1" is "1234 zu 1" after the first run)
_YEAR = re.compile(
    r"(?<![^\WxX])(?<![,/:^\u2212-])" + _STOP + r"(?P<year>1[1-9]\d\d)(?P<er>er)?"
    r"(?![^\WxX]|[/:]|[.,]\d|\s+zu\s+[.,]?\d)"
)
_DECADE = re.compile(
    r"(?<![^\WxX])(?<![,/:^\u2212])" + _STOP + r"(?P<year>1[1-9]\d0)er(?![^\W\d_])"
)


def _years(text: str) -> list[Candidate]:
    found = []
    spans: list[tuple[int, int]] = []
    for match in _DECADE.finditer(text):
        start, end = match.span("year")
        words = year_words(int(match["year"]))
        found.append(Candidate(start, end, words, f'decade "{match.group()}" read as "{words}er"'))
        spans.append((start, end))
    for match in _YEAR.finditer(text):
        if match["er"]:
            continue  # a decade, above
        start, end = match.span("year")
        if not _is_year(text, start, end, spans) or _x_left_alone(text, end):
            continue
        words = year_words(int(match["year"]))
        found.append(Candidate(start, end, words, f'year "{match["year"]}" read as "{words}"'))
        spans.append((start, end))
        spans.sort()
    return found


# --- N-de-4 ranges ---------------------------------------------------------------------------
# after a time too: "13:30 Uhr–15:00 Uhr" reads "13 Uhr 30 bis 15 Uhr"
# after a number's power: "10⁶–10⁷" is "10 hoch 6 bis 10 hoch 7" ("x²–1" is a formula)
_RAISED = "[⁰¹²³⁴⁵⁶⁷⁸⁹]"
_AFTER_POWER = "|".join(
    f"(?<=\\d{sign}{_RAISED}{{{count}}})" for sign in ("", "[⁺⁻]") for count in (1, 2)
)
_DASH_RANGE = re.compile(
    r"(?:(?<=\d)|(?<=\bUhr)|"
    + _AFTER_POWER
    + r")(?P<dash>\s*[\u2013\u2012]\s*|\u2014)(?=[\u2212-]?[.,]?\d)"
)
_HYPHEN_RANGE = re.compile(
    r"(?<![^\WxX])(?<![,/:^\u2212-])"
    + _STOP
    + r"(?<!-\n)(?P<a>\d{1,3}(?:\.\d{3})+|\d{1,4}(?:,\d+)?)(?P<dash>-\n?)"
    r"(?P<b>\d{1,3}(?:\.\d{3})+|\d{1,4}(?:,\d+)?)"
    r"(?![^\WxX]|[/:-]|[.,]\d)"
)
_LEFT_NUMBER = re.compile(r"[\d.,]*\d\Z")
_RIGHT_NUMBER = re.compile(r"[\u2212-]?[\d.,]*\d")


def _ranges(text: str) -> list[Candidate]:
    found = []
    for match in _DASH_RANGE.finditer(text):
        start, end = match.span("dash")
        if _FILE_AFTER.match(text, end):
            continue  # "15.12.1983 – 1 BvR 209/83": the dash leads to a court's file number
        found.append(Candidate(start, end, " bis ", _range_reason(text, start, end)))
    for match in _HYPHEN_RANGE.finditer(text):
        if not _hyphen_range_at(text, match.start()):
            continue  # "3-1" is a score or a code, not a range
        start, end = match.span("dash")
        found.append(Candidate(start, end, " bis ", _range_reason(text, start, end)))
    return found


def _value(number: str) -> float:
    return float(number.replace(".", "").replace(",", "."))


def _range_reason(text: str, start: int, end: int) -> str:
    left = _LEFT_NUMBER.search(_before(text, start))
    right = _RIGHT_NUMBER.match(text, end)
    printed = (left.group() if left else "") + text[start:end] + (right.group() if right else "")
    return f'range "{" ".join(printed.split())}" read with "bis"'


# --- N-de-5, N-de-6 ordinals and dates ------------------------------------------------------
# the ending of an ordinal after these words ("am dritten", "die dritte")
_WEAK_EN = frozenset(
    {"den", "dem", "des", "am", "im", "vom", "zum", "zur", "beim", "einem", "einen", "einer"}
    | {"eines"}
)
_WEAK_E = frozenset({"die", "das", "ins", "ans", "aufs", "fürs", "ums"})
# "der" is "dritte" ("der 3. Platz"), after a preposition "dritten" ("in der 3. Auflage")
_PREPOSITIONS = frozenset(
    {"in", "an", "auf", "aus", "bei", "mit", "nach", "seit", "von", "zu", "vor", "hinter"}
    | {"über", "unter", "neben", "zwischen", "während", "wegen", "trotz", "gemäß", "laut"}
    | {"bis", "ab", "außer", "innerhalb", "außerhalb"}
)
# nouns read after an ordinal with no article before it, by gender: "1. Auflage" is "erste
# Auflage", "20. Jahrhundert" "zwanzigstes Jahrhundert", "2. Weltkrieg" "zweiter Weltkrieg"
_NOUN_ENDINGS = {
    **dict.fromkeys(
        [
            "Weltkrieg",
            "Platz",
            "Rang",
            "Schritt",
            "Tag",
            "Monat",
            "Teil",
            "Band",
            "Versuch",
            "Durchgang",
            "Messzeitpunkt",
            "Termin",
            "Fall",
            "Grad",
            "Abschnitt",
            "Satz",
        ],
        "er",
    ),
    **dict.fromkeys(
        [
            "Auflage",
            "Ausgabe",
            "Klasse",
            "Stelle",
            "Sitzung",
            "Welle",
            "Messung",
            "Stufe",
            "Runde",
            "Woche",
            "Hälfte",
            "Hypothese",
            "Generation",
            "Ordnung",
            "Wahl",
            "Lesung",
            "Instanz",
            "Person",
            "Version",
            "Studie",
            "Liga",
            "Phase",
            "Ebene",
        ],
        "e",
    ),
    **dict.fromkeys(
        [
            "Jahrhundert",
            "Jh",
            "Jahrtausend",
            "Mal",
            "Lebensjahr",
            "Semester",
            "Quartal",
            "Kapitel",
            "Experiment",
            "Jahr",
            "Schuljahr",
            "Halbjahr",
            "Treffen",
            "Gesetz",
        ],
        "es",
    ),
}
_ORDINAL = re.compile(r"(?<![^\WxX])(?<![,/:\u2013-])" + _STOP + r"(?P<n>\d{1,6})\.(?=\s+[^\W\d_])")
_ISO_DATE = re.compile(
    r"(?<![^\WxX])(?<![:/\u2013-])(?<!\d,)"
    + _STOP
    + r"(?P<y>1[5-9]\d\d|20\d\d)-\n?(?P<m>0[1-9]|1[0-2])-\n?(?P<d>0[1-9]|[12]\d|3[01])"
    r"(?![^\WxX]|[⁺⁻^-]|[.,:/]\d)"
)
_NUMERIC_DATE = re.compile(
    r"(?<![^\WxX])(?<![,/:\u2013-])"
    + _STOP
    + r"(?P<d>0?[1-9]|[12]\d|3[01])\.(?P<m>0?[1-9]|1[0-2])\."
    r"(?:(?P<y>1[5-9]\d\d|20\d\d)(?![^\WxX]|[⁺⁻^]|[.,:/]\d)|(?![\w.,]|\s*\d))"
)


def _year_left_alone(text: str, end: int) -> bool:
    """True if a reading that ends in the year is not read: before a unit or an "x" the units
    step leaves as printed ("2019 N" would be the units step's on a second run)."""
    return _unit_left_alone(text, end) or _x_left_alone(text, end)


def _ending(text: str, start: int, *, day: bool = False) -> str | None:
    """The ending an ordinal at `start` takes from the word before it, if one decides it."""
    before = _before(text, start)
    previous = _PREVIOUS_WORD.search(before)
    if previous is not None and previous["dot"] and previous["word"] == "v":
        return "en"  # "BGH v. 22.06.2011": "v." is "vom"
    if previous is None or previous["dot"]:
        return "er" if day else None
    word = previous["word"].lower()
    if word in _WEAK_EN:
        return "en"
    if word in _WEAK_E:
        return "e"
    if word == "der":
        earlier = _PREVIOUS_WORD.search(before, 0, previous.start())
        return "en" if earlier and earlier["word"].lower() in _PREPOSITIONS else "e"
    if day and word == "bis":
        return "en"  # "vom 3. bis 5. Mai"
    if word in _PREPOSITIONS:
        return None  # "in 3. Auflage": the case is not known
    return "er" if day else None


def _after_preposition(text: str, start: int) -> bool:
    previous = _PREVIOUS_WORD.search(_before(text, start))
    return previous is not None and previous["word"].lower() in _PREPOSITIONS


def _date_words(text: str, start: int, day: int, month: int, year: str | None) -> str | None:
    ending = _ending(text, start, day=True)
    if ending is None:
        return None
    words = f"{ordinal(day, ending)} {MONTHS[month - 1]}"
    return f"{words} {year_words(int(year))}" if year else words


def _dates(text: str) -> list[Candidate]:
    found = []
    for match in _ISO_DATE.finditer(text):
        year, month, day = int(match["y"]), int(match["m"]), int(match["d"])
        if day > calendar.monthrange(year, month)[1]:
            continue
        words = _date_words(text, match.start(), day, month, match["y"])
        if words and not _year_left_alone(text, match.end()):
            found.append(_date(match, words))
    for match in _NUMERIC_DATE.finditer(text):
        day, month = int(match["d"]), int(match["m"])
        year = int(match["y"]) if match["y"] else 2000  # 29.2. without a year may be any year
        if day > calendar.monthrange(year, month)[1]:
            continue
        if not match["y"] and _ending(text, match.start()) is None:
            continue  # "3.4." alone is a list or a version; "am 3.4." is a date
        words = _date_words(text, match.start(), day, month, match["y"])
        if words and not _year_left_alone(text, match.end()):
            found.append(_date(match, words))
    return found


def _date(match: re.Match[str], words: str) -> Candidate:
    return Candidate(*match.span(), words, f'date "{match.group()}" read as "{words}"')


# the digits of a decimal read in words ("0 Komma 0 5"): no ordinal ends them ("5. Jahr")
_AFTER_KOMMA = re.compile(r"\bKomma(?: \d)* \Z")


def _ordinals(text: str) -> list[Candidate]:
    found = []
    for match in _ORDINAL.finditer(text):
        n = int(match["n"])
        if not 0 < n <= MAX_ORDINAL:
            continue
        if _AFTER_KOMMA.search(text, max(0, match.start() - WINDOW), match.start()):
            continue  # "0 Komma 0 5. Jahr": the decimal ".05" read, not an ordinal
        previous = _PREVIOUS_WORD.search(_before(text, match.start()))
        if previous is not None and previous["word"] in _MONTH_FORMS:
            continue  # "März 2019. Auflage": a date's year (read from "12.03.2019. Auflage")
        following = _NEXT_WORD.match(text, match.end())
        if following is None:  # unreachable: the pattern looks for a word after it
            continue
        noun = following["word"]
        month = noun in _MONTH_FORMS and (noun in MONTHS or following["dot"])
        ending = _ending(text, match.start(), day=month)
        if ending is None and not _after_preposition(text, match.start()):
            ending = _NOUN_ENDINGS.get(noun) if noun != "Jh" or following["dot"] else None
        if ending is None:
            continue  # "Es waren 3. Die Studie": no article and no known noun
        if month and n > 31:
            continue
        words = ordinal(n, ending)
        found.append(
            Candidate(*match.span(), words, f'ordinal "{match.group()}" read as "{words}"')
        )
    return found


# --- N-de-7 fractions, N-de-8 ratios and times ----------------------------------------------
_FRACTION = re.compile(
    r"(?<![^\WxX])(?<![,/:\u2212-])"
    + _STOP
    + r"(?<!-\n)(?P<n>\d{1,3})/(?P<d>\d{1,3})(?![^\WxX]|[/:⁺⁻^-]|[.,]\d)"
)
_FRACTION_WORDS = {
    2: "halb",
    3: "Drittel",
    4: "Viertel",
    5: "Fünftel",
    6: "Sechstel",
    7: "Siebtel",
    8: "Achtel",
    9: "Neuntel",
    10: "Zehntel",
}
# a number joined to the next one by a dash, colon or slash, by a space, by nothing at all
# ("10⁶3"), or by a word this step reads a dash, colon or slash with
_JOINED_AFTER = re.compile(
    r"\s*[\u2013\u2014\u2012:/-]\s*[.,]?\d|[.,]?\d|\s\d|\s+(?:bis|zu|von)\s+[.,]?\d"
    r"|[⁺⁻^⁰¹²³⁴⁵⁶⁷⁸⁹]"
)
_UNSIGNED = r"\d+(?:,\d+)?"
_RATIO = re.compile(
    r"(?<![^\WxX])(?<![:/,^\u2212-])"
    + _STOP
    + r"(?<!-\n)(?P<a>"
    + _UNSIGNED
    + r"):(?P<b>"
    + _UNSIGNED
    + r")"
    r"(?![^\WxX]|[:/^⁺⁻]|[.,]\d|-\n?\d|\s+Uhr\b)"
)
_TIME = re.compile(
    r"(?<![^\WxX])(?<![:/,-])"
    + _STOP
    + r"(?P<h>[01]?\d|2[0-4])[:.](?P<m>[0-5]\d)(?P<uhr>\s+Uhr\b)?(?![^\WxX]|[:/^⁺⁻]|[.,]\d)"
)
_TIME_BEFORE = re.compile(r"\b(?:um|ab|gegen|von|bis|zwischen|seit|und)\s+\Z", re.IGNORECASE)


# a letter power after the number: "1/5 m⁶" is left as printed, since "m⁶" after "5 " is
# (`_LETTER_POWER`), after "Fünftel " it is not
_LETTER_POWER_AFTER = re.compile(r"\s[^\W\d_][⁺⁻]?[⁰¹²³⁴⁵⁶⁷⁸⁹]")


def _fractions(text: str) -> list[Candidate]:
    found = []
    for match in _FRACTION.finditer(text):
        if _x_left_alone(text, match.end()) or (
            _LETTER_POWER_AFTER.match(text, match.end())
            and not _STATISTICS_SQUARE.match(text, match.end() + 1)
        ):
            continue  # "1/5 m⁶"; "1/5 R²" is read, the statistics step reads "R²"
        n, d = int(match["n"]), int(match["d"])
        if n > d or d == 0:
            continue  # "24/7", "3/2": no reading that is right everywhere
        if d in _FRACTION_WORDS and 0 < n < d and not _JOINED_AFTER.match(text, match.end()):
            if n == 1:  # "ein halb", "ein Drittel": the voice says "eins" for a lone "1"
                words = f"ein {_FRACTION_WORDS[d]}"
                start = match.start()
            elif d == 2:  # unreachable: 0 < n < 2
                continue
            else:
                words = f" {_FRACTION_WORDS[d]}"
                start = match.end("n")
            reading = f"{n if n > 1 else ''}{words}".strip()
            found.append(
                Candidate(
                    start, match.end(), words, f'fraction "{match.group()}" read as "{reading}"'
                )
            )
            continue
        if _unit_left_alone(text, match.end()):
            continue  # "17/20 g": "20 g" would be the units step's on a second run
        start = match.end("n")
        found.append(
            Candidate(start, start + 1, " von ", f'"{match.group()}" read as "{n} von {d}"')
        )
    return found


def _times(text: str) -> list[Candidate]:
    found = []
    for match in _TIME.finditer(text):
        if not (
            match["uhr"] or (match.group()[len(match["h"])] == ":" and _time_before(text, match))
        ):
            continue
        if _unit_left_alone(text, match.end()) or _x_left_alone(text, match.end()):
            continue  # "um 13:30 N": read "13 Uhr 30 N", a second run would read "30 N"
        hours, minutes = int(match["h"]), int(match["m"])
        words = f"{hours} Uhr {minutes}" if minutes else f"{hours} Uhr"
        found.append(Candidate(*match.span(), words, f'time "{match.group()}" read as "{words}"'))
    return found


def _time_before(text: str, match: re.Match[str]) -> bool:
    """True after "um", "ab", "bis" and the like; not after "bis" or "und" that join it to a
    number before ("1–11:12" reads "1 bis 11:12", and a second run must not see a time)."""
    before = _before(text, match.start())
    word = _TIME_BEFORE.search(before)
    if word is None:
        return False
    joining = word.group().split()[0].lower() in ("bis", "und")
    return not (joining and _DIGIT_BEFORE.search(before, 0, word.start()))


def _ratios(text: str) -> list[Candidate]:
    found = []
    for match in _RATIO.finditer(text):
        # unlike English, "8:64–77" (a volume and its pages) is read as a ratio too: a rule that
        # skipped it before "bis 12.03.2019" would read it on a second run, after the date
        if _unit_left_alone(text, match.end()) or _x_left_alone(text, match.end()):
            continue  # "3:1 N": "1 N" would be the units step's on a second run
        start = match.end("a")
        words = f"{match['a']} zu {match['b']}"
        found.append(
            Candidate(start, start + 1, " zu ", f'ratio "{match.group()}" read as "{words}"')
        )
    return found


# --- N-de-9 powers --------------------------------------------------------------------------
_SUPERSCRIPTS = "⁰¹²³⁴⁵⁶⁷⁸⁹"
_SUPER_DIGIT = {char: str(n) for n, char in enumerate(_SUPERSCRIPTS)}
_SUPER = f"[⁺⁻]?[{_SUPERSCRIPTS}]+(?![⁺⁻^])"
_POWER_OF_TEN = re.compile(
    r"(?<![^\WxX])(?<![,^])" + _STOP + r"(?P<base>10)(?P<exp>" + _SUPER + ")"
)
_SIGNED_POWER = re.compile(
    r"(?<![^\WxX])(?<![,^])"
    + _STOP
    + r"(?P<base>\d+)(?P<exp>[⁺⁻]["
    + _SUPERSCRIPTS
    + "]+)(?![⁺⁻^])"
)
_CARET = re.compile(
    r"(?<![\w,])" + _STOP + r"(?P<base>\d+|[^\W\d_" + _SUPERSCRIPTS + r"])"
    r"(?P<exp>\^(?:\{(?P<braced>[+\u2212-]?\d+)\}|\((?P<paren>[+\u2212-]?\d+)\)|(?P<bare>[+\u2212-]?\d+)))"
    r"(?![\w.,⁺⁻])"
)
_TIMES_TEN = re.compile(r"(?<=\d)\s*[×x]\s*(?P<base>10)(?P<exp>[\u2212-]\d{1,3})(?![\w⁺⁻]|[.,]\d)")
_LETTER_POWER = re.compile(
    r"(?<![\w/])(?<!(?<!\^)\d\s)(?<!,\s)(?P<base>[^\W\d_"
    + _SUPERSCRIPTS
    + r"])(?P<exp>"
    + _SUPER
    + r")"
    r"(?![\w" + _SUPERSCRIPTS + "])"
)
_SQUARED_STATISTICS = frozenset("Rrηωεχ")  # the statistics step's ("R Quadrat")
_UNIT_CHAIN = re.compile(
    r"(?<![\w^.,])\d+(?:,\d+)?\s*(?:[^\W\d_"
    + _SUPERSCRIPTS
    + r"]{1,3}["
    + _SUPERSCRIPTS
    + r"⁺⁻]*[\s·⋅]+)+\Z"
)
# a squared name the statistics step reads ("1 η² x⁶" is "1 Eta-Quadrat x⁶"), not a unit
_STATISTICS_SQUARE = re.compile(r"(?<![^\W\d_])[Rrηωεχ]p?²")


def _unit_chain(plain: str, base: int) -> bool:
    """True if the letter power at `base` is a unit after a number and units ("s⁻¹" in "2 m
    s⁻¹"): the units step's. "x⁶" in "5 m² x⁶" is no unit, nor "η²" a unit before it."""
    if not unit_starts_at(plain, base, "de"):
        return False
    chain = _UNIT_CHAIN.search(_before(plain, base))
    return chain is not None and not _STATISTICS_SQUARE.search(chain.group())


# not the exponent of a letter ("x^2 x^2"), whose reading ends in a word
_NUMBER_BEFORE = re.compile(r"(?<!\d)(?<![^\W\d_]\^)\d+ \Z")
# not by a space alone, as in English: German has no rule that joins "5 10⁶" (numbers.py N10)
# ("1500–2001⁻⁴" reads "15 hundert bis 2001⁻⁴": a round year read in words joins it too)
_JOINED_BEFORE = re.compile(
    r"(?:\d|\bhundert)\s*(?:[\u2013\u2014\u2012:/-]|\s(?:bis|zu|von)\s)\s*\Z"
)
_GLUED_MINUS = re.compile(r"\d\u2212\Z")
# "x⁴–1" stays: read "x hoch 4–1", a second run would read "4–1" as a range
_DASH_DIGIT = re.compile(r"\s*[\u2013\u2014\u2012]\s*[\u2212-]?[.,]?\d")


def _exponent_words(exponent: str) -> str:
    digits = "".join(_SUPER_DIGIT.get(c, c) for c in exponent)
    if digits[:1] in "⁻\u2212-":
        return f"minus {digits[1:]}"
    return digits[1:] if digits[:1] in "⁺+" else digits


def _letter_power(exponent: str) -> str | None:
    return " Quadrat" if exponent == "2" else None


def _joined_before(text: str, at: int) -> bool:
    return bool(_JOINED_BEFORE.search(text, max(0, at - WINDOW), at))


def _powers(text: str, plain: str) -> list[Candidate]:
    found: list[tuple[Candidate, int | None]] = []
    for pattern in (_POWER_OF_TEN, _SIGNED_POWER, _TIMES_TEN):
        for match in pattern.finditer(text):
            words = f" hoch {_exponent_words(match['exp'])}"
            found.append((_power(text, match, words), match.start("base")))
    for match in _CARET.finditer(plain):
        exponent = match["braced"] or match["paren"] or match["bare"]
        letter = match["base"].isalpha()
        before = _before(plain, match.start("base"))
        if letter and (_unit_chain(plain, match.start("base")) or _NUMBER_BEFORE.search(before)):
            continue  # "5 m^2": the units step's ("5 Quadratmeter")
        words = (_letter_power(exponent) if letter else None) or (
            f" hoch {_exponent_words(exponent)}"
        )
        found.append((_power(text, match, words), None if letter else match.start("base")))
    for match in _LETTER_POWER.finditer(plain):
        if match["base"] in _SQUARED_STATISTICS and match["exp"] == "²":
            continue
        if _unit_chain(plain, match.start("base")):
            continue  # "2 m s⁻¹": the units step's
        exponent = "".join(_SUPER_DIGIT.get(c, c) for c in match["exp"])
        words = _letter_power(exponent) or f" hoch {_exponent_words(match['exp'])}"
        found.append((_power(text, match, words), None))
    # as in English (numbers.py): a power joined to a number after it, or a number base joined
    # to a number before it, is left as printed
    return [
        c
        for c, base in found
        if not _LABEL_JOINED_AFTER.match(text, c.end)
        and not (
            c.replacement[-1:].isdigit()
            and _DASH_DIGIT.match(text, c.end)
            and not _DASH_RANGE.match(text, c.end)
        )
        and not _unit_left_alone(text, c.end)
        and (
            base is None
            or not (_joined_before(text, base) or _GLUED_MINUS.match(text, max(0, base - 2), base))
        )
    ]


def _power(text: str, match: re.Match[str], words: str) -> Candidate:
    start, end = match.span("exp")
    printed = text[match.start("base") : end]
    return Candidate(start, end, words, f'power "{printed}" read with "{words.strip()}"')


# --- N-de-10 Roman numerals ------------------------------------------------------------------
_KEYWORDS = frozenset(
    {"kapitel", "teil", "teile", "band", "bände", "phase", "phasen", "typ", "typen", "klasse"}
    | {"klassen", "stufe", "stufen", "studie", "studien", "experiment", "experimente"}
    | {"anhang", "abschnitt", "tabelle", "tabellen", "abbildung", "abbildungen", "weltkrieg"}
)
_ABBREVIATED_KEYWORDS = frozenset({"abb", "tab", "kap", "abschn", "bd", "anh"})
_ROMAN = r"[IVX]{1,6}"
# a number joined after a Roman numeral or a label's number; unlike `_JOINED_AFTER` not by a
# space, since German has no rule that joins "1 395" (and "Kapitel I 12.03.2019" reads the
# date as words)
_CLOSE_JOINED_AFTER = re.compile(r"\s*[\u2013\u2014\u2012:/-]\s*[.,]?\d|[.,]?\d|[⁺⁻^⁰¹²³⁴⁵⁶⁷⁸⁹]")
_ROMAN_RUN = re.compile(
    r"(?<![\w-])(?P<keyword>[^\W\d_]+)(?P<dot>\.)?(?(dot)\s*|\s+)(?P<run>"
    + _ROMAN
    + r"(?:(?:\s*[/\u2013-]\s*|,\s*|\s+(?:und|oder|&)\s+)"
    + _ROMAN
    # with a full stop after it, it is left as printed ("Ludwig XIV.", "Kapitel XIV. Kapitel":
    # "14. Kapitel" would be an ordinal on a second run)
    # nor a run cut short before such a numeral: "Teil II und III." is left whole
    + r")*)(?![\w⁺⁻.%]|\s+(?:Quadrat|hoch)\b|(?:\s*[/\u2013-]\s*|,\s*|\s+(?:und|oder|&)\s+)"
    + _ROMAN
    + ")"
)
_ROMAN_PART = re.compile(r"(?P<numeral>" + _ROMAN + r")|(?P<sep>\s*[/\u2013-]\s*)")
_VALID_ROMAN = re.compile(r"\A(?P<tens>X{0,3})(?P<units>IX|IV|V?I{0,3})\Z")
_UNITS = {"": 0, "I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8, "IX": 9}


def _roman_value(numeral: str) -> int:
    match = _VALID_ROMAN.match(numeral)
    if not match or not numeral:
        return 0
    return 10 * len(match["tens"]) + _UNITS[match["units"]]


def _roman_numerals(plain: str) -> list[Candidate]:
    found = []
    for match in _ROMAN_RUN.finditer(plain):
        keyword = match["keyword"]
        known = _ABBREVIATED_KEYWORDS if match["dot"] else _KEYWORDS
        if keyword.lower() not in known:
            continue
        keyword += match["dot"] or ""
        if _CLOSE_JOINED_AFTER.match(plain, match.end("run")) or _X_AFTER.match(
            plain, match.end("run")
        ):
            continue  # "Kapitel I-3", "Kapitel I x1": "1-3" a range, "1 x1" "1 mal 1" next time
        offset = match.start("run")
        parts = list(_ROMAN_PART.finditer(match["run"]))
        if not all(_roman_value(p["numeral"]) for p in parts if p["numeral"]):
            continue  # "Typ IIX": not a numeral, so nothing in the run is read as one
        for part in parts:
            start, end = offset + part.start(), offset + part.end()
            if part["numeral"]:
                value = str(_roman_value(part["numeral"]))
                reason = f'Roman numeral "{part["numeral"]}" after "{keyword}" read as "{value}"'
                found.append(Candidate(start, end, value, reason))
            else:
                sep = part["sep"].strip()
                words = " und " if sep == "/" else " bis "
                reason = f'"{sep}" between Roman numerals read as "{words.strip()}"'
                found.append(Candidate(start, end, words, reason))
    return found


# --- all rules -------------------------------------------------------------------------------


def find_numbers_de(text: str) -> list[Candidate]:
    """The German number edits for one block's text, without overlap, in text order.

    Rules come most specific first: a date is not also read as ordinals or a range, a label's
    "2.5" not as a decimal.
    """
    plain = fold(text)
    years = _years(text)
    labelled, kept = _labelled(text)
    kept = sorted(kept + _file_numbers(text))
    found = pick(
        [
            *_dates(text),
            *_ordinals(text),
            *_roman_numerals(plain),
            *labelled,
            *_powers(text, plain),
            *_times(text),
            *_decimals(text),
            *_thousands(text),
            *years,
            *_ranges(text),
            *_ratios(text),
            *_fractions(text),
        ]
    )
    # a label's run left as printed ("Abschnitt 2.5 und 2.612-1") is left whole: "2612" read
    # alone would make "2.5" a label's number on a second run
    return _outside(found, kept)


# a court's file number ("VI ZR 8/14", "1 BvR 209/83", "Az. 3-10 O 86/12"): a chamber
# number (Roman or Arabic), a register of one to five letters and number/year; or after "Az."
# or "Aktenzeichen" its first token with a digit. No fraction, range or ratio is read there,
# and a dash before one is no range ("15.12.1983 – 1 BvR 209/83").
_FILE_SHAPE = (
    r"(?<![\w/.,])(?:[IVX]{1,6}|\d{1,3}(?:-\d{1,3})?)\s+[A-ZÄÖÜ][A-Za-zäöü]{0,4}"
    r"\s+\d{1,5}/\d{2}(?:\d{2})?(?![\w/])"
)
_FILE_NUMBER = re.compile(_FILE_SHAPE)
_FILE_LABEL = re.compile(
    r"\b(?:Az\.|Aktenzeichen)(?:\s+lautet)?\s*:?\s*(?P<token>[^\s;,()]*\d[^\s;,()]*?)"
    r"(?=[.:]?(?:[\s;,()]|\Z))"
)
_FILE_AFTER = re.compile(r"\s*" + _FILE_SHAPE)


def _file_numbers(text: str) -> list[tuple[int, int]]:
    """The spans of the court file numbers in a text."""
    shaped = [match.span() for match in _FILE_NUMBER.finditer(text)]
    starts = {start for start, _ in shaped}
    # after "Az." a number of another shape is kept by its first token ("Az. 12/2019")
    labelled = [
        match.span("token")
        for match in _FILE_LABEL.finditer(text)
        if match.start("token") not in starts
    ]
    return sorted(shaped + labelled)


def _outside(found: list[Candidate], kept: list[tuple[int, int]]) -> list[Candidate]:
    """The candidates (in text order) not inside a kept span (sorted by start)."""
    result, k = [], 0
    for candidate in found:
        while k < len(kept) and kept[k][1] <= candidate.start:
            k += 1
        if k < len(kept) and kept[k][0] <= candidate.start and candidate.end <= kept[k][1]:
            continue
        result.append(candidate)
    return result
