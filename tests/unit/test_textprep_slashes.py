"""The slash between words read as "and" (#653, D-816)."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from sci2audio.core import BlockKind, Edit, EditKind, Span
from sci2audio.testing import check_text_step, make_document
from sci2audio.testing.regression import render
from sci2audio.textprep import run_steps
from sci2audio.textprep.slashes import SlashStep
from sci2audio.textprep.steps import StepContext

STEP = SlashStep()


def read(text: str, language: str = "en", kind: BlockKind = BlockKind.PARAGRAPH) -> str:
    """The whole chain of built-in steps, so the steps before this one claim their slashes."""
    document = make_document([(kind, text)], language)
    (line,) = render(run_steps(document, StepContext(language), strict=True))
    return line


def edits(text: str, language: str = "en") -> list[Edit]:
    return STEP.find(make_document([(BlockKind.PARAGRAPH, text)], language), StepContext(language))


@pytest.mark.parametrize(
    ("language", "printed", "said"),
    [
        ("de", "den Menschen/Gruppen, die", "den Menschen und Gruppen, die"),
        ("en", "the people/groups here", "the people and groups here"),
        ("de", "Theorie/Praxis", "Theorie und Praxis"),
        ("de", "Theorie / Praxis", "Theorie und Praxis"),
        ("en", "people /groups", "people and groups"),
        ("de", "Schulen/Vereine/Einrichtungen", "Schulen, Vereine und Einrichtungen"),
        ("en", "schools/clubs/centres", "schools, clubs and centres"),
        ("en", "schools / clubs / centres", "schools, clubs and centres"),
        # opposites read "or" (ruled by Colin at triage on 26 Nov 2026), in either order
        ("de", "ja/nein", "ja oder nein"),
        ("de", "nein/ja", "nein oder ja"),
        ("de", "richtig/falsch und wahr/falsch", "richtig oder falsch und wahr oder falsch"),
        ("en", "a Yes/No question", "a Yes or No question"),
        ("en", "true/false", "true or false"),
        # a hyphen fragment keeps its hyphen
        ("de", "Sozial-/Kulturpädagogik", "Sozial- und Kulturpädagogik"),
        ("de", "der Ein-/Ausgang", "der Ein- und Ausgang"),
        # an abbreviation counts by its reading, as a second run reads it
        ("de", "z. B./u. a. hier", "zum Beispiel und unter anderem hier"),
        ("en", "e.g./i.e. here", "for example and that is here"),
        # names no year follows are words like any other: a second run sees no citation
        ("de", "Heydorn/Koneffke zeigen das.", "Heydorn und Koneffke zeigen das."),
        # spaced, the name before a year is a name alone: the year goes and the slash is read,
        # as a second run reads "Smith and Jones" (#1236)
        ("en", "As Smith / Jones (2019) show it.", "As Smith and Jones show it."),
        ("en", "As Smith / Jones (in press) show it.", "As Smith and Jones show it."),
    ],
)
def test_a_slash_between_words_is_read(language: str, printed: str, said: str) -> None:
    assert read(printed, language) == said


@pytest.mark.parametrize(
    ("language", "printed", "said"),
    [
        # each as on main: number pairs, fractions and dates
        ("de", "auf S. (151/148)", "auf S. (151/148)"),
        ("de", "die Ausgabe 1998/2019", "die Ausgabe 1998/2019"),
        ("de", "1/2 und 3/4 der Befragten", "ein halb und 3 Viertel der Befragten"),
        ("de", "am 19/11/2026 und 11/19", "am 19/11/2026 und 11 von 19"),
        # units and rates
        ("de", "mit 5 km/h", "mit 5 Kilometer pro Stunde"),
        ("en", "3 mg/kg", "3 milligrams per kilogram"),
        ("de", "5 €/Monat", "5 Euro/Monat"),
        ("de", "5 Euro/Monat", "5 Euro/Monat"),
        ("de", "3 pro Kopf/Jahr", "3 pro Kopf/Jahr"),
        ("en", "5 dollars/month", "5 dollars/month"),
        # a rate's abbreviated time word, and a quantity after a number per anything (#1237)
        ("en", "120 words/min and 50 requests/sec", "120 words/min and 50 requests/sec"),
        ("en", "the rate in words/min", "the rate in words/min"),
        ("en", "It costs 3 dollars/user.", "It costs 3 dollars/user."),
        ("de", "120 Wörter/min", "120 Wörter/min"),
        ("de", "Es kostet 5 Euro/Nutzer.", "Es kostet 5 Euro/Nutzer."),
        ("de", "Er läuft 3 Meter/Sek.", "Er läuft 3 Meter/Sek."),
        # links, addresses and paths
        ("en", "It is at https://a.org/b/c for all.", "It is for all."),
        ("en", "the files in docs/kb and /usr/bin", "the files in docs/kb and /usr/bin"),
        ("de", "unter C:\\Daten/x", "unter C:\\Daten/x"),
        ("en", "the site example.org/about/team", "the site"),
        # German gender forms (D-816: out of scope, as printed)
        ("de", "die Lehrer/innen", "die Lehrer/innen"),
        ("de", "die Lehrer/-innen", "die Lehrer/-innen"),
        ("de", "ein/e und jede/r", "ein/e und jede/r"),
        ("de", "die Studierende/r", "die Studierende/r"),
        # ... with a capital or a double suffix too (#1250)
        ("de", "Die Lehrer/Innen.", "Die Lehrer/Innen."),
        ("de", "Die Mitarbeiter/In.", "Die Mitarbeiter/In."),
        ("de", "Die Kolleg/inn/en.", "Die Kolleg/inn/en."),
        # acronyms and abbreviations
        ("en", "TCP/IP and I/O", "TCP/IP and I/O"),
        ("en", "an A/B-test", "an A/B-test"),
        ("de", "bzw./oder", "beziehungsweise/oder"),
        # fixed slash words and join words
        ("en", "and/or", "and/or"),
        ("en", "w/o, c/o, n/a and s/he", "w/o, c/o, n/a and s/he"),
        ("de", "und/oder", "und/oder"),
        # a sign's name: "±", which the numbers step reads
        ("en", "It was plus/minus 3 here.", "It was plus/minus 3 here."),
        # maths: a part with no vowel is no word
        ("en", "it equals jzy/Ex and qy/qx", "it equals jzy/Ex and qy/qx"),
        # author names in a citation stay the citations step's (#455)
        ("de", "Wie Heydorn/Koneffke (1964) zeigen.", "Wie Heydorn/Koneffke (1964) zeigen."),
        # ... before an undated bracket or a possessive too, as a second run reads them (#1236)
        ("en", "As Smith/Jones (in press) show.", "As Smith/Jones (in press) show."),
        ("en", "As Smith/Jones (n.d.) show.", "As Smith/Jones (n.d.) show."),
        ("en", "As Smith/Jones (forthcoming) show.", "As Smith/Jones (forthcoming) show."),
        ("en", "As Smith/Jones's (2019) work shows.", "As Smith/Jones's (2019) work shows."),
        (
            "de",
            "Wie Heydorn/Koneffke (im Druck) zeigen.",
            "Wie Heydorn/Koneffke (im Druck) zeigen.",
        ),
        ("de", "Wie Heydorn/Koneffke (o. J.) zeigen.", "Wie Heydorn/Koneffke (o. J.) zeigen."),
        ("de", "Das zeigen auch (Heydorn/Koneffke 1964) hier.", "Das zeigen auch hier."),
    ],
)
def test_a_slash_the_rule_leaves(language: str, printed: str, said: str) -> None:
    assert read(printed, language) == said


def test_another_language_keeps_the_slash() -> None:
    assert not STEP.handles("fr")
    assert edits("les gens/groupes", "fr") == []


def test_the_edit_replaces_the_slash_and_names_what_is_said() -> None:
    text = "the people / groups and schools/clubs/centres"
    first, second, third = edits(text)
    assert (first.span, first.kind, first.replacement) == (
        Span(0, 10, 13),
        EditKind.REPLACE,
        " and ",
    )
    assert first.reason == 'slash between words "people / groups" read as "people and groups"'
    assert [text[e.span.start : e.span.end] for e in (second, third)] == ["/", "/"]
    assert [e.replacement for e in (second, third)] == [", ", " and "]
    assert second.reason == (
        'slash between words "schools/clubs/centres" read as "schools, clubs and centres"'
    )


def test_a_heading_is_read_too() -> None:
    assert read("Theorie/Praxis", "de", BlockKind.HEADING) == "Theorie und Praxis"


def test_a_code_block_is_not_read() -> None:
    document = make_document([(BlockKind.CODE, "input/output")])
    assert STEP.find(document, StepContext("en")) == []


# Property tests: words, signs and numbers around slashes, so most examples reach the rule
WORDS = ["people", "groups", "Ab", "x", "TCP", "and", "or", "yes", "no", "km", "Sozial-",
         "1998", "e.g.", "plus", "minus", "https://a.org", "€", "month", "docs", "kb"]  # fmt: skip
GAPS = ["/", "/", " / ", "/ ", " ", ", ", "-", "\n", "//"]
texts = st.lists(st.tuples(st.sampled_from(WORDS), st.sampled_from(GAPS)), max_size=8).map(
    lambda pairs: "".join(word + gap for word, gap in pairs)
)


@given(st.lists(texts, min_size=1, max_size=3))
def test_the_step_keeps_the_contract_on_any_text(blocks: list[str]) -> None:
    document = make_document([(BlockKind.PARAGRAPH, text) for text in blocks])
    check_text_step(STEP, [document], allow_ask=False)


GERMAN_WORDS = ["Menschen", "Gruppen", "ja", "nein", "Lehrer", "innen", "-innen", "und",
                "oder", "bzw.", "z. B.", "u. a.", "Euro", "Monat", "Ein-", "Ausgang", "e",
                "Über", "Straße", "3"]  # fmt: skip
german_texts = st.lists(
    st.tuples(st.sampled_from(GERMAN_WORDS), st.sampled_from(GAPS)), max_size=8
).map(lambda pairs: "".join(word + gap for word, gap in pairs))


@given(st.lists(german_texts, min_size=1, max_size=3))
def test_the_step_keeps_the_contract_on_any_german_text(blocks: list[str]) -> None:
    document = make_document([(BlockKind.PARAGRAPH, text) for text in blocks], "de")
    check_text_step(STEP, [document], allow_ask=False)
