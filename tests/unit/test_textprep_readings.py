"""The readings module: what the built-in text steps read for a block's printed text (#1107,
#1110, #1111, #1112). Readings are checked here through the readings interface; the second-run tests
check the listening script through the runner."""
# ruff: noqa: RUF001 (the rows hold the signs the units and statistics steps read)

import re
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from sci2audio import textprep
from sci2audio.core import BlockKind
from sci2audio.testing import make_document
from sci2audio.textprep import AbbreviationStep, StatisticsStep, StepContext, UnitStep, readings
from sci2audio.textprep.footnotes import unread_marks
from sci2audio.textprep.placeholders import read_as_prose
from sci2audio.textprep.readings import (
    Reading,
    ReadingsError,
    ReadingsLoopError,
    readings_of,
    words_of,
)
from sci2audio.textprep.steps import Category

UNITS = Category.NUMBERS_AND_UNITS

# ---- the units step's readings, printed text -> (span, words) ---------------------------


@pytest.mark.parametrize(
    ("printed", "said"),
    [
        ("It weighs 3.5 mg/kg here.", [(14, 19, "milligrams per kilogram")]),
        ("A 5-km race.", [(4, 6, "kilometre")]),
        ("It is 1 kg.", [(8, 10, "kilogram")]),
        ("It took 9kg.", [(9, 11, " kilograms")]),
        ("It is 2 m s⁻¹.", [(8, 13, "metres per second")]),
        ("There were 441K apps.", [(14, 15, " thousand")]),
        ("It is 10⁶M now.", [(9, 10, " M")]),
        ("It is 2 litres per m³.", [(19, 21, "cubic metre")]),
        ("It is 3 × 4 and 5 ≈ 6.", [(8, 9, "times"), (18, 19, "approximately")]),
        ("It took ~5 days.", [(8, 9, "about ")]),
        ("A 10x speedup.", [(4, 5, " times")]),
        ("The µ sign.", [(4, 5, "μ")]),
        # nothing read: a label before the number, a variable, no number or "per" before it
        ("See Figure 2 A.", []),
        ("y = 2x + 1", []),
        ("The superm² rose.", []),
    ],
)
def test_english_units_readings(printed: str, said: list[tuple[int, int, str]]) -> None:
    assert readings_of("units", printed, "en") == tuple(
        Reading(start, end, words, UNITS) for start, end, words in said
    )


@pytest.mark.parametrize(
    ("printed", "said"),
    [
        ("Es sind 2,5 km.", [(12, 14, "Kilometer")]),
        ("Es ist 1 kg schwer.", [(7, 8, "ein"), (9, 11, "Kilogramm")]),
        ("Die 1 %-Hürde.", [(4, 5, "Ein"), (5, 7, "-Prozent")]),
        ("Es sind 2 m s⁻².", [(10, 15, "Meter pro Quadratsekunde")]),
        ("Es kostet 3 Euro pro Std. Danach mehr.", [(21, 24, "Stunde")]),
        ("Wir zahlen je km.", [(14, 16, "Kilometer")]),
        ("Es ist 2,5x so groß.", [(10, 11, " mal")]),
        ("Es ist 3 × 4.", [(9, 10, "mal")]),
        # nothing read: a court's file number, a label before the number, no unit after "1"
        ("Az. 13 W 17/12", []),
        ("Kapitel 2,55 m", []),
        ("Nach 1 Stunde.", []),
    ],
)
def test_german_units_readings(printed: str, said: list[tuple[int, int, str]]) -> None:
    assert readings_of("units", printed, "de") == tuple(
        Reading(start, end, words, UNITS) for start, end, words in said
    )


# ---- the units step's edits are its readings --------------------------------------------

_TOKENS = st.sampled_from(
    ["1", "2", "3.5", "2,5", "10", "441", "1.234", "1/2", "10⁶", "0", "17/12", "m", "kg",
     "mg/kg", "m²", "m^2", "s⁻¹", "s2", "%", "°C", "°", "K", "M", "B", "x", "X", "×", "≈", "~",
     "∼", "µ", "µm", "Å", "per", "pro", "je", "a", "ein", "Figure", "Fig.", "Kapitel", "Az.",
     "W", "Std.", "Danach", "=", "+", "−", "-", "(", ")", ".", ",", "y", "the", "equals",
     "less than", "minus", "to the power of", "hoch", "out of", "gleich", "kleiner als"]
)  # fmt: skip
_GAPS = st.sampled_from(["", " ", " ", "  ", "-", "\n", "\u00a0", "\u202f"])


@st.composite
def _blocks(draw: st.DrawFn) -> tuple[str, str]:
    """A block's text in English or German, of the pieces the units rules look at."""
    pieces = draw(st.lists(st.tuples(_TOKENS | st.text("abAB1. ", max_size=3), _GAPS), max_size=12))
    return "".join(token + gap for token, gap in pieces), draw(st.sampled_from(["en", "de"]))


@given(_blocks())
def test_the_units_step_edits_are_its_readings(block: tuple[str, str]) -> None:
    text, language = block
    document = make_document([(BlockKind.PARAGRAPH, text)], language)
    context = StepContext(language)
    # the step reads the block as a second run does, without what the steps before it
    # remove; the readings answer for the printed text alone
    assume(read_as_prose(document.blocks[0], context) and not unread_marks(document, context))
    edits = UnitStep().find(document, context)
    assert [(e.span.start, e.span.end, e.replacement) for e in edits] == [
        (r.start, r.end, r.words) for r in readings_of("units", text, language)
    ]
    assert {r.category for r in readings_of("units", text, language)} <= {UnitStep.category}


# ---- the statistics step's readings, printed text -> (span, words) ----------------------

STATISTICS = StatisticsStep.category


@pytest.mark.parametrize(
    ("printed", "said"),
    [
        # comparisons read on their own, with the white space around them
        ("p < .05 here.", [(1, 4, " less than ")]),
        ("3x > 2", [(2, 5, " greater than ")]),
        (
            "x ≤ 3 and y ≥ 4",
            [(1, 4, " less than or equal to "), (11, 14, " greater than or equal to ")],
        ),
        ("μ ± 2", [(1, 4, " plus or minus ")]),
        ("e.g.=1", [(4, 5, " equals ")]),
        ("It was t(34) = 2.1.", [(8, 12, " of 34"), (12, 15, " equals ")]),
        (
            "χ²(1, N = 100) = 3.2",
            [(0, 2, "chi-square"), (2, 14, " of 1, N equals 100"), (14, 17, " equals ")],
        ),
        ("ηp² was .3", [(0, 3, "partial eta squared")]),
        ("OR = 2.1", [(0, 2, "odds ratio"), (2, 5, " equals ")]),
        # an interval's brackets left out, its comma read "to"
        (
            "95% CI [1.2, 3.4]",
            [(4, 6, "confidence interval"), (7, 8, ""), (11, 13, " to "), (16, 17, "")],
        ),
        ("A ⇒ B", [(1, 4, " implies ")]),
        ("an arrow => B", [(8, 12, " implies ")]),
        # nothing read: a sign glued between letters, an arrow named in prose, a plain "R2"
        ("a<b", []),
        ("where ⇒ marks", []),
        ("R2 rose", []),
    ],
)
def test_english_statistics_readings(printed: str, said: list[tuple[int, int, str]]) -> None:
    assert readings_of("statistics", printed, "en") == tuple(
        Reading(start, end, words, STATISTICS) for start, end, words in said
    )


@pytest.mark.parametrize(
    ("printed", "said"),
    [
        ("p < 0,05 hier.", [(2, 3, "kleiner als")]),
        ("x ≠ 3", [(2, 3, "ungleich")]),
        ("Jh.=1", [(3, 4, " gleich ")]),
        ("Kapitel IV.=1", [(11, 12, " gleich ")]),
        ("t(34) = 2,1", [(1, 5, " mit 34 Freiheitsgraden"), (6, 7, "gleich")]),
        ("χ²(1) = 3", [(0, 2, "Chi-Quadrat"), (2, 5, " mit 1 Freiheitsgrad"), (6, 7, "gleich")]),
        ("R² = 0,5", [(0, 2, "R Quadrat"), (3, 4, "gleich")]),
        ("OR = 2", [(0, 2, "Odds Ratio"), (3, 4, "gleich")]),
        # an interval read whole, with its numbers
        ("95 %-KI [1,2; 3,4]", [(4, 7, " Konfidenzintervall"), (8, 18, "1 Komma 2 bis 3 Komma 4")]),
        (
            "KI [1; 2] und [3; 4]",
            [(0, 2, "Konfidenzintervall"), (3, 9, "1 bis 2"), (14, 20, "3 bis 4")],
        ),
        ("A ⇒ B", [(2, 3, "daraus folgt")]),
        # nothing read: a sign glued between letters
        ("a<b", []),
    ],
)
def test_german_statistics_readings(printed: str, said: list[tuple[int, int, str]]) -> None:
    assert readings_of("statistics", printed, "de") == tuple(
        Reading(start, end, words, STATISTICS) for start, end, words in said
    )


@pytest.mark.parametrize(
    ("language", "sign", "said"),
    [
        ("en", "<", "less than"),
        ("en", "≤", "less than or equal to"),
        ("en", "=", "equals"),
        ("en", "\u0338=", "not equal to"),
        ("en", "±", "plus or minus"),
        ("de", ">", "größer als"),
        ("de", "≥", "größer oder gleich"),
        ("de", "=", "gleich"),
        ("de", "±", "plus minus"),
    ],
)
def test_the_statistics_step_reads_its_signs_with_its_operator_words(
    language: str, sign: str, said: str
) -> None:
    assert words_of("statistics", language).signs[sign] == said


@pytest.mark.parametrize("language", ["en", "de"])
def test_each_sign_and_arrow_reads_its_words_between_two_operands(language: str) -> None:
    said = words_of("statistics", language)
    for sign, words in {**said.signs, **said.arrows}.items():
        printed = f"A {sign} B" if sign in said.arrows else f"x {sign} 1"
        found = readings_of("statistics", printed, language)
        assert [r.words.strip() for r in found] == [words], sign


def test_the_statistics_step_names_what_it_reads_by_name() -> None:
    english, german = words_of("statistics", "en"), words_of("statistics", "de")
    assert english.arrows == {"⇒": "implies", "⇐": "is implied by", "⇔": "if and only if"}
    assert german.arrows == {"⇒": "daraus folgt", "⇐": "folgt aus", "⇔": "genau dann, wenn"}
    assert {"R squared", "partial eta squared", "chi-square"} <= english.squared
    assert {"confidence interval", "confidence intervals", "odds ratio"} <= english.names
    assert english.squared <= english.names
    assert {"R Quadrat", "partielles Eta-Quadrat", "Chi-Quadrat"} <= german.squared
    assert {"Odds Ratio", "Konfidenzintervall"} <= german.names
    assert german.squared <= german.names


_STATISTICS_TOKENS = st.sampled_from(
    ["p", "t", "F", "r", "R", "x", "y", "A", "B", "N", "OR", "CI", "CIs", "KI", "R2", "R²",
     "η²", "ηp²", "ω²", "χ²", "χ2", "(34)", "(2, 57)", "(1, N = 100)", "(1; 2)", "[1, 3]",
     "[1,2; 3,4]", "[−1, 2]", "95%", "95 %-", ".05", "0,05", "2.1", "1", "<", ">", "=", "≤",
     "≥", "≠", "\u0338=", "±", "∓", "≪", "⇒", "⇐", "⇔", "=>", "<=>", "=⇒", "⇐=", "==>", "¬",
     "−", "-", "and", "und", "or", "oder", "where", "The", "e.g.", "Jh.", "z. B.", "Uhr",
     "13:30", "https://x.org", "<i>", "×", "~", "3x"]
)  # fmt: skip


@st.composite
def _statistics_blocks(draw: st.DrawFn) -> tuple[str, str]:
    """A block's text in English or German, of the pieces the statistics rules look at."""
    tokens = _STATISTICS_TOKENS | st.text("aA1.,;( )", max_size=3)
    pieces = draw(st.lists(st.tuples(tokens, _GAPS), max_size=14))
    return "".join(token + gap for token, gap in pieces), draw(st.sampled_from(["en", "de"]))


@given(_statistics_blocks())
def test_the_statistics_step_edits_are_its_readings(block: tuple[str, str]) -> None:
    text, language = block
    document = make_document([(BlockKind.PARAGRAPH, text)], language)
    context = StepContext(language)
    # as for the units step: the readings answer for the printed text alone
    assume(read_as_prose(document.blocks[0], context) and not unread_marks(document, context))
    edits = StatisticsStep().find(document, context)
    found = readings_of("statistics", text, language)
    assert [(e.span.start, e.span.end, e.replacement) for e in edits] == [
        (r.start, r.end, r.words) for r in found
    ]
    assert {r.category for r in found} <= {StatisticsStep.category}


# ---- the abbreviations step's readings, printed text -> (span, words) -------------------

ABBREVIATIONS = AbbreviationStep.category


@pytest.mark.parametrize(
    ("printed", "said"),
    [
        ("See Fig. 3 here.", [(4, 8, "Figure")]),
        ("It holds, e.g. here.", [(10, 14, "for example")]),
        ("See eq.(1) now.", [(4, 7, "equation ")]),  # glued: a space after the reading
        # the full stop is read with it, or stays where the sentence ends (D-115)
        ("It is approx. 5 m.", [(6, 13, "approximately")]),
        ("It is approx. Then more.", [(6, 12, "approximately")]),
        ("No abbreviation here.", []),
    ],
)
def test_english_abbreviation_readings(printed: str, said: list[tuple[int, int, str]]) -> None:
    assert readings_of("abbreviations", printed, "en") == tuple(
        Reading(start, end, words, ABBREVIATIONS) for start, end, words in said
    )


@pytest.mark.parametrize(
    ("printed", "said"),
    [
        ("Siehe Kap. 3 hier.", [(6, 10, "Kapitel")]),
        ("Das gilt z. B. hier.", [(9, 14, "zum Beispiel")]),
        ("i. V. m. 2. Alternative", [(0, 8, "in Verbindung mit")]),
        ("Äpfel, Birnen usw. und mehr.", [(14, 18, "und so weiter")]),
        ("Äpfel, Birnen usw. Dann mehr.", [(14, 17, "und so weiter")]),  # the stop ends it
        ("Kein Kürzel hier.", []),
    ],
)
def test_german_abbreviation_readings(printed: str, said: list[tuple[int, int, str]]) -> None:
    assert readings_of("abbreviations", printed, "de") == tuple(
        Reading(start, end, words, ABBREVIATIONS) for start, end, words in said
    )


_ABBREVIATION_TOKENS = st.sampled_from(
    ["Fig.", "Figs.", "e.g.", "i.e.", "eq.", "approx.", "resp.", "etc.", "et al.", "vs.",
     "Kap.", "z. B.", "z.B.", "usw.", "bzw.", "i. V. m.", "Abs.", "S.", "Nr.", "Dr.", "Then",
     "Dann", "and", "und", "3", "2.", "(1)", "(", ")", ".", ",", "https://x.org/a", "a"]
)  # fmt: skip


@st.composite
def _abbreviation_blocks(draw: st.DrawFn) -> tuple[str, str]:
    """A block's text in English or German, of the pieces the abbreviation rules look at."""
    pieces = draw(st.lists(st.tuples(_ABBREVIATION_TOKENS, _GAPS), max_size=12))
    return "".join(token + gap for token, gap in pieces), draw(st.sampled_from(["en", "de"]))


@given(_abbreviation_blocks())
def test_the_abbreviations_step_edits_are_its_readings(block: tuple[str, str]) -> None:
    text, language = block
    document = make_document([(BlockKind.PARAGRAPH, text)], language)
    context = StepContext(language)
    # as for the units step: the readings answer for the printed text alone
    assume(read_as_prose(document.blocks[0], context) and not unread_marks(document, context))
    edits = AbbreviationStep().find(document, context)
    found = readings_of("abbreviations", text, language)
    assert [(e.span.start, e.span.end, e.replacement) for e in edits] == [
        (r.start, r.end, r.words) for r in found
    ]
    assert {r.category for r in found} <= {AbbreviationStep.category}


def test_the_links_step_alone_asks_the_abbreviations_step_past_the_readings() -> None:
    """The one known exception (#1112): the abbreviations step's readings ask the links step
    for what it removes, and the links step asks back whether an abbreviation reads its full
    stop, so that question stays a window-based call outside the readings. Every other step
    asks the readings."""
    source = Path(textprep.__file__).parent
    callers = sorted(
        path.name
        for path in source.glob("*.py")
        if path.name != "abbreviations.py"
        and re.search(r"\breads_full_stop\(", path.read_text(encoding="utf-8"))
    )
    assert callers == ["links.py"]
    asks = readings.dependencies()
    assert asks["abbreviations"] == ()
    assert "abbreviations" in asks["statistics"]


# ---- the readings table ----------------------------------------------------------------


def test_no_step_readings_ask_in_a_loop() -> None:
    asks = readings.dependencies()
    assert all(set(needed) <= set(asks) for needed in asks.values())

    def walk(step: str, path: tuple[str, ...]) -> None:
        assert step not in path, " → ".join((*path, step))
        for needed in asks[step]:
            walk(needed, (*path, step))

    for step in asks:
        walk(step, ())


@pytest.fixture
def table(monkeypatch: pytest.MonkeyPatch) -> Iterator[Callable[..., None]]:
    """Adds fake steps to the readings table, with nothing cached before or after."""

    def add(step: str, read: Callable[[str, str], tuple[Reading, ...]], asks=()) -> None:
        monkeypatch.setitem(readings._finders(), step, readings.Finder(read, tuple(asks)))

    readings._read.cache_clear()
    yield add
    readings._read.cache_clear()


def test_a_loop_between_readings_is_refused_naming_the_steps(table) -> None:
    table("first", lambda text, language: readings_of("second", text, language), ["second"])
    table("second", lambda text, language: readings_of("first", text, language), ["first"])
    with pytest.raises(ReadingsLoopError) as refused:
        readings_of("first", "5 kg", "en")
    assert refused.value.steps == ("first", "second", "first")
    assert "first → second → first" in str(refused.value)


def test_readings_ask_only_the_steps_their_entry_names(table) -> None:
    table("asking", lambda text, language: readings_of("units", text, language))
    with pytest.raises(ReadingsError, match=r"asking.*units"):
        readings_of("asking", "5 kg", "en")


def test_a_repeated_question_is_answered_from_the_cache(table) -> None:
    asked: list[tuple[str, str]] = []

    def counted(text: str, language: str) -> tuple[Reading, ...]:
        asked.append((text, language))
        return (Reading(0, 1, "five", UNITS),)

    table("counted", counted)
    first = readings_of("counted", "5 kg", "en")
    assert readings_of("counted", "5 kg", "en") == first
    assert asked == [("5 kg", "en")]
    readings_of("counted", "5 kg", "de")
    readings_of("counted", "6 kg", "en")
    assert asked == [("5 kg", "en"), ("5 kg", "de"), ("6 kg", "en")]
