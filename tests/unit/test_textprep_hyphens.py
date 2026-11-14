"""Words hyphenated at a line end (TP-02, #65, D-149, D-150, D-152): the written rule.

Unit cases for each part of the rule, property tests, and the corpus: every line-end hyphen
of the corpus papers against the hand-checked readings in
tests/regression/line-end-hyphens-en.toml (and -de.toml for the German paper, #235), and the
"hyphenation" truth sentences.
"""

import re
import tomllib
from functools import cache
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from sci2audio.core import BlockKind, Document, EditKind, Span, apply_edits
from sci2audio.extraction import extract_pdf
from sci2audio.layout import build_document
from sci2audio.testing import check_text_step, make_document
from sci2audio.textprep import (
    BUILT_IN_STEPS,
    LineEndHyphenStep,
    StepContext,
    UnicodeStep,
    run_steps,
    spoken_text,
)
from sci2audio.textprep.hyphens import SECOND_WORDS, SKIPPED_KINDS, printed_words
from sci2audio.textprep.hyphens import WORDS as HYPHEN_WORDS

EN = StepContext("en")
DE = StepContext("de")
STEP = LineEndHyphenStep()
TESTS = Path(__file__).resolve().parents[1]
PAPERS = sorted((TESTS / "corpus" / "papers").glob("*.pdf"))
READINGS = tomllib.loads((TESTS / "regression" / "line-end-hyphens-en.toml").read_text("utf-8"))
# The German papers' hyphens, read by the German rule (#235).
READINGS_DE = tomllib.loads((TESTS / "regression" / "line-end-hyphens-de.toml").read_text("utf-8"))
GERMAN_PAPERS = {p["name"] for p in READINGS_DE["paper"]}


def readings_of(paper: Path) -> dict:
    return READINGS_DE if paper.stem in GERMAN_PAPERS else READINGS


def edits_of(*texts: str) -> list[tuple[Span, str]]:
    document = make_document([(BlockKind.PARAGRAPH, text) for text in texts])
    edits = STEP.find(document, EN)
    assert all(edit.kind is EditKind.REMOVE for edit in edits)
    return [(edit.span, edit.reason) for edit in edits]


def read(*texts: str) -> list[str]:
    document = make_document([(BlockKind.PARAGRAPH, text) for text in texts])
    script = apply_edits(document, STEP.find(document, EN))
    return [
        spoken_text(piece for piece in script if piece.span.block == index)
        for index in range(len(texts))
    ]


def test_a_split_word_is_joined_by_removing_the_hyphen_and_the_line_break() -> None:
    assert edits_of("normal develop-\nment") == [
        (Span(0, 14, 16), 'word split at a line end joined: "development"')
    ]
    assert read("emotional pro-\ncessing.") == ["emotional processing."]


def test_a_kept_hyphen_loses_only_the_line_break() -> None:
    assert edits_of("a state-of-the-\nart model") == [
        (
            Span(0, 15, 16),
            'hyphen at a line end kept, read as one word: "state-of-the-art" (a compound)',
        )
    ]
    assert read("a state-of-the-\nart model") == ["a state-of-the-art model"]


def test_the_unicode_hyphen_counts_too() -> None:
    assert read("develop\N{HYPHEN}\nment and state-of-the\N{HYPHEN}\nart") == [
        "development and state-of-the\N{HYPHEN}art"
    ]


@pytest.mark.parametrize(
    ("printed", "spoken"),
    [
        ("From 2019-\n2020 on", "From 2019-2020 on"),
        ("COVID-\n19 cases", "COVID-19 cases"),
        ("as J.-\nP. Martin", "as J.-P. Martin"),
        ("Davinci-\n003 model", "Davinci-003 model"),
    ],
)
def test_rule_1_a_hyphen_next_to_a_digit_or_mark_is_kept(printed: str, spoken: str) -> None:
    assert read(printed) == [spoken]
    assert "next to a digit or mark" in edits_of(printed)[0][1]


@pytest.mark.parametrize(
    "printed",
    [
        "a dash -\nand more",  # white space before: a dash, not a split word
        "a-\n(b)",  # nothing to join to
        "end-\n",  # the block ends
        "-\nstart",  # nothing before
    ],
)
def test_rule_1_a_hyphen_with_nothing_to_join_gets_no_edit(printed: str) -> None:
    assert edits_of(printed) == []


@pytest.mark.parametrize("word", ["and", "or", "nor", "And"])
def test_rule_2_a_suspended_hyphen_stays_with_a_space(word: str) -> None:
    assert edits_of(f"pre-\n{word} post-test") == []
    assert read(f"pre-\n{word} post-test") == [f"pre- {word} post-test"]


def test_rule_2_needs_the_whole_word() -> None:
    assert read("pre-\nandesite rocks") == ["preandesite rocks"]  # not "and"


def test_rule_2_not_when_the_conjunction_is_split_again() -> None:
    """Found by Hypothesis: the join after "and" would change the word on a second run."""
    assert read("ab-\nand-\nab")[0] == "abandab"
    assert read("pre-\nand")[0] == "pre- and"  # at the end of the block too


def test_rule_3_the_form_printed_more_often_elsewhere_wins() -> None:
    assert read("Our pre-\ntraining set.", "We use pre-training.") == [
        "Our pre-training set.",
        "We use pre-training.",
    ]
    assert read("A pre-\nfix tree.", "Each prefix counts.") == [
        "A prefix tree.",
        "Each prefix counts.",
    ]
    joined = edits_of("A pre-\nfix tree.", "Each prefix counts.")[0][1]
    assert joined == 'word split at a line end joined: "prefix" (the document prints it so)'


def test_rule_3_counts_without_case_and_a_tie_keeps_the_hyphen() -> None:
    assert read("non-\nterminal", "Non-terminal and nonterminal")[0] == "non-terminal"
    assert read("non-\nterminal", "NONTERMINAL")[0] == "nonterminal"


def test_rule_3_reads_ligatures_as_their_letters() -> None:
    assert read("cost-\nefficient", "cost-eﬃcient")[0] == "cost-efficient"


def test_rule_3_ignores_other_line_end_hyphens() -> None:
    """A word split at a line end is no evidence for itself or its twin."""
    assert printed_words(make_document([(BlockKind.PARAGRAPH, "pre-\ntraining")])) == {
        "pre": 1,
        "training": 1,
    }
    assert read("x-ray of the walk-\nway", "the walk-\nway")[0] == "x-ray of the walkway"


@pytest.mark.parametrize(
    ("printed", "spoken"),
    [
        ("the x-\naxis", "the x-axis"),  # one letter before
        ("PP-\nRoBERTa", "PP-RoBERTa"),  # a capital before
        ("the OH-\nconductance", "the OH-conductance"),
        ("one-to-\none map", "one-to-one map"),  # already holds a hyphen
        ("non-\nEnglish texts", "non-English texts"),  # a capital after
    ],
)
def test_rule_4_a_compound_by_its_look_keeps_the_hyphen(printed: str, spoken: str) -> None:
    assert read(printed) == [spoken]


def test_rule_4_a_hyphen_inside_the_word_after_does_not_count() -> None:
    assert read("ter-\nror-related") == ["terror-related"]


@pytest.mark.parametrize("second", sorted(SECOND_WORDS))
def test_rule_5_words_that_mostly_end_a_compound(second: str) -> None:
    assert read(f"a context-\n{second} view") == [f"a context-{second} view"]


def test_rule_5_self_compounds_keep_the_hyphen() -> None:
    assert read("self-\nreported scores") == ["self-reported scores"]


@pytest.mark.parametrize(
    ("printed", "spoken"),
    [
        ("Kl\N{DIAERESIS}a-\nui", "Kl\N{DIAERESIS}aui"),  # the accent is part of the word
        (
            "Garc\N{ACUTE ACCENT}\N{LATIN SMALL LETTER DOTLESS I}-\na",
            "Garc\N{ACUTE ACCENT}\N{LATIN SMALL LETTER DOTLESS I}a",
        ),
        (
            "\N{LATIN SMALL LIGATURE FI}-\nnally",
            "\N{LATIN SMALL LIGATURE FI}nally",
        ),  # not one letter
        ("Kl-\n\N{DIAERESIS}aui", "Kl\N{DIAERESIS}aui"),  # an accent starts the next line
    ],
)
def test_the_rule_reads_through_tex_accents_and_ligatures(printed: str, spoken: str) -> None:
    """Review S1 of #98: an accent set apart or a ligature does not end or shorten a word."""
    assert read(printed) == [spoken]


def test_the_document_spelling_ignores_accents() -> None:
    """ "Kl\N{DIAERESIS}aui" and "Kl\N{LATIN SMALL LETTER A WITH DIAERESIS}ui" count as one word."""
    doc = make_document(
        [
            (
                BlockKind.PARAGRAPH,
                "Kl\N{DIAERESIS}aui and Kl\N{LATIN SMALL LETTER A WITH DIAERESIS}ui",
            )
        ]
    )
    assert printed_words(doc)["klaui"] == 2


def test_rule_6_otherwise_the_word_is_joined() -> None:
    assert read("bet-\nter", "infor-\nmation", "Pri-\nvacy") == ["better", "information", "Privacy"]


@pytest.mark.parametrize("kind", sorted(SKIPPED_KINDS))
def test_formulas_and_tables_are_left_alone(kind: BlockKind) -> None:
    document = make_document([(kind, "a = b -\nc"), (kind, "develop-\nment")])
    assert STEP.find(document, EN) == []


@pytest.mark.parametrize(
    "kind", [BlockKind.HEADING, BlockKind.CAPTION, BlockKind.FOOTNOTE, BlockKind.LIST_ITEM]
)
def test_other_text_blocks_are_joined(kind: BlockKind) -> None:
    document = make_document([(kind, "develop-\nment")])
    assert len(STEP.find(document, EN)) == 1


def test_english_and_german() -> None:
    assert STEP.handles("en-GB")
    assert STEP.handles("de")
    assert STEP.handles("de-CH")
    assert not STEP.handles("fr")
    assert set(HYPHEN_WORDS) == {"en", "de"}


# German (#96, D-475): the same rule with the German words of rules 2 and 5.


def read_de(*texts: str, language: str = "de") -> list[str]:
    document = make_document([(BlockKind.PARAGRAPH, text) for text in texts], language)
    script = apply_edits(document, STEP.find(document, StepContext(language)))
    return [
        spoken_text(piece for piece in script if piece.span.block == index)
        for index in range(len(texts))
    ]


@pytest.mark.parametrize(
    "word",
    ["und", "oder", "bis", "sowie", "bzw.", "beziehungsweise", "noch", "respektive", "Und"],
)
def test_german_rule_2_a_suspended_hyphen_before_a_conjunction(word: str) -> None:
    assert read_de(f"Wohnungs-\n{word} Sozialarbeit") == [f"Wohnungs- {word} Sozialarbeit"]


@pytest.mark.parametrize("word", ["and", "or", "nor"])
def test_german_text_does_not_take_the_english_conjunctions(word: str) -> None:
    assert read_de(f"Wohnungs-\n{word} Sozialarbeit") == [f"Wohnungs{word} Sozialarbeit"]


def test_english_text_does_not_take_the_german_conjunctions() -> None:
    assert read("Wohnungs-\nund Sozialarbeit") == ["Wohnungsund Sozialarbeit"]


@pytest.mark.parametrize("word", ["u.", "o.", "vs.", "resp.", "versus", "U."])
def test_german_rule_2_short_conjunctions_count_with_their_full_stop(word: str) -> None:
    assert read_de(f"Kinder-\n{word} Jugendhilfe") == [f"Kinder- {word} Jugendhilfe"]


def test_german_rule_2_als_counts_only_before_auch() -> None:
    assert read_de("sowohl Lehr-\nals auch Lernprozesse") == ["sowohl Lehr- als auch Lernprozesse"]
    assert read_de("sowohl Lehr-\nALS AUCH Lern") == ["sowohl Lehr- ALS AUCH Lern"]
    assert read_de("des Materi-\nals zählt") == ["des Materials zählt"]  # a bare "als": split


@pytest.mark.parametrize(
    ("printed", "spoken"),
    [
        # a short form without its full stop is the rest of a split word
        ("die Werk-\nstatt", "die Werkstatt"),  # "statt" is no conjunction here
        ("ab-\nsondern", "absondern"),  # "sondern" is not on the list: it starts a clause
        ("so-\nwie", "sowie"),  # "wie" is not on the list: "sowie" is one word
        ("Kinder-\nu Jugend", "Kinderu Jugend"),  # "u" without its full stop is a split word
        ("Lehr-\nvsx", "Lehrvsx"),  # not "vs."
        ("Materi-\nals Beispiel", "Materials Beispiel"),  # "als" not before "auch"
        ("Materi-\nals auchx", "Materials auchx"),  # "auch" must be a whole word
    ],
)
def test_german_rule_2_joins_these(printed: str, spoken: str) -> None:
    assert read_de(printed) == [spoken]


def test_german_rule_2_needs_the_whole_word() -> None:
    assert read_de("Ver-\nunderung")[0] == "Verunderung"  # not "und"
    assert read_de("Kinder-\nbis-\nher")[0] == "Kinderbisher"  # split again: no conjunction


@pytest.mark.parametrize(
    ("printed", "spoken"),
    [
        ("Corona-\nPandemie", "Corona-Pandemie"),  # a capital after: the author's hyphen
        ("Sozial-\narbeit", "Sozialarbeit"),  # lower case after: a split word
        ("PDF-\nDatei", "PDF-Datei"),
        ("E-\nMail", "E-Mail"),
        ("Ad-hoc-\nAnalyse", "Ad-hoc-Analyse"),
        ("COVID-\n19", "COVID-19"),
        ("Grö-\nße", "Größe"),
        ("Über-\nsetzung", "Übersetzung"),
    ],
)
def test_german_capital_and_compound_tests(printed: str, spoken: str) -> None:
    assert read_de(printed) == [spoken]


@pytest.mark.parametrize("second", sorted(SECOND_WORDS)[:4])
def test_german_has_no_second_word_or_self_rule(second: str) -> None:
    assert read_de(f"kontext-\n{second}") == [f"kontext{second}"]
    assert read_de("self-\nbezogen") == ["selfbezogen"]


def test_german_document_spelling_wins_first() -> None:
    assert read_de("Die Lade-\nstation.", "Die Lade-Station.") == [
        "Die Lade-station.",
        "Die Lade-Station.",
    ]


def test_regional_german_tags_use_the_german_words() -> None:
    assert read_de("Kinder-\nund Jugend", language="de-AT") == ["Kinder- und Jugend"]


# Property tests: words joined mostly by line-end hyphens, so most examples exercise the rule
# (about 3 in 4 propose an edit; the Unicode tests reach about the same).
WORDS = ["ab", "cd", "x", "Ab", "and", "self", "based", "pre", "pre-train", "1", ".", "ﬁ",
         "Kl\N{DIAERESIS}a", "Garc\N{ACUTE ACCENT}\N{LATIN SMALL LETTER DOTLESS I}"]  # fmt: skip
GAPS = ["-\n", "-\n", "-\n", "\N{HYPHEN}\n", " ", "\n", "-", " -\n", "-\n-\n"]
texts = st.lists(st.tuples(st.sampled_from(WORDS), st.sampled_from(GAPS)), max_size=8).map(
    lambda pairs: "".join(word + gap for word, gap in pairs)
)


@given(st.lists(texts, min_size=1, max_size=3))
def test_the_step_keeps_the_contract_on_any_text(blocks: list[str]) -> None:
    document = make_document([(BlockKind.PARAGRAPH, text) for text in blocks])
    check_text_step(STEP, [document], allow_ask=False)


# German words with umlauts, ß and the German conjunctions, so the German paths are reached
GERMAN_WORDS = ["Bun", "des", "und", "oder", "bzw.", "Über", "ße", "Pandemie", "E", "PDF",
                "19", "noch", "Kinder", "bis"]  # fmt: skip
german_texts = st.lists(
    st.tuples(st.sampled_from(GERMAN_WORDS), st.sampled_from(GAPS)), max_size=8
).map(lambda pairs: "".join(word + gap for word, gap in pairs))


@given(st.lists(german_texts, min_size=1, max_size=3))
def test_the_step_keeps_the_contract_on_any_german_text(blocks: list[str]) -> None:
    document = make_document([(BlockKind.PARAGRAPH, text) for text in blocks], "de")
    check_text_step(STEP, [document], allow_ask=False)


@given(st.lists(texts, min_size=1, max_size=3))
def test_only_hyphens_and_line_breaks_after_them_are_removed(blocks: list[str]) -> None:
    document = make_document([(BlockKind.PARAGRAPH, text) for text in blocks])
    for edit in STEP.find(document, EN):
        text = blocks[edit.span.block]
        removed = text[edit.span.start : edit.span.end]
        assert removed in ("-\n", "\N{HYPHEN}\n", "\n")
        assert text[edit.span.end - 2] in "-\N{HYPHEN}"  # the line break follows a hyphen
    script = apply_edits(document, STEP.find(document, EN))
    for index, text in enumerate(blocks):
        spoken = "".join(piece.text for piece in script if piece.span.block == index)
        assert re.sub(r"[\W_]", "", spoken) == re.sub(r"[\W_]", "", text)  # every letter kept


# The corpus papers.


@cache
def document(paper: Path) -> Document:
    return build_document(extract_pdf(paper))


def readings_by_rule(doc: Document) -> list[tuple[str, str, str]]:
    """(word before, word after, reading) for each line-end hyphen the step looks at."""
    context = StepContext(doc.language)  # the German paper by the German rule (#235)
    edits = {(e.span.block, e.span.start, e.span.end) for e in STEP.find(doc, context)}
    found = []
    for index, block in enumerate(doc.blocks):
        if block.kind in SKIPPED_KINDS:
            continue
        for match in re.finditer(r"[-\N{HYPHEN}]\n", block.text):
            at = match.start()
            before = re.search(r"\S*\Z", block.text[: at + 1])
            after = re.match(r"\S*", block.text[at + 2 :])
            assert before is not None
            assert after is not None
            if (index, at, at + 2) in edits:
                reading = "join"
            elif (index, at + 1, at + 2) in edits:
                reading = "keep"
            else:
                reading = "none"
            found.append((before.group(), after.group(), reading))
    return found


@pytest.mark.parametrize("paper", PAPERS, ids=[paper.stem for paper in PAPERS])
def test_every_corpus_line_end_hyphen_reads_as_checked_by_hand(paper: Path) -> None:
    readings = readings_of(paper)
    (expected,) = [p["hyphens"] for p in readings["paper"] if p["name"] == paper.stem]
    misses = {
        (m["before"], m["after"]): m["rule_gives"]
        for m in readings["miss"]
        if m["paper"] == paper.stem
    }
    got = readings_by_rule(document(paper))
    assert [(b, a) for b, a, _ in got] == [(b, a) for b, a, _ in expected]
    for (before, after, reading), (_, _, truth) in zip(got, expected, strict=True):
        want = misses.get((before, after), truth)
        assert reading == want, f"{before!r} / {after!r}: rule reads {reading}, want {want}"


def test_the_readings_file_covers_every_paper_and_the_misses_are_real() -> None:
    named = sorted(p["name"] for readings in (READINGS, READINGS_DE) for p in readings["paper"])
    assert named == [paper.stem for paper in PAPERS]
    for readings, total, most in ((READINGS, 495, 7), (READINGS_DE, 38, 1)):
        assert sum(len(p["hyphens"]) for p in readings["paper"]) == total
        for miss in readings["miss"]:
            (paper,) = [p for p in readings["paper"] if p["name"] == miss["paper"]]
            pair = (miss["before"], miss["after"])
            truths = {r for b, a, r in paper["hyphens"] if (b, a) == pair}
            assert truths, miss
            assert miss["rule_gives"] not in truths, miss
        assert len(readings["miss"]) <= most  # the rule may get better, never worse


def truth_sentences() -> list[tuple[Path, str]]:
    found = []
    for paper in PAPERS:
        path = TESTS / "corpus" / "truth" / f"{paper.stem}.toml"
        truth = tomllib.loads(path.read_text("utf-8"))
        found += [(paper, i["text"]) for i in truth["verbatim"] if i["where"] == "hyphenation"]
    return found


SENTENCES = truth_sentences()


@pytest.mark.parametrize(
    ("paper", "sentence"), SENTENCES, ids=[f"{p.stem}-{t[:20]}" for p, t in SENTENCES]
)
def test_the_hyphenation_truth_sentences_read_word_for_word(paper: Path, sentence: str) -> None:
    doc = document(paper)
    script = run_steps(doc, StepContext(doc.language), (UnicodeStep(), STEP), strict=True).script()
    blocks = [
        spoken_text(piece for piece in script if piece.span.block == index)
        for index in range(len(doc.blocks))
    ]
    assert any(sentence in block for block in blocks), sentence


def test_seven_papers_have_a_hyphenation_truth_sentence() -> None:
    assert len({paper for paper, _ in SENTENCES}) == 7  # the German paper's since #235


def test_characters_and_hyphenation_run_last() -> None:
    """D-150: a one-character fix placed earlier would block the rules after it."""
    assert [step.id for step in BUILT_IN_STEPS][-2:] == ["unicode-clean-up", "line-end-hyphens"]
