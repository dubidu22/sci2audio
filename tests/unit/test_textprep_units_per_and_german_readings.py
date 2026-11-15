# ruff: noqa: RUF001  (units and dashes are meant as papers print them)
"""Units after "per" with no number, German readings and the "2x" variable after a said
comparison: the second textprep batch of v1.2, PR 2 (#230, #231, #233, #250, #265, #358;
D-646). Every row is read by the whole chain, and a second run reads it the same."""

import pytest
from hypothesis import given
from hypothesis import strategies as st
from linear_time import assert_linear

from sci2audio.core import BlockKind
from sci2audio.testing import check_text_step, make_document, rebuilt_from_script
from sci2audio.textprep import AbbreviationStep, StepContext, UnitStep, run_steps, spoken_text
from sci2audio.textprep.units import reads_unit_after_per
from sci2audio.textprep.wordlists import abbreviations, parse_abbreviations, parse_units, units


def read_all(text: str, language: str = "en") -> str:
    document = make_document([(BlockKind.PARAGRAPH, text)], language)
    script = run_steps(document, StepContext(language), strict=True).script()
    again = rebuilt_from_script(document, script)
    second = spoken_text(run_steps(again, StepContext(language), strict=True).script())
    first = spoken_text(script)
    assert second == first, (text, first, second)
    return first


# ---- #230 a unit after "per" / "pro" / "je" with no number --------------------------------


@pytest.mark.parametrize(
    ("language", "printed", "said"),
    [
        ("en", "It is 2 litres per m³.", "It is 2 litres per cubic metre."),
        ("en", "It is 2 L per m^2 here.", "It is 2 litres per square metre here."),
        ("en", "The dose per kg/day is low.", "The dose per kilogram per day is low."),
        ("de", "Es sind 2 Liter pro m^2 hier.", "Es sind 2 Liter pro Quadratmeter hier."),
        (
            "de",
            "Es kostet 3 Euro pro Std. Danach mehr.",
            "Es kostet 3 Euro pro Stunde. Danach mehr.",
        ),
        ("de", "Wir zahlen je km.", "Wir zahlen je Kilometer."),
        # stays: a single capital, a unit that starts a hyphenated word, a word, glued
        ("de", "Die Kosten pro A steigen.", "Die Kosten pro A steigen."),
        ("de", "Die Kosten pro kg-Packung steigen.", "Die Kosten pro kg-Packung steigen."),
        ("de", "Die Kosten pro Kopf steigen.", "Die Kosten pro Kopf steigen."),
        ("en", "The score per A group rose.", "The score per A group rose."),
        ("en", "It is 3 kgper m here.", "It is 3 kgper m here."),
        ("en", "The superm² rose.", "The superm² rose."),
    ],
)
def test_a_unit_after_per_reads_in_the_singular(language: str, printed: str, said: str) -> None:
    assert read_all(printed, language) == said


def test_the_numbers_step_leaves_the_power_of_a_unit_after_per() -> None:
    assert reads_unit_after_per("per m³", 4, "en")
    assert reads_unit_after_per("pro m³", 4, "de")
    assert not reads_unit_after_per("per A", 4, "en")
    assert not reads_unit_after_per("super m³", 6, "en")
    assert not reads_unit_after_per("x m³", 2, "en")


# ---- #250 "pro Quadratsekunde" -------------------------------------------------------------


@pytest.mark.parametrize(
    ("printed", "said"),
    [
        ("Es beschleunigt mit 2 m s⁻².", "Es beschleunigt mit 2 Meter pro Quadratsekunde."),
        ("Es beschleunigt mit 2 m/s2.", "Es beschleunigt mit 2 Meter pro Quadratsekunde."),
        # a cubed second and a squared hour keep "hoch"; a squared second before "pro" too
        ("Es ruckt mit 2 m s⁻³.", "Es ruckt mit 2 Meter pro Sekunde hoch 3."),
        ("Es sind 2 km h⁻².", "Es sind 2 Kilometer pro Stunde hoch 2."),
        ("Es sind 2 s² m⁻¹.", "Es sind 2 Sekunden hoch 2 pro Meter."),
    ],
)
def test_a_squared_second_after_pro_is_one_word(printed: str, said: str) -> None:
    assert read_all(printed, "de") == said


def test_english_keeps_second_squared() -> None:
    assert read_all("It moves at 2 m s⁻².") == "It moves at 2 metres per second squared."


def test_square_after_per_is_read_from_the_unit_list() -> None:
    listed = units("de")
    assert listed is not None
    assert [u.singular for u in listed.units if u.square_after_per] == ["Sekunde"]
    text = '[words]\nper = "per"\n[[unit]]\nprinted = ["s"]\nsingular = "s"\nplural = "s"\n'
    (unit,) = parse_units("test.toml", text + "square_after_per = true\n").units
    assert unit.square_after_per


# ---- #231 "f." after a page, #233 "p. a." and "1 %-Hürde" ----------------------------------


@pytest.mark.parametrize(
    ("printed", "said"),
    [
        ("Siehe S. 12 f.", "Siehe Seite 12 folgende."),
        ("Siehe S. 12 f. Dann mehr.", "Siehe Seite 12 folgende. Dann mehr."),
        ("Siehe Seite 3 f. dazu.", "Siehe Seite 3 folgende dazu."),
        ("Siehe S. 12-14 f. dazu.", "Siehe Seite 12 bis 14 folgende dazu."),
        ("Siehe S. 12 ff. dazu.", "Siehe Seite 12 folgende dazu."),
        # stays: no page before it, a capital, a number with no page word, "f." glued
        ("Das gilt f. d. Inhalt.", "Das gilt f. d. Inhalt."),
        (
            "Wir nehmen die Funktion f. Dann folgt mehr.",
            "Wir nehmen die Funktion f. Dann folgt mehr.",
        ),
        ("Siehe S. 12 F. dazu.", "Siehe Seite 12 F. dazu."),
        ("Es sind 12 f. dazu.", "Es sind 12 f. dazu."),
        ("Im Jahr 12 f. dazu.", "Im Jahr 12 f. dazu."),
        ("Siehe AS. 12 f. dazu.", "Siehe AS. 12 f. dazu."),
    ],
)
def test_f_reads_folgende_only_after_a_page(printed: str, said: str) -> None:
    assert read_all(printed, "de") == said


@pytest.mark.parametrize(
    ("printed", "said"),
    [
        ("Er erhält 10 % p. a. als Zins.", "Er erhält 10 Prozent pro Jahr als Zins."),
        ("Er erhält 10 % p.a. als Zins.", "Er erhält 10 Prozent pro Jahr als Zins."),
        ("Die Zinsen betragen 10 % p. a.", "Die Zinsen betragen 10 Prozent pro Jahr."),
        ("Die 1 %-Hürde ist hoch.", "Die Ein-Prozent-Hürde ist hoch."),
        ("Die 1 kg-Packung ist teuer.", "Die Ein-Kilogramm-Packung ist teuer."),
        ("Die 1-kg-Packung ist teuer.", "Die Ein-Kilogramm-Packung ist teuer."),
        # other numbers, a hyphen with no word after it, an English job
        ("Die 5 %-Hürde ist hoch.", "Die 5 Prozent-Hürde ist hoch."),
        ("Es sind 1 %- und 2 %-Werte.", "Es sind ein Prozent- und 2 Prozent-Werte."),
    ],
)
def test_per_annum_and_one_in_a_spaced_compound(printed: str, said: str) -> None:
    assert read_all(printed, "de") == said


def test_english_has_no_compound_one() -> None:
    assert read_all("The 1 %-level is high.") == "The 1 %-level is high."


def test_after_page_is_read_from_the_abbreviation_list() -> None:
    listed = abbreviations("de")
    assert listed is not None
    assert [e.printed for e in listed if e.after_page] == [("f.",)]
    text = '[[abbreviation]]\nprinted = ["f."]\nreads = "x"\nbefore = "anything"\n'
    (entry,) = parse_abbreviations("test.toml", text + "after_page = true\n")
    assert entry.after_page


# ---- #265 a year that ends a German sentence -----------------------------------------------


@pytest.mark.parametrize(
    ("printed", "said"),
    [
        ("Das war 2019. Kapitel 3 zeigt mehr.", "Das war 2019. Kapitel 3 zeigt mehr."),
        ("Das war 1100. Auflage 3 folgte.", "Das war 1100. Auflage 3 folgte."),
        ("Das war 2099. Teil 3 folgte.", "Das war 2099. Teil 3 folgte."),
        # not a year: 1099, 2100, three digits, two digits; an article sets the ending
        ("Es war die 1099. Auflage.", "Es war die tausendneunundneunzigste Auflage."),
        ("Das war 2100. Auflage 3 folgte.", "Das war zweitausendeinhundertste Auflage 3 folgte."),
        ("Das war 200. Auflage 3 folgte.", "Das war zweihundertste Auflage 3 folgte."),
        ("Die Stichprobe umfasste 12. Kapitel 3.", "Die Stichprobe umfasste zwölftes Kapitel 3."),
        ("Die 2019. Auflage folgte.", "Die zweitausendneunzehnte Auflage folgte."),
    ],
)
def test_a_four_digit_year_before_a_noun_is_no_ordinal(printed: str, said: str) -> None:
    assert read_all(printed, "de") == said


# ---- #358 "y < 2x" -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("printed", "said"),
    [
        ("We have y < 2x and y > 2x.", "We have y less than 2x and y greater than 2x."),
        ("We have (a + b) < 2x here.", "We have (a + b) less than 2x here."),
        ("We have y less than 2x here.", "We have y less than 2x here."),
        # prose keeps "times": no variable, an article, "I", a word, an abbreviation
        ("It is less than 2x slower.", "It is less than 2 times slower."),
        ("It is a less than 2x gain.", "It is a less than 2 times gain."),
        ("I less than 2x it.", "I less than 2 times it."),
        ("Values less than 2x the mean.", "Values less than 2 times the mean."),
        ("See e.g. less than 2x here.", "See for example less than 2 times here."),
    ],
)
def test_x_after_a_said_comparison_of_a_variable(printed: str, said: str) -> None:
    assert read_all(printed) == said


# ---- properties ------------------------------------------------------------------------------

_TOKENS = st.sampled_from(
    ["per", "pro", "je", "m²", "m³", "s", "kg", "A", "A-Gruppe", "2", "1", "%", "%-Hürde",
     "p. a.", "S.", "12", "f.", "2019.", "Kapitel", "y", "<", "less than", "2x", "(a)", "Dann",
     "m^2", "s⁻²", "m/s²", "-"]
)  # fmt: skip


@given(st.lists(_TOKENS, min_size=1, max_size=8), st.sampled_from(["en", "de"]))
def test_the_new_shapes_read_the_same_on_a_second_run(tokens: list[str], language: str) -> None:
    read_all(" ".join(tokens) + ".", language)


@given(st.lists(_TOKENS, min_size=1, max_size=8), st.sampled_from(["en", "de"]))
def test_the_steps_keep_the_contract_on_the_new_shapes(tokens: list[str], language: str) -> None:
    document = make_document([(BlockKind.PARAGRAPH, " ".join(tokens))], language)
    for step in (UnitStep(), AbbreviationStep()):
        check_text_step(step, [document], allow_ask=False)


@pytest.mark.parametrize("language", ["en", "de"])
def test_units_after_per_take_linear_time(language: str) -> None:
    per = "per" if language == "en" else "pro"
    unit = f"Es sind 2 kg {per} m² und y < 2x, S. 12 f. und 10 % p. a. "
    step = UnitStep()

    def edits(text: str) -> object:
        return step.find(
            make_document([(BlockKind.PARAGRAPH, text)], language), StepContext(language)
        )

    assert_linear(edits, lambda n: unit * n, 2000)
