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
from collections.abc import Container
from functools import cache

from sci2audio.textprep.notation import (
    DOUBLE_ARROW,
    FILE_NUMBER_DE,
    Candidate,
    arrows,
    as_one_arrow,
    fold,
    pick,
    unit_follows,
    unit_starts_at,
)
from sci2audio.textprep.readings import (
    Reading,
    first_from,
    holding,
    last_before,
    readings_of,
    words_of,
)
from sci2audio.textprep.wordlists import abbreviations, opens_sentence

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
YEAR_WORDS = frozenset(
    {"jahr", "jahre", "jahres", "jahren", "jahrs", "frühjahr", "frühling", "sommer", "herbst"}
    | {"winter", "wintersemester", "sommersemester", "ws", "ss", "wise", "sose"}
    | {month.lower() for month in _MONTH_FORMS}
)
# words before a number that make it a year unless a noun follows ("seit 1998 gibt es", but
# "um 1500 Teilnehmer")
_MAYBE_YEAR_WORDS = frozenset(
    {"seit", "bis", "ab", "um", "von", "zwischen", "im", "anfang", "mitte", "ende"}
)
# nouns before a number that make it a year as the words above do, printed with a capital
# ("Ausgabe 1998", but "er stand 1998"; "Stand 1500 Punkte" is a count, #591). Not in
# YEAR_WORDS, which the citations step reads too. "Version" is none: "Version 1909" and
# "(Version 1234)" are software's version numbers
_EDITION_WORDS = frozenset({"ausgabe", "stand", "fassung", "jahrgang"})
# ... and "Auflage" only when the number ends the phrase ("(Auflage 1985)"): "Die Auflage
# 1500 wurde verkauft" is a print run (#591)
_PRINT_RUN = "auflage"
# ... and with a colon after it ("Stand: 1998", #782)
_COLON_WORD = re.compile(r"(?P<word>[^\W\d_]+):\s+\Z")
_PHRASE_END = re.compile(r"\s*(?:[)\],;:!?]|\.(?!\d)|\Z)")
# "zwischen 1990 und 1995": a number joined on to a year is a year too
_DIGIT_BEFORE = re.compile(r"\d\s*\Z")
# a "bis" a range made: after a number, or after "Uhr" ("13 Uhr–1234")
# a power's exponent counts too: "10⁶–1234" reads "10⁶ bis 1234" (#253)
# and a year read in hundreds: "1500-1998" reads "15 hundert bis 1998" (#253)
_RANGE_BEFORE = re.compile(r"(?:\d[⁺⁻]?[⁰¹²³⁴⁵⁶⁷⁸⁹]{0,2}|\bUhr|\d hundert)\s*\Z")
_JOINED_YEAR = re.compile(r"(?:\s*[\u2013\u2012\u2014-]\s*|\s+(?:und|oder|bis|bzw\.)\s+)\Z")
_JOINED_NEXT = re.compile(
    r"(?:\s*[\u2013\u2012\u2014-]\s*|\s+(?:und|oder|bis|bzw\.)\s+)"
    # a full stop or a comma after the run ends it ("Auflage 1998 und 1999.", #806), as ")"
    # does; a decimal ("1999,5") does not
    r"(?:1[1-9]\d\d|\d{1,2}\.\d{3})(?!\d|[.,]\d)"
)


def _before(text: str, at: int) -> str:
    return text[max(0, at - WINDOW) : at]


def _is_year(
    text: str, start: int, end: int, years: list[tuple[int, int]], worded: Container[int] = ()
) -> bool:
    """True if the number at start:end is read as a year (N-de-3). `worded` are the ends of
    the caret powers whose exponent is read into a word (`_power_read_as_word`)."""
    before = _before(text, start)
    joined = [end_ for _, end_ in years if end_ <= start]
    if joined and _JOINED_YEAR.fullmatch(text, joined[-1], start):
        return True
    # "Stand: 1998" as "Stand 1998" (#782), but "Anzahl: 1998" and "seit: 1998" stay counts
    colon = _COLON_WORD.search(before)
    previous = colon or _PREVIOUS_WORD.search(before)
    if previous is None:
        return False
    word = previous["word"].lower()
    edition = previous["word"][0].isupper() and word in _EDITION_WORDS | {_PRINT_RUN}
    if colon is not None and not edition:
        return False
    if word in YEAR_WORDS:
        return True
    if not (edition or word in _MAYBE_YEAR_WORDS) or (colon is None and previous["dot"]):
        return False
    range_before = _RANGE_BEFORE.search(before, 0, previous.start()) if word == "bis" else None
    if range_before is not None:
        # "x^2 bis 1234" is "x Quadrat bis 1234" after the first run: no number before "bis",
        # so the year is read, as after "x²" (#1082)
        number_end = start - len(before) + range_before.start() + len(range_before[0].rstrip())
        if not _power_read_as_word(text, number_end, worded):
            return False  # "1 bis 1234": a range ("1–1234" on the first run), not "bis 1998"
    # "zwischen 1234 und 1567 Probanden": the word after the last number of a joined run
    # decides for the whole run, as on a second run, where "1234 und" has no year before it
    while joined_next := _JOINED_NEXT.match(text, end):
        end = joined_next.end()
    if word == _PRINT_RUN:
        return _PHRASE_END.match(text, end) is not None
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
    r"(?:(?<!\.)|(?<=[^\W\d_xX]\.)|(?<=[^\W\d_][xX]\.)|(?<=\d[xX]\.)"
    # after a power too: "5 m^2.45:1" is "5 Quadratmeter.45:1" after the units step
    r"|(?<=\^\d\.)|(?<=\^\d\d\.)|(?<=\}\.)|(?<=[⁰¹²³⁴⁵⁶⁷⁸⁹]\.)"
    # and after "×", which the units step reads "mal"
    r"|(?<=×\.))"
)
# ... or, for a comma decimal, after a full stop glued to a symbol the units step may read as a
# word: "1 %.452,5" is "ein Prozent.452,5" after it. The rule checks that it does
# (`_AfterNumber.unit_ends_at`): "%.452,5", with no number before the "%", stays (#1082)
_STOP_OR_SYMBOL = "(?:" + _STOP + r"|(?<=[^\w\s.]\.)(?P<symbol>))"


@cache
def _sign_start() -> str:
    """The first characters of the signs and arrows the statistics step reads as words, as a
    character class. The patterns with it are built at first use: the readings module reaches
    the step's words only once every step module is loaded."""
    said = words_of("statistics", "de")
    return "[" + re.escape("".join(sorted({s[0] for s in (*said.signs, *said.arrows)}))) + "]"


_UNIT_SIGNS = "\u00d7\u2248~\u223c"  # the signs the units step reads: "mal", "ungefähr", "etwa"
_UNIT_SIGN = f"[{_UNIT_SIGNS}]"
_MICRO_SIGN = "\u00b5"  # which the units step reads as the Greek letter, outside a unit
_GREEK_MU = "\u03bc"

# --- N-de-1, N-de-2 decimals and thousands ---------------------------------------------------
_COMMA_DECIMAL = re.compile(
    r"(?<![,/^])"
    + _STOP_OR_SYMBOL
    + r"(?<![^\WxX])(?P<whole>\d{1,3}(?:\.\d{3})+|\d+),(?P<fraction>\d+)(?![\d_]|[⁺⁻^]|[.,/]\d)"
)


# a point decimal after a comparison sign (a minus may stand between) or a leading point; the
# sign as the statistics step reads it counts too, so a second run decides the same
@cache
def _sign_before() -> re.Pattern[str]:
    signs = words_of("statistics", "de").signs
    return re.compile(
        "(?:["
        + re.escape("".join({key[0] for key in signs} | {"\u0338"}))
        + "]|"
        + "|".join(
            sorted(
                (rf"\b{re.escape(words)}" for words in set(signs.values())),
                key=len,
                reverse=True,
            )
        )
        + r")\s*[\u2212-]?\Z"
    )


# not before a ratio or fraction: ".5:1" read "0 Komma 5:1" would be a ratio on a second run;
# not after "×" or an x after a number, which the units step may read "mal" ("×.45" and
# "1x.45" are "mal.45", no decimal; "1 x0 Komma 4 5" would be "1 mal 0 ..." next time)
_POINT_DECIMAL = re.compile(
    r"(?<![.,/:^×])(?<![^\WxX])(?<!\d[xX])(?<!\d [xX])(?P<whole>\d*)\.(?P<fraction>\d+)"
    # a letter after it is checked in code: a unit the units step reads ("2.5Å") is fine
    r"(?![\d_]|[⁺⁻^]|[.,:/]\d|-\n?\d)"
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
_RUN_DASH = re.compile(r"\s*[\u2013-]\s*")  # "Abschnitt 2.5-11.234": "2 Punkt 5 bis 11 ..."
# a number joined after a label's number by a colon, slash or hyphen (an en dash is a range,
# read "bis" in the same run), by a digit or by a power
_JOINED_TAIL = re.compile(r"\s*[:/-]\s*[.,]?\d[\d.,]*")
_LABEL_JOINED_AFTER = re.compile(r"\s*[:/-]\s*[.,]?\d|[.,]?\d|[⁺⁻^⁰¹²³⁴⁵⁶⁷⁸⁹]")


def _decimals(text: str, after: _AfterNumber | None = None) -> list[Candidate]:
    found = []
    after = after or _AfterNumber(text)
    for match in _COMMA_DECIMAL.finditer(text):
        if _x_left_alone(text, match.end()) or _unit_left_alone(text, match.end()):
            continue
        if _GLUED_MINUS.match(text, max(0, match.start() - 2), match.start()):
            continue  # "10−412,5": an exponent or a sum, not "minus 412 Komma 5" on its own
        if match["symbol"] is not None:
            if not after.unit_ends_at(match.start() - 1):
                continue  # "%.452,5": "452 Komma 5" would leave "%.452", a decimal next time
        elif _LEADING_POINT.search(text, max(0, match.start() - 2), match.start()):
            continue  # "}.452,5": "452 Komma 5" would leave ".452", a decimal on a second run
        left = _HYPHEN_LEFT.search(text, max(0, match.start() - 24), match.start())
        if left is not None and not _hyphen_range_at(text, left.start()):
            continue  # "1-2,5-": no range here, but "1-2 Komma 5" would be one next time
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
        if (
            not whole
            and _KOMMA_AFTER.match(text, match.end())
            and after.unit_ends_at(match.start())
        ):
            # "1 %.452 Komma 5", read from "1 %.452,5" (above): ".452" follows "Prozent" once
            # the units step has read the "%", so it stays, as on a second run (#1082)
            continue
        before = _before(text, match.start())
        if whole and not _sign_before().search(before):
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
    return _X_AFTER.match(text, end) is not None and not x_read_after(text, end, "de")


def _unit_left_alone(text: str, end: int) -> bool:
    """True if a unit follows the number that the units step leaves as printed ("Kapitel
    2,55 m"): read "2 Komma 5 5 m", a second run would read "5 m" as "5 Meter". An "x" the
    units step reads after it is no such unit ("12,5x": the x is "mal")."""
    return unit_follows(text, end, "de") and not _unit_read_after(text, end)


def x_read_after(text: str, end: int, language: str) -> bool:
    """True if the units step reads the "x" right after the number that ends at `end`, glued
    or after one space, as "times" ("2,5x"). The number is read exactly when the x is (#130):
    a second run, on "2,5 mal", then finds nothing new."""
    at = end + 1 if text[end : end + 1] == " " else end
    found = holding(readings_of("units", text, language), at)
    return found is not None and (found.start, found.end) == (at, at + 1) and text[at] in "xX"


def unit_read_after_per(text: str, position: int, language: str) -> bool:
    """True if `position` lies in a unit the units step reads with no number before it,
    right after "per", "pro" or "je" ("per m³" as "per cubic metre", "pro m³", #230): the
    numbers step then leaves its powers, or a second run would read "per metre cubed".

    A unit read after a number starts right after it, after the space it allows or after a
    hyphen, never right after a word and one space. The text is asked as a second run sees
    it, with the Greek letter the units step writes for a micro sign: "per µm²" is "per μm²"
    then, whose unit it reads."""
    text = text.replace(_MICRO_SIGN, _GREEK_MU)
    found = holding(readings_of("units", text, language), position)
    return (
        found is not None
        and text[found.start - 1 : found.start] == " "
        and text[found.start - 2 : found.start - 1].isalpha()
    )


def _unit_read_after(text: str, end: int) -> bool:
    """True if the units step reads the unit, magnitude letter or "x" right after the number
    that ends at `end`, glued or after the space it allows ("2,55 m", "1 %-Hürde", "12,5x");
    not a sign, a "1" it reads as a word, or the micro sign it reads as the Greek letter."""
    found = first_from(readings_of("units", text, "de"), end)
    if found is None or found.start - end > 2 or text[end : found.start].strip():
        return False
    printed = text[found.start : found.end].strip()
    return printed not in (*_UNIT_SIGNS, _MICRO_SIGN) and not printed[:1].isdigit()


_KOMMA_AFTER = re.compile(r" Komma \d")
_LEADING_POINT = re.compile(r"(?:\A|[^\w×]|(?<!\d)[xX])\.\Z")  # a point that would start a decimal
_RATIO_BEFORE = re.compile(r"(?<![\d,])\d+(?:,\d+)?:\Z")
_HYPHEN_AFTER = re.compile(r"-\n?\d")
_HYPHEN_LEFT = re.compile(r"(?<![\d.,])\d[\d.,]*-\n?\Z")  # a number and a hyphen before


def _hyphen_range_at(text: str, start: int) -> bool:
    """True if `_ranges` reads the hyphen range that starts at `start`."""
    match = _HYPHEN_RANGE.match(text, start)
    if match is None or _x_left_alone(text, match.end()):
        return False
    if match["a"].count(".") == 1 and _sign_before().search(_before(text, start)):
        return False  # "= 1.234-1998": a point decimal, left as printed with what joins it
    left = _value(match["a"])
    hundreds = _HUNDRED_BEFORE.search(text, max(0, start - 16), start)
    if hundreds and match["a"].isdigit() and len(match["a"]) <= 2:
        left += 100 * int(hundreds[1])  # "12 hundert 34-1234" is the year 1234 read (#253)
    return left < _value(match["b"])


_HUNDRED_BEFORE = re.compile(r"(?<![\d.,])(1[1-9]) hundert \Z")


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
            # what joins it stays too: "Abschnitt 1.234-2011" is no range "1.234 bis 2011",
            # which a second run would read "1 Punkt 234 bis 2011" (#253)
            joined = _JOINED_TAIL.match(text, end)
            kept.append((match.start("run"), joined.end() if joined else end))
            continue  # "Abschnitt 2.51:1": the new digits would join differently next time
        offset = match.start("run")
        for dash in _RUN_DASH.finditer(match["run"]):
            start, end = offset + dash.start(), offset + dash.end()
            sign, run = dash.group().strip(), match["run"]
            reason = f'"{sign}" in "{run}" after "{match["label"]}" read as "bis"'
            found.append(Candidate(start, end, " bis ", reason))
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


def _in_round_bracket(text: str, start: int) -> bool:
    """True if `start` stands inside a round bracket that closes after it, inner brackets
    skipped: "(Projekt 12.345)", "(12.345-mal)", "(Projekt 12.345 (Müller, 2019))"."""
    depth = 0
    for position in range(start - 1, max(-1, start - 201), -1):
        if text[position] == ")":
            depth += 1
        elif text[position] == "(":
            if not depth:
                break
            depth -= 1
    else:
        return False
    depth = 0
    for char in text[start : start + 200]:
        if char == "(":
            depth += 1
        elif char == ")":
            if not depth:
                return True
            depth -= 1
    return False


def _thousands(text: str, worded: Container[int] = ()) -> list[Candidate]:
    found = []
    for match in _THOUSANDS.finditer(text):
        if _x_left_alone(text, match.end()) or _unit_left_alone(text, match.end()):
            continue  # "1.234abc"; "1.234Å" is read, as the units step reads the unit
        if _LEADING_POINT.search(text, max(0, match.start() - 2), match.start()):
            continue  # "}.1.234": "1234" would leave ".1234", a decimal on a second run (#253)
        number = match.group()
        value = int(number.replace(".", ""))
        # a year word before it, not a year joined by a dash: "im 1234–1.234" reads "12 hundert
        # 34 bis 1234", where a second run sees no year before "1234" either
        if 1100 <= value <= 1999 and _is_year(text, *match.span(), [], worded):
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
            and _sign_before().search(before)
            and not _COUNT_LETTER.search(before)
        ):
            continue  # "M = 2.345": a point decimal, read by N-de-1 (or left as printed)
        # in round brackets "(12.345)" reads "(12 345)", as the voice reads "1 234" well: read
        # "(12345)", "(Projekt 12345)" or "(12345-mal)", the citations step would take it for
        # an identifier on a second run (#285)
        words = number.replace(".", " " if _in_round_bracket(text, match.start()) else "")
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


def _years(text: str, worded: Container[int] = ()) -> list[Candidate]:
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
        if not _is_year(text, start, end, spans, worded) or _x_left_alone(text, end):
            continue
        words = year_words(int(match["year"]))
        found.append(Candidate(start, end, words, f'year "{match["year"]}" read as "{words}"'))
        spans.append((start, end))
        spans.sort()
    # the year after a hyphen range's year: "von 1500-1998" reads "15 hundert bis 19 hundert
    # 98", as with an en dash, not "bis 1998", a year on a second run after "bis" (#253)
    for start, end in list(spans):
        right = _HYPHEN_YEAR.match(text, end)
        if (
            right is not None
            and _hyphen_range_at(text, start)
            and not _x_left_alone(text, right.end())
        ):
            words = year_words(int(right["year"]))
            reason = f'year "{right["year"]}" read as "{words}"'
            found.append(Candidate(*right.span("year"), words, reason))
    return found


_HYPHEN_YEAR = re.compile(r"-\n?(?P<year>1[1-9]\d\d)(?![\d_]|[⁺⁻^]|[.,:/]\d|[^\WxX])")


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


def _ranges(text: str, worded: Container[int] = ()) -> list[Candidate]:
    found = []
    for match in _DASH_RANGE.finditer(text):
        start, end = match.span("dash")
        if _FILE_AFTER.match(text, end):
            continue  # "15.12.1983 – 1 BvR 209/83": the dash leads to a court's file number
        if _power_read_as_word(text, start, worded) and _year_after_bis(text, end):
            # "x^2–1234" is "x Quadrat bis 1234" after the first run, whose "1234" a second
            # run reads as a year; so the dash stays as printed, as after "x²" (#1082)
            continue
        found.append(Candidate(start, end, " bis ", _range_reason(text, start, end)))
    for match in _HYPHEN_RANGE.finditer(text):
        if not _hyphen_range_at(text, match.start()):
            continue  # "3-1" is a score or a code, not a range
        start, end = match.span("dash")
        found.append(Candidate(start, end, " bis ", _range_reason(text, start, end)))
    return found


_CARET_EXPONENT = re.compile(r"\^\d{1,2}\Z")


def _power_read_as_word(text: str, end: int, worded: Container[int]) -> bool:
    """True if a caret power ends at `end` whose exponent the first run reads into a word
    (`worded`): "x^2" as "x Quadrat", "5 m^2" as "5 Quadratmeter". A second run sees no
    number there, so none for a range to start from (#1082)."""
    return _CARET_EXPONENT.search(text, max(0, end - 3), end) is not None and end in worded


def _year_after_bis(text: str, end: int) -> bool:
    """True if a second run reads the number at `end` as a year after "bis" and a word.
    Only a window after `end` is looked at."""
    said = "Quadrat bis "
    return any(c.start == len(said) for c in _years(said + text[end : end + WINDOW]))


class _WordedPowers:
    """Where a caret power ends whose exponent a first run reads into a word: the powers
    rule's "x Quadrat", or the units step's "Quadratmeter" for "m^2"."""

    def __init__(self, after: _AfterNumber, powers: list[Candidate]) -> None:
        self._after = after
        self._ends = {c.end for c in powers if c.replacement.rstrip()[-1:].isalpha()}

    def __contains__(self, end: object) -> bool:
        return isinstance(end, int) and (end in self._ends or self._after.unit_ends_at(end))


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


def _label(word: str, dot: str | bool | None) -> str:
    """The noun an abbreviation with its full stop stands for ("Kap." is "Kapitel")."""
    return _ABBREVIATED_NOUNS.get(word, word) if dot else word


def _abbreviated_nouns() -> dict[str, str]:
    """The abbreviations of the nouns above, without their full stop ("Kap" -> "Kapitel"):
    "12. Kap. 3" reads "zwölftes Kapitel 3", since the abbreviations step reads "Kap." and
    "12. Kapitel" would be an ordinal on a second run."""
    found = {}
    for entry in abbreviations("de") or ():
        if entry.reads in _NOUN_ENDINGS:
            for printed in entry.printed:
                if printed.endswith(".") and printed[:-1].isalpha():
                    found[printed[:-1]] = entry.reads
    return found


_ABBREVIATED_NOUNS = _abbreviated_nouns()
# "13 Uhr 30. Jahr" is a second run of "13:30. Jahr": the number after "Uhr" is the minutes.
# Not after a clock time's own "Uhr" ("13:30 Uhr 3. Mai", any space between): there "3." is
# a day, read as a second run reads it after "13 Uhr 30" (#557, #593)
_AFTER_UHR = re.compile(r"\bUhr\s+\Z")
_CLOCK_UHR = re.compile(r"\d[:.]\d\d\s+Uhr\s+\Z")
_UHR_WINDOW = 24  # characters looked back for "Uhr" and the clock time before it


# a word after it, or what a second run sees as one (`_AfterNumber`): a sign the statistics
# or the units step reads, a "1" the units step reads before its unit, a "1/2" read "ein
# halb", a date read as words
@cache
def _ordinal() -> re.Pattern[str]:
    return re.compile(
        r"(?<![^\WxX])(?<![,/:\u2013-])"
        + _STOP
        + r"(?P<n>\d{1,6})\.(?=\s+[^\W\d_]|\s*"
        + _sign_start()
        + r"|\s*"
        + _UNIT_SIGN
        + r"|\s+\d)"
    )


# after an en dash too, which the range rule reads "bis": a second run sees "bis 2019-03-05"
# (#957)
_ISO_DATE = re.compile(
    r"(?<![^\WxX])(?<![:/-])(?<!\d,)"
    + _STOP
    + r"(?P<y>1[5-9]\d\d|20\d\d)-\n?(?P<m>0[1-9]|1[0-2])-\n?(?P<d>0[1-9]|[12]\d|3[01])"
    r"(?![\d_]|[⁺⁻^-]|[.,:/]\d)"  # a letter after it: `_year_left_alone` decides
)
# a full date ahead: "am 3.4. 12.03.2019" reads the first date too, as a second run, after
# "zwölfter März 2019", would (#303)
_DATE_AHEAD = (
    r"(?:0?[1-9]|[12]\d|3[01])\.(?:0?[1-9]|1[0-2])\.(?:1[5-9]\d\d|20\d\d)"
    r"|(?:1[5-9]\d\d|20\d\d)-\n?(?:0[1-9]|1[0-2])-"
    # ... or a fraction that may be read "ein halb" (`_dates` checks that it is, #310)
    r"|1/\d{1,2}(?!\d)"
)
# a full dotted date, not glued to more digits: what a hyphen range of dates joins (a third
# date may follow it: "3.4.2019-5.4.2019-7.4.2019")
_FULL_DATE = (
    r"(?:0?[1-9]|[12]\d|3[01])\.(?:0?[1-9]|1[0-2])\.(?:1[5-9]\d\d|20\d\d)"
    r"(?![\d_]|[⁺⁻^]|[.,:/]\d)"
)
# a date without its year that ends a range: "3.4.2019-5.4." (#318); before what a date
# without its year may stand before, so both runs decide alike: a full date, or a fraction
# that `_dates` reads "ein ..." (#332)
_YEARLESS_END = (
    r"(?:0?[1-9]|[12]\d|3[01])\.(?:0?[1-9]|1[0-2])\.(?![\w.,]|\s*(?!" + _DATE_AHEAD + r")\d)"
)
_HYPHEN_YEARLESS_END = re.compile("-" + _YEARLESS_END)
# after a date and a hyphen: the second date of a range ("3.4.2019-5.4.2019", "3.4.-5.4.";
# after a date without its year, `_dates` reads it only if it read that date, #318)
_AFTER_DATE_HYPHEN = r"(?<=\d\.1[5-9]\d\d-)|(?<=\d\.20\d\d-)|(?<=\d\.-)"
_NUMERIC_DATE = re.compile(
    r"(?<![^\WxX])(?:(?<![,/:-])|"
    + _AFTER_DATE_HYPHEN
    + r")"
    + _STOP
    + r"(?P<d>0?[1-9]|[12]\d|3[01])\.(?P<m>0?[1-9]|1[0-2])\."
    # a year glued to "-" and a digit stays as printed ("3.4.2019-03-12", #303), unless a
    # full date follows: "3.4.2019-5.4.2019" is a range (#311)
    r"(?:(?P<y>1[5-9]\d\d|20\d\d)(?![\d_]|[⁺⁻^]|[.,:/]\d|-(?!"
    + _FULL_DATE
    + r"|"
    + _YEARLESS_END
    + r")\d)|(?![\w.,]|\s*(?!"
    + _DATE_AHEAD
    # ... or a "1" the units step may read as a word before its unit ("am 3.4. 1 N" is "am
    # 3.4. ein Newton" after the first run; `_dates` checks that it is, #970)
    + r"|1(?![\d.,/]))\d))"
)


def _year_left_alone(text: str, end: int) -> bool:
    """True if a reading that ends in the year is not read: before a unit or an "x" the units
    step leaves as printed ("2019 N" would be the units step's on a second run)."""
    return _unit_left_alone(text, end) or _x_left_alone(text, end)


_RANGE_DASH_BEFORE = re.compile(r"\d\s*[\u2013\u2014]\s*\Z|\d\.\d{4}-\Z|\d\.[\u2013-]\Z")
_DASH_BEFORE = re.compile(r"[\u2013\u2014]\s*\Z")


def _read_before(text: str, start: int) -> tuple[int, str] | None:
    """Where an abbreviation the abbreviations step reads ends right before `start`, with
    only white space between, its start and its reading: "i. V. m. 2. Alternative" gives the
    start of "i. V. m." and "in Verbindung mit". The reading is the word before an ordinal,
    as a second run sees it ("mit zweiter", #264)."""
    if text[:start].rstrip()[-1:] != ".":
        return None
    found = last_before(readings_of("abbreviations", text, "de"), start)
    if found is None or text[found.end : start].strip():
        return None
    return found.start, found.words.strip()


def _before_read(text: str, start: int) -> str:
    """The text before `start` as a second run sees it: an abbreviation the abbreviations
    step reads right before is its reading ("i. V. m. 2." is "in Verbindung mit 2.")."""
    read = _read_before(text, start)
    if read is None:
        return _before(text, start)
    return _before(text, read[0]) + read[1] + " "


def _ending(text: str, start: int, *, day: bool = False) -> str | None:
    """The ending an ordinal at `start` takes from the word before it, if one decides it."""
    before = _before_read(text, start)
    if day and _RANGE_DASH_BEFORE.search(before):
        return "en"  # "1.3.2020–11.3.2020": the dash is read "bis", as in "bis 11.3.2020"
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
    previous = _PREVIOUS_WORD.search(_before_read(text, start))
    return previous is not None and previous["word"].lower() in _PREPOSITIONS


def _date_words(
    text: str, start: int, day: int, month: int, year: str | None, *, paired: bool = False
) -> str | None:
    # the second date of a range is read as after "bis": "bis fünften April" (#318, #334)
    ending = "en" if paired else _ending(text, start, day=True)
    if ending is None:
        return None
    words = f"{ordinal(day, ending)} {MONTHS[month - 1]}"
    return f"{words} {year_words(int(year))}" if year else words


def _dates(text: str, after: _AfterNumber | None = None) -> list[Candidate]:
    found = []
    after = after or _AfterNumber(text)
    for match in _ISO_DATE.finditer(text):
        year, month, day = int(match["y"]), int(match["m"]), int(match["d"])
        if day > calendar.monthrange(year, month)[1]:
            continue
        words = _date_words(text, match.start(), day, month, match["y"])
        if words and not _year_left_alone(text, match.end()):
            found.append(_date(match, words))
    last_date = -1  # where the last date read ends
    read_as_ein: set[int] | None = None  # where a fraction read "ein halb" ... starts
    for match in _NUMERIC_DATE.finditer(text):
        if match["y"] and (end := _HYPHEN_YEARLESS_END.match(text, match.end())):
            ahead = _FRACTION_AHEAD.match(text, end.end())
            if ahead:
                if read_as_ein is None:
                    read_as_ein = _read_as_ein(text)
                if ahead.end() not in read_as_ein:
                    continue  # "3.4.2019-5.4. 1/12": no range, as a second run sees "1 von 12"
        dash = text[match.start() - 1 : match.start()]
        # the second date of a range: read only if the date before the dash is ("3.4.-5.4.",
        # "3.4.–5.4.2019", "3.4.2019–5.4."; #318), also across a spaced en dash or hyphen
        # or an em dash ("3.4.2019 – 5.4.", "3.4.—5.4.", "3.4.2019 - 5.4.2019"; #334)
        sep = _PAIR_DASH.search(text, max(0, match.start() - 3), match.start())
        paired = sep is not None and last_date == sep.start()
        after_yearless = (
            dash in ("-", "\u2013") and text[match.start() - 2 : match.start() - 1] == "."
        )
        if after_yearless and not paired:
            continue  # "3.–5.4.", "Abschnitt 3.4.-5.4.": the dash and the date stay, as on main
        if not paired and not match["y"] and dash == "\u2013":
            continue  # "3.–5.4.": a date without its year after a dash is left as printed
        before = text[max(0, match.start() - 8) : match.start()]
        if not paired and _DASH_BEFORE.search(before) and not _RANGE_DASH_BEFORE.search(before):
            continue  # "1.–3.4.2020": no "bis" for the dash, so the date stays too, as on main
        day, month = int(match["d"]), int(match["m"])
        year = int(match["y"]) if match["y"] else 2000  # 29.2. without a year may be any year
        if day > calendar.monthrange(year, month)[1]:
            continue
        if not match["y"] and not paired and _ending(text, match.start()) is None:
            continue  # "3.4." alone is a list or a version; "am 3.4." is a date
        if not match["y"] and (ahead := _FRACTION_AHEAD.match(text, match.end())):
            # "Am 3.4. 1/2 Tag": read when the fraction is read "ein halb", a word that a
            # second run sees after the date (#310); "2/3" keeps its digit, so the date stays
            if read_as_ein is None:
                read_as_ein = _read_as_ein(text)
            if ahead.end() not in read_as_ein:
                continue
        one = None if match["y"] else _ONE_AHEAD.match(text, match.end())
        if one is not None and not after.one_read_as_word(one.end()):
            continue  # "am 3.4. 1 und 2": no "1" read "ein" before a unit, so the date stays
        if (
            not match["y"]
            and after.unread_arrow(text, match.end())
            and after.reads_arrow_after(MONTHS[month - 1], match.end())
        ):
            # "am 3.4. ⇒ M": the arrow after a full stop is not read, but after "April" a
            # second run reads it; so the date stays as printed with it. Before a prose word
            # ("am 3.4. ⇒ Mai") a second run leaves the arrow too, so the date is read (#970)
            continue
        words = _date_words(text, match.start(), day, month, match["y"], paired=paired)
        if words and not _year_left_alone(text, match.end()):
            found.append(_date(match, words))
            last_date = match.end()
            if paired and sep is not None and not _DASH_RANGE.match(text, sep.start()):
                # "3.4.2019-5.4.2019", "3.4.–5.4.", "3.4. – 5.4.": the dash between two dates
                # is read "bis"; an en dash or em dash after a year is the range rule's
                # ("2019–5", "2019 – 5", N-de-4)
                reason = _range_reason(text, sep.start(), match.start())
                found.append(Candidate(sep.start(), match.start(), " bis ", reason))
            elif dash == "-" and not paired:
                at = match.start() - 1
                reason = _range_reason(text, at, match.start())
                found.append(Candidate(at, match.start(), " bis ", reason))
    return found


_FRACTION_AHEAD = re.compile(r"\s*(?=1/)")
_ONE_AHEAD = re.compile(r"\s*(?=1(?![\d.,/]))")


@cache
def _sign_ahead() -> re.Pattern[str]:
    return re.compile(r"\s*(?=" + _sign_start() + ")")


_UNIT_SIGN_AHEAD = re.compile(r"\s*(?=" + _UNIT_SIGN + ")")
_DIGIT_AHEAD = re.compile(r"\s*(?=\d)")
_SPACES = re.compile(r"\s*")
_ARROW_AHEAD = re.compile(DOUBLE_ARROW)


class _AfterNumber:
    """What a second run sees right after a number where the first run sees no word: the
    words of a sign the statistics step reads ("<" is "kleiner als"), of a "1" the units
    step reads before its unit ("1 N" is "ein Newton"), of a fraction read with "ein"
    ("1/2" is "ein halb"), or of a date ("3.4.2019" is "dritter April 2019"). `printed` is
    the block's text before the arrows are joined, as the statistics step reads it."""

    def __init__(self, printed: str) -> None:
        self.printed = printed
        self._ein: set[int] | None = None  # `_read_as_ein` of the text the rules read
        self._dates: dict[int, str] | None = None  # the dates read in it, by their start
        self._unit_ends: frozenset[int] | None = None

    def _sign_at(self, at: int) -> Reading | None:
        return holding(readings_of("statistics", self.printed, "de"), at)

    def word(self, text: str, end: int) -> str | None:
        """The first word a second run sees after `end`, or None."""
        sign = _sign_ahead().match(text, end)
        if sign is not None:
            read = self._sign_at(sign.end())
            words = read.words.split() if read is not None else []
            return words[0] if words else None
        sign = _UNIT_SIGN_AHEAD.match(text, end)
        if sign is not None:
            return self._sign_word(sign.end())
        one = _ONE_AHEAD.match(text, end)
        if one is not None and one.end() > end and self.one_read_as_word(one.end()):
            return "ein"
        fraction = _FRACTION_AHEAD.match(text, end)
        if fraction is not None and fraction.end() > end:
            # "am 3. 1/2 N" is "am 3. ein halb N" after the first run, whose "3." a second run
            # reads "dritten"; "3/4" and "1/12" keep their digit, so the ordinal stays (#1078)
            if self._ein is None:
                self._ein = _read_as_ein(text)
            if fraction.end() in self._ein:
                return "ein"
        digit = _DIGIT_AHEAD.match(text, end)
        if digit is not None and digit.end() > end:
            # "am 3. 3.4.2019" is "am 3. dritter April 2019" after the first run, whose "3." a
            # second run reads "dritten" (#1082)
            if self._dates is None:
                self._dates = {c.start: c.replacement for c in _dates(text, self)}
            date = self._dates.get(digit.end(), "").split()
            return date[0] if date else None
        return None

    def unit_ends_at(self, end: int) -> bool:
        """True if what the units step reads as words ends at `end` ("%" after a number is
        "Prozent", "m^2" "Quadratmeter"): a second run sees a word there (#1082)."""
        if self._unit_ends is None:
            self._unit_ends = frozenset(r.end for r in readings_of("units", self.printed, "de"))
        return end in self._unit_ends

    def one_read_as_word(self, at: int) -> bool:
        """True if the units step reads the "1" at `at` as a word before its unit ("1 N" as
        "ein Newton"): a second run sees that word after a date or an ordinal before it
        ("am 3.4. 1 N", #970). No other reading of the units step starts at a digit."""
        found = holding(readings_of("units", self.printed, "de"), at)
        return found is not None and found.start == at and self.printed[at].isdigit()

    def _sign_word(self, at: int) -> str | None:
        """The word the units step reads for the "×", "≈" or "~" at `at`, or None."""
        found = holding(readings_of("units", self.printed, "de"), at)
        if found is None or self.printed[at : at + 1] not in (*_UNIT_SIGNS,):
            return None
        return found.words.strip()

    def unread_arrow(self, text: str, end: int) -> bool:
        """True if an arrow of logic follows `end` that the statistics step leaves as printed."""
        at = _SPACES.match(text, end).end()  # type: ignore[union-attr]
        return _ARROW_AHEAD.match(self.printed, at) is not None and self._sign_at(at) is None

    def reads_arrow_after(self, word: str, end: int) -> bool:
        """True if the statistics step reads the arrow after `end` once a second run sees
        `word` (the reading's last word) before it. Only a window after `end` is looked at."""
        around = word + self.printed[end : end + WINDOW]
        at = _SPACES.match(around, len(word)).end()  # type: ignore[union-attr]
        return holding(readings_of("statistics", around, "de"), at) is not None


# the dash between the two dates of a range: a hyphen or en dash glued to both, an em dash
# glued or spaced, or an en dash or hyphen with a space on each side (DIN 5008, #334)
_PAIR_DASH = re.compile(r"(?:[\u2013-]| ?\u2014 ?| [\u2013-] )\Z")


def _read_as_ein(text: str) -> set[int]:
    """Where the fractions start that are read in words. After a date only "1/x" is looked
    for, and the fractions read in words that start with "1/" are those read with "ein"
    ("1/2" as "ein halb", up to "1/10"); "1/12" keeps its digits (#310)."""
    return {c.start for c in _fractions(text)}


def _date(match: re.Match[str], words: str) -> Candidate:
    return Candidate(*match.span(), words, f'date "{match.group()}" read as "{words}"')


# the digits of a decimal read in words ("0 Komma 0 5"): no ordinal ends them ("5. Jahr")
_AFTER_KOMMA = re.compile(r"\bKomma(?: \d)* \Z")
# ... nor a power read in words ("10-2. Jahr" is "10 hoch minus 2. Jahr" after the first run)
_DATE_BEFORE = re.compile(r"(?<![\d.])\d{1,2}\.\d{1,2}\.\s*\Z")  # a date without its year
_AFTER_HOCH = re.compile(r"\bhoch (?:minus |plus )?\Z")
# ... nor the last part of a dotted number read with "Punkt" ("Kapitel 1.2.3. Tag" is "Kapitel 1
# Punkt 2 Punkt 3. Tag" after the first run, #349); only that reading has a digit before
# "Punkt", so "Der Punkt 3. Mai" keeps its ordinal (#368)
_AFTER_PUNKT = re.compile(r"\d Punkt \Z")
# ... nor a source number the citations step reads ("unter [12]. Studie" is "unter Quelle 12.
# Studie" after the first run; the words are the German wording's, #212)
_AFTER_SOURCE = re.compile(r"\bQuellen? (?:\d+(?:, | und | bis ))*\Z")


_YEAR_LIKE = re.compile(r"1[1-9]\d\d|20\d\d")  # 1100 to 2099
# ... nor the rest of a year read in hundreds ("im Jahr 1998. Jahr" reads "19 hundert 98. Jahr";
# a second run must not read "98." as "achtundneunzigstes", #536)
_AFTER_HUNDRED = re.compile(r"(?<![\d.,])1[1-9] hundert \Z")


def _ordinals(text: str, after: _AfterNumber | None = None) -> list[Candidate]:
    found = []
    after = after or _AfterNumber(text)
    for match in _ordinal().finditer(text):
        n = int(match["n"])
        if not 0 < n <= MAX_ORDINAL:
            continue
        if _AFTER_KOMMA.search(text, max(0, match.start() - WINDOW), match.start()):
            continue  # "0 Komma 0 5. Jahr": the decimal ".05" read, not an ordinal
        if _DATE_BEFORE.search(text, max(0, match.start() - 16), match.start()):
            continue  # "am 3.4. 3. Mai": the date before is left as printed, and so is this
        window = max(0, match.start() - _UHR_WINDOW)
        if _AFTER_UHR.search(text, window, match.start()) and not _CLOCK_UHR.search(
            text, window, match.start()
        ):
            continue  # "13 Uhr 30. Jahr", from "13:30. Jahr": the minutes, no ordinal (#253)
        if _AFTER_HUNDRED.search(text, max(0, match.start() - 16), match.start()):
            continue  # "19 hundert 98. Jahr", from "1998. Jahr": a year's rest, no ordinal (#536)
        if _AFTER_HOCH.search(text, max(0, match.start() - 16), match.start()):
            continue  # "10 hoch minus 2. Jahr": a power's exponent, not "zweites Jahr"
        if _AFTER_PUNKT.search(text, max(0, match.start() - 8), match.start()):
            continue  # "1 Punkt 2 Punkt 3. Tag": a section number's last part (#349)
        if _AFTER_SOURCE.search(text, max(0, match.start() - WINDOW), match.start()):
            continue  # "Quelle 12. Studie": a source's number ends the sentence
        previous = _PREVIOUS_WORD.search(_before(text, match.start()))
        if previous is not None and previous["word"] in _MONTH_FORMS:
            continue  # "März 2019. Auflage": a date's year (read from "12.03.2019. Auflage")
        following = _NEXT_WORD.match(text, match.end())
        if following is not None:
            noun, noun_dot = following["word"], bool(following["dot"])
        else:
            # "am 3. < 1" is "am 3. kleiner als 1" after the first run, whose "3." a second
            # run reads "dritten"; a sign the statistics step leaves is no word (#970)
            said = after.word(text, match.end())
            if said is None:
                continue
            noun, noun_dot = said, False
        if opens_sentence(text, match.end(), "de"):
            continue  # "Die 12. Dann mehr": a number ends the sentence (#227, D-530)
        month = noun in _MONTH_FORMS and (noun in MONTHS or noun_dot)
        if previous is not None and _label(previous["word"], previous["dot"]) == _label(
            noun, noun_dot
        ):
            # "Es gilt Satz 2. Satz 3", "Kap. 2. Kap. 3": a label's number, then the same
            # label again, ends the sentence (D-719); "Im Punkt 2. Teil" keeps its ordinal.
            # Abbreviated or not: "Kapitel 14. Kap. 3" is "Kapitel 14. Kapitel 3" on a second
            # run, as "Kapitel XIV. Kap. 3" is; where the abbreviations step leaves "Kap."
            # ("Kap. drei") it is the same label on both runs alike (#1082)
            continue
        ending = _ending(text, match.start(), day=month)
        if (
            ending is None
            and not _after_preposition(text, match.start())
            and not _YEAR_LIKE.fullmatch(match["n"])
        ):
            # a four-digit year before a noun with no word that sets the ending ends its
            # sentence: "Das war 2019. Kapitel 3" (#265, D-646)
            if noun_dot:
                noun = _ABBREVIATED_NOUNS.get(noun, noun)
            ending = _NOUN_ENDINGS.get(noun) if noun != "Jh" or noun_dot else None
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
# "ein halb", "ein Drittel": the readings of a fraction of one, which the sentence cutter keeps
# whole (#482)
FRACTIONS_OF_ONE = frozenset(f"ein {word}" for word in _FRACTION_WORDS.values())
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
# ... and a letter power that ends a unit chain after it ("2/3 m s⁻²", "3/4 kg m²"), if the
# powers rule leaves that power to the units step after the printed number (`_unit_chain`):
# after the fraction's words it would read it (#359)
_CHAIN_POWER_AFTER = re.compile(
    r"\s(?:[^\W\d_]{1,3}[⁺⁻]?[⁰¹²³⁴⁵⁶⁷⁸⁹]*[\s·⋅]+)+(?P<base>[^\W\d_])[⁺⁻]?[⁰¹²³⁴⁵⁶⁷⁸⁹]"
)


def _power_left_after(text: str, end: int) -> bool:
    """True if a letter power after the fraction that ends at `end` is left as printed on
    the first run, where it would be read after the fraction's words on a second run."""
    if _LETTER_POWER_AFTER.match(text, end):
        return not _STATISTICS_SQUARE.match(text, end + 1)  # "1/5 R²": the statistics step's
    chain = _CHAIN_POWER_AFTER.match(text, end)
    return chain is not None and _unit_chain(text, chain.start("base"))


def _fractions(text: str) -> list[Candidate]:
    found = []
    for match in _FRACTION.finditer(text):
        if _x_left_alone(text, match.end()) or _power_left_after(text, match.end()):
            continue  # "1/5 m⁶", "2/3 m s⁻²"; "1/5 R²" is read, the statistics step reads "R²"
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
        if minutes and _hyphen_range_after(words, text, match.end(), len(str(minutes))):
            continue  # "um 13:30-1500": "13 Uhr 30-1500" would be a range on a second run
        found.append(Candidate(*match.span(), words, f'time "{match.group()}" read as "{words}"'))
    return found


def _hyphen_range_after(words: str, text: str, end: int, digits: int) -> bool:
    """True if the number that ends `words`, the reading of what ends at `end`, starts a
    hyphen range `_ranges` reads with what follows (#970). Only a window after `end` is
    looked at, so long blocks stay linear."""
    around = words + text[end : end + WINDOW]
    return _hyphen_range_at(around, len(words) - digits)


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
    # after an x glued to a number too, which the units step reads "mal": "1x1^1"
    r"(?:(?<![\w,])|(?<=\d[xX])|(?<=\d [xX]))"
    + _STOP
    + r"(?P<base>\d+|[^\W\d_"
    + _SUPERSCRIPTS
    + r"])"
    r"(?P<exp>\^(?:\{(?P<braced>[+\u2212-]?\d+)\}|\((?P<paren>[+\u2212-]?\d+)\)|(?P<bare>[+\u2212-]?\d+)))"
    # but an x and a digit, which the units step may read "mal" ("10^2x1"; `_x_left_alone`
    # keeps the power as printed where it does not, #253)
    r"(?!(?![xX]\d)[\w.,⁺⁻])"
)
# a signed power of a bracketed term, "(I − P)⁻¹" (an inverse), its raise printed or in its
# run (#815, as numbers.py for #589); not before a letter or digit, which may go on the power
_BRACKET_POWER = re.compile(
    r"(?P<base>[)\]])(?P<exp>[⁺⁻][" + _SUPERSCRIPTS + r"]+)(?![\w⁺⁻^" + _SUPERSCRIPTS + "])"
)
_TIMES_TEN = re.compile(r"(?<=\d)\s*[×x]\s*(?P<base>10)(?P<exp>[\u2212-]\d{1,3})(?![\w⁺⁻]|[.,]\d)")
# not after a number and a space ("5 m²", the units step's), but after a time ("24:00 n²",
# which reads "24 Uhr n²", #253)
_LETTER_POWER = re.compile(
    r"(?<![\w/])(?<!(?<!\^)(?<!:\d)\d\s)(?<!,\s)(?P<base>[^\W\d_"
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


_CLOCK_BEFORE = re.compile(r"(?<![\d:])\d{1,2}:\d\d\s+\Z")


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
    for match in _BRACKET_POWER.finditer(text):
        words = f" hoch {_exponent_words(match['exp'])}"
        found.append((_power(text, match, words), None))
    for match in _CARET.finditer(plain):
        exponent = match["braced"] or match["paren"] or match["bare"]
        letter = match["base"].isalpha()
        before = _before(plain, match.start("base"))
        # the minutes of a clock time are no number before it, as for a raised power: "um
        # 24:00 R^2" reads "24 Uhr R^2" on a first run, whose "R^2" a second run reads (#970)
        clock = letter and _CLOCK_BEFORE.search(plain, max(0, match.start() - 16), match.start())
        if letter and (
            _unit_chain(plain, match.start("base"))
            or (_NUMBER_BEFORE.search(before) and not clock)
            or unit_read_after_per(plain, match.start("base"), "de")
        ):
            continue  # "5 m^2", "pro m^2": the units step's ("5 Quadratmeter", #230)
        if clock and unit_starts_at(plain, match.start("base"), "de"):
            continue  # "um 13:30 m^2": a unit after a time is left as printed, as the time is
        words = (_letter_power(exponent) if letter else None) or (
            f" hoch {_exponent_words(exponent)}"
        )
        found.append((_power(text, match, words), None if letter else match.start("base")))
    for match in _LETTER_POWER.finditer(plain):
        if match["base"] in _SQUARED_STATISTICS and match["exp"] == "²":
            continue
        if _unit_chain(plain, match.start("base")) or unit_read_after_per(
            plain, match.start("base"), "de"
        ):
            continue  # "2 m s⁻¹", "pro m³": the units step's (#230)
        if _CLOCK_BEFORE.search(plain, max(0, match.start() - 16), match.start()) and (
            unit_starts_at(plain, match.start("base"), "de")
        ):
            continue  # "um 13:30 m²": a unit after a time is left as printed, as the time is
        exponent = "".join(_SUPER_DIGIT.get(c, c) for c in match["exp"])
        words = _letter_power(exponent) or f" hoch {_exponent_words(match['exp'])}"
        found.append((_power(text, match, words), None))
    # as in English (numbers.py): a power joined to a number after it, or a number base joined
    # to a number before it, is left as printed
    read_as_ein: set[int] | None = None
    kept = []
    for c, base in found:
        joined = _LABEL_JOINED_AFTER.match(text, c.end)
        if joined and text[joined.end() - 1].isdigit():
            # "R³ : 1/5" is "R³ : ein Fünftel" after the first run: no number joins the power
            # there, so it is read on both runs (#970)
            if read_as_ein is None:
                read_as_ein = _read_as_ein(text)
            if joined.end() - 1 in read_as_ein:
                joined = None
        kept.append((c, base, joined))
    return [
        c
        for c, base, joined in kept
        if joined is None
        and not (
            c.replacement[-1:].isdigit()
            and _DASH_DIGIT.match(text, c.end)
            and not _DASH_RANGE.match(text, c.end)
        )
        and not _unit_left_alone(text, c.end)
        # "× 10-2 x1": "hoch minus 2 x1" would read "mal" on a second run ("x^2 x^2" is read)
        and not (c.replacement[-1:].isdigit() and _x_left_alone(text, c.end))
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
# the keywords that number a part of a text: their one numeral is read before a full stop too
# ("Kapitel I. Einleitung" as "Kapitel I, Einleitung" is, #976); after any other keyword
# ("Typ I.", "Phase II.") such a numeral is left as printed, as is "Ludwig XIV.", and so is a
# run ("Teil II und III.")
_PART_KEYWORDS = frozenset(
    {"kapitel", "teil", "teile", "abschnitt", "anhang", "band", "bände"}
    | {"kap", "abschn", "anh", "bd"}
)
_ROMAN = r"[IVX]{1,6}"
# a number joined after a Roman numeral or a label's number; unlike `_JOINED_AFTER` not by a
# space, since German has no rule that joins "1 395" (and "Kapitel I 12.03.2019" reads the
# date as words)
_CLOSE_JOINED_AFTER = re.compile(r"\s*[\u2013\u2014\u2012:/-]\s*[.,]?\d|[.,]?\d|[⁺⁻^⁰¹²³⁴⁵⁶⁷⁸⁹]")


@cache
def _roman_run() -> re.Pattern[str]:
    return re.compile(
        r"(?<![\w-])(?P<keyword>[^\W\d_]+)(?P<dot>\.)?(?(dot)\s*|\s+)(?P<run>"
        + _ROMAN
        + r"(?:(?:\s*[/\u2013-]\s*|,\s*|\s+(?:und|oder|&)\s+)"
        + _ROMAN
        # with a full stop glued on after it, it is left as printed ("Kapitel I.2"); before a
        # full stop and white space or the end, only one numeral after a part's keyword is
        # read (`_PART_KEYWORDS`)
        # nor a run cut short before such a numeral: "Teil II und III." is left whole, and so
        # is a range joined by "bis", read none as "Kapitel I. bis III." is (#996, #1010)
        # nor before " %": "Kapitel I %CI" ("1 %CI" would read the CI on a second run)
        # ... but a full stop glued to a sign may stand before the sign's words on a second
        # run ("Kapitel IV.=1" is "Kapitel IV. gleich 1" then): the statistics step decides
        # (#1010)
        + r")*)(?![\w⁺⁻%]|\.(?!\s|\Z|"
        + _sign_start()
        + r")|\s+%|\s+(?:Quadrat|hoch)\b"
        + r"|(?:\s*[/\u2013-]\s*|,\s*|\s+(?:und|oder|&)\s+)"
        + _ROMAN
        + r"|\s+bis\s+"
        + _ROMAN
        + r"(?!\w)"
        + ")"
    )


# a list that goes on after a numeral's full stop ("Kapitel I. und II.", "Kapitel I. bis
# III."): the first numeral is no part number on its own, so the list stays as printed as a
# whole, as "Teil II und III." does (#996)
_LIST_AFTER_STOP = re.compile(
    r"\.(?:,\s*|\s+(?:und|oder|&|bis)\s+|\s*[/\u2013-]\s*)" + _ROMAN + r"(?!\w)"
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
    for match in _roman_run().finditer(plain):
        keyword = match["keyword"]
        known = _ABBREVIATED_KEYWORDS if match["dot"] else _KEYWORDS
        if keyword.lower() not in known:
            continue
        keyword += match["dot"] or ""
        if _CLOSE_JOINED_AFTER.match(plain, match.end("run")) or _X_AFTER.match(
            plain, match.end("run")
        ):
            continue  # "Kapitel I-3", "Kapitel I x1": "1-3" a range, "1 x1" "1 mal 1" next time
        stop = match.end("run")
        glued_after_stop = plain[stop + 1 : stop + 2]
        if plain[stop : stop + 1] == "." and glued_after_stop and not glued_after_stop.isspace():
            sign = first_from(readings_of("statistics", plain, "de"), stop + 1)
            if sign is None or sign.start != stop + 1:
                continue  # "Kapitel IV.==1": the sign stays as printed, so does the numeral
        offset = match.start("run")
        parts = list(_ROMAN_PART.finditer(match["run"]))
        if not all(_roman_value(p["numeral"]) for p in parts if p["numeral"]):
            continue  # "Typ IIX": not a numeral, so nothing in the run is read as one
        if plain[match.end("run") : match.end("run") + 1] == "." and (
            match["keyword"].lower() not in _PART_KEYWORDS
            or len(parts) > 1
            or _LIST_AFTER_STOP.match(plain, match.end("run"))
            or _ordinal_on_a_second_run(plain, *match.span("run"), str(_roman_value(match["run"])))
        ):
            continue  # "Typ I.", "Teil II und III.", "Kapitel I. und II.", "Kapitel I. Teil"
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


def _ordinal_on_a_second_run(plain: str, start: int, end: int, digits: str) -> bool:
    """True if the numeral at `start`, read as `digits`, makes an ordinal or a date with the
    full stop after it on a second run ("Kapitel I. Teil" is "Kapitel 1. Teil" then, whose
    "1." is "erster"; "Kapitel I. Mai"): it is left as printed there, as before (#976). An
    abbreviated keyword is its words there ("Kap. I. Kapitel" is "Kapitel 1. Kapitel"). Only
    the text around the numeral is looked at, so long blocks stay linear."""
    low = max(0, start - 2 * WINDOW)
    before = plain[low:start]
    read = _read_before(plain, start)
    if read is not None and read[0] >= low:
        printed = plain[read[0] : start]
        gap = printed[len(printed.rstrip()) :]
        before = plain[low : read[0]] + read[1] + gap
    around = before + digits + plain[end : end + 2 * WINDOW]
    at, stop = len(before), len(before) + len(digits) + 1  # the full stop with it
    return any(c.start < stop and c.end > at for c in (*_ordinals(around), *_dates(around)))


# --- all rules -------------------------------------------------------------------------------


def find_numbers_de(text: str) -> list[Candidate]:
    """The German number edits for one block's text, without overlap, in text order.

    Rules come most specific first: a date is not also read as ordinals or a range, a label's
    "2.5" not as a decimal.
    """
    # the other rules read the text as a second run sees it after the arrows: "←−1:1" is
    # "←1:1", so its ratio is read on both runs, not left after "−" on the first (#593)
    found_arrows = arrows(text)
    after = _AfterNumber(text)  # the printed text: the statistics step reads its arrows whole
    text = as_one_arrow(text, found_arrows)
    plain = fold(text)
    powers = _powers(text, plain)
    worded = _WordedPowers(after, powers)
    labelled, kept = _labelled(text)
    kept = sorted(kept + _file_numbers(text))
    found = pick(
        [
            *found_arrows,
            *_dates(text, after),
            *_ordinals(text, after),
            *_roman_numerals(plain),
            *labelled,
            *powers,
            *_times(text),
            *_decimals(text, after),
            *_thousands(text, worded),
            *_years(text, worded),
            *_ranges(text, worded),
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
_FILE_SHAPE = FILE_NUMBER_DE
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
