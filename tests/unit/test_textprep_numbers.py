# ruff: noqa: RUF001
# (minus signs, dashes and Greek letters are what these rules are about)
"""Numbers the voice reads wrong (TP-09, TP-13, #67): unit cases and properties of `NumbersStep`."""

import re
import unicodedata
from collections.abc import Callable

import pytest
from hypothesis import example, given
from linear_time import assert_linear
from notation_texts import notation_documents

from sci2audio.core import Block, BlockKind, Document, EditKind, Span, apply_edits
from sci2audio.testing import check_text_step, make_document
from sci2audio.textprep import NumbersStep, StepContext, run_steps, spoken_text

EN = StepContext("en")
STEP = NumbersStep()


def read(text: str, kind: BlockKind = BlockKind.PARAGRAPH) -> str:
    document = make_document([(kind, text)])
    return spoken_text(apply_edits(document, STEP.find(document, EN)))


@pytest.mark.parametrize(
    ("printed", "said"),
    [
        # N1 minus sign
        ("r = −.32", "r = minus .32"),
        ("(−0.5, 1.1)", "(minus 0.5, 1.1)"),
        ("from − 3", "from minus 3"),
        ("N − 1", "N minus 1"),
        ("\u20123 dB", "minus 3 dB"),
        # #527: an arrow printed as two glyphs is one arrow, glued or spaced, never "minus"
        ("β ←− 0 and S −→ ε", "β ← 0 and S → ε"),
        ("X −→ α", "X → α"),
        ("X−→α∈R and (α−→β)∈τ", "X→α∈R and (α→β)∈τ"),
        ("a ←−→ b and x ←−5", "a ↔ b and x ←5"),
        # ... and a longer one, with more minus signs (#593)
        ("X −−→ α and Y ←−− β", "X → α and Y ← β"),
        ("X ←−−→ Y and −−→AB", "X ↔ Y and →AB"),
        ("b ←−−1", "b ←1"),
        # #590: a long double arrow printed as "=" and an arrow is one arrow, never "equals"
        ("so A =⇒ B", "so A ⇒ B"),
        ("A=⇒B and C⇐=D", "A⇒B and C⇐D"),
        ("P ⇐=⇒ Q and P⇐⇒Q", "P ⇔ Q and P⇔Q"),
        ("A ==⇒ B and C ⇐== D and ⇐=1", "A ⇒ B and C ⇐ D and ⇐1"),
        # ... and an "=" with no double arrow beside it is left as printed
        ("x = 3, a == b, y ≤ 2, z => w, ⇒ and ⇔", "x = 3, a == b, y ≤ 2, z => w, ⇒ and ⇔"),
        # ... and a minus sign glued to a closing bracket is left as printed (an inverse
        # whose raise was lost, or "f(x) minus 1": the voice says "minus" either way, #589)
        (
            "(I − P)−1 and f(x)−1 and [A]−1 and {B}−2",
            "(I − P)−1 and f(x)−1 and [A]−1 and {B}−2",
        ),
        ("(a) − 1 and x −1", "(a) minus 1 and x minus 1"),
        # N2 ranges
        ("aged 3–5 years", "aged 3 to 5 years"),
        ("3 – 5", "3 to 5"),
        ("1.2–3.4", "1.2 to 3.4"),
        ("2010–15", "2010 to 15"),
        ("−3–3", "minus 3 to 3"),
        ("3—5", "3 to 5"),
        ("pages 3615– 3620", "pages 3615 to 3620"),
        ("lines 4–\n5", "lines 4 to 5"),
        ("18-25 years", "18 to 25 years"),
        ("Rows 2-9", "Rows 2 to 9"),
        ("1-2% of", "1 to 2% of"),
        ("aged 18-\n25", "aged 18 to 25"),
        # N3 four-digit counts
        ("1234 participants", "1,234 participants"),
        ("n = 1234", "n = 1,234"),
        ("N ≥ 1905", "N ≥ 1,905"),
        ("1999 participants", "1,999 participants"),
        ("the 1234 cells", "the 1,234 cells"),
        ("2050 people", "2,050 people"),
        ("1905 children", "1,905 children"),
        # ... and before a sign or the word a second run sees for it, unless year-like (#844)
        ("1234 = A", "1,234 = A"),
        ("1234×", "1,234×"),
        ("1234x larger", "1,234x larger"),
        ("1234 times", "1,234 times"),
        ("2019 = A", "2019 = A"),
        ("2019 equals A", "2019 equals A"),
        ("1234 == A", "1234 == A"),
        # N4 trailing zeros
        ("2.50", "2 point 5 0"),
        ("1.00", "1 point 0 0"),
        ("CC BY 4.0", "CC BY 4 point 0"),
        ("1,234.50", "1,234 point 5 0"),
        # N5, N6 powers
        ("10⁶", "10 to the power of 6"),
        ("1.5 × 10⁻⁴", "1.5 × 10 to the power of minus 4"),
        ("2⁻³", "2 to the power of minus 3"),
        ("10^6 and 10^-4", "10 to the power of 6 and 10 to the power of minus 4"),
        ("2^{10} and 2^(−3)", "2 to the power of 10 and 2 to the power of minus 3"),
        ("3 × 10−4", "3 × 10 to the power of minus 4"),
        ("1.5×10−6", "1.5×10 to the power of minus 6"),
        ("x² and y³ and zⁿ", "x squared and y cubed and zⁿ"),
        ("σ² and x⁴", "σ squared and x to the power of 4"),
        ("x^2 and e^(−5)", "x squared and e to the power of minus 5"),
        # N7 ratios
        ("a 3:1 ratio", "a 3 to 1 ratio"),
        ("1:100 dilution", "1 to 100 dilution"),
        ("1:10 at room temperature", "1 to 10 at room temperature"),
        ("Journal 8:64", "Journal 8 to 64"),  # a volume and page without a range: a ratio
        # N8 fractions
        ("1/2 and 2/3", "1 half and 2 thirds"),
        ("3/4 of them", "3 quarters of them"),
        ("1/10 the size", "1 tenth the size"),
        ("17/20 passed", "17 out of 20 passed"),
        ("0/5", "0 out of 5"),
        ("5/5", "5 out of 5"),
        # N9 ISO dates
        ("on 2019-03-12", "on 12 March 2019"),
        ("2020-02-29", "29 February 2020"),
        # N10 grouped digits
        ("50\u2009000 cells", "50,000 cells"),
        ("50\u202f000 and 12\u00a0345", "50,000 and 12,345"),
        ("1 000 000 reads", "1,000,000 reads"),
        # R1 Roman numerals
        ("Fig. II and Exp. III", "Fig. 2 and Exp. 3"),  # short keywords (#132)
        ("Sec. IV, Figs. I/II", "Sec. 4, Figs. 1 and 2"),
        ("Fig.II shows", "Fig.2 shows"),
        ("World War II", "World War 2"),
        ("Phase III trials", "Phase 3 trials"),
        ("a Type I error", "a Type 1 error"),
        ("type II errors", "type 2 errors"),
        ("Phase I/II trial", "Phase 1 and 2 trial"),
        ("Stages I–III", "Stages 1 to 3"),
        ("Types I and II", "Types 1 and 2"),
        ("Chapter XII, Part IV", "Chapter 12, Part 4"),
        ("Studies XXXIX", "Studies 39"),
    ],
)
def test_numbers_read_as_said(printed: str, said: str) -> None:
    assert read(printed) == said


@pytest.mark.parametrize(
    "printed",
    [
        # read right by the voice (D-176)
        "1,234 and 10,000 and 12.5% and 0.001 and .050 and 3rd and the 1990s",
        "On 12 March 2019 and March 12, 2019",
        "In 2019 studies used the 2019 guidelines",
        "ACL 2023 is adopted from NAACL 2022",
        "we select 1000 examples and 1200 ms",
        "a GTX 1080 Ti and clinac 2300C/D",
        "In his seminal 1892 paper",
        "in 2019 was",
        # not ranges, minus signs or counts
        "the team won 3-1",
        "COVID-19 and 978-0-201 and 2019-13-45 and 2019-02-30",
        "X → α and x−1",  # a two-glyph arrow is one arrow now (#527): read as said, above
        "arXiv:2401.17620 and v1.2.0",
        # times, chains, dates and fractions that have no reading right everywhere
        "at 10:30 and 9:05 am and 14:00 h",
        "12/03/2019 and 2019/2020 and 24/7 and 3/2",
        # one plain-space group could be two numbers; mixed separators are not one number
        "Table 2 000 and 12 345",
        "1 000\u2009000",
        # powers that are units (#68), statistics or footnote marks
        "5 m² and kg/m² and R² and 2019¹",
        "5\nm² and .05\nm² and 5\tm²",  # a line break after a number is a space too (#445)
        # a run of superscript signs is no power the voice could say
        "10⁶⁻⁴ and x⁶⁻⁴ and 2⁻³⁺¹ and 2^3⁻⁴",
        "10⁶^0 and 33/310^2 and 3:10^2 and 2019-03-12^2",  # chained with a caret
        "aged 3-\n33:3 and 1-\n2/3",  # chains broken by a line end
        "3:1999-02-01 and 1/2019-03-12",  # a date joined to a number before it
        # Roman numerals elsewhere
        "Henry VIII and Pope John Paul II",
        "the part I think",
        "Type IIX",
        "the end. II and Vol. II",  # a full stop after a word that is no short keyword
        "",
    ],
)
def test_what_the_voice_reads_right_is_left_alone(printed: str) -> None:
    assert read(printed) == " ".join(printed.split())


def test_each_edit_quotes_the_printed_number() -> None:
    document = make_document([(BlockKind.PARAGRAPH, "In 1234 cases, −3–5 at 2.50 (Phase II).")])
    edits = STEP.find(document, EN)
    assert [(e.span, e.kind, e.replacement, e.reason) for e in edits] == [
        (Span(0, 3, 7), EditKind.REPLACE, "1,234", '"1234" read as a number, not a year'),
        (Span(0, 15, 16), EditKind.REPLACE, "minus ", '"−" before a number read as "minus"'),
        (Span(0, 17, 18), EditKind.REPLACE, " to ", 'range "3–5" read with "to"'),
        (Span(0, 23, 27), EditKind.REPLACE, "2 point 5 0",
         '"2.50" read with its trailing zeros as "2 point 5 0"'),
        (Span(0, 35, 37), EditKind.REPLACE, "2", 'Roman numeral "II" after "Phase" read as "2"'),
    ]  # fmt: skip
    assert {e.step for e in edits} == {"numbers"}


@pytest.mark.parametrize(
    ("printed", "said"),
    [
        ("3 × 10\u22124\u207b\u2074", "3 × 10\u22124\u207b\u2074"),  # glued minus sign
        ("3 × 10-4\u207b\u2074", "3 × 10-4\u207b\u2074"),
        ("5 \u2212 10\u2076", "5 minus 10 to the power of 6"),  # spaced: read as "minus"
    ],
)
def test_a_power_joined_to_a_number_reads_the_same_on_a_second_run(printed: str, said: str) -> None:
    """Run 1 must not read a base that run 2 would read differently (#132)."""
    assert read(printed) == said
    assert read(said) == said


def test_a_range_dash_at_a_line_end_takes_the_line_break() -> None:
    # so the line-end hyphen step (#65), which runs later, has nothing left to keep there
    document = make_document([(BlockKind.PARAGRAPH, "aged 18-\n25")])
    (edit,) = STEP.find(document, EN)
    assert document.text_of(edit.span) == "-\n"


@pytest.mark.parametrize(
    "kind", [BlockKind.FURNITURE, BlockKind.TABLE, BlockKind.FORMULA, BlockKind.FIGURE]
)
def test_blocks_other_steps_claim_whole_are_not_read(kind: BlockKind) -> None:
    document = make_document([Block(kind, "pages 3–5")])
    assert STEP.find(document, EN) == []


def test_english_and_german() -> None:
    """German has its own rules since #130 (test_textprep_numbers_statistics_de.py)."""
    assert STEP.handles("en-GB")
    assert STEP.handles("de")
    assert not STEP.handles("fr")


@pytest.mark.timeout(60)
def test_a_long_block_is_quick() -> None:
    """100,000 characters: every look back is bounded (#132)."""
    unit = "In 1234 cases 3–5 (p < .05) at 2.50 and 1/2 of 10⁶. "  # 2000 times: 100,000 chars
    edits = assert_linear(
        lambda text: STEP.find(make_document([(BlockKind.PARAGRAPH, text)]), EN),
        lambda n: unit * n,
        2000,
    )  # against a base run (#276)
    assert len(edits) == 5 * 2000  # the p value is the statistics step's


@pytest.mark.timeout(60)
@pytest.mark.parametrize(
    ("sized", "size"),
    [
        (lambda n: "Journal 8:64–77, pp. 123–145. " * n, 3400),
        (lambda n: "1–" * n, 50_000),
        (lambda n: "Phase " + "I/" * n, 30_000),
        (lambda n: "2^" * n, 50_000),
        (lambda n: "10⁶ 2.50 " * n, 10_000),
        (lambda n: "a" + " " * n + "1234 participants", 100_000),
    ],
    ids=["reference-lines", "dashes", "roman-run", "carets", "powers-and-zeros", "long-space"],
)
def test_pathological_blocks_take_linear_time(sized: Callable[[int], str], size: int) -> None:
    assert_linear(
        lambda text: STEP.find(make_document([(BlockKind.PARAGRAPH, text)]), EN), sized, size
    )


@pytest.mark.parametrize(
    ("printed", "said"),
    [
        ("3:\u00ad4 cut", "3 to 4 cut"),
        ("on 2019-\u00ad\n03-12 and 3\u200b\u20135", "on 12 March 2019 and 3 to 5"),
        ("p <\u200b.05", "p less than .05"),
        ("x <\u00af 3 and 3 \u00b4\u2013 5", "x less than 3 and 3 to 5"),  # stray accents
    ],
)
def test_characters_not_read_do_not_hide_a_number(printed: str, said: str) -> None:
    """A soft hyphen, zero-width space or stray accent, which the Unicode step removes last
    (D-150), does not keep a rule from its number; else a second run would find it
    (#132)."""
    document = make_document([(BlockKind.PARAGRAPH, printed)])
    run = run_steps(document, EN, strict=True)
    assert spoken_text(run.script()) == said


# ---- properties ------------------------------------------------------------------------------


@given(notation_documents())
@example(make_document([(BlockKind.PARAGRAPH, "3\u20133\u20131999-02-01")]))  # #957
@example(make_document([(BlockKind.PARAGRAPH, "3-3-1999-02-01")]))  # #957
@example(make_document([(BlockKind.PARAGRAPH, "3\u20143\u20141999-02-01")]))  # #957
@example(make_document([(BlockKind.PARAGRAPH, "1999-02-01:3 \u00d7 10\u22124")]))  # #1053
@example(make_document([(BlockKind.HEADING, "1999-02-01:3")]))  # #1053
def test_the_step_keeps_the_contract_on_any_document(document: Document) -> None:
    check_text_step(STEP, [document], allow_ask=False)


def digits(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKC", text) if c.isdigit())


@given(notation_documents())
def test_the_step_keeps_every_digit_except_where_it_says_why(document: Document) -> None:
    for edit in STEP.find(document, StepContext(document.language)):
        printed = document.text_of(edit.span)
        if edit.reason.startswith("fraction"):  # "/2" read "half": the denominator is a word
            assert digits(edit.replacement) == ""
            assert printed.startswith("/")
        elif edit.reason.startswith("Roman numeral"):  # "III" read "3": digits only added
            assert digits(printed) == ""
            assert re.fullmatch(r"\d+", edit.replacement)
        elif re.search(r'read with "(?:squared|cubed)"', edit.reason):  # "x²": "x squared"
            assert digits(printed) in ("2", "3")
            assert digits(edit.replacement) == ""
        elif edit.reason.startswith("date"):  # "2019-03-12": the same year and day, a month name
            year, _, day = printed.split("-")
            assert edit.replacement.startswith(f"{int(day)} ")
            assert edit.replacement.endswith(f" {year}")
        else:
            assert digits(printed) == digits(edit.replacement), edit


@given(notation_documents())
def test_all_built_in_steps_run_together_without_a_problem(document: Document) -> None:
    run = run_steps(document, StepContext(document.language), strict=True)
    assert not run.problems


@pytest.mark.parametrize(
    ("printed", "said"),
    [
        # a time is left as printed: hours up to 24, two-digit minutes up to 59, and a word
        # for time after it even when none comes before (mutation run, #80)
        ("it ended 10:30 pm.", "it ended 10:30 pm."),
        ("it ended 24:00 h.", "it ended 24:00 h."),
        ("it ended 10:59 h.", "it ended 10:59 h."),
        # anything else is a ratio
        ("it ended 25:00 h.", "it ended 25 to 00 h."),
        ("it ended 10:60 h.", "it ended 10 to 60 h."),
        ("it ended 10:5 h.", "it ended 10 to 5 h."),
    ],
)
def test_the_bounds_of_a_time(printed: str, said: str) -> None:
    assert read(printed) == said


def _read_all(text: str) -> str:
    """The whole chain of built-in steps, as an English job runs it."""
    document = make_document([(BlockKind.PARAGRAPH, text)])
    return spoken_text(run_steps(document, EN, strict=True).script())


@pytest.mark.parametrize(
    ("printed", "said"),
    [
        # #304 (D-577): a fraction after a minus sign read "minus" is read on the first run
        ("It is −1/2 here.", "It is minus 1 half here."),
        ("It is 5 −1/2 here.", "It is 5 minus 1 half here."),
        ("3–33–3 −3/3", "3 to 33 to 3 minus 3 out of 3"),
        ("x = −3/4 of it", "x equals minus 3 quarters of it"),
        ("It is −17/20 here.", "It is minus 17 out of 20 here."),
        # a minus glued after a number, or the ASCII hyphen, is not read: nor the fraction
        ("It is 5−1/2 here.", "It is 5−1/2 here."),
        ("It is -1/2 here.", "It is -1/2 here."),
        ("It is a−1/2 here.", "It is a−1/2 here."),
        ("It is (a)−1/2 here.", "It is (a)−1/2 here."),  # #527: glued to a bracket
        ("It is [a]−1/2 here.", "It is [a]−1/2 here."),
        ("It is {a}−1/2 here.", "It is {a}−1/2 here."),
        ("x ←−1/2 here", "x ←1 half here"),  # #527: one arrow, then the fraction
        # ... after "/" or ":" N1 reads "minus", so the fraction is read too (#332)
        ("It is /−1/2 here.", "It is /minus 1 half here."),
        ("ratio 1:−1/2", "ratio 1:minus 1 half"),
        ("12:−3/4", "12:minus 3 quarters"),
        ("x/−1/2", "x/minus 1 half"),
        # #304: "~" before a hyphen at a line end and a digit reads "about" on both runs
        ("0:~-\n0", "0: about -0"),
        ("about ~-\n5 dB", "about about -5 decibels"),
    ],
)
def test_a_second_run_reads_the_same_after_a_sign(printed: str, said: str) -> None:
    once = _read_all(printed)
    assert once == said
    assert _read_all(once) == once


@pytest.mark.parametrize(
    ("printed", "said"),
    [
        # #336 (D-605): a minus sign at a line end, its number on the next line
        ("It is −\n5 here.", "It is minus 5 here."),
        ("It is (−\n0.5, 1) here.", "It is (minus 0.5, 1) here."),
        ("It is x −\nb here.", "It is x − b here."),  # no number after it
        ("It is −\n\n5 here.", "It is − 5 here."),  # two line breaks: left as printed
        # #210: a caret power whose exponent groups its thousands reads it whole
        ("It is 10^250 000 000 here.", "It is 10 to the power of 250,000,000 here."),
        ("It is 10^250 000 here.", "It is 10 to the power of 250,000 here."),
        ("It is x^250 000 000 here.", "It is x to the power of 250,000,000 here."),
        ("It is 10^250 000 here.", "It is 10^250 000 here."),  # one plain-space group
        ("It is 10^250 000 000 5 here.", "It is 10^250 000 000 5 here."),  # a digit runs on
        # #210 (#361): a signed grouped exponent reads its sign too
        ("It is 10^-250 000 000 here.", "It is 10 to the power of minus 250,000,000 here."),
        ("It is 10^+250 000 000 here.", "It is 10 to the power of 250,000,000 here."),
        ("It is 10^\u2212250 000 000 here.", "It is 10 to the power of minus 250,000,000 here."),
        # #340: a power of ten whose minus exponent runs into a caret power stays as printed
        ("It is 3 × 10−410^2 here.", "It is 3 × 10−410^2 here."),
        ("It is 3 × 10−4^2 here.", "It is 3 × 10−4^2 here."),
        ("It is 3 × 10−4 here.", "It is 3 × 10 to the power of minus 4 here."),
    ],
)
def test_minus_signs_and_powers_that_read_the_same_on_a_second_run(printed: str, said: str) -> None:
    assert read(printed) == said


@pytest.mark.parametrize(
    "printed",
    [
        "It is −\n5 here.",
        "It is ~−\n5 here.",
        "It is 10^250 000 000 here.",
        "It is 10^-250 000 000 here.",
        "It is 10^+250 000 000 here.",
        "It is 10^\u2212250 000 000 here.",
        "It is 3 × 10−410^2 here.",
        "It is 2^10 000 000 and 2^20.",
    ],
)
def test_the_whole_chain_reads_these_the_same_on_a_second_run(printed: str) -> None:
    first = _read_all(printed)
    assert _read_all(first) == first


@pytest.mark.parametrize(
    ("printed", "said"),
    [
        # #335 (D-605): a unit power after a fraction read as words is the units step's, as
        # after the printed fraction on the first run
        ("It is 1 half s⁻¹ here.", "It is 1 half s⁻¹ here."),
        ("It is 3 quarters s⁻¹ here.", "It is 3 quarters s⁻¹ here."),
        ("It is 3 quarters m s⁻¹ here.", "It is 3 quarters m s⁻¹ here."),
        ("It is 2 thirds W m⁻² here.", "It is 2 thirds W m⁻² here."),
        # a letter power after a word that is no fraction is read as before
        ("The quarters s⁻¹ here.", "The quarters s to the power of minus 1 here."),
        ("It is 3 apples s⁻¹ here.", "It is 3 apples s to the power of minus 1 here."),
    ],
)
def test_a_unit_power_after_a_read_fraction_is_left_to_the_units_step(
    printed: str, said: str
) -> None:
    assert read(printed) == said


@pytest.mark.parametrize("printed", ["It is 1/2 s⁻¹ here.", "It is −3/4 m s⁻¹ here."])
def test_a_unit_power_after_a_fraction_reads_the_same_on_a_second_run(printed: str) -> None:
    first = _read_all(printed)
    assert _read_all(first) == first


def test_the_numbers_step_keeps_its_contract_on_the_issue_shapes() -> None:
    """#210, #340: the conformance check the nightly property runs, on the shapes it found."""
    for text in ("10^250 000 000", "3 × 10−410^2"):
        check_text_step(STEP, [make_document([(BlockKind.PARAGRAPH, text)])], allow_ask=False)


def test_a_fraction_word_after_a_longer_number_is_no_fraction_reading() -> None:
    """Pins the look-behind of `_UNIT_CHAIN_AFTER_FRACTION` (#359): the step
    reads no fraction with a decimal or longer numerator, so "2.5 quarters" or "1,003
    halves" is prose, and a letter power after it is read as before."""
    assert read("It is 2.5 quarters s⁻¹ here.") == (
        "It is 2.5 quarters s to the power of minus 1 here."
    )
    assert read("It is 1,003 halves s⁻¹ here.") == (
        "It is 1,003 halves s to the power of minus 1 here."
    )
