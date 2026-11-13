# ruff: noqa: RUF001
# (minus signs, dashes and Greek letters are what these rules are about)
"""Statistics read as words (TP-11, #67): unit cases and properties of `StatisticsStep`."""

import re
import unicodedata

import pytest
from hypothesis import given
from notation_texts import notation_documents

from sci2audio.core import Block, BlockKind, Document, EditKind, Span, apply_edits
from sci2audio.testing import check_text_step, make_document
from sci2audio.textprep import StatisticsStep, StepContext, spoken_text

EN = StepContext("en")
STEP = StatisticsStep()


def read(text: str, kind: BlockKind = BlockKind.PARAGRAPH) -> str:
    document = make_document([(kind, text)])
    return spoken_text(apply_edits(document, STEP.find(document, EN)))


@pytest.mark.parametrize(
    ("printed", "said"),
    [
        # S1 operators, spaced or not, before a number, a letter or a bracket
        ("n = 35", "n equals 35"),
        ("p<.05", "p less than .05"),
        ("p < .001", "p less than .001"),
        ("x > 3", "x greater than 3"),
        ("n>30", "n greater than 30"),
        ("0 ≤ i ≤ N", "0 less than or equal to i less than or equal to N"),
        ("a ⩽ b, c ≦ d", "a less than or equal to b, c less than or equal to d"),
        ("aged ≥ 18", "aged greater than or equal to 18"),
        ("a ⩾ b ≧ c", "a greater than or equal to b greater than or equal to c"),
        ("x ≠ 2", "x not equal to 2"),
        ("Y, Z \u0338= S", "Y, Z not equal to S"),
        ("Y =\u0338 S", "Y not equal to S"),
        ("(± 12%)", "(plus or minus 12%)"),
        ("4.2 ± 1.1", "4.2 plus or minus 1.1"),
        ("±SD", "plus or minus SD"),
        ("a ∓ b", "a minus or plus b"),
        ("τ ≪ 1 and ωτ ≫ 1", "τ much less than 1 and ωτ much greater than 1"),
        ("for < 5% of", "for less than 5% of"),
        ("G = (N, Σ)", "G equals (N, Σ)"),
        ("r = −.32", "r equals −.32"),  # the minus sign is the numbers step's
        ("x≥-3", "x greater than or equal to -3"),
        ("w =\nw1", "w equals w1"),
        # S2 degrees of freedom
        ("t(34) = 2.45", "t of 34 equals 2.45"),
        ("F(2, 57) = 4.31", "F of 2 and 57 equals 4.31"),
        ("t(33.4) < 1", "t of 33.4 less than 1"),
        ("r(48) = .32", "r of 48 equals .32"),
        ("H(2) = 7.1, U(1)=3", "H of 2 equals 7.1, U of 1 equals 3"),
        # S3 squared statistics
        ("R2 = .45", "R squared equals .45"),
        ("R² = .45 and r² < .1", "R squared equals .45 and r squared less than .1"),
        ("η2 = .06, ηp2 = .1", "eta squared equals .06, partial eta squared equals .1"),
        (
            "η²p = .1 and ηp² = .2",
            "partial eta squared equals .1 and partial eta squared equals .2",
        ),
        ("ω² = .03, ε2 = .02", "omega squared equals .03, epsilon squared equals .02"),
        ("χ2(1) = 5.6", "chi-square of 1 equals 5.6"),
        ("χ²(2, N = 1,200) = 9.1", "chi-square of 2, N equals 1,200 equals 9.1"),
        # S4 confidence intervals
        ("95% CI [1.2, 3.4]", "95% confidence interval 1.2 to 3.4"),
        ("95 % CI (−0.5; 1.1)", "95 % confidence interval −0.5 to 1.1"),
        ("CI = [1.2, 3.4]", "confidence interval equals 1.2 to 3.4"),
        ("95% CIs overlap", "95% confidence intervals overlap"),
        ("CI: 1.2–3.4", "confidence interval: 1.2–3.4"),  # the range is the numbers step's
        # S5 odds ratio
        ("OR = 1.5", "odds ratio equals 1.5"),
        # not test statistics or squared names: only the operator is read
        ("Wait(3) = 2 and f(2) = 1", "Wait(3) equals 2 and f(2) equals 1"),
        ("Rp2 = 3", "Rp2 equals 3"),  # only eta has a partial form
        ("(OR < 2)", "(odds ratio less than 2)"),
        # math-italic letters are found too
        ("\U0001d45d < .05", "\U0001d45d less than .05"),
        ("\U0001d702\U0001d45d2 = .1", "partial eta squared equals .1"),
    ],
)
def test_statistics_read_as_words(printed: str, said: str) -> None:
    assert read(printed) == said


@pytest.mark.parametrize(
    "printed",
    [
        "X -> Y and a <- b and a => b and a == b and a <= b and a != b",
        "<i>x</i> and <sup>2</sup>",
        "a<b",  # no space, a letter after: not read as a comparison
        "= 5",  # nothing before "="
        "x =",  # nothing after
        "R2 values and the CI of each",  # no operator, no percentage, no bracket
        "the OR operator",
        "SD and M and HR and df",  # left for the voice to spell
        "η2 alone",
        "",
    ],
)
def test_what_is_not_statistics_is_left_alone(printed: str) -> None:
    assert read(printed) == spoken_text_of(printed)


def spoken_text_of(text: str) -> str:
    return " ".join(text.split())


def test_each_edit_quotes_the_printed_notation() -> None:
    document = make_document([(BlockKind.PARAGRAPH, "So t(34) = 2.45 (95% CI [1, 3])")])
    edits = STEP.find(document, EN)
    about = 'confidence interval "[1, 3]" read as "1 to 3"'
    assert [(e.span, e.kind, e.replacement, e.reason) for e in edits] == [
        (Span(0, 4, 8), EditKind.REPLACE, " of 34", 'degrees of freedom "(34)" read as "of 34"'),
        (Span(0, 8, 11), EditKind.REPLACE, " equals ", '"=" read as "equals"'),
        (Span(0, 21, 23), EditKind.REPLACE, "confidence interval",
         '"CI" read as "confidence interval"'),
        (Span(0, 24, 25), EditKind.REMOVE, "", f"{about}: bracket not read"),
        (Span(0, 26, 28), EditKind.REPLACE, " to ", f'{about}: "," read as "to"'),
        (Span(0, 29, 30), EditKind.REMOVE, "", f"{about}: bracket not read"),
    ]  # fmt: skip
    assert {e.step for e in edits} == {"statistics"}


@pytest.mark.parametrize(
    "kind", [BlockKind.FURNITURE, BlockKind.TABLE, BlockKind.FORMULA, BlockKind.FIGURE]
)
def test_blocks_other_steps_claim_whole_are_not_read(kind: BlockKind) -> None:
    document = make_document([Block(kind, "p < .05")])
    assert STEP.find(document, EN) == []


@pytest.mark.parametrize("kind", [BlockKind.HEADING, BlockKind.CAPTION, BlockKind.FOOTNOTE,
                                  BlockKind.LIST_ITEM])  # fmt: skip
def test_every_other_block_kind_is_read(kind: BlockKind) -> None:
    assert read("p < .05", kind) == "p less than .05"


def test_english_only() -> None:
    assert STEP.handles("en-GB")
    assert not STEP.handles("de")


# ---- properties ------------------------------------------------------------------------------


@given(notation_documents())
def test_the_step_keeps_the_contract_on_any_document(document: Document) -> None:
    check_text_step(STEP, [document], allow_ask=False)


def digits(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKC", text) if c.isdigit())


@given(notation_documents())
def test_the_step_keeps_every_number_and_drops_only_the_2_of_a_squared_name(
    document: Document,
) -> None:
    for edit in STEP.find(document, StepContext(document.language)):
        printed = document.text_of(edit.span)
        if re.search(r'read as "(?:partial )?\w+ squared"|read as "chi-square"', edit.reason):
            assert digits(printed) == "2"
            assert digits(edit.replacement) == ""
        else:
            assert digits(printed) == digits(edit.replacement), edit
