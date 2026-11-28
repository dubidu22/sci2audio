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
  or ":"; a bracketed pair of numbers after it read "1.2 to 3.4", and so is each pair joined
  on by "and", "or" or a comma ("CIs [1, 3] and [2, 4]", D-450).
- S5 (D-181): "OR" before an operator read "odds ratio"; other statistic letters are left
  to the voice, which spells them.
- S6 (#796): the arrows of logic, which the voices do not read, read as words between two
  operands: "⇒" "implies", "⇐" "is implied by", "⇔" "if and only if"; so are their pieced
  forms ("=⇒", "⇐=", "⇐=⇒", #590) and the ASCII "=>" and "<=>". An arrow without an operand
  on its line before it, or without one after it (a list bullet, a figure label), is left as
  printed; code blocks are never read here.

The step's edits and its readings (`find_readings`), which the other steps learn of it through
the readings module (#1107), come from the same rules; so do the words it says for its signs
and names (`words`).
"""

from __future__ import annotations

import bisect
import re
from collections.abc import Iterator, Mapping
from functools import partial
from types import MappingProxyType

from sci2audio.core import Document, Edit
from sci2audio.textprep.characters import ACCENTS
from sci2audio.textprep.footnotes import unread_marks
from sci2audio.textprep.notation import (
    DOUBLE_ARROW,
    LEFT_ARROW_TAIL,
    Candidate,
    fold,
    in_ascii_run,
    padded,
    pick,
    through_unread,
    to_edits,
)
from sci2audio.textprep.placeholders import read_as_prose
from sci2audio.textprep.readings import Reading, Words, ending_at, readings_of
from sci2audio.textprep.statistics_de import ARROWS_DE, OPERATORS_DE, WORDS_DE, find_statistics_de
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
# characters that make an ASCII "<", ">" or "=" part of an arrow or a doubled sign; "⇐="
# is a long double arrow the numbers step reads as "⇐" (#590)
_ARROW = frozenset("<>=-−!:~|⇐")
# a sign this step reads counts as a word next to another sign, since after the first run it
# is one ("x = ≤ 3" reads both, so a second run on the script finds nothing more)
_SIGNS = "".join(sorted({key[0] for key in OPERATORS} | {"\u0338"}))
# maths symbols that stand for a quantity: increment, nabla, infinity, angle brackets
# ("∆ = 0.88", "W = ⟨A, ⊕⟩", "⟨x⟩ = 1"; #132)
_QUANTITY_SIGNS = "∆∇∞"
# signs the units step (#68) reads as words ("times", "approximately"), so they are words to
# this step on a second run too
_UNIT_SIGNS = "×≈~"
# an accent printed apart before its letter is that letter once the Unicode step joins them
_OPERAND = re.compile(
    r"[\w(\[{|√+\-−⟨" + _QUANTITY_SIGNS + _UNIT_SIGNS + re.escape(_SIGNS) + r"]|\.\d"
    r"|[" + "".join(ACCENTS) + r"][^\W\d_]"
)
_NEGATIONS = re.compile(r"(?:¬\s*)+")  # before an operand after an arrow: "⇒ ¬B", "⇒ ¬ ¬B"
_LEFT_OF_EQUALS = re.compile(
    r"[\w)\]}%'′|⟩" + _QUANTITY_SIGNS + _UNIT_SIGNS + re.escape(_SIGNS) + "]"
)

# S6 (#796): the double arrows of logic (`DOUBLE_ARROW`); an ASCII one after "<", ">" or "="
# ("==>", ">=>") is none (`in_ascii_run`)
ARROWS = {"⇒": "implies", "⇐": "is implied by", "⇔": "if and only if"}
# an arrow or an operator; the arrow first, so "=⇒" is one arrow and not "="
_SIGN = re.compile(f"(?P<arrow>{DOUBLE_ARROW})|{_OPERATOR.pattern}")
# what ends an operand before an arrow: not a sign this step reads, unless it was read (a sign
# left as printed would be read on a second run, where the arrow is a word after it)
_LEFT_OF_ARROW = re.compile(
    r"[\w)\]}%'′|⟩" + _QUANTITY_SIGNS + _UNIT_SIGNS + re.escape("".join(ACCENTS)) + "]"
)
_LINE_BREAKS = frozenset("\n\r\x0b\x0c\x1c\x1d\x1e\x85\u2028\u2029")
_SPACE = re.compile(r"\s*")
_NUMBER_START = re.compile(r"[−+-]?\.?\d")
# a minus sign the numbers step reads "minus" with a space or line break before its number
# (its N1, `numbers._MINUS`); glued to the number it starts one (`_NUMBER_START`)
_MINUS_READ = re.compile(r"[\u2212\u2012](?: |\n)\.?\d")
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
_PARTIAL = "partial "  # before "eta squared" only
_CI_WORDS = ("confidence interval", "confidence intervals")
_ODDS_RATIO_WORDS = "odds ratio"
_SQUARED_WORDS = frozenset({*_SQUARED_NAMES.values(), _PARTIAL + _SQUARED_NAMES["η"]})
_WORDS = Words(
    signs=MappingProxyType(OPERATORS),
    arrows=MappingProxyType(ARROWS),
    names=_SQUARED_WORDS | {*_CI_WORDS, _ODDS_RATIO_WORDS},
    squared=_SQUARED_WORDS,
)
_SQUARED = re.compile(
    r"(?<![\w′'])(?P<name>[Rrηωεχ])(?P<p1>p)?(?:(?P<sup>²)|(?P<two>2))(?P<p2>p)?(?![\w²])"
)
_THEN_OPERATOR_OR_DF = re.compile(f"(?:{_OPERATOR_AHEAD}|\\s*\\()")

# S4: confidence intervals
_CI = re.compile(r"(?<![\w′'])CI(?P<plural>s)?(?![\w′'])")
# a closing bracket may stand between: the interval rule removes it ("[1, 3]% CI")
# a look back reads at most this many characters, so long blocks take linear time
_WINDOW = 64
_AFTER_PERCENT = re.compile(r"\d[\])]?\s?%\s*\Z")
_BEFORE_CI_THING = re.compile(r"\s*[\[(=:]")
_INTERVAL = re.compile(
    r"\s*(?:[=:]\s*)?(?P<open>[\[(]\s*)(?P<a>" + _SIGNED + r")(?P<sep>\s*[,;]\s*)"
    r"(?P<b>" + _SIGNED + r")(?P<close>\s*[\])])"
)
_JOIN = re.compile(r"\s*(?:,\s*)?(?:and|or)(?=[\s\[(])|\s*,")  # "[1, 3] and [2, 4]"
MAX_JOINED_INTERVALS = 8  # intervals read after one "CIs", so a long list costs linear time

# S5: odds ratio
_ODDS_RATIO = re.compile(r"(?<![\w′'])OR(?![\w′'])" + _THEN_OPERATOR)


class StatisticsStep(TextStep):
    """Read statistical notation as words; one edit per piece of notation."""

    id = "statistics"
    languages = ("en", "de")
    category = Category.NUMBERS_AND_UNITS
    stage = Stage.INLINE

    def find(self, document: Document, context: StepContext) -> list[Edit]:
        find = partial(_found, language=context.language)
        marks = unread_marks(document, context)  # read as a second run reads, without them
        edits = []
        for index, block in enumerate(document.blocks):
            if not read_as_prose(block, context) or not block.text:
                continue
            unread = marks.get(index, ())
            edits += to_edits(index, through_unread(block.text, find, unread), self.id)
        return edits


def _is_german(language: str) -> bool:
    return language.split("-", 1)[0].lower() == "de"


def find_readings(text: str, language: str) -> list[Reading]:
    """The step's readings in `text`, one per edit it makes there, in text order: the rules
    of this module, which the step's edits and every other step's questions both come from.
    A reading is the edit's span and words, without the reason the step's report gives."""
    return [
        Reading(c.start, c.end, c.replacement, StatisticsStep.category)
        for c in _found(text, language)
    ]


def words(language: str) -> Words:
    """The words the step says for its signs, its arrows and the notation it reads by name."""
    return WORDS_DE if _is_german(language) else _WORDS


def _found(text: str, language: str) -> list[Candidate]:
    return _german(text) if _is_german(language) else _english(text)


def _german(text: str) -> list[Candidate]:
    """The German statistics edits (statistics_de.py, #130) for one block's text."""
    plain = fold(text)
    return pick(
        [
            *find_statistics_de(text, plain),
            *_operators(text, plain, OPERATORS_DE, ARROWS_DE, word_stop=True, language="de"),
        ]
    )


def _english(text: str) -> list[Candidate]:
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
        words = (_PARTIAL if partial else "") + _SQUARED_NAMES[match["name"]]
        start, end = match.span()
        found.append(Candidate(start, end, words, f'"{text[start:end]}" read as "{words}"'))
    return found


def _confidence_intervals(text: str, plain: str) -> list[Candidate]:
    found = []
    for match, intervals in _ci_runs(plain):
        start, end = match.span()
        words = _CI_WORDS[1] if match["plural"] else _CI_WORDS[0]
        reading = padded(text, start, end, words)  # "95%CI[1, 3]": not "95%confidence"
        if plain[start - 1 : start] in ("<", ">"):
            # "<CI=": no space after the sign, which would have it read on a second run but
            # not on the first, where a letter follows it (#253)
            reading = reading.lstrip()
        found.append(Candidate(start, end, reading, f'"{text[start:end]}" read as "{words}"'))
        for interval in intervals:
            found += _interval(text, plain, interval)
    return found


def _ci_runs(plain: str) -> Iterator[tuple[re.Match[str], list[re.Match[str]]]]:
    """Each "CI" read as words, with the intervals read after it: the bracketed pair right
    after it, then each pair joined on by "and", "or" or a comma ("CIs [1, 3] and [2, 4]",
    #151, D-450), at most `MAX_JOINED_INTERVALS` in all."""
    for match in _CI.finditer(plain):
        start, end = match.span()
        after_percent = bool(_AFTER_PERCENT.search(plain, max(0, start - _WINDOW), start))
        if not after_percent and not _BEFORE_CI_THING.match(plain, end):
            continue
        intervals = []
        interval = _INTERVAL.match(plain, end)
        while interval is not None and len(intervals) < MAX_JOINED_INTERVALS:
            intervals.append(interval)
            joined = _JOIN.match(plain, interval.end())
            interval = _INTERVAL.match(plain, joined.end()) if joined else None
        yield match, intervals


def _interval(text: str, plain: str, interval: re.Match[str]) -> list[Candidate]:
    """The bracket of an interval left out and its comma read "to"."""
    printed = text[interval.start("open") : interval.end("close")]
    about = f'confidence interval "{printed}" read as "{interval["a"]} to {interval["b"]}"'
    sep_start, sep_end = interval.span("sep")
    close_start, close_end = interval.span("close")
    # a word glued after the bracket ("[1, 3]of") keeps a space from the number
    glued = close_end < len(plain) and plain[close_end].isalnum()
    return [
        Candidate(*interval.span("open"), "", f"{about}: bracket not read"),
        Candidate(sep_start, sep_end, " to ", f'{about}: "," read as "to"'),
        Candidate(close_start, close_end, " " if glued else "", f"{about}: bracket not read"),
    ]


def _odds_ratios(text: str, plain: str) -> list[Candidate]:
    return [
        Candidate(m.start(), m.end(), _ODDS_RATIO_WORDS, f'"OR" read as "{_ODDS_RATIO_WORDS}"')
        for m in _ODDS_RATIO.finditer(plain)
    ]


def _operators(
    text: str,
    plain: str,
    said: Mapping[str, str] = OPERATORS,
    arrows: Mapping[str, str] = ARROWS,
    *,
    word_stop: bool = False,
    language: str = "en",
) -> list[Candidate]:
    """The comparison signs and the arrows of logic (S6) read as words. With `word_stop`
    (German), "=" needs nothing on its left: after "Jh.=1" (#130), a footnote's "=1" (#212)
    or a removed link or citation (#101) a second run sees a word, a full stop or the block
    start there. In both languages an abbreviation the abbreviations step reads with its full
    stop ends an operand, as its words do on a second run ("e.g.=1", "Jh.⇒1", #924, #972)."""
    found = []
    tags = [m.span() for m in _TAG.finditer(plain)]  # in text order, never overlapping
    tag_starts = [a for a, _ in tags]
    taken = 0  # where the last operator's span ended: two signs never share the space between
    read_end = -1  # where the last sign read as words ended: it is a word for the next sign
    for match in _SIGN.finditer(plain):
        op = match.group()
        start, end = match.span()
        inside = bisect.bisect_right(tag_starts, start) - 1
        if inside >= 0 and start < tags[inside][1]:
            continue  # "<i>", "</sup>": markup left in the text, not a comparison
        before = plain[start - 1] if start and start != read_end else ""
        after = plain[end] if end < len(plain) else ""
        left = _left_end(plain, start)
        right_start = _SPACE.match(plain, end).end()  # type: ignore[union-attr]
        if match["arrow"]:
            if in_ascii_run(plain, start, op):
                continue  # "==>", ">=>": no arrow of logic
            # a negated operand too: "A ⇒ ¬B", but a negation sign with nothing to negate is
            # no operand ("A ⇒ ¬.", #853)
            negated = _NEGATIONS.match(plain, right_start)
            if not _OPERAND.match(plain, negated.end() if negated else right_start):
                continue
            # an abbreviation read as words ends an operand, as one prose word
            read_abbreviation = _LINE_BREAKS.isdisjoint(
                plain[left:start]
            ) and _read_abbreviation_before(plain, left, language)
            if not read_abbreviation and not _operand_before_arrow(
                plain, left, start, read_end, word_stop
            ):
                continue  # a list bullet, an arrow at a line start: no sentence word
            if left != read_end and _named_in_prose(
                plain, left, right_start, prose_before=read_abbreviation, language=language
            ):
                continue  # "where ⇒ marks", "The arrow ⇒ denotes": the symbol itself
            words = arrows[_one_arrow(op)]
            span_start, span_end = _span(left, start, end, right_start, taken, word_stop)
            taken, read_end = span_end, end
            found.append(
                Candidate(
                    span_start,
                    span_end,
                    padded(text, span_start, span_end, words),
                    f'"{text[start:end]}" read as "{words}"',
                )
            )
            continue
        # an English "=" glued before a minus sign the numbers step reads apart from its
        # number is no arrow: a second run sees "A=minus 3" and reads "equals" there, so the
        # first does too (#1010)
        minus_read = op == "=" and language == "en" and bool(_MINUS_READ.match(plain, end))
        if not (_OPERAND.match(plain, right_start) or minus_read):
            continue
        if op in "<>=" and (
            (before in _ARROW and not LEFT_ARROW_TAIL.search(plain, max(0, start - 16), start))
            or (after and after in "<>=")
            or (_arrow_after(plain, end) and not minus_read)
        ):
            continue
        # German (`word_stop`) reads "=" whatever comes before it: what comes before can be
        # a link, a citation or a sentence that another step removes, so a second run would
        # see "=" at the block start or after a full stop (#101); "Jh.=1" is read too (#130)
        # a sign read just before is a word ("A ⇒ = 3" reads "A implies equals 3")
        if (
            op == "="
            and not word_stop
            and left != read_end
            and not (left and _LEFT_OF_EQUALS.match(plain[left - 1]))
            and not _read_abbreviation_before(plain, left, language)
        ):
            continue
        if op in "<>" and not (
            after.isspace() or after in _SIGNS + _UNIT_SIGNS or _starts_number(plain, end)
        ):
            continue  # "a<b" or "<i>": not a comparison anyone reads aloud
        span_start, span_end = _span(left, start, end, right_start, taken, word_stop)
        taken, read_end = span_end, end
        words = said[op]
        found.append(
            Candidate(
                span_start,
                span_end,
                padded(text, span_start, span_end, words),
                f'"{text[start:end]}" read as "{words}"',
            )
        )
    return found


def _span(
    left: int, start: int, end: int, right_start: int, taken: int, word_stop: bool
) -> tuple[int, int]:
    """The span a sign's reading replaces: the sign and the white space around it. With
    `word_stop` (German) the white space next to the sign stays where it is: the step that
    removes a link, a citation or a sentence beside it may take that space along, and the
    sign's reading must not be set aside for it (#101)."""
    span_start, span_end = max(left, taken), right_start
    if word_stop:
        if left < start:
            span_start = max(start, taken)
        if right_start > end:
            span_end = end
    return span_start, span_end


def _one_arrow(glyphs: str) -> str:
    """The arrow a printed run stands for: "⇐=⇒" and "<=>" are "⇔", "=⇒" and "=>" "⇒"."""
    if glyphs in ("⇔", "<=>") or (glyphs[0] == "⇐" and glyphs[-1] == "⇒"):
        return "⇔"
    return "⇒" if glyphs[-1] in "⇒>" else "⇐"


def _operand_before_arrow(
    plain: str, left: int, start: int, read_end: int, word_stop: bool
) -> bool:
    """True if an operand ends before the arrow at `start`, on the same line: a word, a
    number, a closing bracket or a sign read as words. An arrow at a line start is a list
    bullet, even if the line before ends in a word; but not after a sign read in English,
    whose reading takes the line break along ("A ⇒\n=> B" is "A implies => B" then)."""
    if left and left == read_end:
        return word_stop is False or _LINE_BREAKS.isdisjoint(plain[left:start])
    if not left or not _LINE_BREAKS.isdisjoint(plain[left:start]):
        return False
    return bool(_LEFT_OF_ARROW.match(plain, left - 1))


def _read_abbreviation_before(plain: str, left: int, language: str) -> bool:
    """True if an abbreviation the abbreviations step reads with its full stop ends at `left`:
    it is an operand before an arrow or "=", since a second run sees its words there ("Jh.⇒1"
    is "Jahrhundert⇒1" then, #924; "e.g.=1" is "for example=1", #972)."""
    return (
        left > 0
        and plain[left - 1] == "."
        and ending_at(readings_of("abbreviations", plain, language), left) is not None
    )


def _named_in_prose(
    plain: str, left: int, right_start: int, *, prose_before: bool = False, language: str = "en"
) -> bool:
    """True if an ordinary prose word ends at `left` and another starts at `right_start`
    ("where ⇒ marks", "The arrow ⇒ denotes"): the arrow between them is named, not read as
    a connective. A symbol is no prose word ("A", "x", "α", "αXγ"). With `prose_before` the
    text before is an abbreviation read as words, one prose word whatever its last printed
    piece ("z. B. ⇒ Die" is named as "zum Beispiel ⇒ Die" is on a second run, #924). The
    "Uhr" of a German clock time with minutes is none: the numbers step reads "13:30 Uhr"
    as "13 Uhr 30", so a second run sees the minutes before the arrow (#970)."""
    after = right_start
    while after < len(plain) and after - right_start < _PROSE_REACH and _in_word(plain[after]):
        after += 1
    if not _prose_word(plain[right_start:after]):
        return False
    if prose_before:
        return True
    before = left
    while before > 0 and left - before < _PROSE_REACH and _in_word(plain[before - 1]):
        before -= 1
    if (
        language == "de"
        and plain[before:left] == "Uhr"
        and _CLOCK_WITH_MINUTES.search(plain, max(0, before - 16), before)
    ):
        return False
    return _prose_word(plain[before:left])


# a clock time whose reading ends in its minutes ("13 Uhr 30"); "13:00 Uhr" is "13 Uhr"
_CLOCK_WITH_MINUTES = re.compile(r"\d[:.](?!00)\d\d\s+\Z")


_PROSE_REACH = 40  # a word looked at is at most this long, so long blocks stay linear


def _in_word(char: str) -> bool:
    return char.isalnum() or char == "_" or char == "\u00ad" or char in ACCENTS


def _prose_word(word: str) -> bool:
    """True for an ordinary word: two or more letters (an accent printed apart is part of its
    letter, as the Unicode step joins them), a capital at most first, no Greek letter."""
    letters = [c for c in word if c != "\u00ad" and c not in ACCENTS]
    return (
        0 < len(word) < _PROSE_REACH
        and len(letters) >= 2
        and all(c.isalpha() and not _greek(c) for c in letters)
        and all(c.islower() for c in letters[1:])
    )


def _greek(char: str) -> bool:
    return "\u0370" <= char <= "\u03ff" or "\u1f00" <= char <= "\u1fff"


def _left_end(plain: str, start: int) -> int:
    """Where the text before `start` ends without its trailing white space (no copy, so the
    step stays linear on long blocks)."""
    while start and plain[start - 1].isspace():
        start -= 1
    return start


def _arrow_after(plain: str, end: int) -> bool:
    """True if a "-" or "−" right after the sign makes an arrow, not a negative number."""
    if end >= len(plain) or plain[end] not in "-−":
        return False
    return not _starts_number(plain, end + 1)


def _starts_number(plain: str, at: int) -> bool:
    return bool(_NUMBER_START.match(plain, at))
