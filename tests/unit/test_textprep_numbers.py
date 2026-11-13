# ruff: noqa: RUF001
# (minus signs, dashes and Greek letters are what these rules are about)
"""Numbers the voice reads wrong (TP-09, TP-13, #67): unit cases and properties of `NumbersStep`."""

import re
import time
import unicodedata

import pytest
from hypothesis import given
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
        ("Fig. II and Exp. III", "Fig. 2 and Exp. 3"),  # short keywords (review of #132)
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
        "X −→ α and x−1",
        "arXiv:2401.17620 and v1.2.0",
        # times, chains, dates and fractions that have no reading right everywhere
        "at 10:30 and 9:05 am and 14:00 h",
        "12/03/2019 and 2019/2020 and 24/7 and 3/2",
        # one plain-space group could be two numbers; mixed separators are not one number
        "Table 2 000 and 12 345",
        "1 000\u2009000",
        # powers that are units (#68), statistics or footnote marks
        "5 m² and kg/m² and R² and 2019¹",
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


def test_english_only() -> None:
    assert STEP.handles("en-GB")
    assert not STEP.handles("de")


@pytest.mark.timeout(60)
def test_a_long_block_is_quick() -> None:
    """100,000 characters: every look back is bounded (review of PR #132)."""
    text = "In 1234 cases 3–5 (p < .05) at 2.50 and 1/2 of 10⁶. " * 2000  # about 100,000 chars
    document = make_document([(BlockKind.PARAGRAPH, text)])
    started = time.perf_counter()
    edits = STEP.find(document, EN)
    assert time.perf_counter() - started < 3
    assert len(edits) == 5 * 2000  # the p value is the statistics step's


@pytest.mark.timeout(60)
@pytest.mark.parametrize(
    "text",
    [
        "Journal 8:64–77, pp. 123–145. " * 3400,
        "1–" * 50_000,
        "Phase " + "I/" * 30_000,
        "2^" * 50_000,
        "10⁶ 2.50 " * 10_000,
        "a" + " " * 100_000 + "1234 participants",
    ],
    ids=["reference-lines", "dashes", "roman-run", "carets", "powers-and-zeros", "long-space"],
)
def test_pathological_blocks_take_linear_time(text: str) -> None:
    document = make_document([(BlockKind.PARAGRAPH, text)])
    started = time.perf_counter()
    STEP.find(document, EN)
    assert time.perf_counter() - started < 3


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
    (D-150), does not keep a rule from its number; else a second run would find it (review of
    PR #132)."""
    document = make_document([(BlockKind.PARAGRAPH, printed)])
    run = run_steps(document, EN, strict=True)
    assert spoken_text(run.script()) == said


# ---- properties ------------------------------------------------------------------------------


@given(notation_documents())
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
