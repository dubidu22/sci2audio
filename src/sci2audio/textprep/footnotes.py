"""Footnotes: marks left out of the running text, notes read where layout placed them (TP-05).

Q2: a note is read where layout placed it (the foot of its column, in reading order),
introduced by its mark ("Footnote 1."), and its mark is left out of the running text. A
note cannot move next to its mark: an edit never crosses blocks (D-61 (1)).

Two categories (D-142): "Footnotes" (on by default) holds `FootnoteStep`, which removes the
marks and introduces the notes; "Footnote texts" (off by default) holds `FootnoteTextStep`,
which removes every note, so switching it on leaves all footnotes out. Its whole-block
removals run first and claim the notes' blocks, so the introductions are then set aside
(D-128); the marks stay out either way.

A mark is found from what extraction recorded (D-143): a run of its own that is tagged as a
superscript (EPUB, Markdown) or set smaller than the block's main size (PDF), whose text is
the label of a note on the same page, after a word of at least two letters (digits may
follow: "Ahmad3" before an asterisk mark) or closing punctuation, and not followed by a
maths operator. So "N3" and "|N|3" in a formula set in line stay. Each label is taken once
per page, at its first match in reading order. A note whose mark is not found is still read.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable, Iterator, Mapping

from sci2audio.core import (
    Block,
    BlockKind,
    Document,
    Edit,
    EditKind,
    Item,
    Page,
    Span,
    TextLine,
    TextRun,
)
from sci2audio.textprep.steps import ANY_LANGUAGE, Category, Stage, StepContext, TextStep
from sci2audio.textprep.wording import Wording, wording_for

# a run this much smaller than the block's main size is set small (layout's size_change)
SMALLER = 0.08
# the kinds of block whose text can hold a footnote mark
MARKED_KINDS = frozenset(
    {BlockKind.PARAGRAPH, BlockKind.HEADING, BlockKind.CAPTION, BlockKind.LIST_ITEM}
)
_CLOSING = frozenset(".,;:!?)]}\u2019\u201d\"'")  # also the closing quotes
_OPERATORS = frozenset("+=−×·|<>≤≥∈∉⊂⊆∑∏/^_")  # noqa: RUF001 (the minus sign is meant)
_WORD_END = re.compile(r"[^\W\d_]{2,}\d*\Z")  # two letters or more, then maybe digits
_SPOKEN_MARK = re.compile(r"[0-9A-Za-z]+")  # a mark that can be read: a number or letters
_INTRODUCED = re.compile(r"Footnote\b")


class FootnoteTextStep(TextStep):
    """Leave every footnote out; its category is off unless the user turns it on."""

    id = "footnote-texts"
    languages = (ANY_LANGUAGE,)
    category = Category.FOOTNOTE_TEXTS
    stage = Stage.BLOCK

    def find(self, document: Document, context: StepContext) -> list[Edit]:
        return [
            Edit(
                Span(index, 0, len(block.text)),
                EditKind.REMOVE,
                reason=f"{_name(block)} is left out (all footnotes are left out)",
                step=self.id,
            )
            for index, block in enumerate(document.blocks)
            if block.kind is BlockKind.FOOTNOTE and block.text
        ]


class FootnoteStep(TextStep):
    """Remove footnote marks from the running text and introduce each note."""

    id = "footnotes"
    languages = ("en",)
    category = Category.FOOTNOTES
    stage = Stage.INLINE

    def find(self, document: Document, context: StepContext) -> list[Edit]:
        wording = wording_for(context.language)
        items = document.content.items()  # once: it is built anew on every call
        edits = []
        labels: set[tuple[int, str]] = set()  # (page, label) of every note with a mark
        for index, block in enumerate(document.blocks):
            if block.kind is BlockKind.FOOTNOTE:
                if edit := self._introduction(index, block, wording):
                    edits.append(edit)
                if block.label and block.parts:
                    labels.add((items[block.parts[0].item][0].number, block.label))
        found: set[tuple[int, str]] = set()
        for index, block in enumerate(document.blocks):
            if block.kind in MARKED_KINDS and labels:
                edits += self._marks(items, index, block, labels, found)
        return edits

    def _introduction(self, index: int, block: Block, wording: Wording) -> Edit | None:
        """The edit that introduces a note: its mark read as "Footnote 1.", or "Footnote."
        put before a note without one; none for a note already introduced or empty."""
        text = block.text
        lead = len(text) - len(text.lstrip())
        if lead == len(text) or _INTRODUCED.match(text, lead):
            return None
        label = block.label
        if label and text.startswith(label, lead):
            end = lead + len(label)
            spoken = (
                wording.footnote.format(label)
                if _SPOKEN_MARK.fullmatch(label)
                else wording.footnote_unnamed
            )
            if end < len(text) and not text[end].isspace():
                spoken += " "
            return Edit(
                Span(index, lead, end),
                EditKind.REPLACE,
                reason=f"footnote {label} is introduced by its mark",
                step=self.id,
                replacement=spoken,
            )
        return Edit(
            Span(index, lead, lead),
            EditKind.REPLACE,
            reason="a footnote is introduced",
            step=self.id,
            replacement=wording.footnote_unnamed + " ",
        )

    def _marks(
        self,
        items: Mapping[str, tuple[Page, Item]],
        index: int,
        block: Block,
        labels: set[tuple[int, str]],
        found: set[tuple[int, str]],
    ) -> list[Edit]:
        """Remove-edits for the footnote marks in one block of running text."""
        runs = list(_runs(items, block))
        main = _main_size(run for _, _, run in runs)
        edits = []
        for page, offset, run in runs:
            mark = run.text.strip()
            key = (page, mark)
            if not mark or key not in labels or key in found:
                continue
            start = offset + run.text.index(mark)
            end = start + len(mark)
            if (
                _set_small(run, main)
                and _after_word(block.text[:start])
                and _not_maths(block.text[end:])
            ):
                found.add(key)
                edits.append(
                    Edit(
                        Span(index, start, end),
                        EditKind.REMOVE,
                        reason=f"footnote mark {mark} is not read; the note is read at the "
                        "foot of the column (Q2)",
                        step=self.id,
                    )
                )
        return edits


def _name(block: Block) -> str:
    return f"footnote {block.label}" if block.label else "a footnote"


def _runs(
    items: Mapping[str, tuple[Page, Item]], block: Block
) -> Iterator[tuple[int, int, TextRun]]:
    """Each run of the block's lines with its page and where its text starts in the block.

    A line whose text is not where its part says (it never should be) is skipped, so a span
    never points at other text.
    """
    for part in block.parts:
        page, item = items[part.item]
        if not isinstance(item, TextLine):
            continue
        if block.text[part.start : part.start + len(item.text)] != item.text:
            continue
        offset = part.start
        for run in item.runs:
            yield page.number, offset, run
            offset += len(run.text)


def _main_size(runs: Iterable[TextRun]) -> float:
    """The size most of the letters have; 0 when the source gives no sizes."""
    letters: Counter[float] = Counter()
    for run in runs:
        letters[run.size] += len(run.text.strip())
    return letters.most_common(1)[0][0] if letters else 0.0


def _set_small(run: TextRun, main: float) -> bool:
    """A superscript: tagged so by the source, or set smaller than the block's text."""
    return "sup" in run.tags or (0 < run.size < (1 - SMALLER) * main)


def _after_word(before: str) -> bool:
    """True if the text before a mark ends in a word or closing punctuation, not in a
    one-letter variable or a maths sign ("N", "|N |")."""
    words = before.split()
    if not words:
        return False
    last = words[-1]
    return last[-1] in _CLOSING or _WORD_END.search(last) is not None


def _not_maths(after: str) -> bool:
    """True unless a maths operator follows the mark (the "3" of "N3 + 1")."""
    rest = after.lstrip()
    return not rest or rest[0] not in _OPERATORS
