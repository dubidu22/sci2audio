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
          "%", "(", ")", "[", "]", ",", ";", ".", "{", "}", "->", "⟨", "⟩", "∆", "∞"]  # fmt: skip
_NAMES = ["t", "F", "r", "R2", "η²", "ηp2", "χ2", "CI", "CIs", "OR", "p",
          "n", "N", "\U0001d45d", "M", "SD", "σ"]  # fmt: skip
_WORDS = ["Phase", "Type", "type", "War", "part", "III", "II", "I", "IV", "and", "the", "in",
          "participants", "is", "at", "am", "cases", "Henry", "VIII", "Fig.", "Exp.",
          "end."]  # fmt: skip
_GAPS = ["", " ", " ", "\n", "\u2009", "\u00a0", "\u00ad", "\u200b"]

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


# ---- German (#130) ---------------------------------------------------------------------------

_GERMAN_NUMBERS = ["1", "3", "5", "12", "20", "34", "1234", "1998", "2019", "1500", "2,5",
                   "0,05", "1.234", "12.345.678", "2.5", ".45", "1,0", "31", "03"]  # fmt: skip
_GERMAN_WORDS = ["der", "die", "das", "den", "am", "im", "vom", "zum", "in", "bis", "seit",
                 "um", "von", "zwischen", "und", "Jahr", "Mai", "März", "Auflage", "Platz",
                 "Jahrhundert", "Jh.", "Kapitel", "Abschnitt", "Abb.", "Phase", "Uhr", "KI",
                 "Teilnehmer", "gibt", "Die", "Ende", "WS", "er", "Version"]  # fmt: skip
_GERMAN_PIECE = (
    st.sampled_from(_GERMAN_NUMBERS)
    | st.sampled_from(_SIGNS)
    | st.sampled_from(_NAMES)
    | st.sampled_from(_GERMAN_WORDS)
)


@st.composite
def _german_expression(draw: st.DrawFn) -> str:
    """One expression a German rule is written for, with its parts drawn."""

    def one(*choices: str) -> str:
        return draw(st.sampled_from(choices))

    a, b = draw(st.sampled_from(_GERMAN_NUMBERS)), draw(st.sampled_from(_GERMAN_NUMBERS))
    shapes = [
        f"{a}{draw(_DASH)}{b}",
        f"{one('t', 'F', 'r', 'χ²')}({a}{one('', ', ' + b, '; ' + b, ', N = ' + b)})"
        f"{draw(_OPERATOR)}{b}",
        f"{one('R²', 'ηp²', 'OR', 'p', 'N')}{draw(_OPERATOR)}{one('.05', '0,05', b)}",
        f"95 {one('%-KI', '% KI', '%-CI')} [{a}; {b}]{one('', ' und [1,2; 3,4]')}",
        f"{one('am', 'der', 'in der', 'vom', '', 'Es waren')} {one('3', '12', '1', '20')}. "
        f"{one('Mai', 'März', 'Auflage', 'Platz', 'Jahrhundert', 'Jh.', 'Die', 'bis')}",
        f"{one('am ', '', 'bis ')}"
        f"{one('12.03.2019', '1.3.2020', '31.2.2019', '3.4.', '2019-03-12')}",
        f"{one('im Jahr', 'seit', 'um', 'Mai', 'zwischen', 'Ende')} "
        f"{one('1998', '1500', '1.998', '1990er', '2019')}"
        f"{one('', ' und 1995', ' gibt', ' Teilnehmer', '–2001', '/99')}",
        f"{a}:{b}{one('', ' Uhr')}",
        f"{one('um ', 'ab ', '')}{one('13:30', '9.05', '24:00')}{one('', ' Uhr')}",
        f"{a}/{b}",
        f"{one('Kapitel', 'Phase', 'Abb.', 'Typ', 'Ludwig')} "
        f"{one('I', 'IV', 'II und III', 'I–III', 'XIV.')}",
        f"{one('Abschnitt', 'Abb.', 'Version', 'Tab.')} "
        f"{one('2.5', '3.1.2', '2.5 und 2.6', '1.234')}",
        f"{one('10', 'x', 'R', '5 m')}{one('⁶', '⁻⁴', '²', '³', '^2', '^{-3}')}",
        f"{a} × 10{one('−4', '-2')}",
        f"{one('', 'r = ', 'p < ', 'M = ', 'N = ')}{one('', '−', '-')}{a}",
    ]
    return draw(st.sampled_from(shapes))


@st.composite
def german_notation_text(draw: st.DrawFn) -> str:
    """German expressions and loose pieces joined by gaps, or now and then any text."""
    if draw(st.integers(0, 9)) == 0:
        return draw(st.text(max_size=40))
    parts = []
    for _ in range(draw(st.integers(1, 8))):
        parts.append(draw(_german_expression() | _GERMAN_PIECE))
        parts.append(draw(st.sampled_from(_GAPS)))
    return "".join(parts)


@st.composite
def german_notation_documents(draw: st.DrawFn) -> Document:
    """One to four blocks of German notation text, mostly paragraphs."""
    kinds = st.sampled_from([BlockKind.PARAGRAPH] * 4 + [*BlockKind])
    first = draw(_german_expression()) + draw(st.sampled_from(_GAPS))
    first += draw(german_notation_text())
    blocks = [(BlockKind.PARAGRAPH, first)]
    blocks += [(draw(kinds), draw(german_notation_text())) for _ in range(draw(st.integers(0, 3)))]
    return make_document(blocks, draw(st.sampled_from(["de", "de-AT"])))
