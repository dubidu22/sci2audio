"""The utterance cutter: sentences, the fallback cut for long ones, spans (#63, D-98, Q4)."""

import re
from bisect import bisect_right
from functools import cache
from itertools import pairwise
from pathlib import Path

import pytest
from core_strategies import documents, edits_on, overlaps, spans_in
from hypothesis import given
from hypothesis import strategies as st
from linear_time import assert_linear

from sci2audio.core import BlockKind, Document, Edit, EditKind, ScriptPiece, Span, apply_edits
from sci2audio.extraction import extract_pdf
from sci2audio.layout import build_document
from sci2audio.testing import make_document
from sci2audio.testing.documents import rebuilt_from_script
from sci2audio.textprep import (
    ABBREVIATIONS,
    DEFAULT_MAX_CHARS,
    StepContext,
    Utterance,
    cut_utterances,
    run_steps,
    spoken_text,
)
from sci2audio.textprep.utterances import (
    _BEFORE_NUMBERS,
    _PAIRS_DE,
    MIN_PIECE,
    _counts,
    _cut_point,
    _joined,
    _rank,
    _readings,
)
from sci2audio.textprep.wordlists import clause_openers, parse_clause_openers


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
        # glued to a dash or a slash (review of #105, S1)
        ("Results\u2014e.g. Table 2 shows it.", ["Results\u2014e.g. Table 2 shows it."]),
        ("Results\u2013e.g. Table 2 shows it.", ["Results\u2013e.g. Table 2 shows it."]),
        ("The results/e.g. Table 2 agree.", ["The results/e.g. Table 2 agree."]),
        # a capital glued to a bracket or an apostrophe is no initial: these end a sentence
        # (review of #105, M1)
        ("I SAID I DON'T. Then we left.", ["I SAID I DON'T.", "Then we left."]),
        ("We cite [1]A. Next.", ["We cite [1]A.", "Next."]),
        ("It is in Table 1(a)B. Next.", ["It is in Table 1(a)B.", "Next."]),
        ("The value was x)A. Next.", ["The value was x)A.", "Next."]),
        ("It was 5'A. Next.", ["It was 5'A.", "Next."]),
        ("We call it Plan(B. Next one.", ["We call it Plan(B.", "Next one."]),
        # ... while an initial after an opening bracket or quote still is one
        ("Thanks to (J. Smith) for it.", ["Thanks to (J. Smith) for it."]),
    ],
)  # fmt: skip
def test_an_abbreviation_glued_to_a_bracket_is_no_sentence_end(
    text: str, utterances: list[str]
) -> None:
    assert cut(text) == utterances


_GLUE = "([{\"'\u201c\u2018)]}\u2013\u2014/"  # brackets, quotes, dashes and a slash


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


# ---- the best cut of a long sentence (#460, D-719 PR 4) -----------------------------------


@pytest.mark.parametrize(
    ("text", "at", "rank"),
    [
        ("one; two", 4, 0),
        ("one: two", 4, 0),
        ("one, but two", 4, 1),
        ("one, \u201cwhich two", 4, 1),  # an opening quote before the word
        ("one, But two", 4, 1),  # any case
        ("one, small two", 4, 2),
        ("one \u2013 two", 5, 3),
        ("one two", 4, 4),
        ("one,two", 4, None),  # no white space after the mark: "1,5", "a,b"
        ("one-two", 4, None),
    ],
)
def test_cut_places_are_ranked(text: str, at: int, rank: int | None) -> None:
    assert _rank(text, at, clause_openers("en")) == rank


def test_a_comma_before_a_clause_opener_wins_over_a_later_comma() -> None:
    text = "a" * 50 + ", which " + "b" * 50 + ", small " + "c" * 50 + " end."
    parts = cut(text, max_chars=150)
    assert parts[0] == "a" * 50 + ","
    # no clause opener: the comma nearest an even share wins
    assert cut(text.replace("which", "wide"), max_chars=150)[0].endswith("wide " + "b" * 50 + ",")


def test_a_colon_wins_even_when_it_makes_a_short_part() -> None:
    text = "a " * 30 + "b: " + "c, " * 40 + "d."
    assert cut(text, max_chars=150)[0] == ("a " * 30 + "b:")


# the cut-rule tests below were sized for a 300-character limit (#460, #481); they test where
# a sentence is cut, not the default limit, so they keep that size (#494 raised it to 400)
SIZED_FOR = 300


def _sentence(length: int) -> str:
    """A sentence of `length` characters without a clause mark."""
    body = ("word " * 100)[: length - 1]
    if body.endswith(" "):
        body = body[:-1] + "s"
    return body + "."


def test_a_sentence_up_to_the_default_limit_is_one_utterance() -> None:
    """#494: 400 characters, about 464 of the voice's 510 phoneme tokens at the worst
    measured German rate; one more character and the sentence is cut."""
    assert DEFAULT_MAX_CHARS == 400
    for length in (301, 399, 400):
        text = _sentence(length)
        assert len(text) == length
        assert cut(text) == [text]
    text = _sentence(401)
    parts = cut(text)
    assert len(parts) == 2
    assert " ".join(parts) == text


def test_the_second_piece_of_a_sentence_over_the_default_limit_continues_it() -> None:
    text = _sentence(401)
    document = make_document([(BlockKind.PARAGRAPH, text)], "en")
    utterances = cut_utterances(document, apply_edits(document, []))
    assert [u.continues for u in utterances] == [False, True]


def test_parts_keep_about_the_same_length() -> None:
    text = " ".join(["word"] * 70) + "."  # 350 characters, no clause mark
    parts = cut(text, max_chars=SIZED_FOR)
    assert len(parts) == 2
    assert abs(len(parts[0]) - len(parts[1])) <= 10


def test_no_cut_leaves_a_part_under_the_minimum_when_another_cut_does_not() -> None:
    # the colon would leave "Note:" alone; a comma later leaves both parts long enough
    text = "Note: " + "a " * 100 + "b, " + "c " * 100 + "d."
    parts = cut(text)
    assert all(len(part) >= MIN_PIECE for part in parts)
    assert parts[0].endswith("b,")
    # with no other place the short part is taken
    assert cut("Note: " + "x" * 30, max_chars=20)[0] == "Note:"


def test_a_semicolon_that_leaves_a_clipped_last_part_is_not_taken() -> None:
    # the fair filter checks the part after the cut too (#481 review N3)
    text = "w " * 80 + "b, " + "c " * 62 + "d; " + "e " * 8 + "f."  # 308 characters
    parts = cut(text, max_chars=SIZED_FOR)
    assert parts[0].endswith("b,")
    assert all(len(part) >= MIN_PIECE for part in parts)


def test_three_parts_share_the_whole_sentence_evenly() -> None:
    # the even share is taken over what is left of the sentence, not over the window
    parts = cut(" ".join(["word"] * 140) + ".", max_chars=SIZED_FOR)  # 700, no clause mark
    assert len(parts) == 3
    assert max(map(len, parts)) - min(map(len, parts)) <= 10


def _open(part: str, opening: str, closing: str) -> int:
    depth = 0
    for char in part:
        depth += char in opening
        depth -= char in closing and depth > 0
    return depth


@pytest.mark.parametrize(
    ("text", "language", "opening", "closing"),
    [
        # a comma inside a bracket lies nearest the even share; one outside wins (#481 S1)
        (
            "w " * 60 + "(for example, " + "x " * 40 + "y) and " + "z " * 40 + "end, " + "v " * 20,
            "en",
            "(",
            ")",
        ),
        # a space right after an opening bracket is inside it
        ("w " * 70 + "( " + "x " * 70 + ") " + "z " * 30 + "end.", "en", "(", ")"),
        (
            "w " * 60 + "\u201cfor example, " + "x " * 40 + "y\u201d, " + "z " * 60,
            "en",
            "\u201c",
            "\u201d",
        ),
        (
            "w " * 60 + "\u201ezum Beispiel, " + "x " * 40 + "y\u201c, " + "z " * 60,
            "de",
            "\u201e",
            "\u201c",
        ),
        (
            "w " * 60 + "\u00bbzum Beispiel, " + "x " * 40 + "y\u00ab, " + "z " * 60,
            "de",
            "\u00bb",
            "\u00ab",
        ),
    ],
)
def test_a_long_sentence_is_cut_outside_brackets_and_quotes(
    text: str, language: str, opening: str, closing: str
) -> None:
    parts = cut(text, max_chars=SIZED_FOR, language=language)
    assert len(parts) > 1
    assert all(
        _open(" ".join(parts[: n + 1]), opening, closing) == 0 for n in range(len(parts) - 1)
    )


_HEARD_EN = "the listeners heard every part of the recording in the quiet room and "
_HEARD_DE = "die Hörer hörten jeden Teil der Aufnahme im stillen Raum und "


@pytest.mark.parametrize(
    ("text", "language"),
    [
        (
            "We test a) the speed and b) the care with which "
            + _HEARD_EN * 2
            + "(as we saw in the first study, which "
            + _HEARD_EN
            + "of the long run) "
            + _HEARD_EN
            + "it ended.",
            "en",
        ),
        (
            "Wir prüfen a) das Tempo und b) die Sorgfalt, mit der "
            + _HEARD_DE * 2
            + "(wie die erste Studie, die "
            + _HEARD_DE
            + "zeigte) "
            + _HEARD_DE * 2
            + "und es endete.",
            "de",
        ),
    ],
)
def test_a_closing_mark_of_an_inline_list_opens_no_bracket_for_cutting(
    text: str, language: str
) -> None:
    # the ")" of "a)" closes nothing: the depth stays at zero, so the later "(" still counts
    # as open and no part ends inside it (#481 review round 2); sized for a 300 limit (#494)
    parts = cut(text, language=language, max_chars=SIZED_FOR)
    assert len(parts) > 1
    for part in parts:
        assert "(" not in part or part.rfind("(") < part.rfind(")")


def test_a_sentence_all_inside_a_bracket_is_still_cut() -> None:
    text = "(" + "word, " * 80 + "end)."
    parts = cut(text)
    assert len(parts) > 1
    assert all(len(part) <= DEFAULT_MAX_CHARS for part in parts)
    assert " ".join(parts) == text


def test_the_cut_never_falls_past_the_limit_and_takes_the_last_fit_without_a_place() -> None:
    text = "x" * 30
    counts = _counts(text)
    assert _cut_point(text, counts, 10) == 10


@given(
    st.lists(
        st.sampled_from(["word", "and", "which", "dass", "x" * 12, ",", ";", ":", "\u2013", "."]),
        min_size=1,
        max_size=120,
    ),
    st.integers(MIN_PIECE, 200),
)
def test_a_colon_cut_that_leaves_fair_parts_is_always_taken(
    tokens: list[str], max_chars: int
) -> None:
    text = " ".join(tokens).replace(" ,", ",").replace(" ;", ";").replace(" :", ":")
    counts = _counts(text)
    if counts[-1] <= max_chars:
        return
    cut_at = _cut_point(text, counts, max_chars, None, clause_openers("en"))
    assert 0 < cut_at <= len(text)
    assert counts[cut_at] <= max_chars or cut_at == bisect_right(counts, max_chars) - 1
    fair_colon = [
        i
        for i in range(1, len(text) + 1)
        if counts[i] <= max_chars
        and _rank(text, i, frozenset()) == 0
        and counts[i] >= MIN_PIECE
        and counts[-1] - counts[i] - 1 >= MIN_PIECE
    ]
    if fair_colon:
        assert text[cut_at - 1] in ";:"


def test_the_clause_openers_load_lower_case() -> None:
    assert {"and", "but", "which", "because"} <= clause_openers("en-GB")
    assert {"und", "dass", "weil", "die", "welche"} <= clause_openers("de")
    assert clause_openers("fr") == frozenset()
    for language in ("en", "de"):
        assert all(word.islower() and word.isalpha() for word in clause_openers(language))


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ('openers = ["und", "und"]', "listed twice"),
        ('openers = ["Und"]', "not one lower-case word"),
        ('openers = ["so dass"]', "not one lower-case word"),
        ('openers = ["und"]\nextra = 1', "unknown keys"),
    ],
)
def test_a_broken_clause_opener_list_names_the_file(text: str, message: str) -> None:
    with pytest.raises(ValueError, match=message) as error:
        parse_clause_openers("de/clause_openers.toml", text)
    assert "de/clause_openers.toml" in str(error.value)


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
    # the space nearest an even share lies inside "one two": the cut moves to before it; the
    # rest is then cut into even parts (#460)
    assert utterances == (
        Utterance("aa bb", Span(0, 0, 5)),
        Utterance("one two", Span(0, 6, 7), continues=True),
        Utterance("cc dd", Span(0, 8, 13), continues=True),
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
    # 300,000 characters: 0.08 s; the quadratic cut would take about 11 s (#276: ratio)
    parts = assert_linear(cut, lambda n: "word " * n, 60_000)
    assert all(len(part) <= DEFAULT_MAX_CHARS for part in parts)
    assert " ".join(parts) == ("word " * 60_000).strip()


@pytest.mark.timeout(60)
def test_a_block_of_many_sentences_is_cut_in_linear_time() -> None:
    # #268: the word before each full stop was searched from the start of the run
    parts = assert_linear(cut, lambda n: "It was here. Then more. " * n, 16_000)
    assert len(parts) == 32_000
    assert parts[:2] == ["It was here.", "Then more."]


# ---- sentence-rule fixes of the sentence test set (D-719) -----------------------------------


@pytest.mark.parametrize(
    ("text", "sentences"),
    [
        # a single capital after a maths symbol is a letter, no initial (#141)
        ("Let x \u2208 N. This holds.", ["Let x \u2208 N.", "This holds."]),
        ("Take A \u2282 B. Then C.", ["Take A \u2282 B.", "Then C."]),
        # ... also when the symbol is glued to the variable before it (#478 review S1)
        ("Let x= N. This holds.", ["Let x= N.", "This holds."]),
        ("Let 2x\u2264 N. This holds.", ["Let 2x\u2264 N.", "This holds."]),
        # ... and after a label word of the unit list
        ("See Appendix C. It lists all.", ["See Appendix C.", "It lists all."]),
        ("See Table A. It lists all.", ["See Table A.", "It lists all."]),
        # an initial still holds the sentence together
        ("We thank J. Smith today.", ["We thank J. Smith today."]),
        ("Given x and J. Smith today.", ["Given x and J. Smith today."]),
        # a section number alone starts its title's sentence
        ("1. Introduction", ["1. Introduction"]),
        ("2.1. Methods We used it.", ["2.1. Methods We used it."]),
        ("It ended. 2. Methods follow.", ["It ended.", "2. Methods follow."]),
        # ... of one to three digits each: a year alone is a sentence of its own
        ("It ended. 2019. Then more.", ["It ended.", "2019.", "Then more."]),
        # a number after words still ends its sentence
        ("Results. 25 cases followed.", ["Results.", "25 cases followed."]),
        ("The count was 12. Then more.", ["The count was 12.", "Then more."]),
    ],
)
def test_sentence_ends_found_by_the_sentence_test_set(text: str, sentences: list[str]) -> None:
    assert cut(text) == sentences


def test_a_sentence_ends_where_a_removed_stretch_ended_it() -> None:
    # the year is removed with its full stop; the sentence ended there, after "et al."
    document = make_document([(BlockKind.PARAGRAPH, "Smith et al. (2019). Then more.")])
    edit = Edit(Span(0, 12, 20), EditKind.REMOVE, "citation", "r")
    utterances = cut_utterances(document, apply_edits(document, [edit]))
    assert [u.text for u in utterances] == ["Smith et al.", "Then more."]
    # removed text without a full stop at its end ends nothing
    document = make_document([(BlockKind.PARAGRAPH, "Smith et al. (2019) Then more.")])
    edit = Edit(Span(0, 12, 19), EditKind.REMOVE, "citation", "r")
    utterances = cut_utterances(document, apply_edits(document, [edit]))
    assert [u.text for u in utterances] == ["Smith et al. Then more."]


def test_a_removed_stretch_ending_in_a_full_stop_and_a_closing_bracket_ends_it() -> None:
    document = make_document([(BlockKind.PARAGRAPH, "See Fig. (as shown.) Then more.")])
    edit = Edit(Span(0, 8, 20), EditKind.REMOVE, "aside", "r")
    utterances = cut_utterances(document, apply_edits(document, [edit]))
    assert [u.text for u in utterances] == ["See Fig.", "Then more."]


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


# ---- German sentence ends (#227, #229; D-530) ----------------------------------------------


def cut_read(text: str, language: str = "de") -> list[str]:
    """The utterances of the script the built-in steps make of `text`."""
    document = make_document([(BlockKind.PARAGRAPH, text)], language)
    script = run_steps(document, StepContext(language), strict=True).script()
    return [u.text for u in cut_utterances(document, script) if not u.pause]


@pytest.mark.parametrize(
    ("text", "sentences"),
    [
        # #227: no cut after a number or a short dotted word that does not end the sentence
        ("Es folgt 2. Teilnehmer Gruppe B.", ["Es folgt 2. Teilnehmer Gruppe B."]),
        ("Seit 3. Quartal stieg es.", ["Seit 3. Quartal stieg es."]),
        ("Er wurde 3. Sieger.", ["Er wurde 3. Sieger."]),
        ("Er war 2. Vorsitzender.", ["Er war 2. Vorsitzender."]),
        ("Siehe abb. 3 dazu.", ["Siehe abb. 3 dazu."]),
        ("Es gilt o. J. als Datum.", ["Es gilt o. J. als Datum."]),
        ("Gemessen in Tsd. Euro.", ["Gemessen in Tsd. Euro."]),
        # listed since #264, so read in full: still one utterance each
        ("Werk i. S. v. § 2 UrhG.", ["Werk im Sinne von § 2 UrhG."]),
        (
            "Ausnahmen von lit. a\u2013d. Ob das gilt.",
            ["Ausnahmen von Buchstabe a\u2013d.", "Ob das gilt."],
        ),
        (
            "Gemäß Art. 2 Abs. 1 i. V. m. Art. 1 Abs. 1 GG gilt das.",
            ["Gemäß Artikel 2 Absatz 1 in Verbindung mit Artikel 1 Absatz 1 GG gilt das."],
        ),
        (
            "Siehe Abbildung 1. PrivacyScore ist gut.",
            ["Siehe Abbildung 1.", "PrivacyScore ist gut."],
        ),
        ("Am 3. 4. 2019 kam es.", ["Am 3. 4. 2019 kam es."]),
        # ... while a sentence opener after the number still starts a sentence
        ("Es waren 3. Die Studie lief.", ["Es waren 3.", "Die Studie lief."]),
        ("Es waren 3. „Die Studie“ lief.", ["Es waren 3.", "„Die Studie“ lief."]),
        ("Es waren 2019. Studien folgten.", ["Es waren 2019.", "Studien folgten."]),
        # the limit (D-530): a noun after a bare number stays in the sentence
        ("Es waren 3. Studien zeigen das.", ["Es waren 3. Studien zeigen das."]),
        # already right before #227, kept
        ("Die 3. Welle kam.", ["Die dritte Welle kam."]),
        ("S. Müller schrieb.", ["S. Müller schrieb."]),
        ("Es sind 1. bis 3. genannt.", ["Es sind 1. bis 3. genannt."]),
        ("Äpfel usw. Dann mehr.", ["Äpfel und so weiter.", "Dann mehr."]),
        # #229: a dotted unit keeps its full stop before a sentence opener
        (
            "Die Messung dauerte 2 Std. Danach wurde gewertet.",
            ["Die Messung dauerte 2 Stunden.", "Danach wurde gewertet."],
        ),
        ("Es dauerte 5 Min. Dann kam er.", ["Es dauerte 5 Minuten.", "Dann kam er."]),
        ("Es kostet 2 Mio. Er zahlte.", ["Es kostet 2 Millionen.", "Er zahlte."]),
        ("Es waren 2 Mio. Im Jahr danach mehr.", ["Es waren 2 Millionen.", "Im Jahr danach mehr."]),
        # ... and reads it as one sentence before a noun
        (
            "2 Mio. Euro, 3 Mrd. Dollar, 5 Min. Pause, 3 Std. Fahrt.",
            ["2 Millionen Euro, 3 Milliarden Dollar, 5 Minuten Pause, 3 Stunden Fahrt."],
        ),
        # a citation after a read abbreviation leaves the sentence its full stop
        ("Siehe Kap. (Müller, 2019). Dann mehr.", ["Siehe Kapitel.", "Dann mehr."]),
        ("Siehe z. B. (Müller, 2019). Dann mehr.", ["Siehe zum Beispiel.", "Dann mehr."]),
        ("Die 12. (Müller & Schmidt, 2019). Dann mehr.", ["Die 12.", "Dann mehr."]),
        # PR #267 review: the first part of a compound opens no sentence (R1) ...
        ("Der 2. In-vitro-Versuch lief gut.", ["Der zweite In-vitro-Versuch lief gut."]),
        ("Es folgte der 2. Vor-Ort-Termin.", ["Es folgte der zweite Vor-Ort-Termin."]),
        ("Die 3. Nach-Untersuchung kam.", ["Die dritte Nach-Untersuchung kam."]),
        ("Die 2. Seit\u2011Ansicht fehlt.", ["Die zweite Seit\u2011Ansicht fehlt."]),
        (
            "Es dauerte 2 Std. Ein-Euro-Jobs kamen später.",
            ["Es dauerte 2 Stunden Ein-Euro-Jobs kamen später."],
        ),
        # ... nor a word that is also a noun after an ordinal (R3) ...
        ("Der 3. Laut des Wortes ist stumm.", ["Der dritte Laut des Wortes ist stumm."]),
        ("Das 2. Ich ist stark.", ["Das zweite Ich ist stark."]),
        # ... and a German quote opens a sentence, its closing one may end it (R4)
        ("Es dauerte 2 Std. »Danach« kam er.", ["Es dauerte 2 Stunden.", "»Danach« kam er."]),
        ("Es waren 3. »Die Studie« lief.", ["Es waren 3.", "»Die Studie« lief."]),
        ("»Es war gut.« Danach kam er.", ["»Es war gut.«", "Danach kam er."]),
        # #315 (D-577): the closing quotes of „…“, of the single low quote and of Swiss «…» end a
        # sentence too
        ("Er sagte „ja.“ Dann ging er.", ["Er sagte „ja.“", "Dann ging er."]),
        ("Er rief „Halt!“ Dann stand er.", ["Er rief „Halt!“", "Dann stand er."]),
        (
            "Sie fragte \u201awann?\u2018 Dann ging sie.",
            ["Sie fragte \u201awann?\u2018", "Dann ging sie."],
        ),
        ("Sie rief «Halt!» Dann stand sie.", ["Sie rief «Halt!»", "Dann stand sie."]),
        ("Er sagte „ja.“) Dann ging er.", ["Er sagte „ja.“)", "Dann ging er."]),
        # ... but not before a lower-case word, nor after an abbreviation inside the quote
        ("Er sagte „gut.“ und ging.", ["Er sagte „gut.“ und ging."]),
        ("Er sagte „z. B.“ dazu.", ["Er sagte „zum Beispiel“ dazu."]),
        # PR #333 review R1-3: the closing quote is taken off before the abbreviation and
        # initial checks, so "Dr." and "A." inside it end no sentence
        ("Er nannte „Dr.“ Müller dann.", ["Er nannte „Dr.“ Müller dann."]),
        ("Er sagte „A.“ Dann ging er.", ["Er sagte „A.“ Dann ging er."]),
        # R1-4: the single guillemets quote inside »…« and «…»; they close a sentence, and
        # open the next one
        ("Er sagte \u203aja.\u2039 Dann ging er.", ["Er sagte \u203aja.\u2039", "Dann ging er."]),
        ("Er sagte \u2039ja.\u203a Dann ging er.", ["Er sagte \u2039ja.\u203a", "Dann ging er."]),
        (
            "Er sagte »ja.« \u203aNein.\u2039 Dann ging er.",
            ["Er sagte »ja.«", "\u203aNein.\u2039", "Dann ging er."],
        ),
        (
            "Er sagte «ja.» \u2039Nein.\u203a Dann ging er.",
            ["Er sagte «ja.»", "\u2039Nein.\u203a", "Dann ging er."],
        ),
        ("Er sagte \u203az. B.\u2039 dazu.", ["Er sagte \u203azum Beispiel\u2039 dazu."]),
        # PR #333 review R2-1: an initial inside them ends no sentence, as in „A.“
        ("Er sagte \u203aA.\u2039 Dann ging er.", ["Er sagte \u203aA.\u2039 Dann ging er."]),
        ("Er sagte \u2039A.\u203a Dann ging er.", ["Er sagte \u2039A.\u203a Dann ging er."]),
        ("Er nannte \u203aDr.\u2039 Müller dann.", ["Er nannte \u203aDr.\u2039 Müller dann."]),
        # #342 (D-605): an abbreviation that ends the sentence inside a closing quote keeps
        # its full stop, as without the quote
        ("Er schrieb „usw.“ Dann ging er.", ["Er schrieb „und so weiter.“", "Dann ging er."]),
        ("Er schrieb »usw.« Dann ging er.", ["Er schrieb »und so weiter.«", "Dann ging er."]),
        ("Er schrieb „etc.“ Dann ging er.", ["Er schrieb „et zetera.“", "Dann ging er."]),
        (
            "Er schrieb \u203ausw.\u2039 Dann ging er.",
            ["Er schrieb \u203aund so weiter.\u2039", "Dann ging er."],
        ),
        ("Er schrieb «usw.» Dann ging er.", ["Er schrieb «und so weiter.»", "Dann ging er."]),
        ("Er schrieb „usw.“", ["Er schrieb „und so weiter.“"]),
        # ... but not before a lower-case word, and a title before a name ends nothing
        ("Er schrieb „usw.“ und ging.", ["Er schrieb „und so weiter“ und ging."]),
        ("Sie nannte ihn „Dr.“ Müller sagte es.", ["Sie nannte ihn „Dr.“ Müller sagte es."]),
    ],
)
def test_german_sentences_end_where_german_ends_them(text: str, sentences: list[str]) -> None:
    assert cut_read(text) == sentences


@pytest.mark.parametrize(
    "text",
    [
        # in English these quotes open a quote: no cut before them (#315, D5: German only)
        "He said “yes.“ Then he left.",
        "She asked \u2018when?\u2018 Then she left.",
        "He wrote «stop.» Then he left.",
        # ... nor the single guillemets (PR #333 review R1-4), after or before the full stop
        "He wrote \u203astop.\u2039 Then he left.",
        "He wrote \u2039stop.\u203a Then he left.",
        "He wrote stop. \u203aThen\u2039 he left.",
    ],
)
def test_english_ends_no_sentence_at_a_german_closing_quote(text: str) -> None:
    assert cut_read(text, "en") == [text]


def test_a_citation_after_a_read_english_abbreviation_keeps_the_sentence_end() -> None:
    assert cut_read("See e.g. (Smith, 2019). Then more.", "en") == [
        "See for example.",
        "Then more.",
    ]
    # "et al." stays as printed and the citation takes the full stop after it (M2 of the #66
    # review); the printed sentence ended after the citation, so the cutter ends it (D-719)
    assert cut_read("Smith et al. (2019). Then more.", "en") == ["Smith et al.", "Then more."]


def test_the_german_abbreviations_come_from_the_word_lists() -> None:
    german = ABBREVIATIONS["de"]
    assert {"abb.", "z.", "b.", "o.", "std.", "mio.", "tsd.", "kap."} <= german
    assert "usw." not in german  # it can end a sentence
    assert all(word.endswith(".") and word == word.lower() for word in german)


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
    for index in range(len(document.blocks)):
        # spans of one block are in order; a footnote read at its mark (#213) stands between
        # two utterances of another block, so blocks are no longer in order across the script
        mine = [u for u in utterances if u.span.block == index]
        for a, b in pairwise(mine):
            assert a.span.end <= b.span.start
        spoken = spoken_text([p for p in script if p.span.block == index and not p.pause])
        said = [u.text for u in mine if not u.pause]
        assert " ".join(said) == spoken  # exact, block by block


@pytest.mark.benchmark
def test_benchmark_cutting_the_largest_paper(benchmark) -> None:
    largest = max(PAPERS, key=lambda paper: paper.stat().st_size)
    document, script = paper_script(largest)
    benchmark(cut_utterances, document, script)


@pytest.mark.parametrize(
    ("text", "language", "parts"),
    [
        ("The first set is called A. Then set B follows.", "en", 2),
        ("The first set is called A. “Then set B follows.”", "en", 2),
        ("Most data came from the U.S. The rest came from Canada.", "en", 2),
        ("The data came from the U.S. Census Bureau in 2019.", "en", 1),
        ("See A. A. Milne for this.", "en", 1),
        # the English rule of #477 is English only: German keeps its initial rule
        ("Die erste Gruppe heißt A. Dann folgt B.", "de", 1),
    ],
)
def test_an_english_initial_ends_a_sentence_only_before_a_sentence_opener(
    text: str, language: str, parts: int
) -> None:
    # #477, D-744: "A." and "U.S." end a sentence before "Then" or "The", not before a name
    assert len(cut(text, language=language)) == parts


# ---- B6: a label word again, readings, and the cut's own rules (#479, #482, #533) ----------


@pytest.mark.parametrize(
    ("text", "sentences"),
    [
        # #479: a number between the same word twice is that word's number; its full stop
        # ends the sentence, as after a label word of the unit list ("Satz 2. Satz 3")
        (
            "Es gilt Abs. 2. Abs. 3 gilt hier auch.",
            ["Es gilt Absatz 2.", "Absatz 3 gilt hier auch."],
        ),
        ("Es gilt Absatz 2. Absatz 3 gilt.", ["Es gilt Absatz 2.", "Absatz 3 gilt."]),
        # ... also where the label opens the paragraph (the word before starts at 0)
        ("Abs. 2. Abs. 3 gilt.", ["Absatz 2.", "Absatz 3 gilt."]),
        ("Es gilt Art. 3. Art. 4 gilt auch.", ["Es gilt Artikel 3.", "Artikel 4 gilt auch."]),
        ("Es gilt Rn. 3. Rn. 4 gilt auch.", ["Es gilt Randnummer 3.", "Randnummer 4 gilt auch."]),
        ("Es gilt Satz 2. Satz 3 gilt nicht.", ["Es gilt Satz 2.", "Satz 3 gilt nicht."]),
        ("Es gilt Nr. 2. Nr. 3 gilt auch.", ["Es gilt Nummer 2.", "Nummer 3 gilt auch."]),
        # ... an ordinal the numbers step reads cuts nothing (its full stop is read with it),
        # and without a full stop nothing ends
        ("Im Abs. 2. Teil steht es.", ["Im Absatz zweiter Teil steht es."]),
        ("Es gilt Abs. 2 Satz 3 hier.", ["Es gilt Absatz 2 Satz 3 hier."]),
        # ... a dotted word left as printed counts with its full stop ("Az.", #406)
        ("Es gilt Az. 3. Az. 4 gilt auch.", ["Es gilt Az. 3.", "Az. 4 gilt auch."]),
        # ... another word after the full stop is no label again: as before
        ("Es gilt Absatz 2. Studien zeigen es.", ["Es gilt Absatz 2. Studien zeigen es."]),
        # ... and the word must stand alone before the number: glued to a bracket it is not
        # the same word, so the sentence stays whole, as before
        ("Es gilt (Absatz 2. Absatz 3) hier.", ["Es gilt (Absatz 2. Absatz 3) hier."]),
    ],
)
def test_a_number_between_the_same_word_twice_ends_the_sentence(
    text: str, sentences: list[str]
) -> None:
    assert cut_read(text) == sentences
    # the same on a second run over the script, where the readings are plain words
    assert cut_read(" ".join(sentences)) == sentences


def test_the_same_word_is_the_same_as_printed() -> None:
    """#479: the two words are compared exactly, as the numbers step compares them, so both
    steps agree on what is the same label; "absatz 2. Absatz" is no label again."""
    assert cut("Es gilt absatz 2. Absatz 3 gilt.", language="de") == [
        "Es gilt absatz 2. Absatz 3 gilt."
    ]
    assert cut("Es gilt Absatz 2. Absatz 3 gilt.", language="de") == [
        "Es gilt Absatz 2.",
        "Absatz 3 gilt.",
    ]


def _rebuilt_cuts(text: str, language: str) -> tuple[list[str], list[str]]:
    """The utterances of a first run's script and of a second run over it (D-577)."""
    document = make_document([(BlockKind.PARAGRAPH, text)], language)
    context = StepContext(language)
    first = run_steps(document, context, strict=True)
    second = run_steps(rebuilt_from_script(document, first.script()), context, strict=True)
    return (
        [u.text for u in cut_utterances(first.document, first.script())],
        [u.text for u in cut_utterances(second.document, second.script())],
    )


@pytest.mark.parametrize(
    ("language", "printed", "read"),
    [
        ("de", "u. a.", "unter anderem"),
        ("de", "3,5 %", "3 Komma 5 Prozent"),
        ("de", "z. B.", "zum Beispiel"),
        ("de", "am 3. Mai", "dritten Mai"),
        ("de", "5 km/h", "5 Kilometer pro Stunde"),
        ("en", "e.g.", "for example"),
        ("en", "x ≤ 5", "less than or equal to 5"),
        ("en", "10⁻³", "10 to the power of minus 3"),
        ("en", "2.5 m²", "2.5 square metres"),
        # the numbers, units and statistics steps' readings (#616 review F1)
        ("en", "95% CI", "confidence interval"),
        ("en", "5 N m", "5 newton metres"),
        ("en", "12/20", "12 out of 20"),
        ("de", "1/2 der", "ein halb der"),
        ("de", "ηp²", "partielles Eta-Quadrat"),
    ],
)
def test_a_long_sentence_is_cut_outside_a_reading_on_both_runs(
    language: str, printed: str, read: str
) -> None:
    """#482: a space between the words of a reading ranks below any other space, so a second
    run, where the reading is plain words, cuts where the first run did. The reading moves
    word by word across the even share of a sentence over the limit with no comma."""
    filler = "die Hörer hörten jede Stelle" if language == "de" else "the people heard every word"
    words = filler.split() * 30
    for before in range(20, 50):
        text = " ".join([*words[:before], printed, *words[: 75 - before]]) + "."
        first, second = _rebuilt_cuts(text, language)
        assert len(first) == 2, text
        assert first == second, f"{text}\n{first}\n{second}"
        assert read in first[0] or read in first[1], first  # the reading is not cut


_UA = "aaaa bbbb cccc unter anderem dddd eeee ffff"
_BRACKET_UA = "aaaa bbbb (cccc dddd) unter anderem eeee ffff gggg"
_SEMICOLON_UA = "(aaaa bbbb cccc dddd; eeee)unter anderem(ffff)"


@pytest.mark.parametrize(
    ("text", "max_chars", "plain", "read"),
    [
        # the even share falls on "unter | anderem": the cut goes before "unter" or after
        # "anderem", whichever is nearer
        (_UA, 24, "aaaa bbbb cccc unter ", "aaaa bbbb cccc "),
        (_UA, 42, "aaaa bbbb cccc unter ", "aaaa bbbb cccc unter anderem "),
        # with nothing else to take, a space inside the reading is still a place
        ("unter anderem", 9, "unter ", "unter "),
        # ... and it beats every place inside a bracket
        ("(aaaa bbbb)unter anderem(cccc dddd)", 30, "(aaaa bbbb)unter ", "(aaaa bbbb)unter "),
        # ... even a semicolon inside one, nearer the even share
        (_SEMICOLON_UA, 36, _SEMICOLON_UA[:33], _SEMICOLON_UA[:33]),
        (_BRACKET_UA, 28, "aaaa bbbb (cccc dddd) unter ", "aaaa bbbb (cccc dddd) "),
    ],
)  # fmt: skip
def test_a_space_inside_a_reading_ranks_after_every_other_space(
    text: str, max_chars: int, plain: str, read: str
) -> None:
    counts = _counts(text)
    for readings, part in ((None, plain), (_readings("de"), read)):
        assert (
            text[: _cut_point(text, counts, max_chars, None, frozenset(), _PAIRS_DE, readings)]
            == part
        )


@pytest.mark.parametrize(
    ("language", "text", "joined"),
    [
        ("de", "aaa 3 Komma 5 Prozent bbb", ["aaa | 3", "3 | Komma", "Komma | 5", "5 | Prozent"]),
        ("de", "aaa unter anderem bbb", ["unter | anderem"]),
        ("de", "aaa Kilometer pro Stunde bbb", ["Kilometer | pro", "pro | Stunde"]),
        ("de", "aaa kleiner oder gleich bbb", ["kleiner | oder", "oder | gleich"]),
        ("de", "aaa zehn hoch minus drei", ["hoch | minus"]),
        ("de", "am dritten Mai bbb", ["dritten | Mai"]),
        ("en", "aaa for example bbb", ["for | example"]),
        ("en", "aaa square metres bbb", ["square | metres"]),
        ("en", "aaa degrees Celsius bbb", ["degrees | Celsius"]),
        ("de", "aaa Grad Celsius bbb", ["Grad | Celsius"]),
        ("en", "aaa R squared bbb", ["R | squared"]),
        ("en", "a less than or equal to b", ["less | than", "than | or", "or | equal",
                                             "equal | to"]),
        ("en", "a to the power of minus b", ["to | the", "the | power", "power | of",
                                             "of | minus"]),
        ("en", "on the third May bbb", ["third | May"]),
        # ... "may" the verb is no month, and plain words join nothing
        ("en", "it may rain here", []),
        ("de", "die Hörer hörten es", []),
        # German writes "Quadrat" into the unit ("Quadratmeter"): alone it joins nothing
        ("de", "das Quadrat hier", []),
        # a reading inside a longer word is none ("in Verbindung mit", "that is")
        ("de", "aaa darin Verbindung mit bbb", []),
        ("en", "aaa that isotope bbb", []),
        # the reading of "u. a." before a year, the singular unit name, both powers' words
        ("de", "aaa und andere bbb", ["und | andere"]),
        ("en", "aaa degree Celsius bbb", ["degree | Celsius"]),
        ("en", "aaa x cubed bbb", ["x | cubed"]),
        ("en", "aaa x squaredness bbb", []),  # a power's word is a whole word
        ("en", "aaa cubic metres bbb", ["cubic | metres"]),
        ("en", "a 10 to the power of 6", ["a | 10", "10 | to", "to | the", "the | power",
                                          "power | of", "of | 6"]),
        # a joining word joins on both sides, however many follow (#616 review F1)
        ("en", "aaa joules per kilogram per kelvin", ["joules | per", "per | kilogram",
                                                     "kilogram | per", "per | kelvin"]),
        ("en", "aaa metres per second squared", ["metres | per", "per | second",
                                                 "second | squared"]),
        ("en", "aaa watts per square metre", ["watts | per", "per | square", "square | metre"]),
        # units side by side, fractions, statistics symbols
        ("en", "aaa newton metres bbb", ["newton | metres"]),
        ("en", "aaa electronvolt angstroms bbb", ["electronvolt | angstroms"]),
        ("en", "aaa newton metre seconds bbb", ["newton | metre", "metre | seconds"]),
        ("en", "aaa 12 out of 20 bbb", ["aaa | 12", "12 | out", "out | of", "of | 20",
                                        "20 | bbb"]),
        ("en", "aaa out of reach", []),  # "out of" between numbers only
        # a unit read only after "per" joins no unit name ("Tag", "Jahr"; English also lists
        # "day" for "d", so "second | day" is joined)
        ("de", "jede Minute Jahr für Jahr", []),
        ("en", "on the second day", ["second | day"]),
        ("en", "ask the Mayor", []),  # a month is a whole word
        ("en", "aaa confidence intervals bbb", ["confidence | intervals"]),
        ("en", "aaa odds ratio bbb", ["odds | ratio"]),
        ("en", "aaa partial eta squared bbb", ["partial | eta", "eta | squared"]),
        ("de", "aaa ein Drittel bbb", ["ein | Drittel"]),
        ("de", "aaa partielles Eta-Quadrat bbb", ["partielles | Eta-Quadrat"]),
        ("de", "aaa R Quadrat bbb", ["R | Quadrat"]),
        ("de", "aaa Odds Ratio bbb", ["Odds | Ratio"]),
        # at the very start and the very end of the text
        ("de", "unter anderem bbb", ["unter | anderem"]),
        ("de", "5 Komma 3", ["5 | Komma", "Komma | 3"]),
        ("en", "aaa per s", ["aaa | per", "per | s"]),
    ],
)  # fmt: skip
def test_the_spaces_that_join_a_reading_are_found_from_the_text(
    language: str, text: str, joined: list[str]
) -> None:
    found = _joined(text, len(text), _readings(language))
    assert [f"{text[:i].split()[-1]} | {text[i:].split()[0]}" for i in sorted(found)] == joined


@pytest.mark.parametrize(
    ("text", "last", "joined"),
    [
        ("aaa unter anderem bbb", 9, []),  # "unter | anderem" is place 10
        ("aaa unter anderem bbb", 10, ["unter | anderem"]),
        ("aaa 3 Komma 5", 5, ["aaa | 3"]),  # "3 | Komma" is place 6
    ],
)
def test_no_joined_place_is_past_the_last_place(text: str, last: int, joined: list[str]) -> None:
    """`_joined` looks one reading past `last` to find a reading that starts before it, but
    returns no place after `last`."""
    found = _joined(text, last, _readings("de"))
    assert [f"{text[:i].split()[-1]} | {text[i:].split()[0]}" for i in sorted(found)] == joined


def test_a_comma_at_the_limit_before_a_clause_opener_is_a_clause_cut() -> None:
    """#533 (1): the window holds the word after the last place that fits, so a comma right
    before the limit ranks as a clause cut when "which" follows past the limit, over a plain
    comma nearer the even share."""
    text = "a" * 44 + ", " + "b" * 12 + ", which " + "c " * 30 + "d."
    parts = cut(text, max_chars=60)
    assert parts[0] == "a" * 44 + ", " + "b" * 12 + ","


def test_no_utterance_is_over_the_limit_when_the_text_holds_long_white_space_runs() -> None:
    """#533 (2): white space runs count as one space, so a window of many characters may hold
    exactly the limit; it is widened until it holds more, never taken as the whole rest."""
    text = "aaaa" + " " * 13 + "bbbbb" + " cccc dddd eeee ffff."
    parts = cut(text, max_chars=10)
    assert all(len(part) <= 10 for part in parts)
    assert " ".join(parts) == "aaaa bbbbb cccc dddd eeee ffff."


def test_the_even_share_counts_the_space_at_each_cut_once() -> None:
    """#533 (3): what is left of a sentence after a cut is its rest without the space at the
    cut, so the next part gets its even share of exactly that."""
    text = (
        "wwwwx, " + " ".join(["vvvv"] * 7)[:-4] + "vvvvy, " + " ".join(["uuuu"] * 12)[:-4]
        + "uuuuz, tttt tttt."
    )  # fmt: skip
    assert [len(part) for part in cut(text, max_chars=60)] == [43, 34, 37]


def test_on_a_tie_the_later_cut_wins() -> None:
    """#533 (4): two places as near the even share: the later one, so the first part is the
    longer one."""
    text = "wwwwx, vvvvy, " + " ".join(["uuuu"] * 9)[:-4] + "uuuuz, " + " ".join(["tttt"] * 6) + "."
    assert [len(part) for part in cut(text, max_chars=60)] == [48, 42]


def test_a_cut_inside_a_replacement_too_long_for_one_call_ends_at_its_end() -> None:
    """#533 (5): a replacement longer than the limit is cut where it must be; the part that
    then starts inside it ends at the replacement's end when that fits."""
    document = make_document([(BlockKind.PARAGRAPH, "x aaaa bbbb.")])
    edit = Edit(Span(0, 0, 1), EditKind.REPLACE, "r", "x", replacement="one two three four")
    utterances = cut_utterances(document, apply_edits(document, [edit]), max_chars=10)
    assert [u.text for u in utterances] == ["one two", "three four", "aaaa bbbb."]


def test_a_sentence_too_short_for_two_parts_of_40_is_cut_at_its_best_place() -> None:
    """#533 (6): no cut of a 61-character sentence leaves two parts of 40 characters, so the
    best kind of place wins (a comma), even though it leaves a part of 20; a part of 30 is
    no fair part."""
    text = "wwwwx, vvvvy, uuuuz, " + " ".join(["tttt"] * 8) + "."
    assert [len(part) for part in cut(text, max_chars=60)] == [20, 40]


def test_a_cut_that_leaves_two_parts_of_40_is_fair() -> None:
    """#533 (7): a space that leaves two parts of exactly 40 characters beats a comma that
    leaves a part of 20."""
    text = "wwwwx, vvvvy, uuuuz, " + " ".join(["tttt"] * 12) + "."
    assert [len(part) for part in cut(text, max_chars=60)] == [40, 40]
