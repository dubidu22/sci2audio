"""The readings module: what the built-in text steps read for a block's printed text (#1107,
#1110). Readings are checked here through the readings interface; the second-run tests check
the listening script through the runner."""
# ruff: noqa: RUF001 (the rows hold the signs the units step reads)

from collections.abc import Callable, Iterator

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from sci2audio.core import BlockKind
from sci2audio.testing import make_document
from sci2audio.textprep import StepContext, UnitStep, readings
from sci2audio.textprep.footnotes import unread_marks
from sci2audio.textprep.placeholders import read_as_prose
from sci2audio.textprep.readings import Reading, ReadingsError, ReadingsLoopError, readings_of
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
