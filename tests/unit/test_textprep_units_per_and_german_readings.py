"""Units after "per" with no number, German readings and the "2x" variable after a said
comparison: the second textprep batch of v1.2, PR 2 (#230, #231, #233, #250, #265, #358;
D-646; the legal forms of #264 are pinned with the other German abbreviations). Every row
is read by the whole chain, and a second run reads it the same."""

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st
from linear_time import assert_linear

from sci2audio.core import BlockKind
from sci2audio.testing import check_text_step, make_document, rebuilt_from_script
from sci2audio.textprep import (
    AbbreviationStep,
    NumbersStep,
    StepContext,
    UnitStep,
    readings,
    run_steps,
    spoken_text,
)
from sci2audio.textprep.readings import Reading, readings_of
from sci2audio.textprep.steps import Category
from sci2audio.textprep.units import _compiled
from sci2audio.textprep.wordlists import abbreviations, parse_abbreviations, units


@pytest.fixture(autouse=True)
def _read_afresh() -> None:
    """Each test reads with the code it tests: the compiled lists and the units readings are
    kept for the process, and a mutation run forks its workers from a process whose test run
    filled them, so a mutant would otherwise meet only the answers of the unmutated code."""
    _compiled.cache_clear()
    readings._read.cache_clear()


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
    units = Category.NUMBERS_AND_UNITS
    assert readings_of("units", "per m³", "en") == (Reading(4, 6, "cubic metre", units),)
    assert readings_of("units", "pro m³", "de") == (Reading(4, 6, "Kubikmeter", units),)
    assert readings_of("units", "per A", "en") == ()
    assert readings_of("units", "super m³", "en") == ()
    assert readings_of("units", "x m³", "en") == ()


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
        # a printed "pro" or "je" before the squared second, with no number
        ("Die Kraft pro s² steigt.", "Die Kraft pro Quadratsekunde steigt."),
        ("Die Kraft je s² s⁻¹ steigt.", "Die Kraft je Quadratsekunde pro Sekunde steigt."),
        ("Die Kraft pro s³ steigt.", "Die Kraft pro Sekunde hoch 3 steigt."),
        # only the first unit after "pro" is read as one after it (mutation run of PR 3)
        ("Das sind pro m s² mehr.", "Das sind pro Meter Sekunde hoch 2 mehr."),
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
    english = units("en")
    assert english is not None
    assert not any(u.square_after_per for u in english.units)


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
        ("Die 1\u00a0%-Hürde ist hoch.", "Die Ein-Prozent-Hürde ist hoch."),
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


# ---- #264 legal forms ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("printed", "said"),
    [
        # B1: the word before an ordinal is what the abbreviation reads, on both runs
        ("Das gilt i. S. d. 3. Abschnitts.", "Das gilt i. S. d. 3. Abschnitts."),
        ("Das gilt i.S.d. 3. Abschnitts.", "Das gilt i.S.d. 3. Abschnitts."),
        (
            "Das gilt i. S. d. 2019. Kapitel 3 beginnt.",
            "Das gilt i. S. d. 2019. Kapitel 3 beginnt.",
        ),
        ("Das gilt i. S. v. 3. Abschnitt.", "Das gilt im Sinne von 3. Abschnitt."),
        ("Das gilt i. V. m. 2. Alternative.", "Das gilt in Verbindung mit 2. Alternative."),
        ("Das gilt i.V.m. 2. Alternative.", "Das gilt in Verbindung mit 2. Alternative."),
        ("Urteil v. 3. Mai 2019 hier.", "Urteil vom dritten Mai 2019 hier."),
        ("Das gilt gem. 3. Abschnitt.", "Das gilt gemäß 3. Abschnitt."),  # as "gemäß 3."
        # S1: "i. S. d." only before a law's paragraph, article or subsection
        ("Daten i. S. d. § 3 BDSG.", "Daten im Sinne des § 3 BDSG."),
        ("Daten i.S.d. § 3 BDSG.", "Daten im Sinne des § 3 BDSG."),
        ("Daten i. S. d. §§ 3 und 4.", "Daten im Sinne des §§ 3 und 4."),
        ("Daten i. S. d. Art. 4 DSGVO.", "Daten im Sinne des Artikel 4 DSGVO."),
        ("Daten i. S. d. Abs. 2 hier.", "Daten im Sinne des Absatz 2 hier."),
        ("Daten i. S. d. DSGVO.", "Daten i. S. d. DSGVO."),
        ("Daten i.S.d. DSGVO.", "Daten i.S.d. DSGVO."),
        ("Daten i. S. d. Richtlinie.", "Daten i. S. d. Richtlinie."),
        # S2: "a. F." and "n. F." inside a law citation end no sentence
        ("Nach § 28 a. F. BDSG gilt das.", "Nach § 28 alte Fassung BDSG gilt das."),
        ("Nach Art. 7 a. F. EGBGB gilt das.", "Nach Artikel 7 alte Fassung EGBGB gilt das."),
        ("Nach § 28 BDSG a. F. Abs. 2 gilt das.", "Nach § 28 BDSG alte Fassung Absatz 2 gilt das."),
        ("Nach Art. 7 n. F. Satz 2 gilt das.", "Nach Artikel 7 neue Fassung Satz 2 gilt das."),
        ("Nach Art. 7 n.F. § 3 gilt das.", "Nach Artikel 7 neue Fassung § 3 gilt das."),
        ("Nach § 28 a. F. Nr. 2 gilt das.", "Nach § 28 alte Fassung Nummer 2 gilt das."),
        (
            "Nach § 28 BDSG a. F. Die Norm ist alt.",
            "Nach § 28 BDSG alte Fassung. Die Norm ist alt.",
        ),
        ("Nach § 28 BDSG a. F. Satz und Absatz.", "Nach § 28 BDSG alte Fassung. Satz und Absatz."),
        (
            "Nach § 28 BDSG a. F. Dr. Müller sagt das.",
            "Nach § 28 BDSG alte Fassung. Doktor Müller sagt das.",
        ),
        ("Er erhält 10 % p. a. BDSG.", "Er erhält 10 Prozent pro Jahr. BDSG."),  # "p. a." keeps it
        # N1: "Hs." only after a sentence's number; "S." before one is "Satz"
        ("Nach § 3 S. 1 Hs. 2 gilt das.", "Nach § 3 Satz 1 Halbsatz 2 gilt das."),
        ("Nach § 3 Satz 1 Hs. 2 gilt das.", "Nach § 3 Satz 1 Halbsatz 2 gilt das."),
        ("Die Hs. B und Hs. 12 sind alt.", "Die Hs. B und Hs. 12 sind alt."),
        ("Siehe S. 12 und Hs. 2 hier.", "Siehe Seite 12 und Hs. 2 hier."),
    ],
)
def test_legal_forms_read_the_same_on_both_runs(printed: str, said: str) -> None:
    assert read_all(printed, "de") == said


def test_the_new_list_fields_are_read() -> None:
    listed = abbreviations("de")
    assert listed is not None
    assert [e.printed for e in listed if e.after_sentence] == [("Hs.",)]
    assert [e.printed for e in listed if e.inside_citation] == [
        ("ff.",),  # "§§ 185 ff. StGB" (D-719)
        ("a. F.", "a.F."),
        ("n. F.", "n.F."),
    ]
    assert [e.printed for e in listed if e.before == "law"] == [("i. S. d.", "i.S.d.")]
    text = '[[abbreviation]]\nprinted = ["x."]\nreads = "x"\nbefore = "law"\n'
    (entry,) = parse_abbreviations(
        "test.toml", text + "after_sentence = true\ninside_citation = true\n"
    )
    assert (entry.before, entry.after_sentence, entry.inside_citation) == ("law", True, True)


# ---- #265 a year that ends a German sentence -----------------------------------------------


@pytest.mark.parametrize(
    ("printed", "said"),
    [
        ("Das war 2019. Kapitel 3 zeigt mehr.", "Das war 2019. Kapitel 3 zeigt mehr."),
        ("Das war 1100. Auflage 3 folgte.", "Das war 1100. Auflage 3 folgte."),
        ("Das war 2099. Teil 3 folgte.", "Das war 2099. Teil 3 folgte."),
        # not a year: 1099, 2100, three digits, two digits; an article sets the ending
        ("Es war die 1099. Auflage.", "Es war die tausendneunundneunzigste Auflage."),
        ("Das war 2100. Auflage 3 folgte.", "Das war zweitausendhundertste Auflage 3 folgte."),
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
        (
            "It costs 2 kg per s less than 2x more.",
            "It costs 2 kilograms per second less than 2 times more.",
        ),
        ("Values less than 2x the mean.", "Values less than 2 times the mean."),
        ("See e.g. less than 2x here.", "See for example less than 2 times here."),
        # a letter at the end of a word is no variable (mutation run of PR 3)
        ("Then xy less than 2x slower.", "Then xy less than 2 times slower."),
    ],
)
def test_x_after_a_said_comparison_of_a_variable(printed: str, said: str) -> None:
    assert read_all(printed) == said


# ---- properties ------------------------------------------------------------------------------

_BEFORE = st.sampled_from(
    ["Es sind 2 kg", "It is 1.5 kg", "Die Kosten", "The cost", "2 m²", "Siehe S. 12",
     "Das war 2019.", "y < 2x und", "y < 2x and", "Die 1 %-Hürde", "Er erhält 10 % p. a.", ""]
)  # fmt: skip
# a per word only in its own language: "per" in German (and "pro" in English) is no per word,
# and their letter powers read differently on a second run today (as on main)
_PER = {
    "en": st.sampled_from(["per", "", "less than 2x", "f.", "p. a."]),
    "de": st.sampled_from(
        [
            "pro",
            "je",
            "",
            "less than 2x",
            "f.",
            "p. a.",
            "i. S. d.",
            "i. S. v.",
            "i.V.m.",
            "a. F.",
            "n.F.",
            "gem.",
            "S. 1",
            "Hs.",
        ]
    ),
}
_UNIT = st.sampled_from(
    ["m²", "m³", "s", "kg", "A", "A-Gruppe", "km/h", "m s⁻¹", "s²", "Std.", "Kopf", "kg-Packung",
     "2x", "Kapitel 3", "1 %-Hürde", "3. Abschnitt", "2019. Kapitel", "§ 3", "BDSG", "Art. 4",
     "Abs. 2", "Satz 2", "Hs. 2", "Die Norm", "12.03.2015"]
)  # fmt: skip
_POWERS = frozenset(("m²", "m³", "m s⁻¹", "s²"))
_AFTER = st.sampled_from(["", " Fläche", " of area", " und mehr", " Dann mehr", " here", "."])


@st.composite
def _shapes(draw: st.DrawFn) -> tuple[str, str, str, str, str]:
    language = draw(st.sampled_from(["en", "de"]))
    before, per, unit = draw(_BEFORE), draw(_PER[language]), draw(_UNIT)
    # left out, as they read differently on a second run on main too: a glued "2x" before a
    # unit power (#379), and a German unit power after an English decimal point ("1.5 kg m²")
    assume(not (per.endswith("2x") and unit in _POWERS))
    assume(not (language == "de" and before == "It is 1.5 kg" and not per and unit in _POWERS))
    return before, per, unit, draw(_AFTER), language


@given(_shapes())
def test_the_new_shapes_read_the_same_on_a_second_run(
    shape: tuple[str, str, str, str, str],
) -> None:
    before, per, unit, after, language = shape
    read_all(" ".join(part for part in (before, per, unit) if part) + after + ".", language)


@given(_shapes())
def test_the_steps_keep_the_contract_on_the_new_shapes(
    shape: tuple[str, str, str, str, str],
) -> None:
    before, per, unit, after, language = shape
    text = " ".join(part for part in (before, per, unit) if part) + after
    document = make_document([(BlockKind.PARAGRAPH, text)], language)
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


# ---- the readings the 1.5.0 mutation run found unpinned (#1124) -------------------------


@pytest.mark.parametrize(
    ("language", "printed", "said"),
    [
        # a symbol after a line-end hyphen takes the line break, so a second run finds no
        # "11-\ntimes" to join
        ("en", "It is 11-\n\u00d7 5 here.", "It is 11- times 5 here."),
        # after an ordinal or a date, the numbers step asks which word a second run sees:
        # "ein" for a "1" read before a unit, the word for a symbol
        ("de", "am 3. 1 N", "am dritten ein Newton"),
        ("de", "am 3.4. 1 N 1/12", "am 3.4. 1 N 1/12"),  # a court's file number
        ("de", "am 3.4. 1 und 2", "am 3.4. 1 und 2"),
        ("de", "am 3.4. 1 s\u207b\u00b9", "am 3.4. 1 pro Sekunde"),
        ("de", "am 3. ~ 5", "am dritten etwa 5"),
        ("de", "am 3.\u00d75", "am dritten mal 5"),
        ("de", "am 3. \u00d7 5", "am dritten mal 5"),
        ("de", "am 3. \u2248 5", "am dritten ungefähr 5"),
        ("de", "am 3. \u00d7\u00d7 5", "am 3. \u00d7\u00d7 5"),
        ("de", "am 3. \u2248\u2248 5", "am 3. \u2248\u2248 5"),
        ("de", "1 \u20ac.452,5", "ein Euro.452 Komma 5"),
        # a number is split into words only where the units step reads its unit or its x
        ("de", "2,5\u00c5", "2 Komma 5 \u00c5ngström"),
        ("de", "Es galt 0,05%x als Wert.", "Es galt 0,05%x als Wert."),
        ("de", "1:1x", "1 zu 1 mal"),
        ("de", "10^2x1", "10 hoch 2 mal 1"),
        ("de", "10\u2076 x1", "10 hoch 6 mal 1"),
        ("de", "am 12.03.2019 x .45", "am zwölften März 2019 mal 0 Komma 4 5"),
        ("de", "Es ist 3x so schnell, y = 2,5x.", "Es ist 3 mal so schnell, y gleich 2,5x."),
        ("de", "y gleich 2,5x", "y gleich 2,5x"),
        ("en", "It is minus 1234x here.", "It is minus 1234x here."),
        ("en", "y less than 1234x", "y less than 1234x"),
    ],
)
def test_the_numbers_step_reads_as_the_units_step_reads_beside_it(
    language: str, printed: str, said: str
) -> None:
    assert read_all(printed, language) == said


@pytest.mark.parametrize(
    ("language", "printed", "said"),
    [
        ("en", "It is 5 mL\u22121 here.", "It is 5 per millilitre here."),
        ("de", "Es sind 5 mL\u22121 hier.", "Es sind 5 pro Milliliter hier."),
    ],
)
def test_a_raised_exponent_the_units_step_reads_is_not_written_as_printed(
    language: str, printed: str, said: str
) -> None:
    """The minus one is raised only by its run: the units step reads it as "per", so the
    numbers step does not write it in superscripts (#589); a second run reads the same."""
    raised = printed.index("\u2212")
    document = make_document(
        [(BlockKind.PARAGRAPH, printed)], language, tags={0: [(raised, raised + 2, "sup")]}
    )
    context = StepContext(language)
    script = run_steps(document, context, strict=True).script()
    again = rebuilt_from_script(document, script)
    second = spoken_text(run_steps(again, context, strict=True).script())
    assert (spoken_text(script), second) == (said, said)


def test_ordinals_after_abbreviations_take_linear_time() -> None:
    # the word before each ordinal is looked up in the text around it only (#264)
    unit = "Das gilt i. V. m. 2. Alternative, i. S. d. 3. Abschnitts und gem. 4. Absatz. "
    step = NumbersStep()

    def edits(text: str) -> object:
        return step.find(make_document([(BlockKind.PARAGRAPH, text)], "de"), StepContext("de"))

    assert_linear(edits, lambda n: unit * n, 2000)
