# ruff: noqa: RUF001, RUF003
# (minus signs, dashes and Greek letters are what these texts are about)
"""German numbers, dates and statistics (#130): the numbers and statistics steps' German rules."""

import gc
import re
import time
from collections.abc import Callable, Iterator

import pytest
from hypothesis import given
from linear_time import assert_linear
from notation_texts import german_notation_documents

from sci2audio.core import BlockKind, Document, apply_edits
from sci2audio.testing import check_text_step, make_document, rebuilt_from_script
from sci2audio.textprep import (
    AbbreviationStep,
    NumbersStep,
    StatisticsStep,
    StepContext,
    UnitStep,
    run_steps,
    spoken_text,
)
from sci2audio.textprep.abbreviations import _Removals
from sci2audio.textprep.numbers_de import ordinal, year_words
from sci2audio.textprep.statistics_de import say_decimal

DE = StepContext("de")
NUMBERS = NumbersStep()
STATISTICS = StatisticsStep()


def read(step: NumbersStep | StatisticsStep, text: str) -> str:
    document = make_document([(BlockKind.PARAGRAPH, text)], "de")
    return spoken_text(apply_edits(document, step.find(document, DE)))


def read_all(text: str) -> str:
    """The whole chain of built-in steps, as a German job runs it."""
    document = make_document([(BlockKind.PARAGRAPH, text)], "de")
    return spoken_text(run_steps(document, DE, strict=True).script())


# ---- number words ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("n", "word"),
    [
        (1, "erste"), (2, "zweite"), (3, "dritte"), (7, "siebte"), (8, "achte"),
        (11, "elfte"), (16, "sechzehnte"), (19, "neunzehnte"), (20, "zwanzigste"),
        (21, "einundzwanzigste"), (31, "einunddreißigste"), (100, "hundertste"),
        (101, "hunderterste"), (103, "hundertdritte"), (120, "hundertzwanzigste"),
        (200, "zweihundertste"), (1000, "tausendste"), (2019, "zweitausendneunzehnte"),
        (999_999, "neunhundertneunundneunzigtausendneunhundertneunundneunzigste"),
    ],
)  # fmt: skip
def test_ordinal_words(n: int, word: str) -> None:
    assert ordinal(n, "e") == word


@pytest.mark.parametrize("n", [0, -1, 1_000_000])
def test_no_ordinal_outside_its_range(n: int) -> None:
    with pytest.raises(ValueError, match="no German ordinal"):
        ordinal(n, "e")


@pytest.mark.parametrize(
    ("year", "words"),
    [(1998, "19 hundert 98"), (1900, "19 hundert"), (1100, "11 hundert"), (1099, "1099"),
     (2019, "2019"), (1905, "19 hundert 5")],
)  # fmt: skip
def test_year_words(year: int, words: str) -> None:
    assert year_words(year) == words


@pytest.mark.parametrize(
    ("number", "words"),
    [("2,45", "2 Komma 4 5"), ("2.45", "2 Komma 4 5"), (".05", "0 Komma 0 5"),
     ("−.32", "−0 Komma 3 2"), ("34", "34"), ("2,50", "2 Komma 5 0")],
)  # fmt: skip
def test_say_decimal(number: str, words: str) -> None:
    assert say_decimal(number) == words


# ---- the numbers step --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("printed", "said"),
    [
        # N-de-1 decimals
        ("2,5 und 2,45 und 0,05", "2 Komma 5 und 2 Komma 4 5 und 0 Komma 0 5"),
        ("2,50", "2 Komma 5 0"),  # trailing zeros kept
        ("1.234,5", "1234 Komma 5"),
        ("r = .45, p < .05", "r = 0 Komma 4 5, p < 0 Komma 0 5"),
        ("M = 2.345 und r = −.32", "M = 2 Komma 3 4 5 und r = −0 Komma 3 2"),
        (
            "Abschnitt 2.5, Abb. 3.1 und Version 2.1.3",
            "Abschnitt 2 Punkt 5, Abb. 3 Punkt 1 und Version 2 Punkt 1 Punkt 3",
        ),
        ("Abschnitte 2.1 und 2.2", "Abschnitte 2 Punkt 1 und 2 Punkt 2"),
        # N-de-2 thousands
        ("1.234 Teilnehmer und 12.345.678", "1234 Teilnehmer und 12345678"),
        ("N = 1.234", "N = 1234"),
        # N-de-3 years
        ("im Jahr 1998", "im Jahr 19 hundert 98"),
        ("seit 1998 gibt es", "seit 19 hundert 98 gibt es"),
        ("im März 1998 Daten", "im März 19 hundert 98 Daten"),
        ("zwischen 1990 und 1995", "zwischen 19 hundert 90 und 19 hundert 95"),
        ("die 1990er-Jahre", "die 19 hundert 90er-Jahre"),
        ("Ende 1900", "Ende 19 hundert"),
        ("bis 1998 und S. 1–1234", "bis 19 hundert 98 und S. 1 bis 1234"),
        # N-de-4 ranges
        ("3–5, 3 – 5, 3-5", "3 bis 5, 3 bis 5, 3 bis 5"),
        ("2010–2015 und 1,2–3,4", "2010 bis 2015 und 1 Komma 2 bis 3 Komma 4"),
        # N-de-5, N-de-6 ordinals and dates
        ("am 3. Mai 2019", "am dritten Mai 2019"),
        ("der 3. Platz", "der dritte Platz"),
        ("in der 3. Auflage", "in der dritten Auflage"),
        ("die 2. Welle", "die zweite Welle"),
        ("im 20. Jahrhundert", "im zwanzigsten Jahrhundert"),
        (
            "1. Auflage, 20. Jahrhundert, 2. Weltkrieg",
            "erste Auflage, zwanzigstes Jahrhundert, zweiter Weltkrieg",
        ),
        ("3. Mai", "dritter Mai"),
        ("vom 3. bis 5. Mai", "vom dritten bis fünften Mai"),
        ("12.03.2019 und am 1.3.2020", "zwölfter März 2019 und am ersten März 2020"),
        ("2019-03-12 und am 2019-03-12", "zwölfter März 2019 und am zwölften März 2019"),
        ("am 12.03.1998", "am zwölften März 19 hundert 98"),
        ("am 3.4. kam", "am dritten April kam"),
        # N-de-7 fractions
        ("1/2, 1/4, 3/4, 2/3, 17/20", "ein halb, ein Viertel, 3 Viertel, 2 Drittel, 17 von 20"),
        # N-de-8 ratios and times
        ("3:1", "3 zu 1"),
        ("8:64–77", "8 zu 64 bis 77"),  # read as a ratio, unlike English
        ("13:30 Uhr, um 13:30, 9.05 Uhr, 15:00 Uhr", "13 Uhr 30, um 13 Uhr 30, 9 Uhr 5, 15 Uhr"),
        # N-de-9 powers
        ("10⁶ und 10⁻⁴ und 10^6", "10 hoch 6 und 10 hoch minus 4 und 10 hoch 6"),
        ("3 × 10−4", "3 × 10 hoch minus 4"),
        ("x² und y³", "x Quadrat und y hoch 3"),
        ("x^2 und 5 m^2", "x Quadrat und 5 m^2"),  # after a number: the units step's
        # N-de-10 Roman numerals
        ("Kapitel IV", "Kapitel 4"),
        ("Phase II und III, Typ I–III", "Phase 2 und 3, Typ 1 bis 3"),
        ("Abb. II", "Abb. 2"),
    ],
)  # fmt: skip
def test_german_numbers_read_as_said(printed: str, said: str) -> None:
    assert read(NUMBERS, printed) == said


@pytest.mark.parametrize(
    "printed",
    [
        "2019 und 1066 und 10 000",  # read right by the voice
        "1234 Teilnehmer",  # a count: the voice reads it right
        "um 1500 Teilnehmer",  # a noun follows: a count, not a year
        "nach 1500 Versuchen",
        "2.5 Mio",  # a point between digits in running text is ambiguous
        "Es waren 3. Die Studie",  # no article and no known noun
        "in 3. Auflage",  # a preposition alone does not tell the case
        "Ludwig XIV.",  # no keyword
        "Kapitel IV.",  # a full stop after it: left as printed (plan, N-de-10)
        "31.2.2019",  # no such day
        "3.4.",  # a list or a version without "am" before it
        "1,2,3",  # a list, not a decimal
        "3/2 und 24/7",  # no reading right everywhere
        "R² und 5 m²",  # the statistics and units steps'
    ],
)
def test_what_the_voice_reads_right_or_is_unclear_is_left_alone(printed: str) -> None:
    assert read(NUMBERS, printed) == printed


def test_english_rules_are_not_used_for_german() -> None:
    assert read(NUMBERS, "1234 participants and 2.50") == "1234 participants and 2.50"
    assert NUMBERS.handles("de-AT")


def test_each_german_edit_quotes_the_printed_text() -> None:
    document = make_document([(BlockKind.PARAGRAPH, "am 3. Mai lag p bei 2,5")], "de")
    reasons = [edit.reason for edit in NUMBERS.find(document, DE)]
    assert reasons == [
        'ordinal "3." read as "dritten"',
        'decimal "2,5" read as "2 Komma 5"',
    ]


# ---- the statistics step -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("printed", "said"),
    [
        ("p < .05 und x > 3", "p kleiner als .05 und x größer als 3"),
        (
            "x ≤ 3, y ≥ 4, z ≠ 5, a = 1",
            "x kleiner oder gleich 3, y größer oder gleich 4, z ungleich 5, a gleich 1",
        ),
        ("12 ± 3", "12 plus minus 3"),
        ("t(34) = 2", "t mit 34 Freiheitsgraden gleich 2"),
        ("t(34,5) = 2", "t mit 34 Komma 5 Freiheitsgraden gleich 2"),
        ("F(2, 57) = 3", "F mit 2 und 57 Freiheitsgraden gleich 3"),
        ("F(1; 57) = 3", "F mit 1 und 57 Freiheitsgraden gleich 3"),
        ("χ²(1) = 5", "Chi-Quadrat mit 1 Freiheitsgrad gleich 5"),
        ("χ²(2, N = 1.234) = 5", "Chi-Quadrat mit 2 Freiheitsgraden, N gleich 1234 gleich 5"),
        ("R² = .31 und ηp² = .12", "R Quadrat gleich .31 und partielles Eta-Quadrat gleich .12"),
        ("ω² = 1, R2 = 1", "Omega-Quadrat gleich 1, R Quadrat gleich 1"),
        ("95 %-KI [1,2; 3,4]", "95 % Konfidenzintervall 1 Komma 2 bis 3 Komma 4"),
        ("95 % KI [1, 3]", "95 % Konfidenzintervall 1 bis 3"),
        ("KI = [−0,3; 0,1]", "Konfidenzintervall gleich −0 Komma 3 bis 0 Komma 1"),
        ("KIs [1; 2] und [3; 4]", "Konfidenzintervalle 1 bis 2 und 3 bis 4"),
        ("95 % CI [1.2, 3.4]", "95 % Konfidenzintervall 1 Komma 2 bis 3 Komma 4"),
        ("OR = 2,5", "Odds Ratio gleich 2,5"),
    ],
)  # fmt: skip
def test_german_statistics_read_as_said(printed: str, said: str) -> None:
    assert read(STATISTICS, printed) == said


@pytest.mark.parametrize("printed", ["KI ist wichtig", "Der R2 war", "OR und", "[1,3] KI"])
def test_german_statistics_left_alone(printed: str) -> None:
    assert read(STATISTICS, printed) == printed


def test_english_statistics_are_unchanged() -> None:
    document = make_document([(BlockKind.PARAGRAPH, "t(34) = 2, p < .05")])
    english = spoken_text(apply_edits(document, STATISTICS.find(document, StepContext("en"))))
    assert english == "t of 34 equals 2, p less than .05"


# ---- the whole chain ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("printed", "said"),
    [
        (
            "Der Effekt war signifikant, t(34) = 2,45, p < .05, d = 0,42.",
            "Der Effekt war signifikant, t mit 34 Freiheitsgraden gleich 2 Komma 4 5, "
            "p kleiner als 0 Komma 0 5, d gleich 0 Komma 4 2.",
        ),
        (
            "95 %-KI [1,2; 3,4] und OR = 2,5",
            "95 Prozent Konfidenzintervall 1 Komma 2 bis 3 Komma 4 und Odds Ratio gleich 2 Komma 5",
        ),
        (
            "Die Proben wogen 2,5 kg; 1 kg reichte; 10⁻⁴ mol",
            "Die Proben wogen 2 Komma 5 Kilogramm; ein Kilogramm reichte; 10 hoch minus 4 Mol",
        ),
        (
            "Siehe Abb. 3.1 und Kap. IV, im 19. Jh. und S. 12",
            "Siehe Abbildung 3 Punkt 1 und Kapitel 4, im neunzehnten Jahrhundert und Seite 12",
        ),
        (
            "Wir befragten 1.234 Personen von 13:30 Uhr bis 15:00 Uhr; 3/4 stimmten zu (3:1).",
            "Wir befragten 1234 Personen von 13 Uhr 30 bis 15 Uhr; 3 Viertel stimmten zu (3 zu 1).",
        ),
    ],
)
def test_a_german_job_reads_numbers_and_statistics(printed: str, said: str) -> None:
    assert read_all(printed) == said
    assert read_all(said) == said  # a second run changes nothing


# texts the second-run properties found: each reading is one a second run leaves as it is
@pytest.mark.parametrize(
    ("printed", "said"),
    [
        # left as printed: the reading would give another rule or step something new to read
        ("um 13:30⁻⁴", "um 13:30⁻⁴"),
        ("um 13:30 N", "um 13:30 N"),
        ("um 13:30 Uhr N", "um 13:30 Uhr N"),
        ("1:2,5:", "1:2,5:"),
        ("1,0-1", "1,0-1"),  # "1 Komma 0-1" would be a range
        ("x.2,5", "x.2,5"),
        ("x⁴–1", "x⁴–1"),  # "x hoch 4–1" would be a range
        ("r = 1.234-1998", "r gleich 1.234-1998"),
        ("1x⁶", "1x⁶"),  # no "1 mal ⁶"
        ("1:1-3", "1:1-3"),
        ("am 12.03.2019:1", "am 12.03.2019:1"),
        ("Abschnitt 2.5 und 2.612-1", "Abschnitt 2.5 und 2.612-1"),
        ("Kapitel I%", "Kapitel I%"),
        ("1/5 m⁶", "1/5 m⁶"),
        ("10^21:1", "10^21:1"),
        ("1:15 m²", "1:15 m²"),
        ("KI [1; 2]–3", "Konfidenzintervall [1; 2]–3"),
        ("R² = .05,2019-03-12", "R Quadrat gleich .05,2019-03-12"),
        # read, as a second run would read it
        ("t(1)=1x", "t mit 1 Freiheitsgrad gleich 1x"),  # "gleich 1x" as "=1x": a variable
        ("Abb.2,5–3", "Abbildung 2 Komma 5 bis 3"),
        ("Abb.1.234", "Abbildung 1 Punkt 234"),
        ("Abb.1:1", "Abbildung 1 zu 1"),
        ("Abb. .45", "Abbildung 0 Komma 4 5"),
        ("Jh.CI [1; 2]", "Jh.Konfidenzintervall 1 bis 2"),
        ("Jh.=1", "Jahrhundert gleich 1"),
        ("1 %KI", "1 %Konfidenzintervall"),
        ("1<CI(", "1<Konfidenzintervall ("),
        ("10⁶–10⁷", "10 hoch 6 bis 10 hoch 7"),
        ("am 12.03.2019x", "am zwölften März 2019 mal"),
        ("im Jahr 1998x", "im Jahr 19 hundert 98 mal"),
        ("im 1234–1.234", "im 12 hundert 34 bis 1234"),
        ("seit 1.998 %", "seit 1998 Prozent"),
        ("am 3.4.=1", "am dritten April gleich 1"),
        ("1x1:1", "1 mal 1 zu 1"),
        ("1:1x", "1 zu 1 mal"),
        ("x^2 x^2", "x Quadrat x Quadrat"),
        ("R² = .05. Jahr", "R Quadrat gleich 0 Komma 0 5. Jahr"),  # no "fünftes Jahr"
        ("1 η² x⁶", "1 Eta-Quadrat x hoch 6"),
        ("am 3. Jh. x⁶", "am dritten Jahrhundert x hoch 6"),
        ("am 3.4. R⁶", "am dritten April R hoch 6"),
        ("R² = .05 bis 12.03.2019", "R Quadrat gleich 0 Komma 0 5 bis zwölften März 2019"),
        ("10^25 m^2", "10 hoch 25 Quadratmeter"),
        ("5 m^2.45:1", "5 Quadratmeter.45 zu 1"),
        ("1/1 R² = .05", "1 von 1 R Quadrat gleich 0 Komma 0 5"),
        ("5 m⁻⁴² x⁶", "5 Meter⁻⁴² x hoch 6"),
        ("2,5Å", "2 Komma 5 Ångström"),
        ("1.234Å", "1234 Ångström"),
        ("×.2,5", "mal.2 Komma 5"),
        # review of PR #242: nightly seeds 303 and 505
        ("seit 1998x mehr", "seit 1998 mal mehr"),
        ("bis 1998x mehr", "bis 1998 mal mehr"),
        ("95 %-KI [1; 1],1–1", "95 Prozent Konfidenzintervall [1; 1],1 bis 1"),
        ("1–11–1 N 1/12", "1 bis 11–1 N 1/12"),
        (
            "Kapitel I %CI",
            "Kapitel I %CI",
        ),  # seed 1717, review round 2  # seed 303 after round 1: no "Newton"
        (
            "Das KI [1,2; 3,4],1–2 war breit.",
            "Das Konfidenzintervall [1 Komma 2; 3 Komma 4],1 bis 2 war breit.",
        ),
        # #253: nightly seeds 66, 222 and 11 on main
        ("10⁶ x1", "10 hoch 6 mal 1"),
        ("im 1234-1234", "im 12 hundert 34-1234"),
        ("1–11.3.2020", "1 bis elften März 2020"),
        ("vom 1.3.2020–11.3.2020", "vom ersten März 2020 bis elften März 2020"),
        # review of PR #263 (F1, F2): no "bis" for the dash, no date after it, as on main;
        # an em dash between full dates is a range like the en dash
        ("vom 1.–3.4.2020", "vom 1.–3.4.2020"),
        ("vom 1.3.–11.3.2020", "vom ersten März–11.3.2020"),
        ("1.3.2020\u201411.3.2020", "erster März 2020 bis elften März 2020"),
        ("110⁶–1234", "110⁶ bis 1234"),
        ("1 × 10-2 x1–1", "1 mal 10-2 x1 bis 1"),
        ("im 1500—1234", "im 15 hundert bis 12 hundert 34"),
        ("um 24:00 n²", "um 24 Uhr n Quadrat"),
        ("um 13:30 m² Fläche", "um 13:30 m² Fläche"),
        ("Abschnitt 1.234-2011", "Abschnitt 1.234-2011"),
        # an ordinal before the abbreviation of its noun, which the abbreviations step reads
        ("Daten zeigt 12. Kap. (S. 3).", "Daten zeigt zwölftes Kapitel (Seite 3)."),
        ("12. Kap. 3", "zwölftes Kapitel 3"),
        ("Siehe 12. Kap. dazu.", "Siehe zwölftes Kap. dazu."),
        ("die 12. Aufl. erschien", "die zwölfte Auflage erschien"),
        ("5x× 3", "5x mal 3"),
        # review of PR #256 (D1): an abbreviation before a link the links step removes
        ("Siehe Kap. https://x.org/a (ebd., S. 3).", "Siehe Kapitel (ebenda, Seite 3)."),
        # an opener the links step removes with the link, and a long gap (PR #263 review G1)
        ("Siehe Kap. <https://x.org/a> 3 dazu.", "Siehe Kapitel 3 dazu."),
        ("Siehe Kap. (siehe https://x.org/a) 3 dazu.", "Siehe Kapitel 3 dazu."),
        ("Siehe Kap.          https://x.org/a 3 dazu.", "Siehe Kapitel 3 dazu."),
        ("Kap. www.x.org 3 zeigt", "Kapitel 3 zeigt"),
        ("10^{-3}.1.234", "10^{-3}.1.234"),  # nightly seed 11 after the fixes above
        ("1–1im 1500-1998", "1 bis 1im 15 hundert bis 19 hundert 98"),  # seed 222 after them
        ("im 1234-1998", "im 12 hundert 34 bis 19 hundert 98"),
        ("im 1500-1998 m", "im 1500 bis 1998 Meter"),
        ("1-2,5-", "1-2,5-"),  # seed 6005
        ("1-2,5 m", "1 bis 2 Komma 5 Meter"),
        ("um 13:30. Jahr", "um 13 Uhr 30. Jahr"),  # seed 6003
        ("um 13 Uhr 30. Mai", "um 13 Uhr 30. Mai"),
        ("10^2x1", "10 hoch 2 mal 1"),  # seed 7001
        ("am 12.03.2019 x .45", "am zwölften März 2019 mal 0 Komma 4 5"),  # seed 8007
        ("Ft\u00adt(1998)=1", "Ftt gleich 1"),  # seed 6007: a soft hyphen in a name
        # #269 (seed 13001): a sign unit glued before a letter is still a unit
        ("R²=.05%12.03.2019", "R Quadrat gleich .05%zwölfter März 2019"),
        ("Es sind 0,05%12.03.2019", "Es sind 0,05%zwölfter März 2019"),
        ("r = .05%3. Platz", "r gleich .05%dritter Platz"),
        ("Es sind 0,05%a.", "Es sind 0,05%a."),
        ("Eine 2,5%ige Lösung.", "Eine 2 Komma 5%ige Lösung."),  # an adjective of it
        ("Ein 2,5‰iger Anteil.", "Ein 2 Komma 5‰iger Anteil."),
        # PR #273 review: coordinates read as before, glued or spaced (F1) ...
        ("Bei 52,5°N und 13,4°O.", "Bei 52 Komma 5°N und 13 Komma 4°O."),
        ("Bei 52,5 °N gemessen.", "Bei 52 Komma 5 °N gemessen."),
        ("Bei 52,5°NNE.", "Bei 52 Komma 5°NNE."),
        # ... and a dotted unit keeps the rule of a word (F2), as on main
        ("Es dauerte 1,5 Min.Pause.", "Es dauerte 1 Komma 5 Min.Pause."),
        ("Es waren 2,5 Mio.Einwohner.", "Es waren 2,5 Mio.Einwohner."),
    ],
)
def test_a_second_run_reads_nothing_new(printed: str, said: str) -> None:
    assert read_all(printed) == said
    assert read_all(said) == said


@pytest.mark.timeout(60)
@pytest.mark.parametrize(
    ("sized", "size"),
    [
        (
            lambda n: (
                "Am 3. Mai 1998 lag r = .45 (t(34) = 2,45; 95 %-KI [1,2; 3,4]) bei 1/2 von 10⁶. "
                * n
            ),
            1500,
        ),
        (lambda n: "1–" * n, 50_000),
        (lambda n: "der " + "3. " * n + "Mai", 30_000),
        (lambda n: "Kapitel " + "I/" * n, 30_000),
        (lambda n: "1.234." * n, 20_000),
        (lambda n: "a" + " " * n + "seit 1998", 100_000),
    ],
    ids=["sentences", "dashes", "ordinals", "roman-run", "points", "long-space"],
)
def test_long_german_blocks_take_linear_time(sized: Callable[[int], str], size: int) -> None:
    def run(text: str) -> None:
        document = make_document([(BlockKind.PARAGRAPH, text)], "de")
        NUMBERS.find(document, DE)
        STATISTICS.find(document, DE)

    assert_linear(run, sized, size)  # 8 times the text against a base run (#276)


def _abbreviations_seconds(text: str) -> float:
    """The best of three runs of the abbreviations step alone, gc off while it runs, so a
    collection or a busy runner does not decide (#274)."""
    document = make_document([(BlockKind.PARAGRAPH, text)], "de")
    best = float("inf")
    for _ in range(3):
        gc.collect()
        gc.disable()
        try:
            started = time.perf_counter()
            AbbreviationStep().find(document, DE)
            best = min(best, time.perf_counter() - started)
        finally:
            gc.enable()
    return best


@pytest.mark.timeout(180)
@pytest.mark.parametrize(
    ("unit", "count"),
    [
        ("Siehe Kap. https://x.org/a dazu. ", 1_000),
        ("Kap. https://x.org/a Kap. x ", 1_000),
        ("Siehe Kap. dazu. ", 4_000),  # faster per character: more of it, for a fair timing
    ],
    ids=["link-after-label", "dense", "no-link"],
)
def test_the_link_look_ahead_of_the_abbreviations_step_takes_linear_time(
    unit: str, count: int
) -> None:
    """Review of PR #263 (F3): the look past a removed link after an abbreviation runs the
    links step's pass once per block and bisects it. Eight times the text takes about eight
    times as long; the limit, 32, is four times that and half of quadratic, so a shared
    runner does not decide (#274: the macOS runner measured 8.7 for four times the text)."""
    small = _abbreviations_seconds(unit * count)
    large = _abbreviations_seconds(unit * count * 8)
    assert large < 32 * max(small, 0.05)


class _CountedSpans(list[tuple[int, int]]):
    """The removals of a block, counting every one that is looked at."""

    looked_at = 0

    def __iter__(self) -> Iterator[tuple[int, int]]:
        for span in super().__iter__():
            self.looked_at += 1
            yield span

    def __getitem__(self, index):  # type: ignore[no-untyped-def]
        self.looked_at += 1
        return super().__getitem__(index)


@pytest.mark.parametrize(
    "unit",
    ["Siehe Kap. https://x.org/a dazu. ", "Kap. https://x.org/a Kap. x "],
    ids=["link-after-label", "dense"],
)
def test_the_link_look_ahead_looks_at_one_removal_per_abbreviation(unit: str) -> None:
    """#274: the timing test above cannot tell the quadratic look-ahead of the #263 review
    from a busy runner on small blocks (its end-to-end ratio was 7 for four times the text,
    as the links pass dominates). Counted instead: each look past an abbreviation looks at
    one removal, found by bisection, not at every removal before it."""
    text = unit * 2_000
    ends = [match.end() for match in re.finditer(r"Kap\.", text)]
    removals = _Removals(text, BlockKind.PARAGRAPH, "", "de")
    assert removals.past(ends[0]) is not None  # the links pass runs here, once
    counted = _CountedSpans(removals._spans or ())
    removals._spans = counted
    for end in ends:
        removals.past(end)
    assert counted.looked_at <= len(ends)


def test_the_units_step_skips_many_file_numbers_in_linear_time() -> None:
    # review round 2 of PR #242: one walk over the file-number spans, not one per number
    assert_linear(
        lambda text: UnitStep().find(make_document([(BlockKind.PARAGRAPH, text)], "de"), DE),
        lambda n: "1 O 1/12 " * n,
        9000,
    )


# ---- properties ------------------------------------------------------------------------------


@given(german_notation_documents())
def test_both_steps_keep_the_contract_on_any_german_document(document: Document) -> None:
    check_text_step(NUMBERS, [document], allow_ask=False)
    check_text_step(STATISTICS, [document], allow_ask=False)


@given(german_notation_documents())
def test_a_german_job_reads_the_same_on_a_second_run(document: Document) -> None:
    context = StepContext(document.language)
    first = run_steps(document, context, strict=True)
    assert not first.problems
    rebuilt = rebuilt_from_script(document, first.script())
    second = run_steps(rebuilt, context, strict=True)
    assert spoken_text(second.script()) == spoken_text(first.script())


@pytest.mark.parametrize(
    ("printed", "said"),
    [
        ("Urteil vom 13.1.2015 – VI ZR 8/14.", "Urteil vom dreizehnten Januar 2015 – VI ZR 8/14."),
        ("OLG Köln, 6 U 12/10 und 1 BvR 209/83", "OLG Köln, 6 U 12/10 und 1 BvR 209/83"),
        ("Az. 3-10 O 86/12 und 3/4 davon", "Az. 3-10 O 86/12 und 3 Viertel davon"),
        ("Az.: 12/2019 und 1/2 davon", "Az.: 12/2019 und ein halb davon"),
        (
            "Das Aktenzeichen lautet 2 O 8/15, am 3.5.2019 entschieden.",
            "Das Aktenzeichen lautet 2 O 8/15, am dritten Mai 2019 entschieden.",
        ),
        (
            "Das Aktenzeichen lautet 2 O 8/15 und das Urteil fiel am 3.5.2019.",
            "Das Aktenzeichen lautet 2 O 8/15 und das Urteil fiel am dritten Mai 2019.",
        ),
    ],
)
def test_a_court_file_number_is_kept_but_nothing_after_it(printed: str, said: str) -> None:
    """Review of PR #242, items 1 and 2: the number in its usual shape, with or without
    "Az.", stays as printed; a dash before it is no range; what follows it is read."""
    assert read_all(printed) == said


@pytest.mark.parametrize(
    ("printed", "said"),
    [
        ("von 1.500 auf 2.000 Euro", "von 15 hundert auf 2000 Euro"),
        ("um 1.200 erhöht", "um 12 hundert erhöht"),
        ("im Jahr 1.998 kam es", "im Jahr 19 hundert 98 kam es"),
        ("um 1.200 Teilnehmer", "um 1200 Teilnehmer"),
        ("zwischen 1234 und 1567 Probanden", "zwischen 1234 und 1567 Probanden"),
        ("zwischen 1990 und 1995 gab es", "zwischen 19 hundert 90 und 19 hundert 95 gab es"),
        ("von 1990–1995 Probanden", "von 1990 bis 1995 Probanden"),
    ],
)
def test_thousands_and_joined_numbers_after_a_year_word(printed: str, said: str) -> None:
    """Review of PR #242, items 3 and 7."""
    assert read_all(printed) == said
    assert read_all(said) == said
