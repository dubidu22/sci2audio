# ruff: noqa: RUF001
# (minus signs, dashes, Greek letters and odd spaces are what these texts are made of)
"""Hypothesis strategies for the number and statistics steps (#67).

Texts are built from the pieces the rules look for (numbers, signs, dashes, statistic
names, Roman numerals, year words), so most examples give the rules work to do; a few are
arbitrary text, so nothing else makes them crash.
"""

from hypothesis import strategies as st

from sci2audio.core import BlockKind, Document
from sci2audio.testing import make_document

_NUMBERS = ["3", "5", "18", "25", "34", "1234", "1999", "2019", "1000", "2.50", "1.2", ".05",
            "1,234", "10", "0", "03", "12"]  # fmt: skip
_SIGNS = ["−", "-", "–", "—", "\u2012", "=", "<", ">", "≤", "≥", "±",
          "\u0338=", "≠", ":", "/", "^", "×", "x", "²", "⁻⁴", "⁶",
          "%", "(", ")", "[", "]", ",", ";", ".", "{", "}", "->"]  # fmt: skip
_NAMES = ["t", "F", "r", "R2", "η²", "ηp2", "χ2", "CI", "CIs", "OR", "p",
          "n", "N", "\U0001d45d", "M", "SD", "σ"]  # fmt: skip
_WORDS = ["Phase", "Type", "type", "War", "part", "III", "II", "I", "IV", "and", "the", "in",
          "participants", "is", "at", "am", "cases", "Henry", "VIII"]  # fmt: skip
_GAPS = ["", " ", " ", "\n", "\u2009", "\u00a0"]

_PIECE = (
    st.sampled_from(_NUMBERS)
    | st.sampled_from(_SIGNS)
    | st.sampled_from(_NAMES)
    | st.sampled_from(_WORDS)
)


_NUMBER = st.sampled_from(_NUMBERS)
_DASH = st.sampled_from(["\u2013", " \u2013 ", "-", "\u2014", "\u2012", "\u2013\n", "-\n"])
_OPERATOR = st.sampled_from(
    ["=", " = ", " < ", "<", " \u2265 ", " \u2264 ", " \u00b1 ", " \u0338= "]
)


@st.composite
def _expression(draw: st.DrawFn) -> str:
    """One expression a rule is written for, with its parts drawn."""

    def one(*choices: str) -> str:
        return draw(st.sampled_from(choices))

    a, b = draw(_NUMBER), draw(_NUMBER)
    shapes = [
        f"{a}{draw(_DASH)}{b}",
        f"{one('t', 'F', 'r', 'χ2')}({a}{one('', ', ' + b)}){draw(_OPERATOR)}{b}",
        f"{one('R2', 'η2', 'OR', 'p', 'n')}{draw(_OPERATOR)}{b}",
        f"95% CI [{a}, {b}]",
        f"{a}:{b}",
        f"{a}/{b}",
        f"{one('1999', '2019', '2023')}-{one('02', '03', '12')}-{one('01', '12', '29', '31')}",
        f"{one('Phase', 'Type', 'War', 'part', 'Henry')} "
        f"{one('I', 'II', 'III', 'IV', 'I/II', 'I–III', 'IIX')}",
        f"{one('1234', '1999', '2019', '1100')} {one('participants', 'is', 'cases', 'data')}",
        f"{one('10', '2', 'x', 'σ', 'R', '5 m')}{one('⁶', '⁻⁴', '²', '^2', '^{-3}', '^(10)')}",
        f"{a} × 10{one('−4', '-2', '6')}",
        f"{one('', '(', 'r = ')}\u2212{one('', ' ', '.')}{a}",
        f"{a}.{one('0', '50', '00', '5')}",
        f"{one('50', '1', '12')}{one(' ', '\u2009', '\u00a0')}000{one('', ' 000', '\u2009000')}",
    ]
    return draw(st.sampled_from(shapes))


@st.composite
def notation_text(draw: st.DrawFn) -> str:
    """Expressions and loose pieces joined by gaps, or now and then any text."""
    if draw(st.integers(0, 9)) == 0:
        return draw(st.text(max_size=40))
    parts = []
    for _ in range(draw(st.integers(1, 8))):
        parts.append(draw(_expression() | _PIECE))
        parts.append(draw(st.sampled_from(_GAPS)))
    return "".join(parts)


@st.composite
def notation_documents(draw: st.DrawFn) -> Document:
    """One to four blocks of notation text, mostly paragraphs, in English or British English."""
    kinds = st.sampled_from([BlockKind.PARAGRAPH] * 4 + [*BlockKind])
    # the first block always holds an expression, so every example gives a rule work
    first = draw(_expression()) + draw(st.sampled_from(_GAPS)) + draw(notation_text())
    blocks = [(BlockKind.PARAGRAPH, first)]
    blocks += [(draw(kinds), draw(notation_text())) for _ in range(draw(st.integers(0, 3)))]
    return make_document(blocks, draw(st.sampled_from(["en", "en-GB"])))
