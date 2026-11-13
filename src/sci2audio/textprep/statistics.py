# ruff: noqa: RUF001, RUF002
# (minus signs, dashes, primes and math letters are what these rules are about)
"""Statistics read as words (TP-11, #67): operators, degrees of freedom, R², CI, OR.

The voice reads ordinary numbers well (D-54), but not the notation of a results section:
"<" and ">" are silent, the 34 of "t(34)" is dropped, "R2" is "R two" and "OR" is the word
"or". This step proposes one `replace` edit per piece of notation, whose reason quotes it as
printed; the numbers themselves stay digits for the voice (D-176).

- S1 (D-177): every comparison operator, ± and ∓ read as words ("p less than .05").
- S2 (D-179): a df parenthesis after a test statistic read "of" ("t of 34", "F of 2 and 57").
- S3: R², η², ηp², ω², ε² read "squared" and χ² "chi-square"; with a plain 2, as PDFs give
  it, only before an operator or a df parenthesis.
- S4 (D-180): "CI" read "confidence interval" after a percentage or before a bracket, "="
  or ":"; a bracketed pair of numbers after it read "1.2 to 3.4".
- S5 (D-181): "OR" before an operator read "odds ratio"; other statistic letters are left
  to the voice, which spells them.
"""

from __future__ import annotations

import re

from sci2audio.core import Document, Edit
from sci2audio.textprep.notation import SKIPPED_KINDS, Candidate, fold, padded, pick, to_edits
from sci2audio.textprep.steps import Category, Stage, StepContext, TextStep

OPERATORS = {
    "=": "equals",
    "<": "less than",
    ">": "greater than",
    "≤": "less than or equal to",
    "⩽": "less than or equal to",
    "≦": "less than or equal to",
    "≥": "greater than or equal to",
    "⩾": "greater than or equal to",
    "≧": "greater than or equal to",
    "≠": "not equal to",
    "\u0338=": "not equal to",  # how PDFs give ≠: a combining long solidus, then "="
    "=\u0338": "not equal to",
    "±": "plus or minus",
    "∓": "minus or plus",
    "≪": "much less than",
    "≫": "much greater than",
}
_OPERATOR = re.compile("|".join(sorted(map(re.escape, OPERATORS), key=len, reverse=True)))
# characters that make an ASCII "<", ">" or "=" part of an arrow or a doubled sign
_ARROW = frozenset("<>=-−!:~|")
# a sign this step reads counts as a word next to another sign, since after the first run it
# is one ("x = ≤ 3" reads both, so a second run on the script finds nothing more)
_SIGNS = "".join(sorted({key[0] for key in OPERATORS} | {"\u0338"}))
_OPERAND = re.compile(r"[\w(\[{|√∞+\-−" + re.escape(_SIGNS) + r"]|\.\d")
_LEFT_OF_EQUALS = re.compile(r"[\w)\]}%'′|" + re.escape(_SIGNS) + "]")
_SPACE = re.compile(r"\s*")
_TAG = re.compile(r"</?[A-Za-z][\w-]*(?:\s[^<>]*)?>")
_NUMBER = r"\d+(?:\.\d+)?"
_SIGNED = r"[−-]?(?:\d+(?:,\d{3})*(?:\.\d+)?|\.\d+)"

# an operator that S1 reads, as a lookahead: what makes a plain "R2" or "OR" a statistic
_OPERATOR_AHEAD = r"\s*(?:\u0338=|=\u0338|[=<>≤⩽≦≥⩾≧≠≪≫])"
_THEN_OPERATOR = f"(?={_OPERATOR_AHEAD})"

# S2: a test statistic, its df in a parenthesis (two numbers at most, or a chi-square's
# "1, N = 100"), then an operator
_DF = re.compile(
    r"(?<![\w′'])(?:[tFrHUWzG]|χ[2²]?|X2)"
    r"(?P<paren>\(\s*(?P<a>" + _NUMBER + r")\s*"
    r"(?:,\s*(?:(?P<n>[Nn]\s*=\s*\d[\d,]*)|(?P<b>" + _NUMBER + r")))?\s*\))" + _THEN_OPERATOR
)

# S3: squared statistics; the letter may carry a "p" for partial (ηp², η²p)
_SQUARED_NAMES = {
    "R": "R squared",
    "r": "r squared",
    "η": "eta squared",
    "ω": "omega squared",
    "ε": "epsilon squared",
    "χ": "chi-square",
}
_SQUARED = re.compile(
    r"(?<![\w′'])(?P<name>[Rrηωεχ])(?P<p1>p)?(?:(?P<sup>²)|(?P<two>2))(?P<p2>p)?(?![\w²])"
)
_THEN_OPERATOR_OR_DF = re.compile(f"(?:{_OPERATOR_AHEAD}|\\s*\\()")

# S4: confidence intervals
_CI = re.compile(r"(?<![\w′'])CI(?P<plural>s)?(?![\w′'])")
# a closing bracket may stand between: the interval rule removes it ("[1, 3]% CI")
_AFTER_PERCENT = re.compile(r"\d[\])]?\s?%\s*\Z")
_BEFORE_CI_THING = re.compile(r"\s*[\[(=:]")
_INTERVAL = re.compile(
    r"\s*(?:[=:]\s*)?(?P<open>[\[(]\s*)(?P<a>" + _SIGNED + r")(?P<sep>\s*[,;]\s*)"
    r"(?P<b>" + _SIGNED + r")(?P<close>\s*[\])])"
)

# S5: odds ratio
_ODDS_RATIO = re.compile(r"(?<![\w′'])OR(?![\w′'])" + _THEN_OPERATOR)


class StatisticsStep(TextStep):
    """Read statistical notation as words; one edit per piece of notation."""

    id = "statistics"
    languages = ("en",)
    category = Category.NUMBERS_AND_UNITS
    stage = Stage.INLINE

    def find(self, document: Document, context: StepContext) -> list[Edit]:
        edits = []
        for index, block in enumerate(document.blocks):
            if block.kind in SKIPPED_KINDS or not block.text:
                continue
            edits += to_edits(index, find_statistics(block.text), self.id)
        return edits


def find_statistics(text: str) -> list[Candidate]:
    """The statistics edits for one block's text, without overlap, in text order."""
    plain = fold(text)
    return pick(
        [
            *_degrees_of_freedom(text, plain),
            *_squared(text, plain),
            *_confidence_intervals(text, plain),
            *_odds_ratios(text, plain),
            *_operators(text, plain),
        ]
    )


def _degrees_of_freedom(text: str, plain: str) -> list[Candidate]:
    found = []
    for match in _DF.finditer(plain):
        start, end = match.span("paren")
        if match["n"]:
            n = re.sub(r"\s*=\s*", " equals ", match["n"])
            words = f" of {match['a']}, {n}"
        elif match["b"]:
            words = f" of {match['a']} and {match['b']}"
        else:
            words = f" of {match['a']}"
        printed = text[start:end]
        found.append(
            Candidate(
                start,
                end,
                words,
                f'degrees of freedom "{printed}" read as "{words.strip()}"',
            )
        )
    return found


def _squared(text: str, plain: str) -> list[Candidate]:
    found = []
    for match in _SQUARED.finditer(plain):
        if match["two"] and not _THEN_OPERATOR_OR_DF.match(plain, match.end()):
            continue
        partial = bool(match["p1"] or match["p2"])
        if partial and match["name"] != "η":
            continue
        words = ("partial " if partial else "") + _SQUARED_NAMES[match["name"]]
        start, end = match.span()
        found.append(Candidate(start, end, words, f'"{text[start:end]}" read as "{words}"'))
    return found


def _confidence_intervals(text: str, plain: str) -> list[Candidate]:
    found = []
    for match in _CI.finditer(plain):
        start, end = match.span()
        after_percent = bool(_AFTER_PERCENT.search(plain, 0, start))
        if not after_percent and not _BEFORE_CI_THING.match(plain, end):
            continue
        words = "confidence intervals" if match["plural"] else "confidence interval"
        found.append(Candidate(start, end, words, f'"{text[start:end]}" read as "{words}"'))
        interval = _INTERVAL.match(plain, end)
        if interval is None:
            continue
        printed = text[interval.start("open") : interval.end("close")]
        about = f'confidence interval "{printed}" read as "{interval["a"]} to {interval["b"]}"'
        found.append(Candidate(*interval.span("open"), "", f"{about}: bracket not read"))
        sep_start, sep_end = interval.span("sep")
        found.append(Candidate(sep_start, sep_end, " to ", f'{about}: "," read as "to"'))
        found.append(Candidate(*interval.span("close"), "", f"{about}: bracket not read"))
    return found


def _odds_ratios(text: str, plain: str) -> list[Candidate]:
    return [
        Candidate(m.start(), m.end(), "odds ratio", '"OR" read as "odds ratio"')
        for m in _ODDS_RATIO.finditer(plain)
    ]


def _operators(text: str, plain: str) -> list[Candidate]:
    found = []
    tags = [m.span() for m in _TAG.finditer(plain)]
    taken = 0  # where the last operator's span ended: two signs never share the space between
    read_end = -1  # where the last sign read as words ended: it is a word for the next sign
    for match in _OPERATOR.finditer(plain):
        op = match.group()
        start, end = match.span()
        if any(a <= start < b for a, b in tags):
            continue  # "<i>", "</sup>": markup left in the text, not a comparison
        before = plain[start - 1] if start and start != read_end else ""
        after = plain[end] if end < len(plain) else ""
        if op in "<>=" and (
            before in _ARROW or (after and after in "<>=") or _arrow_after(plain, end)
        ):
            continue
        left = plain[:start].rstrip()
        right_start = _SPACE.match(plain, end).end()  # type: ignore[union-attr]
        if not _OPERAND.match(plain, right_start):
            continue
        if op == "=" and not (left and _LEFT_OF_EQUALS.match(left[-1])):
            continue
        if op in "<>" and not (after.isspace() or after in _SIGNS or _starts_number(plain, end)):
            continue  # "a<b" or "<i>": not a comparison anyone reads aloud
        span_start, span_end = max(len(left), taken), right_start
        taken, read_end = span_end, end
        words = OPERATORS[op]
        found.append(
            Candidate(
                span_start,
                span_end,
                padded(text, span_start, span_end, words),
                f'"{text[start:end]}" read as "{words}"',
            )
        )
    return found


def _arrow_after(plain: str, end: int) -> bool:
    """True if a "-" or "−" right after the sign makes an arrow, not a negative number."""
    if end >= len(plain) or plain[end] not in "-−":
        return False
    return not _starts_number(plain, end + 1)


def _starts_number(plain: str, at: int) -> bool:
    return bool(re.match(r"[−+-]?\.?\d", plain[at:]))
