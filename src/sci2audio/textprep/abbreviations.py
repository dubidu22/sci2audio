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
read so before a year, bracketed or not: "Müller u. a. (2019)" is "Müller und andere", any
other "u. a." "unter anderem". An abbreviation that can end a sentence and stands at the end
of the block or before a capital letter keeps its full stop as printed, so the sentence still
ends there (D-234). Furniture and placeholder blocks are claimed whole by other steps and skipped.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from functools import cache

from sci2audio.core import Block, BlockKind, Document, Edit, EditKind, Span
from sci2audio.textprep.notation import edits_through_unread
from sci2audio.textprep.steps import Category, Stage, StepContext, TextStep
from sci2audio.textprep.wordlists import Abbreviation, abbreviations

# what may follow an abbreviation read only before a label, a number or a word
_SPACE = r"[^\S\r]{0,2}"
_LABEL = re.compile(_SPACE + r"(?:\d|[(\[]\w|[A-Z](?![a-z]|\.[A-Za-z]))")
_NUMBER = re.compile(_SPACE + r"\d")
_WORD = re.compile(r"[^\S\r]{1,2}(?:[A-Z]|\d)")
_FOLLOWS = {"label": _LABEL, "number": _NUMBER, "word": _WORD}
# a sentence after the full stop: white space, maybe an opening quote or bracket, a capital
_NEXT_SENTENCE = re.compile(r"\s+[\"'(\[\u201c\u2018]?[A-Z]")
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
        edits = []
        for index, block in enumerate(document.blocks):
            if _skipped(block):
                continue
            edits += edits_through_unread(
                index,
                block.text,
                lambda read: self._edits(index, read, pattern, by_form),  # noqa: B023
                self.id,
            )
        return edits

    def _edits(
        self,
        index: int,
        text: str,
        pattern: re.Pattern[str],
        by_form: dict[str, tuple[Abbreviation, ...]],
    ) -> Iterator[Edit]:
        for match in pattern.finditer(text):
            printed = match.group()
            entry = next(
                (
                    entry
                    for entry in by_form[_key(printed)]
                    if _case_fits(printed, entry) and _place_fits(text, match.end(), entry)
                ),
                None,
            )
            if entry is None:
                continue
            start, end = match.span()
            reads = entry.reads
            if entry.before_year and _YEAR_AFTER.match(text, end):
                reads = entry.before_year
            if not entry.exact_case:
                reads = _cased(reads, printed)
            if entry.can_end_sentence and _ends_sentence(text, end):
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


def _place_fits(text: str, end: int, entry: Abbreviation) -> bool:
    follows = _FOLLOWS.get(entry.before)
    if follows is None:  # "anything": a word of its own, no letter or digit glued after it
        return end == len(text) or not text[end].isalnum()
    return follows.match(text, end) is not None


def _ends_sentence(text: str, end: int) -> bool:
    return not text[end:].strip() or _NEXT_SENTENCE.match(text, end) is not None


def _cased(reads: str, printed: str) -> str:
    first = reads[0].upper() if printed[0].isupper() else reads[0].lower()
    return first + reads[1:]
