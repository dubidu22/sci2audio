"""Characters read as plain text (IN-04, FX-04, D-151, D-153, #65): unit and property tests."""

import unicodedata

import pytest
from hypothesis import given
from hypothesis import strategies as st

from sci2audio.core import BlockKind, EditKind, Span, apply_edits
from sci2audio.testing import check_text_step, make_document
from sci2audio.textprep import StepContext, UnicodeStep, spoken_text
from sci2audio.textprep.characters import INVISIBLE, SOFT_HYPHEN, _read_on

EN = StepContext("en")
STEP = UnicodeStep()


def edits_of(text: str) -> list[tuple[Span, EditKind, str, str]]:
    document = make_document([(BlockKind.PARAGRAPH, text)])
    return [(e.span, e.kind, e.replacement, e.reason) for e in STEP.find(document, EN)]


def read(text: str) -> str:
    document = make_document([(BlockKind.PARAGRAPH, text)])
    return spoken_text(apply_edits(document, STEP.find(document, EN)))


def test_a_ligature_is_replaced_by_its_letters() -> None:
    assert edits_of("Andro\ufb00 and \ufb01ve") == [
        (Span(0, 5, 6), EditKind.REPLACE, "ff", 'ligature "\ufb00" read as "ff"'),
        (Span(0, 11, 12), EditKind.REPLACE, "fi", 'ligature "\ufb01" read as "fi"'),
    ]


@pytest.mark.parametrize(
    ("ligature", "letters"),
    [("\ufb00", "ff"), ("\ufb01", "fi"), ("\ufb02", "fl"), ("\ufb03", "ffi"),
     ("\ufb04", "ffl"), ("\ufb05", "st"), ("\ufb06", "st")],
)  # fmt: skip
def test_every_latin_ligature(ligature: str, letters: str) -> None:
    assert read(f"x{ligature}y") == f"x{letters}y"


def test_neighbouring_math_letters_are_one_edit() -> None:
    # MATHEMATICAL BOLD CAPITAL A, BOLD SMALL X
    assert edits_of("Let \U0001d400\U0001d431 be") == [
        (
            Span(0, 4, 6),
            EditKind.REPLACE,
            "Ax",
            'mathematical characters "\U0001d400\U0001d431" read as "Ax"',
        )
    ]


@pytest.mark.parametrize(
    ("printed", "spoken"),
    [
        ("\U0001d465", "x"),  # MATHEMATICAL ITALIC SMALL X
        ("\U0001d6fc", "\u03b1"),  # MATHEMATICAL ITALIC SMALL ALPHA: Greek stays Greek
        ("\U0001d7cf", "1"),  # MATHEMATICAL BOLD DIGIT ONE
        ("\u2113", "l"),  # SCRIPT SMALL L
        ("\u210e", "h"),  # PLANCK CONSTANT, the italic h
        ("\u211d", "R"),  # DOUBLE-STRUCK CAPITAL R
    ],
)
def test_math_letters_fold_to_plain_letters(printed: str, spoken: str) -> None:
    assert read(f"on {printed} only") == f"on {spoken} only"


@pytest.mark.parametrize(
    "kept",
    [
        "\u210f",  # PLANCK CONSTANT OVER TWO PI: folds to a letter with a stroke, a symbol
        "\u2139",  # INFORMATION SOURCE
        "\u2116",  # NUMERO SIGN: folds to two letters
        "\u2135",  # ALEF SYMBOL: not a Latin letter
        "\u2202",  # PARTIAL DIFFERENTIAL: a symbol (#68)
        "\u03c0",  # a plain Greek letter
        "\u0131",  # dotless i on its own (Turkish)
        "\ufffd",  # a glyph the PDF could not map: the extraction report shows it
        "\u200d",  # ZERO WIDTH JOINER: emoji and some scripts need it
        "\u200c",  # ZERO WIDTH NON-JOINER
    ],
)
def test_symbols_and_needed_characters_are_left_alone(kept: str) -> None:
    assert edits_of(f"a {kept} b") == []


def test_soft_hyphens_are_removed_and_join_a_word_at_a_line_end() -> None:
    assert edits_of(f"extra{SOFT_HYPHEN}ordinary re{SOFT_HYPHEN}\nported") == [
        (Span(0, 5, 6), EditKind.REMOVE, "", "soft hyphen not read"),
        (Span(0, 17, 19), EditKind.REMOVE, "", "soft hyphen at a line end: the word is joined"),
    ]
    assert read(f"extra{SOFT_HYPHEN}ordinary re{SOFT_HYPHEN}\nported") == ("extraordinary reported")


def test_two_soft_hyphens_in_a_row_are_one_edit_and_a_line_end_ends_the_run() -> None:
    text = f"a{SOFT_HYPHEN}{SOFT_HYPHEN}b{SOFT_HYPHEN}\n{SOFT_HYPHEN}c"
    assert [edit[0] for edit in edits_of(text)] == [Span(0, 1, 3), Span(0, 4, 6), Span(0, 6, 7)]
    assert read(text) == "abc"


def test_invisible_characters_are_removed_with_their_names() -> None:
    assert edits_of("data\u200bset\u2060\ufeff ok") == [
        (
            Span(0, 4, 5),
            EditKind.REMOVE,
            "",
            "invisible character not read: U+200B ZERO WIDTH SPACE",
        ),
        (
            Span(0, 8, 10),
            EditKind.REMOVE,
            "",
            "invisible character not read: U+2060 WORD JOINER, U+FEFF ZERO WIDTH NO-BREAK SPACE",
        ),
    ]  # fmt: skip


@pytest.mark.parametrize("char", sorted(INVISIBLE))
def test_every_invisible_character_is_removed(char: str) -> None:
    assert read(f"a{char}b") == "ab"
    assert unicodedata.category(char) == "Cf"  # all format characters, none is white space
    assert not char.isspace()


@pytest.mark.parametrize(
    "space", ["\u00a0", "\u2002", "\u2009", "\u200a", "\u202f", "\u205f", "\u3000", "\t"]
)
def test_white_space_gets_no_edit_and_reads_as_one_plain_space(space: str) -> None:
    """D-151: every kind of space is already one plain space for the voice."""
    assert edits_of(f"Groups{space}A and B") == []
    assert read(f"Groups{space}A") == "Groups A"


@pytest.mark.parametrize(
    ("printed", "spoken"),
    [
        ("Garc\u00b4\u0131a", "Garc\u00eda"),  # Garc´ıa: TeX accent on a dotless i
        ("G\u00a8obel", "G\u00f6bel"),  # G¨obel
        ("\u02daAkerman", "\u00c5kerman"),  # ˚Akerman, at the start of a word
        ("Hovan\u02c7c\u00b4\u0131k", "Hovan\u010d\u00edk"),  # two accents, one edit
        ("Fran\u00b8cois", "Fran\u00e7ois"),  # Fran¸cois: cedilla
        ("Nguy\u02c6en", "Nguy\u00ean"),  # a circumflex inside a word
        ("Pi\u00b4echon", "Pi\u00e9chon"),
        ("Zelezn\u00b4y,", "Zelezn\u00fd,"),
    ],
)
def test_an_accent_set_apart_is_read_with_its_letter(printed: str, spoken: str) -> None:
    assert read(printed) == spoken


def test_the_accent_edit_names_what_was_printed() -> None:
    assert edits_of("Garc\u00b4\u0131a") == [
        (
            Span(0, 4, 6),
            EditKind.REPLACE,
            "\u00ed",
            'accent printed apart from its letter: "\u00b4\u0131" read as "\u00ed"',
        )
    ]


@pytest.mark.parametrize(
    "printed",
    [
        "the \u02c6j operator",  # a hat on a symbol in maths
        "\u02c6\u03c1 and L\u02c6",  # on a Greek letter, and after the letter
        "it\u00b4s the children\u00b4s and we\u00b4re",  # an acute used as an apostrophe
        "the mean \u00afx",  # x with macron has no single character
        "\u00b4\u00b4",  # an accent next to an accent
    ],
)
def test_accents_that_are_not_on_a_letter_are_left_alone(printed: str) -> None:
    assert edits_of(printed) == []


def test_a_stray_accent_is_not_read() -> None:
    assert edits_of("Marasovic, \u00b4 Swabha") == [
        (Span(0, 11, 12), EditKind.REMOVE, "", 'accent mark "\u00b4" without its letter not read')
    ]
    assert read("Noah A \u00b4\nSmith and \u02c7\nJ. Sinova") == "Noah A Smith and J. Sinova"


def test_an_apostrophe_accent_is_judged_as_the_text_will_be_read() -> None:
    """Found by Hypothesis: a soft hyphen after "it´s" hid that a letter follows."""
    assert edits_of("it\u00b4s\nnext") == []
    assert read(f"\ufb00\u00b4s{SOFT_HYPHEN}\ufb00") == "ff\u015bff"
    assert read("\ufb00\u00b4s\u00b4a") == "ff\u015b\u00e1"  # an accent does not end the word


def test_unread_characters_between_an_accent_and_its_letter_are_looked_through() -> None:
    assert read(f"Garc\u00b4{SOFT_HYPHEN}\n\u0131a") == "Garc\u00eda"
    assert read("x \u00b4\u200b y") == "x y"


def test_every_block_kind_is_cleaned() -> None:
    document = make_document(
        [(kind, "\ufb01") for kind in BlockKind if kind is not BlockKind.FIGURE]
    )
    assert len(STEP.find(document, EN)) == len(document.blocks)


def test_it_runs_for_every_language() -> None:
    assert STEP.handles("de")
    assert STEP.handles("en-GB")


# Property tests: text built mostly from the characters the step is about, so that most
# examples exercise it.
SPECIAL = [
    "\ufb00", "\ufb01", "\ufb03", "\U0001d400", "\U0001d465", "\U0001d6fc", "\u2113", "\u211d",
    "\u210f", SOFT_HYPHEN, f"{SOFT_HYPHEN}\n", "\u200b", "\u2060", "\ufeff", "\u200d",
    "\u00b4", "\u00a8", "\u02c6", "\u02c7", "\u0131", "\u00a0", "\u2009",
]  # fmt: skip
PLAIN = ["a", "e", "s", "t", "A", " ", "\n", ".", "-", "1", "\u03c1"]
texts = st.lists(st.sampled_from(SPECIAL) | st.sampled_from(PLAIN), max_size=30).map("".join)
NOT_LEFT = {SOFT_HYPHEN, *INVISIBLE, "\ufb00", "\ufb01", "\ufb03", "\U0001d400", "\U0001d465"}


@given(st.lists(texts, min_size=1, max_size=3))
def test_the_step_keeps_the_contract_on_any_text(blocks: list[str]) -> None:
    document = make_document([(BlockKind.PARAGRAPH, text) for text in blocks])
    check_text_step(STEP, [document], allow_ask=False)  # valid spans, same edits, idempotent


@given(texts)
def test_no_ligature_math_letter_soft_hyphen_or_invisible_character_is_left(text: str) -> None:
    spoken = read(text)
    assert not set(spoken) & NOT_LEFT
    assert "\U0001d6fc" not in spoken  # math alpha folded to the Greek letter


@given(texts)
def test_edits_only_remove_or_replace_and_never_touch_plain_characters(text: str) -> None:
    document = make_document([(BlockKind.PARAGRAPH, text)])
    for edit in STEP.find(document, EN):
        assert edit.kind in (EditKind.REMOVE, EditKind.REPLACE)
        changed = text[edit.span.start : edit.span.end]
        # every edit starts on a character it is about; plain text is only taken along as
        # the letter under an accent or the line break after a soft hyphen
        assert changed[0] not in PLAIN
        assert edit.reason.strip()


def test_a_maths_hat_inside_a_word_is_left_alone() -> None:
    """Review M1 of #98: in liu, "v\N{MODIFIER LETTER CIRCUMFLEX ACCENT}y" is the hat of v,
    not "y" with a circumflex."""
    liu = "1/2{L\N{MODIFIER LETTER CIRCUMFLEX ACCENT} z, v\N{MODIFIER LETTER CIRCUMFLEX ACCENT}y}"
    assert edits_of(liu) == []
    accented = "J\N{ACUTE ACCENT}er\N{MODIFIER LETTER CIRCUMFLEX ACCENT}ome"
    assert (
        read(accented)
        == "J\N{LATIN SMALL LETTER E WITH ACUTE}r\N{LATIN SMALL LETTER O WITH CIRCUMFLEX}me"
    )


def test_a_letterlike_symbol_that_looks_like_its_letter_is_named() -> None:
    """Review N3 of #98: 'read "K" as "K"' would look like an edit that does nothing."""
    assert edits_of("at 300 \N{KELVIN SIGN} only")[0][3] == (
        'mathematical characters U+212A KELVIN SIGN read as "K"'
    )
    assert edits_of("on \N{SCRIPT SMALL L}")[0][3] == (
        'mathematical characters U+2113 SCRIPT SMALL L read as "l"'
    )


def test_an_accent_after_a_ligature_reads_the_same_on_a_second_run() -> None:
    """#160: the acute before "ℓ" is no apostrophe of "'ll", because the "ˇℓ" after it
    reads "ľ"; so it is composed on the first run, as on the second."""
    first = read("\ufb00\u00b4\u2113\u02c7\u2113")
    assert first == "ff\u013a\u013e"
    assert read(first) == first


def test_an_apostrophe_accent_before_a_contraction_stays() -> None:
    assert read("it\u00b4ll go") == "it\u00b4ll go"
    assert read("it\u00b4s fine") == "it\u00b4s fine"


@pytest.mark.parametrize(
    ("text", "read_on"),
    [  # what the contraction check sees after an acute (#160, review F3 of PR #208)
        ("\u2113\u02c7\u2113", "l\u013e"),  # a math letter folded, an accent composed
        ("\u02c7\u0131", "\u01d0"),  # TeX's dotless i takes the accent as "i"
        ("\u00b4q", "q"),  # no single letter for "q" with an acute: the accent is dropped
        ("\u00b4\u00fc", "\u00fc"),  # only a plain letter takes an accent, as in the step
        ("\u02c7l\u00ads", "\u013es"),  # a soft hyphen after the composed letter is unread
    ],
)
def test_reading_on_composes_accents_as_the_step_does(text: str, read_on: str) -> None:
    assert _read_on(text, 0) == read_on
