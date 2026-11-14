# ruff: noqa: RUF001  (dashes and quotes are meant as papers print them)
"""German links and citations (#101): the links and citations steps' German rows."""

import time

import pytest
from hypothesis import given
from hypothesis import strategies as st

from sci2audio.core import Block, BlockKind, Document, apply_edits
from sci2audio.testing import check_text_step, make_document, rebuilt_from_script
from sci2audio.textprep import CitationStep, LinkStep, StepContext, run_steps, spoken_text
from sci2audio.textprep.citations import WORDS as CITATION_WORDS
from sci2audio.textprep.links import WORDS as LINK_WORDS

DE = StepContext("de")
LINKS = LinkStep()
CITATIONS = CitationStep()


def read(step: LinkStep | CitationStep, text: str) -> str:
    document = make_document([(BlockKind.PARAGRAPH, text)], "de")
    return spoken_text(apply_edits(document, step.find(document, DE)))


def read_all(text: str) -> str:
    """The whole chain of built-in steps, as a German job runs it."""
    document = make_document([(BlockKind.PARAGRAPH, text)], "de")
    return spoken_text(run_steps(document, DE, strict=True).script())


def test_both_steps_have_a_german_row_and_english_stays_as_it_was() -> None:
    assert set(LINK_WORDS) == set(CITATION_WORDS) == {"en", "de"}
    assert "de" in LINKS.languages
    assert "de" in CITATIONS.languages
    english = LINK_WORDS["en"]
    assert english.access == ()  # English has no access-note words: unchanged (#101)
    assert "also" in english.fillers
    assert "for" in english.purposes
    assert CITATION_WORDS["en"].name_leads is None  # English names are not checked so


# ---- links -------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("printed", "said"),
    [
        # 4. a preposition before it goes, so the verb at the end still reads
        ("Die Daten sind unter https://x.org/d verfügbar.", "Die Daten sind verfügbar."),
        ("Ein Prototyp ist auf https://x.org abrufbar.", "Ein Prototyp ist abrufbar."),
        # 2. a label that starts the sentence takes the sentence
        ("Kontakt: a.muster@uni-beispiel.de. Danach mehr.", "Danach mehr."),
        ("Quellcode: https://github.com/a/b. Danach mehr.", "Danach mehr."),
        # a pointer sentence goes whole
        ("Siehe https://x.org für Details. Dann mehr.", "Dann mehr."),
        ("Siehe auch https://x.org/a zum Code. Dann mehr.", "Dann mehr."),
        ("Vgl. https://x.org. Dann mehr.", "Dann mehr."),
        # 1. a bracket of the link and lead words goes whole
        ("Die Daten (frei verfügbar unter https://x.org/d) sind neu.", "Die Daten sind neu."),
        ("Wir nutzen OpenWPM (https://github.com/mozilla/OpenWPM).", "Wir nutzen OpenWPM."),
        # links joined by "und", "oder", "sowie" are one run
        ("Mehr unter https://x.org/a und https://x.org/b.", "Mehr."),
        ("Die Seiten https://a.org sowie https://b.org zeigen es.", "Die Seiten zeigen es."),
        # an abbreviation's full stop before a link ends no sentence; two words before it go
        ("Die Daten liegen z. B. unter https://x.org. Dann mehr.", "Die Daten liegen. Dann mehr."),
        (
            "Daten finden sich u. a. unter https://x.org. Dann mehr.",
            "Daten finden sich unter anderem. Dann mehr.",
        ),
        ("Das gilt ggf. https://x.org. Dann mehr.", "Das gilt gegebenenfalls. Dann mehr."),
        ("Siehe z. B. https://x.org. Dann mehr.", "Dann mehr."),
        # "bzw." joins links and goes before one
        (
            "Code liegt bei GitHub bzw. https://x.org. Dann mehr.",
            "Code liegt bei GitHub. Dann mehr.",
        ),
        ("Mehr bei https://a.org bzw. https://b.org.", "Mehr."),
        ("Die Daten bzw. https://x.org sind neu.", "Die Daten sind neu."),
        # a join word left with nothing after it goes too
        (
            "Das ist Praxis (vgl. Suchmaschinen und z. B. https://archive.org/). Dennoch nicht.",
            "Das ist Praxis (vergleiche Suchmaschinen). Dennoch nicht.",
        ),
    ],
)
def test_german_link_repairs(printed: str, said: str) -> None:
    assert read_all(printed) == said


@pytest.mark.parametrize(
    ("printed", "said"),
    [
        (
            "Der Bericht https://x.org/r (abgerufen am 12.03.2020) zeigt es.",
            "Der Bericht zeigt es.",
        ),
        (
            "Der Bericht (https://x.org/r, abgerufen am 12.03.2020) zeigt es.",
            "Der Bericht zeigt es.",
        ),
        ("Die Seite https://x.org/r [letzter Zugriff: 1.2.2019] zeigt es.", "Die Seite zeigt es."),
        ("Die Seite https://x.org/r (Stand: Mai 2017) zeigt es.", "Die Seite zeigt es."),
        ("Mehr dazu unter https://x.org/r, Zugriff am 3. Mai 2017.", "Mehr dazu."),
        ("Die Seite https://x.org/r (Abruf: 3.5.2017) zeigt es.", "Die Seite zeigt es."),
        # a note set off by commas takes its closing comma too
        ("Die Seite https://x.org/r, abgerufen am 3.5.2017, zeigt es.", "Die Seite zeigt es."),
        # a bracket that is no access note stays
        ("Die Seite https://x.org/r (2017) zeigt es.", "Die Seite (2017) zeigt es."),
        (
            "Die Seite https://x.org/r (Stand der Technik) zeigt es.",
            "Die Seite (Stand der Technik) zeigt es.",
        ),
    ],
)
def test_an_access_note_after_a_link_goes_with_it(printed: str, said: str) -> None:
    assert read_all(printed) == said


def test_the_reason_names_the_link_without_its_access_note() -> None:
    text = "Der Bericht https://x.org/r (abgerufen am 12.03.2020) zeigt es."
    document = make_document([(BlockKind.PARAGRAPH, text)], "de")
    [edit] = LINKS.find(document, DE)
    assert edit.reason == (
        'URL "https://x.org/r" is not read; the access note after it goes too (TP-07)'
    )


@pytest.mark.parametrize(
    "text",
    [
        "4 https://blog.example.org/bericht/",
        "7 z.B. https://securityheaders.io/",
        "8 Siehe https://x.org und https://y.org.",
        "9 https://x.org/a, abgerufen am 3.5.2017",
    ],
)
def test_a_footnote_of_its_mark_lead_words_and_links_reads_nothing(text: str) -> None:
    document = make_document([Block(BlockKind.FOOTNOTE, text, label=text.split()[0])], "de")
    assert spoken_text(apply_edits(document, LINKS.find(document, DE))) == ""


def test_a_url_cut_at_a_line_end_leaves_a_german_sentence_word() -> None:
    assert read(LINKS, "Die Daten liegen auf https://x.org/\nund werden gepflegt.") == (
        "Die Daten liegen und werden gepflegt."
    )
    assert read(LINKS, "Die URL https://x.org/\ndaten.html ist neu.") == "Die URL ist neu."


# ---- citations ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("printed", "said"),
    [
        # an aside goes
        ("Das gilt (Müller & Schmidt, 2019).", "Das gilt."),
        ("Das gilt (Müller und Schmidt 2019, Kap. 3).", "Das gilt."),
        ("Das gilt (vgl. Müller u. a. 2019, S. 12).", "Das gilt."),
        ("Das gilt (siehe Müller, 2019, S. 8–10).", "Das gilt."),
        ("Das gilt (Müller et al., 2019; Schmidt 2020, S. 8 f.).", "Das gilt."),
        ("Das gilt (vgl. auch Müller u. a., 2019a, b; Schmidt & Weber, 2020).", "Das gilt."),
        ("Das gilt (Müller, o. J.) sicher.", "Das gilt sicher."),
        ("Das gilt (Müller im Druck) sicher.", "Das gilt sicher."),
        ("Das gilt (Müller, 2019, Rn. 12).", "Das gilt."),
        ("Das gilt [3, 5].", "Das gilt."),
        # a narrative citation keeps its names
        ("Wie Müller (2019) zeigt, gilt es.", "Wie Müller zeigt, gilt es."),
        ("Müller u. a. (2019) zeigen es.", "Müller und andere zeigen es."),
        ("Laut Anna Müller (2019) gilt es.", "Laut Anna Müller gilt es."),
        ("Die Studie von Müller (2019) zeigt es.", "Die Studie von Müller zeigt es."),
        ("Dies zeigen Müller und Schmidt (2019).", "Dies zeigen Müller und Schmidt."),
        # a numeric citation the sentence needs is read with the German words
        ("Wie in [12] gezeigt, gilt das.", "Wie in Quelle 12 gezeigt, gilt das."),
        ("Siehe auch [2–6].", "Siehe auch Quellen 2 bis 6."),
        ("Nach [3, 5] gilt das.", "Nach Quellen 3 und 5 gilt das."),
        ("[12] zeigt das.", "Quelle 12 zeigt das."),
        ("Laut Quelle [4] gilt das.", "Laut Quelle 4 gilt das."),
    ],
)
def test_german_citations(printed: str, said: str) -> None:
    assert read_all(printed) == said


@pytest.mark.parametrize(
    "text",
    [
        "Die Olympischen Spiele (2016) waren groß.",  # a capital noun after an article
        "Die neue Studie (2019) zeigt es.",  # ... or after an inflected adjective
        "Das Ergebnis des Bundes (2019) ist klar.",
        "Im Bericht (2019) steht es.",
        "Die Werte liegen in [0, 1].",  # an interval after "in" and a maths sign
        "Abb. [3] zeigt es.",  # a label's number
        "Fahl et al. haben gezeigt [Fa14].",  # alphanumeric keys are not read yet
        # a round bracket of German intervals of decimals stays, as each interval does (#266)
        "Die Werte ([1,2; 3,4]) sind klein.",
        "Die Werte ( [1,2; 3,4]) sind klein.",
        "Die Werte ([1,2; 3,4], [5,6; 7,8]) sind klein.",
    ],
)
def test_german_brackets_that_are_no_citation_stay(text: str) -> None:
    assert read(CITATIONS, text) == text


@pytest.mark.parametrize(
    ("printed", "said"),
    [
        (
            "Das KI [1; 3] und [12] zeigen es.",
            "Das Konfidenzintervall 1 bis 3 und Quelle 12 zeigen es.",
        ),
        (
            "Das 95 %-KI [1,2; 3,4] ist klein.",
            "Das 95 Prozent Konfidenzintervall 1 Komma 2 bis 3 Komma 4 ist klein.",
        ),
        (
            "Das 95 %-KI [1; 3],1 war breit.",
            "Das 95 Prozent Konfidenzintervall [1; 3],1 war breit.",
        ),
    ],
)
def test_a_german_confidence_interval_is_no_citation(printed: str, said: str) -> None:
    assert read_all(printed) == said


def test_german_abbreviations_end_no_sentence_for_the_citation_rules() -> None:
    # "vgl." does not start a sentence: the citation after it is read in lower case
    assert read(CITATIONS, "Das gilt, vgl. [3].") == "Das gilt, vgl. Quelle 3."


# ---- properties and time -----------------------------------------------------------------------

WORDS = st.sampled_from(
    ["Die", "Daten", "sind", "unter", "verfügbar", "siehe", "vgl.", "und", "oder", "z. B.",
     "Kontakt:", "Code:", "(", ")", "für", "Details", "Müller", "zeigt", "die", "Studie", "in",
     "auf", "x", "=", "KI", "95 %-KI", "Quelle", "abgerufen am"]
)  # fmt: skip
PIECES = st.sampled_from(
    [
        "https://example.org/daten",
        "https://example.org/\nweiter",
        "www.beispiel.de/a",
        "a.muster@uni-beispiel.de",
        "doi:10.1000/xyz",
        "(abgerufen am 12.03.2020)",
        ", Zugriff am 3. Mai 2017",
        "[letzter Zugriff: 1.2.2019]",
        "(Müller & Schmidt, 2019)",
        "(vgl. Müller u. a. 2019, S. 12)",
        "Müller (2019)",
        "Müller u. a. (2019)",
        "(Müller, o. J.)",
        "[12]",
        "[2–6, 16]",
        "[1,2; 3,4]",
        "[1; 3],1",
        "die neue Studie (2019)",
        "[0, 1]",
    ]
)
ENDS = st.sampled_from([".", ",", ")", "", ";", ". Dann"])
SPACE = st.sampled_from([" ", "\n"])


@st.composite
def german_documents(draw: st.DrawFn) -> Document:
    """One or two German blocks of words, links, access notes and citations."""
    blocks = []
    for _ in range(draw(st.integers(1, 2))):
        parts: list[str] = []
        for _ in range(draw(st.integers(1, 4))):
            parts += draw(st.lists(WORDS, max_size=4))
            parts.append(draw(PIECES) + draw(ENDS))
        text = ""
        for part in parts:
            text += (draw(SPACE) if text else "") + part
        kind = draw(st.sampled_from([BlockKind.PARAGRAPH] * 3 + [BlockKind.FOOTNOTE]))
        blocks.append((kind, text))
    return make_document(blocks, draw(st.sampled_from(["de", "de-AT"])))


@given(german_documents())
def test_both_steps_keep_the_contract_on_any_german_document(document: Document) -> None:
    check_text_step(LINKS, [document], allow_ask=False)
    check_text_step(CITATIONS, [document], allow_ask=False)


@given(german_documents())
def test_a_german_job_with_links_and_citations_reads_the_same_on_a_second_run(
    document: Document,
) -> None:
    context = StepContext(document.language)
    first = run_steps(document, context, strict=True)
    assert not first.problems
    rebuilt = rebuilt_from_script(document, first.script())
    second = run_steps(rebuilt, context, strict=True)
    assert spoken_text(second.script()) == spoken_text(first.script())


@pytest.mark.parametrize(
    "text",
    [
        # a citation next to a link the links step removes with its punctuation
        "https://example.org/daten, (Müller, o. J.).",
        "Siehe https://example.org/daten, (Müller, o. J.).",
        "(Müller, o. J.), https://example.org/daten.",
        "(Müller, o. J.). https://example.org/daten)",
        "https://example.org/daten. (Müller, o. J.), https://example.org/daten.",
        "https://example.org/daten (Müller, 2020). Mehr.",
        # a name that starts the sentence once the link before it goes
        "https://example.org/daten Müller (2019).",
        "Text https://example.org/daten Müller (2019) dazu.",
        # "=" next to a removed link, e-mail address or citation
        "https://example.org/daten. = https://example.org/daten Die.",
        "https://example.org/daten. Die = https://example.org/daten Die.",
        "https://example.org/daten, = (abgerufen am 12.03.2020).",
        "https://example.org/daten. = a.muster@uni-beispiel.de Die.",
        "weiter, = Die https://example.org/daten.",
        "(Müller & Schmidt, 2019). = Die https://example.org/daten.",
        "= (Müller & Schmidt, 2019) Die.",
        "Die =\nhttps://example.org/daten Die.",
        # a bracket after a sign, printed or said, is a value
        "Sei x = [12].",
        "Sei x gleich [12].",
        # two German decimals in a bracket are an interval, not sources
        "95 %-KI [1; 1] und [1,2; 3,4] N",
        # ... also in a round bracket, once a citation before it is gone (#266)
        "( (Müller & Schmidt, 2019) [1,2; 3,4])",
        "Die Werte ([1,2; 3,4]; Müller, 2019) sind klein.",
        "Das gilt ([12]; [1,2; 3,4]).",
        "Das gilt ([1,2; 3,4]; [12]).",
        "Das gilt ([1,2; 3,4], [12]).",
        # a statistic's reading is no author's name
        "χ²(1998) ± 1",
        # "KI" with a link between it and its interval
        "https://example.org/daten. KI https://example.org/daten [1,2; 3,4].",
        "KI https://example.org/\nweiter ( https://example.org/daten.",
        "https://example.org/daten. KI unter https://example.org/daten [1,2; 3,4].",
        "https://example.org/daten. KI Kontakt: https://example.org/daten [1,2; 3,4].",
        # a source number read before a full stop is no ordinal
        "unter [12]. Studie https://example.org/daten.",
        "Wie in [3, 12]. Studie zeigt.",
    ],
)
def test_a_second_run_reads_nothing_new(text: str) -> None:
    once = read_all(text)
    assert read_all(once) == once, (text, once)


@pytest.mark.parametrize(
    ("printed", "said"),
    [
        # #266 (nightly seed 31337): the first run kept the interval, a second removed it
        ("( (Müller & Schmidt, 2019) [1,2; 3,4])", "( [1,2; 3,4])"),
        ("Die Werte ([1,2; 3,4]; Müller, 2019) sind klein.", "Die Werte ([1,2; 3,4]) sind klein."),
        # a source among the brackets goes alone; the interval stays (D-534; the ";" is #272)
        ("Das gilt ([12]; [1,2; 3,4]).", "Das gilt (; [1,2; 3,4])."),
    ],
)
def test_the_citations_step_alone_decides_an_aside_the_same_on_a_second_run(
    printed: str, said: str
) -> None:
    once = read(CITATIONS, printed)
    assert once == said
    assert read(CITATIONS, once) == once


@pytest.mark.parametrize(
    ("printed", "said"),
    [
        # #271: the outer bracket is judged on what it reads once its inner citations go
        ("Lärm wirkt ((Müller, 2019) Schmidt, 2020). Dann", "Lärm wirkt. Dann"),
        ("Lärm wirkt (vgl. (Müller, 2019) Schmidt, 2020). Dann", "Lärm wirkt. Dann"),
        ("Lärm wirkt ((Müller, 2019)). Dann", "Lärm wirkt. Dann"),
        ("((Müller, 2019) Schmidt, 2020) zeigt das.", "Schmidt zeigt das."),
        # prose once the inner citation is read: the bracket stays (D-541)
        ("Es gilt ((Müller, 2019) siehe Tabelle 2).", "Es gilt (Müller siehe Tabelle 2)."),
    ],
)  # fmt: skip
def test_a_nested_citation_reads_the_same_on_a_second_run(printed: str, said: str) -> None:
    once = read(CITATIONS, printed)
    assert once == said
    assert read(CITATIONS, once) == once
    assert read_all(read_all(printed)) == read_all(printed)


def test_an_english_round_bracket_of_numbers_is_still_a_citation() -> None:
    """English has no decimal comma: "[1,2; 3,4]" cites sources 1, 2, 3 and 4."""
    document = make_document([(BlockKind.PARAGRAPH, "It holds ([1,2; 3,4]).")], "en")
    edits = CITATIONS.find(document, StepContext("en"))
    assert spoken_text(apply_edits(document, edits)) == "It holds."


@given(st.text(max_size=200))
def test_any_text_keeps_the_contract_in_german(text: str) -> None:
    document = make_document([(BlockKind.PARAGRAPH, text)], "de")
    check_text_step(LINKS, [document], allow_ask=False)
    check_text_step(CITATIONS, [document], allow_ask=False)


@pytest.mark.parametrize(
    "text",
    [
        "Siehe https://x.org/a (abgerufen am 12.03.2020) und " * 3000,
        "(vgl. Müller u. a. 2019, S. 12) " * 3000,
        "Laut " + "Anna " * 20_000 + "Müller (2019)",
        "(" * 20_000 + "Müller 2019" + ")" * 20_000,
        "https://x.org/a, (Müller, 2019). https://x.org/b (Müller, 2019) " * 1000,
        "Das KI unter https://x.org/a [1; 2] und KI Druck " * 2000,
    ],
    ids=[
        "access-notes",
        "citations",
        "long-names",
        "deep-brackets",
        "links-and-citations",
        "intervals-after-links",
    ],
)
def test_long_german_blocks_take_linear_time(text: str) -> None:
    document = make_document([(BlockKind.PARAGRAPH, text)], "de")
    started = time.perf_counter()
    LINKS.find(document, DE)
    CITATIONS.find(document, DE)
    assert time.perf_counter() - started < 3
