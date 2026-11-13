"""The utterance cutter: sentences, the fallback cut for long ones, spans (#63, D-98, Q4)."""

import re
import time
from functools import cache
from itertools import pairwise
from pathlib import Path

import pytest
from core_strategies import documents, edits_on, overlaps, spans_in
from hypothesis import given
from hypothesis import strategies as st

from sci2audio.core import BlockKind, Document, Edit, EditKind, ScriptPiece, Span, apply_edits
from sci2audio.extraction import extract_pdf
from sci2audio.layout import build_document
from sci2audio.testing import make_document
from sci2audio.textprep import (
    ABBREVIATIONS,
    DEFAULT_MAX_CHARS,
    StepContext,
    Utterance,
    cut_utterances,
    run_steps,
    spoken_text,
)
from sci2audio.textprep.utterances import _BEFORE_NUMBERS


def cut(text: str, max_chars: int = DEFAULT_MAX_CHARS, language: str = "en") -> list[str]:
    document = make_document([(BlockKind.PARAGRAPH, text)], language)
    return [
        u.text for u in cut_utterances(document, apply_edits(document, []), language, max_chars)
    ]


@pytest.mark.parametrize(
    ("text", "sentences"),
    [
        ("One. Two? Three! Four", ["One.", "Two?", "Three!", "Four"]),
        ("Line one\nends here. Next\tline.", ["Line one ends here.", "Next line."]),
        ('He said "Stop." Then left.', ['He said "Stop."', "Then left."]),
        ("It was (as shown.) Then more.", ["It was (as shown.)", "Then more."]),
        ("Results. 25 cases followed.", ["Results.", "25 cases followed."]),
        ("Seen. (Later) more.", ["Seen.", "(Later) more."]),
        ("Not a cut. lower case goes on.", ["Not a cut. lower case goes on."]),
        ("The value p < .05 held. Next.", ["The value p < .05 held.", "Next."]),
        ("Values 1.5 and 2.25 hold.", ["Values 1.5 and 2.25 hold."]),
        ("1 Introduction", ["1 Introduction"]),
        ("Wait... More text.", ["Wait...", "More text."]),
        ("", []),
        (" \n\t ", []),
    ],
)
def test_sentences_end_at_full_stops_before_a_new_sentence(text: str, sentences: list[str]) -> None:
    assert cut(text) == sentences


@pytest.mark.parametrize(
    "abbreviation",
    ["Fig.", "Figs.", "Eq.", "Sec.", "Tab.", "et al.", "e.g.", "i.e.", "cf.", "vs.", "Dr.",
     "Prof.", "approx.", "Approx.", "resp.", "ca.", "incl.", "(Fig.", "(e.g."],
)  # fmt: skip
def test_no_sentence_ends_after_an_abbreviation(abbreviation: str) -> None:
    text = f"As shown {abbreviation} One more word. Next sentence."
    assert cut(text) == [f"As shown {abbreviation} One more word.", "Next sentence."]


@pytest.mark.parametrize(
    ("text", "utterances"),
    [
        # #91: the abbreviation is glued to a bracket or other text before it
        ("Smith (2022)[p. 8], it works.", ["Smith (2022)[p. 8], it works."]),
        ("See it [Fig. 3] here. Next.", ["See it [Fig. 3] here.", "Next."]),
        ("Data (2020)(pp. 3-5) hold. Next.", ["Data (2020)(pp. 3-5) hold.", "Next."]),
        ("As in “Fig. 2” we see.", ["As in “Fig. 2” we see."]),
        ("He said “e.g. This” works.", ["He said “e.g. This” works."]),
        # ... but a word glued to a bracket that is no abbreviation still ends a sentence
        ("It was seen [here]. Then more.", ["It was seen [here].", "Then more."]),
        ("It holds (in 2022)[ours]. Then more.", ["It holds (in 2022)[ours].", "Then more."]),
        # "no." glued to a bracket is still an abbreviation only before a number
        ("The answer [no.] Then we stop.", ["The answer [no.]", "Then we stop."]),
    ],
)  # fmt: skip
def test_an_abbreviation_glued_to_a_bracket_is_no_sentence_end(
    text: str, utterances: list[str]
) -> None:
    assert cut(text) == utterances


_GLUE = "([{\"'\u201c\u2018)]}"  # brackets and quotes, curly ones too


@given(
    st.sampled_from(sorted(ABBREVIATIONS["en"])),
    st.text(alphabet=_GLUE + "0123456789", max_size=6),
    st.sampled_from(_GLUE),
    st.sampled_from(["One", "Two", "5", "(A", "“Then"]),
)
def test_an_abbreviation_with_anything_glued_before_it_is_never_a_sentence_end(
    abbreviation: str, glued: str, bracket: str, following: str
) -> None:
    glued += bracket  # "(2022)[" before "p.": the abbreviation starts after a bracket or quote
    if abbreviation in _BEFORE_NUMBERS and not following[0].isdigit():
        following = "5"
    text = f"As shown {glued}{abbreviation} {following} more."
    assert cut(text) == [text]


def test_no_and_p_are_abbreviations_only_before_a_number() -> None:
    assert cut("See No. 5 and p. 12 there. Next.") == ["See No. 5 and p. 12 there.", "Next."]
    assert cut("The answer is no. Then we stop.") == ["The answer is no.", "Then we stop."]


@pytest.mark.parametrize(
    "text",
    ["Smith et al.\u00a0(2019) showed it.", "As in Fig.\u00a02 we see.", "See\u00a0Fig. 2 now."],
)
def test_a_no_break_space_does_not_hide_an_abbreviation(text: str) -> None:
    assert cut(text) == [text.replace("\u00a0", " ")]


def test_no_sentence_ends_after_an_initial() -> None:
    assert cut("We thank J. Smith and A. B. Jones. They helped.") == [
        "We thank J. Smith and A. B. Jones.",
        "They helped.",
    ]


def test_other_languages_use_the_punctuation_rule_without_english_abbreviations() -> None:
    assert cut("Siehe Fig. Zwei. Dann mehr.", language="de") == [
        "Siehe Fig.",
        "Zwei.",
        "Dann mehr.",
    ]
    assert cut("See Fig. Two.", language="en-GB") == ["See Fig. Two."]


def test_a_long_sentence_is_cut_at_a_semicolon_or_colon_first() -> None:
    first = "a " * 20 + "b; "
    text = first + "c, " * 10 + "d."
    assert cut(text, max_chars=60) == [first.strip(), ("c, " * 10 + "d.")]


def test_then_at_a_comma_then_at_a_dash_then_at_a_space() -> None:
    assert cut("aaa bbb, ccc \u2013 ddd eee fff.", max_chars=12) == [
        "aaa bbb,",
        "ccc \u2013",
        "ddd eee fff.",
    ]
    assert cut("aaa bbb ccc ddd", max_chars=8) == ["aaa bbb", "ccc ddd"]


def test_a_word_longer_than_the_limit_is_cut_where_it_must_be() -> None:
    assert cut("x" * 25, max_chars=10) == ["x" * 10, "x" * 10, "x" * 5]


def test_a_1000_character_sentence_fits_the_limit() -> None:
    text = " ".join(f"word{n}," for n in range(150)) + " end."
    parts = cut(text)
    assert len(text) > 1000
    assert all(len(part) <= DEFAULT_MAX_CHARS for part in parts)
    assert all(part.endswith(",") for part in parts[:-1])
    assert " ".join(parts) == text


def test_only_the_parts_after_a_length_cut_continue_their_sentence() -> None:
    document = make_document([(BlockKind.PARAGRAPH, "aaa bbb, ccc ddd. Next one. Last.")])
    utterances = cut_utterances(document, apply_edits(document, []), max_chars=12)
    assert [(u.text, u.continues) for u in utterances] == [
        ("aaa bbb,", False),
        ("ccc ddd.", True),
        ("Next one.", False),
        ("Last.", False),
    ]


def test_a_new_block_never_continues() -> None:
    document = make_document([(BlockKind.PARAGRAPH, "x" * 15), (BlockKind.PARAGRAPH, "y" * 5)])
    utterances = cut_utterances(document, apply_edits(document, []), max_chars=10)
    assert [u.continues for u in utterances] == [False, True, False]


def test_max_chars_must_be_positive() -> None:
    with pytest.raises(ValueError, match="at least 1"):
        cut_utterances(make_document([]), (), max_chars=0)


def test_spans_point_at_the_original_and_pauses_stand_alone() -> None:
    text = "Several studies (Smith, 2019) agree. Dr. Lee\ndisagrees."
    document = make_document([(BlockKind.PARAGRAPH, text), (BlockKind.HEADING, "2 Methods")])
    edits = [
        Edit(Span(0, 15, 29), EditKind.REMOVE, "citation", "x"),
        Edit(Span(0, 37, 40), EditKind.REPLACE, "abbreviation", "x", replacement="Doctor"),
        Edit(Span(1, 9, 9), EditKind.PAUSE, "after a heading", "x"),
    ]
    utterances = cut_utterances(document, apply_edits(document, edits))
    assert utterances == (
        Utterance("Several studies agree.", Span(0, 0, 36)),
        Utterance("Doctor Lee disagrees.", Span(0, 37, 55)),
        Utterance("2 Methods", Span(1, 0, 9)),
        Utterance("", Span(1, 9, 9), pause=True),
    )


def test_a_cut_does_not_split_a_replacement_that_fits() -> None:
    document = make_document([(BlockKind.PARAGRAPH, "aa bb x cc dd")])
    edit = Edit(Span(0, 6, 7), EditKind.REPLACE, "r", "x", replacement="one two")
    utterances = cut_utterances(document, apply_edits(document, [edit]), max_chars=12)
    # the last space that fits lies inside "one two": the cut moves to before it
    assert utterances == (
        Utterance("aa bb", Span(0, 0, 5)),
        Utterance("one two cc", Span(0, 6, 10), continues=True),
        Utterance("dd", Span(0, 11, 13), continues=True),
    )


def test_a_sentence_end_inside_a_replacement_does_not_split_it() -> None:
    document = make_document([(BlockKind.PARAGRAPH, "See note 1 here. More.")])
    edit = Edit(Span(0, 9, 10), EditKind.REPLACE, "r", "x", replacement="one. The note says hi.")
    assert cut_utterances(document, apply_edits(document, [edit])) == (
        Utterance("See note one. The note says hi. here.", Span(0, 0, 16)),
        Utterance("More.", Span(0, 17, 22)),
    )


def test_a_replacement_starting_with_white_space_keeps_its_span() -> None:
    document = make_document([(BlockKind.PARAGRAPH, "First part. X tail.")])
    edit = Edit(Span(0, 12, 13), EditKind.REPLACE, "r", "x", replacement=" Footnote one")
    assert cut_utterances(document, apply_edits(document, [edit])) == (
        Utterance("First part.", Span(0, 0, 11)),
        Utterance("Footnote one tail.", Span(0, 12, 19)),
    )


def test_a_same_length_replacement_is_still_a_replacement() -> None:
    # "A. B" has the length of "x yz", but is not the original text: it is read whole
    document = make_document([(BlockKind.PARAGRAPH, "Go x yz now.")])
    edit = Edit(Span(0, 3, 7), EditKind.REPLACE, "r", "x", replacement="a. Bc")
    assert [u.text for u in cut_utterances(document, apply_edits(document, [edit]))] == [
        "Go a. Bc now."
    ]


@pytest.mark.timeout(60)
def test_a_long_text_without_a_full_stop_is_cut_in_linear_time() -> None:
    text = "word " * 60_000  # 300,000 characters: 0.08 s; the quadratic cut would take about 11 s
    started = time.perf_counter()
    parts = cut(text)
    assert time.perf_counter() - started < 5
    assert all(len(part) <= DEFAULT_MAX_CHARS for part in parts)
    assert " ".join(parts) == text.strip()


def test_a_replacement_longer_than_the_limit_gives_later_parts_an_empty_span() -> None:
    document = make_document([(BlockKind.PARAGRAPH, "a X b")])
    edit = Edit(Span(0, 2, 3), EditKind.REPLACE, "r", "x", replacement="long " * 6)
    utterances = cut_utterances(document, apply_edits(document, [edit]), max_chars=12)
    spans = [u.span for u in utterances]
    assert spans[0] == Span(0, 0, 1)
    assert spans[1] == Span(0, 2, 3)
    assert all(span == Span(0, 3, 3) for span in spans[2:-1])
    assert spans[-1].end == 5
    assert all(len(u.text) <= 12 for u in utterances)


# ---- properties -------------------------------------------------------------------------


@st.composite
def scripts(draw: st.DrawFn) -> tuple[Document, tuple[ScriptPiece, ...]]:
    """A document and its script after some valid edits."""
    document = draw(documents())
    edits: list[Edit] = []
    if document.blocks:
        for _ in range(draw(st.integers(0, 5))):
            edit = draw(edits_on(draw(spans_in(document))))
            if not any(overlaps(edit.span, other.span) for other in edits):
                edits.append(edit)
    return document, apply_edits(document, edits)


@given(scripts(), st.integers(1, 80), st.sampled_from(["en", "de"]))
def test_utterances_cover_the_script_inside_their_blocks_in_order(
    case: tuple[Document, tuple[ScriptPiece, ...]], max_chars: int, language: str
) -> None:
    document, script = case
    utterances = cut_utterances(document, script, language, max_chars)
    for utterance in utterances:
        document.check_span(utterance.span)
        if utterance.pause:
            assert not utterance.text
            assert utterance.span.start == utterance.span.end
        else:
            assert utterance.text == spoken_text([ScriptPiece(utterance.text, utterance.span)])
            assert 0 < len(utterance.text) <= max_chars
    for a, b in pairwise(utterances):
        assert (a.span.block, a.span.end) <= (b.span.block, b.span.start)
    for index in range(len(document.blocks)):
        spoken = spoken_text([p for p in script if p.span.block == index and not p.pause])
        said = [u.text for u in utterances if u.span.block == index and not u.pause]
        # nothing lost or added; a cut inside a word adds a space, so compare without them
        assert re.sub(r"\s", "", "".join(said)) == re.sub(r"\s", "", spoken)
        pieces = [p for p in script if p.span.block == index]
        if all(len(word) <= max_chars for word in spoken.split()) and all(
            not p.pause and p.text == document.text_of(p.span) for p in pieces
        ):  # no replacement or pause, which may cut inside a word
            assert " ".join(said) == spoken
        # a replacement that fits the limit is read whole, inside one utterance
        for piece in pieces:
            words = spoken_text([piece])
            replaced = not piece.pause and piece.text != document.text_of(piece.span)
            if replaced and 0 < len(words) <= max_chars:
                assert any(words in text for text in said), (words, said)
    pauses = [p.span for p in script if p.pause]
    assert [u.span for u in utterances if u.pause] == pauses


@given(scripts(), st.integers(1, 80))
def test_continuing_utterances_join_into_the_uncut_sentences(
    case: tuple[Document, tuple[ScriptPiece, ...]], max_chars: int
) -> None:
    document, script = case
    cut_ = cut_utterances(document, script, max_chars=max_chars)
    whole = cut_utterances(document, script, max_chars=10**9)
    assert not any(u.continues for u in whole)
    groups: list[list[Utterance]] = []
    for utterance in cut_:
        if utterance.continues:
            assert groups
            assert not groups[-1][-1].pause
            assert groups[-1][-1].span.block == utterance.span.block
            groups[-1].append(utterance)
        else:
            groups.append([utterance])
    assert [u.pause for u in whole] == [group[0].pause for group in groups]
    for group, sentence in zip(groups, whole, strict=True):
        joined = "".join(u.text for u in group)
        assert re.sub(r"\s", "", joined) == re.sub(r"\s", "", sentence.text)
        assert group[0].span.start == sentence.span.start


@given(documents())
def test_the_built_in_script_cuts_without_failing(document: Document) -> None:
    run = run_steps(document, StepContext(document.language), strict=True)
    cut_utterances(document, run.script())


# ---- corpus -----------------------------------------------------------------------------

PAPERS = sorted((Path(__file__).resolve().parents[1] / "corpus" / "papers").glob("*.pdf"))


@cache
def paper_script(paper: Path) -> tuple[Document, tuple[ScriptPiece, ...]]:
    document = build_document(extract_pdf(paper))
    return document, run_steps(document, StepContext(document.language), strict=True).script()


@pytest.mark.timeout(120)
@pytest.mark.parametrize("paper", PAPERS, ids=[paper.stem for paper in PAPERS])
def test_every_corpus_paper_cuts_into_utterances_under_the_limit(paper: Path) -> None:
    document, script = paper_script(paper)
    utterances = cut_utterances(document, script)
    assert utterances
    assert all(0 < len(u.text) <= DEFAULT_MAX_CHARS for u in utterances)
    for utterance in utterances:
        document.check_span(utterance.span)
    for a, b in pairwise(utterances):
        assert (a.span.block, a.span.end) <= (b.span.block, b.span.start)
    for index in range(len(document.blocks)):
        spoken = spoken_text([p for p in script if p.span.block == index and not p.pause])
        said = [u.text for u in utterances if u.span.block == index and not u.pause]
        assert " ".join(said) == spoken  # exact, block by block


@pytest.mark.benchmark
def test_benchmark_cutting_the_largest_paper(benchmark) -> None:
    largest = max(PAPERS, key=lambda paper: paper.stat().st_size)
    document, script = paper_script(largest)
    benchmark(cut_utterances, document, script)
