"""Abbreviations read in full (TP-08, D-227 to D-235).

The voice reads "Dr.", "vs.", "No. 5", "etc." and "et al." right, and spells or clips the
rest ("e.g." as "E G", "Fig." as "fig", "Approx." as "approx"). This step proposes one
`replace` edit per abbreviation in `data/<language>/abbreviations.toml`, where its entry
says it is meant:

- "anything": anywhere, as a word of its own ("e.g.", "approx.");
- "number": before a number ("ca. 1900");
- "label": before a label: a digit, "(" or "[", or a capital letter or Roman numeral standing
  alone ("Fig. 2a", "Eq. (8)", "Eq. [3]", "App. B", "Sec. III");
- "word": before a capitalised word or a label ("Suppl. Fig. 3").

The reading's first letter follows the printed one ("E.g." reads "For example", "fig. 2"
"figure 2", "FIG. 3" "Figure 3"); a form glued to what follows gets a space ("eq.(1)" reads
"equation (1)"). An entry marked `exact_case` is found only as printed and read as listed:
German "S. 12" is "Seite 12" and "s." is "siehe" (#113). An entry with `before_year` is
read so before a year, bracketed or not, after a name: "Müller u. a. (2019)" is "Müller und
andere", any other "u. a." "unter anderem". In a language other than English a capital after
an abbreviation is any upper-case letter ("Dr. Özdemir"). An abbreviation that can end a
sentence and stands at the end of the block or before a capital letter keeps its full stop as
printed, so the sentence still ends there (D-234). Furniture and placeholder blocks are claimed
whole by other steps and skipped.
"""

from __future__ import annotations

import re
from bisect import bisect_left
from collections.abc import Iterator
from functools import cache

from sci2audio.core import Block, BlockKind, Document, Edit, EditKind, Span
from sci2audio.textprep.footnotes import unread_marks
from sci2audio.textprep.links import find_links, link_removals
from sci2audio.textprep.notation import edits_through_unread
from sci2audio.textprep.steps import Category, Stage, StepContext, TextStep
from sci2audio.textprep.wordlists import Abbreviation, abbreviations

# what may follow an abbreviation read only before a label, a number or a word
_SPACE = r"[^\S\r]{0,2}"
_LABEL = re.compile(_SPACE + r"(?:\d|[(\[]\w|[A-Z](?![a-z]|\.[A-Za-z]))")
_NUMBER = re.compile(_SPACE + r"\d")
_WORD = re.compile(r"[^\S\r]{1,2}(?:[A-Z]|\d)")
# a date: a day and its full stop, then a month's number or German name ("v. 12.03.2015")
_DATE = re.compile(
    _SPACE + r"(?:[1-9]|[012]\d|3[01])\.\s?(?:(?:0?[1-9]|1[0-2])\.|(?:Januar|Februar|März"
    r"|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)\b)"
)
# a law's paragraph or article: "i. S. d. § 3", "i. S. d. Art. 4" (#264 review round 1)
_LAW = re.compile(_SPACE + r"(?:§|Art\.|Abs\.)")
_FOLLOWS = {"label": _LABEL, "number": _NUMBER, "word": _WORD, "date": _DATE, "law": _LAW}
# a sentence after the full stop: white space, maybe an opening quote or bracket, a capital
_NEXT_SENTENCE = re.compile(r"\s+[\"'(\[\u201c\u2018]?[A-Z]")
# German: a capital is any upper-case letter ("Dr. Özdemir", "usw. Über"; review of PR #228);
# English keeps [A-Z] as it was
_UPPER = "".join(c for c in map(chr, range(0x250)) if c.isupper())
_LOWER = "".join(c for c in map(chr, range(0x250)) if c.islower())
# and a number may start with its decimal point (".45"), which the numbers step reads "0 Komma
# 4 5" in the same run (#130)
_FOLLOWS_ANY_CAPITAL = {
    "label": re.compile(
        _SPACE + rf"(?:\.?\d|[(\[]\w|[{_UPPER}](?![{_LOWER}]|\.[{_UPPER}{_LOWER}]))"
    ),
    "number": re.compile(_SPACE + r"\.?\d"),
    "word": re.compile(rf"[^\S\r]{{1,2}}(?:[{_UPPER}]|\.?\d)"),
    "date": _DATE,
    "law": _LAW,
}
# ... maybe after a closing quote: "Er schrieb „usw.“ Dann" ends a sentence at the quote, as
# the cutter ends it there (#315), so the full stop stays (#342); double and single quotes
_CLOSING_QUOTES = ("\u201c", "\u00bb", "\u00ab", "\u203a", "\u2039", "\u2018")
_NEXT_SENTENCE_ANY_CAPITAL = re.compile(
    rf"[\u201c\u00bb\u00ab\u203a\u2039\u2018]?\s+[\"'(\[\u201c\u2018\u201e\u00bb\u203a]?[{_UPPER}]"
)
# the word right before an abbreviation: "before_year" is read only after a name
_NAME_BEFORE = re.compile(r"([^\W\d_])[^\W\d_]*[.,]?\s+\Z")
# a year after an abbreviation, maybe in brackets or after a comma: "u. a. (2019)", "u. a., 2019"
_YEAR_AFTER = re.compile(r"\s*(?:\(\s*|,\s*)?(?:1[5-9]|20)\d\d(?!\d)")


class AbbreviationStep(TextStep):
    """Read the abbreviations of the language's list in full."""

    id = "abbreviations"
    languages = ("en", "de")
    category = Category.ABBREVIATIONS
    stage = Stage.INLINE

    def find(self, document: Document, context: StepContext) -> list[Edit]:
        entries = abbreviations(context.language)
        if not entries:
            return []
        pattern, by_form = _compiled(entries)
        any_capital = context.language.split("-", 1)[0].lower() != "en"
        marks = unread_marks(document, context)  # read as a second run reads, without them
        edits = []
        for index, block in enumerate(document.blocks):
            if _skipped(block):
                continue
            edits += edits_through_unread(
                index,
                block.text,
                lambda read, index=index, block=block: self._edits(
                    index,
                    read,
                    pattern,
                    by_form,
                    any_capital,
                    _Removals(read, block.kind, block.label, context.language),
                ),
                self.id,
                marks.get(index, ()),
            )
        return edits

    def _edits(
        self,
        index: int,
        text: str,
        pattern: re.Pattern[str],
        by_form: dict[str, tuple[Abbreviation, ...]],
        any_capital: bool = False,
        removals: _Removals | None = None,
    ) -> Iterator[Edit]:
        for match in pattern.finditer(text):
            printed = match.group()
            entry = next(
                (
                    entry
                    for entry in by_form[_key(printed)]
                    if _case_fits(printed, entry)
                    and (not entry.after_page or _after_page(text, match.start()))
                    and (not entry.after_sentence or _after_sentence(text, match.start()))
                    and (
                        _place_fits(text, match.end(), entry, any_capital)
                        or (
                            removals is not None
                            and (after := removals.past(match.end())) is not None
                            and _place_fits(text, after, entry, any_capital)
                        )
                    )
                ),
                None,
            )
            if entry is None:
                continue
            start, end = match.span()
            reads = entry.reads
            if entry.before_year and _YEAR_AFTER.match(text, end) and _after_name(text, start):
                reads = entry.before_year
            if entry.after_paragraph and (
                _after_paragraph(text, start) or _HALF_SENTENCE_AFTER.match(text, end)
            ):
                reads = entry.after_paragraph
            if not entry.exact_case:
                reads = _cased(reads, printed)
            if (
                entry.can_end_sentence
                and _ends_sentence(text, end, any_capital)
                and not (entry.inside_citation and _citation_goes_on(text, end, by_form))
            ):
                end -= 1  # the full stop stays and still ends the sentence
            elif end < len(text) and (text[end].isalnum() or text[end] in "(["):
                reads += " "  # glued: "eq.(1)", "Fig.4", "App.B"
            shown = " ".join(printed.split())
            yield Edit(
                Span(index, start, end),
                EditKind.REPLACE,
                reason=f'abbreviation "{shown}" read as "{reads.strip()}"',
                step=self.id,
                replacement=reads,
            )


def reads_full_stop(text: str, end: int, language: str) -> bool:
    """True if this step reads an abbreviation that ends at `end` with its full stop ("Kap."
    as "Kapitel", "e.g." as "for example"): the citations step then leaves the full stop
    after a citation that follows it, or the sentence would lose its end ("Siehe Kap.
    (Müller, 2019). Dann", #227). Only the text around `end` is looked at."""
    entries = abbreviations(language)
    if not entries or text[end - 1 : end] != ".":
        return False
    pattern, by_form = _compiled(entries)
    any_capital = language.split("-", 1)[0].lower() != "en"
    low = max(0, end - _AROUND)
    window = text[low : end + _AROUND]
    return any(
        edit.span.end == end - low
        for edit in AbbreviationStep()._edits(0, window, pattern, by_form, any_capital)
    )


def read_before(text: str, start: int, language: str) -> tuple[int, str] | None:
    """Where an abbreviation this step reads ends right before `start`, with only white space
    between, its start and its reading: "i. V. m. 2. Alternative" gives the start of "i. V.
    m." and "in Verbindung mit". The numbers step takes the reading as the word before an
    ordinal, as a second run sees it ("mit zweiter", #264 review round 1)."""
    entries = abbreviations(language)
    if not entries or text[max(0, start - _AROUND) : start].rstrip()[-1:] != ".":
        return None
    pattern, by_form = _compiled(entries)
    any_capital = language.split("-", 1)[0].lower() != "en"
    low = max(0, start - _AROUND)
    window = text[low : start + _AROUND]
    for edit in AbbreviationStep()._edits(0, window, pattern, by_form, any_capital):
        if edit.span.end < start - low and not window[edit.span.end : start - low].strip():
            return low + edit.span.start, (edit.replacement or "").strip()
    return None


_AROUND = 96  # more than any form and the look back of `_after_name`


class _Removals:
    """Where the links step removes text in a block, found once and only when asked: an
    abbreviation before a removed link reads as it does before what follows the link ("Kap.
    https://x.org/a (ebd.)" is "Kapitel (ebenda)", as a second run, without the link, reads
    it; #253)."""

    def __init__(self, text: str, kind: BlockKind, label: str, language: str) -> None:
        self._text = text
        self._kind = kind
        self._label = label
        self._language = language
        self._spans: list[tuple[int, int]] | None = None
        self._starts: list[int] = []

    def past(self, end: int) -> int | None:
        """The end of the removal that starts right after `end`, white space between. The
        removals are in order and never overlap: the first that starts at or after `end` is
        the only one to look at, found by bisection (linear on link-dense blocks)."""
        position = end
        while position < len(self._text) and self._text[position] in " \t\u00a0":
            position += 1  # linear: the matches are apart, so no white space is walked twice
        if self._spans is None:
            # the links step's pass over the block runs only once a link starts close by,
            # maybe after an opener it removes with the link ("<https://…>", "(see https://…)")
            near = position + _LEAD
            if not _LINK_START.search(self._text, position, near):
                return None  # cheap: no scheme, "www." or dotted host here
            window = self._text[position : position + _LINK_WINDOW]
            if not any(link.start < _LEAD for link in find_links(window)[:1]):
                return None
            self._spans = link_removals(self._text, self._kind, self._label, self._language)
            self._starts = [start for start, _ in self._spans]
        at = bisect_left(self._starts, end)
        if at < len(self._spans):
            start, stop = self._spans[at]
            if start <= position < stop:
                return stop
        return None


_LEAD = 48  # an opener and lead words the links step removes before a link, at most
_LINK_WINDOW = 512  # enough to see that a link starts
# what a link may start with: a scheme, "www." or a host with a dot ("x.org/a")
_LINK_START = re.compile(r"(?:https?:|ftp:|mailto:|www\.|doi|[\w-]+(?:\.[\w-]+)+[/:])", re.I)


def _skipped(block: Block) -> bool:
    return block.kind is BlockKind.FURNITURE or block.is_placeholder


def _key(printed: str) -> str:
    return " ".join(printed.split()).casefold()


@cache
def _compiled(
    entries: tuple[Abbreviation, ...],
) -> tuple[re.Pattern[str], dict[str, tuple[Abbreviation, ...]]]:
    """One pattern for every printed form, longest first, and the entries of each form
    without case (two only for forms told apart by case, such as "S." and "s.")."""
    by_form: dict[str, tuple[Abbreviation, ...]] = {}
    for entry in entries:
        for form in entry.printed:
            by_form[_key(form)] = (*by_form.get(_key(form), ()), entry)
    forms = sorted(by_form, key=len, reverse=True)
    alternatives = "|".join(r"\s".join(map(re.escape, form.split(" "))) for form in forms)
    # no letter or digit before it (a full stop may be: "Fig.FIG. 3" is two, each read);
    # what may follow is the entry's `before`
    pattern = re.compile(rf"(?<!\w)(?:{alternatives})", re.IGNORECASE)
    return pattern, by_form


def _case_fits(printed: str, entry: Abbreviation) -> bool:
    """True for a form as listed, with its first letter in the other case, or in capitals.

    Capitals count only for a one-word form ("FIG."): "S.T." and "I.E." are initials. An
    `exact_case` entry fits only as printed.
    """
    flat = " ".join(printed.split())
    if entry.exact_case:
        return any(flat == " ".join(form.split()) for form in entry.printed)
    return any(
        flat == form or flat[1:] == form[1:] or (flat == form.upper() and form.count(".") == 1)
        for form in entry.printed
    )


def _place_fits(text: str, end: int, entry: Abbreviation, any_capital: bool = False) -> bool:
    follows = (_FOLLOWS_ANY_CAPITAL if any_capital else _FOLLOWS).get(entry.before)
    if follows is None:  # "anything": a word of its own, no letter or digit glued after it
        return end == len(text) or not text[end].isalnum()
    return follows.match(text, end) is not None


def _ends_sentence(text: str, end: int, any_capital: bool = False) -> bool:
    following = _NEXT_SENTENCE_ANY_CAPITAL if any_capital else _NEXT_SENTENCE
    rest = text[end:].strip()
    if any_capital and rest in _CLOSING_QUOTES:
        return bool(rest)  # "Er schrieb „usw.“" at the block's end (#342)
    return not rest or following.match(text, end) is not None


# a page number, maybe a range, after "S." or "Seite(n)", right before "f." (#231, D-646)
_PAGE_BEFORE = re.compile(r"(?:(?<![^\W\d_])S\.|\bSeiten?)\s*\d+(?:\s*[-\u2013\u2014]\s*\d+)?\s+\Z")


def _after_page(text: str, start: int) -> bool:
    return _PAGE_BEFORE.search(text, max(0, start - 32), start) is not None


# a paragraph's number after "Abs." or "Absatz", right before "S." (#264)
_PARAGRAPH_BEFORE = re.compile(r"(?:(?<![^\W\d_])Abs\.|\bAbsatz)\s*\d+[a-z]?\s+\Z")


# ... or before a half sentence: "S. 1 Hs. 2" is "Satz 1 Halbsatz 2"
_HALF_SENTENCE_AFTER = re.compile(r"\s*\d+\s+Hs\.")


def _after_paragraph(text: str, start: int) -> bool:
    return _PARAGRAPH_BEFORE.search(text, max(0, start - 32), start) is not None


# a sentence's number after "S." or "Satz", right before "Hs." (#264 review round 1)
_SENTENCE_BEFORE = re.compile(r"(?:(?<![^\W\d_])S\.|\bSatz)\s*\d+\s+\Z")


def _after_sentence(text: str, start: int) -> bool:
    return _SENTENCE_BEFORE.search(text, max(0, start - 32), start) is not None


# what goes on with a law citation after "a. F." (#264 review round 1): a word in capitals
# ("BDSG", "GG"), "§", or a label word and its number ("Satz 2"); a listed label
# abbreviation ("Abs.", "Nr.", "S.") is checked against the list
_CITATION_GOES_ON = re.compile(
    rf"\s+(?:[{_UPPER}]{{2,}}(?![{_LOWER}])|§|(?:Satz|Absatz|Artikel|Nummer|Paragraph)\s+\d)"
)
_NEXT_FORM = re.compile(r"\s+(\S+?\.)")


def _citation_goes_on(text: str, end: int, by_form: dict[str, tuple[Abbreviation, ...]]) -> bool:
    if _CITATION_GOES_ON.match(text, end):
        return True
    form = _NEXT_FORM.match(text, end)
    return form is not None and any(
        entry.before in ("label", "number") and form.group(1) in entry.printed
        for entry in by_form.get(_key(form.group(1)), ())
    )


def _after_name(text: str, start: int) -> bool:
    """True if the word right before starts with a capital: "Müller u. a. (2019)" names
    authors, "gilt u. a. 2019" does not (review of PR #228)."""
    word = _NAME_BEFORE.search(text, max(0, start - 64), start)
    return word is not None and word.group(1).isupper()


def _cased(reads: str, printed: str) -> str:
    first = reads[0].upper() if printed[0].isupper() else reads[0].lower()
    return first + reads[1:]
