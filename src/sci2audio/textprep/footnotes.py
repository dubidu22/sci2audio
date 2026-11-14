"""Footnotes: marks left out of the running text, notes read where layout placed them (TP-05).

Q2: a note is read where layout placed it (the foot of its column, in reading order),
introduced by its mark ("Footnote 1.", in a German job "Fußnote 1.", #212), and its mark is
left out of the running text. A note cannot move next to its mark: an edit never crosses
blocks (D-61 (1)).

Two categories (D-142): "Footnotes" (on by default) holds `FootnoteStep`, which removes the
marks and introduces the notes; "Footnote texts" (off by default) holds `FootnoteTextStep`,
which removes every note, so switching it on leaves all footnotes out. Its whole-block
removals run first and claim the notes' blocks, so the introductions are then set aside
(D-128); the marks stay out either way.

A mark is found from what extraction recorded (D-143): a run of its own that is tagged as a
superscript (EPUB, Markdown), set smaller than the block's main size (PDF) or set in that
size but raised over the run beside it (a superior figure, #212), whose text is the label of
a note on the same page (a printed asterisk matches a note marked by the asterisk operator),
after a word of at least two letters (digits may follow: "Ahmad3" before an asterisk mark) or
closing punctuation (the German closing quote too), and not followed by a maths operator. So
"N3" and "|N|3" in a formula set in line stay. Each label is taken once per page, at its
first match in reading order. A note whose mark is not found is still read.

EPUB and Markdown tie a mark to its note by tags instead (D-428): a run tagged
`role:doc-noteref` or `epub:noteref` whose `link:` points at an item of a FOOTNOTE block is a
**linked mark**. It is removed wherever the note stands (another page, an Endnotes chapter),
every time it is used (D-421), in body text and in notes alike (D-420), without the four
conditions above; a noteref linking anywhere else, or to the note it stands in, is read as
printed (D-423), and the printed-label rule never looks at a noteref run. A note whose own
label is "" is introduced by its first linked mark in reading order (D-425), a mark printed
in brackets by what is inside them: "[1]" gives "Footnote 1." (D-422). A back-link in a note
(`role:doc-backlink`, `epub:backlink`, the "↩" back to the mark) is removed with the white
space before it (D-424); a note that holds nothing else gets no introduction.
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
# a run raised this many em above the text next to it on its line is a superior figure set in
# the text's own size (layout's footnote_mark_rise, D-507; #212)
RISE = 0.1
# the kinds of block whose text can hold a footnote mark
MARKED_KINDS = frozenset(
    {BlockKind.PARAGRAPH, BlockKind.HEADING, BlockKind.CAPTION, BlockKind.LIST_ITEM}
)
# the tags of a mark that links to its note, and of a note's link back to its mark (D-307)
NOTEREF_TAGS = frozenset({"role:doc-noteref", "epub:noteref"})
BACKLINK_TAGS = frozenset({"role:doc-backlink", "epub:backlink"})
# the kinds of block whose text can hold a linked mark (D-420)
LINKED_KINDS = MARKED_KINDS | {BlockKind.FOOTNOTE}
_LINK = "link:"
# also the closing quotes: U+2019, U+201D (English), U+201C, U+2018, U+00AB (German) and U+00BB
# (Swiss guillemets close with it; #212, #248 S2)
_CLOSING = frozenset(".,;:!?)]}\u2019\u201d\u201c\u2018\u00ab\u00bb\"'")
_OPERATORS = frozenset("+=−×·|<>≤≥∈∉⊂⊆∑∏/^_")  # noqa: RUF001 (the minus sign is meant)
_WORD_END = re.compile(r"[^\W\d_]{2,}\d*\Z")  # two letters or more, then maybe digits
_SPOKEN_MARK = re.compile(r"[0-9A-Za-z]+")  # a mark that can be read: a number or letters
_BRACKETED = re.compile(r"\[([^\[\]]+)\]|\(([^()]+)\)")  # "[1]" or "(1)": one pair


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
    languages = ("en", "de")
    category = Category.FOOTNOTES
    stage = Stage.INLINE

    def find(self, document: Document, context: StepContext) -> list[Edit]:
        wording = wording_for(context.language)
        items = document.content.items()  # once: it is built anew on every call
        notes = {
            part.item: index
            for index, block in enumerate(document.blocks)
            if block.kind is BlockKind.FOOTNOTE
            for part in block.parts
        }
        found: set[tuple[int, str]] = set()  # (page, label) of every mark taken
        linked: dict[int, str] = {}  # note block -> its first linked mark
        marks: dict[int, list[Edit]] = {}  # block -> its linked-mark removals
        if notes:
            for index, block in enumerate(document.blocks):
                if block.kind in LINKED_KINDS:
                    for page, edit, note in self._linked_marks(items, index, block, notes):
                        marks.setdefault(index, []).append(edit)
                        mark = document.text_of(edit.span)
                        linked.setdefault(note, mark)
                        if label := document.blocks[note].label:
                            found.add((page, _same(label)))
        edits = []
        labels: set[tuple[int, str]] = set()  # (page, label) of every note with a mark
        for index, block in enumerate(document.blocks):
            if block.kind is BlockKind.FOOTNOTE:
                backlinks = list(self._backlinks(items, index, block))
                edits += backlinks
                # the note starts after what is removed: back-links and marks of other notes
                removed = [e.span for e in (*backlinks, *marks.get(index, ()))]
                if edit := self._introduction(index, block, wording, linked.get(index), removed):
                    edits.append(edit)
                if block.label and block.parts:
                    labels.add((items[block.parts[0].item][0].number, _same(block.label)))
        for index in sorted(marks):
            edits += marks[index]
        for index, block in enumerate(document.blocks):
            if block.kind in MARKED_KINDS and labels:
                edits += self._marks(items, index, block, labels, found)
        return edits

    def _linked_marks(
        self,
        items: Mapping[str, tuple[Page, Item]],
        index: int,
        block: Block,
        notes: Mapping[str, int],
    ) -> Iterator[tuple[int, Edit, int]]:
        """Remove-edits for the linked marks in one block, each with the page it stands on
        and the note it links to (D-428). Runs next to each other with the same noteref
        link are one mark."""
        group: list[tuple[int, int, int, str]] = []  # (page, start, end, link) of one mark
        for page, offset, run in [*_runs(items, block), (0, -1, None)]:
            link = _noteref_link(run) if run is not None else None
            if group and (link != group[-1][3] or offset != group[-1][2]):
                if found := self._linked_mark(index, block, group, notes):
                    yield found
                group = []
            if link is not None:
                group.append((page, offset, offset + len(run.text), link))

    def _linked_mark(
        self,
        index: int,
        block: Block,
        group: list[tuple[int, int, int, str]],
        notes: Mapping[str, int],
    ) -> tuple[int, Edit, int] | None:
        page, start, _, link = group[0]
        end = group[-1][2]
        note = notes.get(link)
        if note is None or note == index:  # links elsewhere or to its own note (D-423)
            return None
        text = block.text[start:end]
        mark = text.strip()
        if not mark:
            return None
        start += len(text) - len(text.lstrip())
        return (
            page,
            Edit(
                Span(index, start, start + len(mark)),
                EditKind.REMOVE,
                reason=f"footnote mark {mark} is not read; the note is read where the file "
                "places it (Q2, D-414)",
                step=self.id,
            ),
            note,
        )

    def _backlinks(
        self, items: Mapping[str, tuple[Page, Item]], index: int, block: Block
    ) -> Iterator[Edit]:
        """Remove-edits for a note's back-links, each with the white space before it
        (D-424). Back-link runs next to each other are one."""
        spans: list[list[int]] = []
        for _, offset, run in _runs(items, block):
            if not BACKLINK_TAGS & set(run.tags):
                continue
            end = offset + len(run.text)
            if spans and spans[-1][1] == offset:
                spans[-1][1] = end
            else:
                spans.append([offset, end])
        # where the last back-link edit ends: the next one's white space starts after it. Each
        # edit ends on a letter (rstrip), so this only guards the no-overlap rule (#194 N1).
        taken = 0
        for start, end in spans:
            text = block.text[start:end]
            if not text.strip():
                continue
            end = start + len(text.rstrip())
            while start > taken and block.text[start - 1].isspace():
                start -= 1
            taken = end
            yield Edit(
                Span(index, start, end),
                EditKind.REMOVE,
                reason="the back-link of a footnote is not read",
                step=self.id,
            )

    def _introduction(
        self,
        index: int,
        block: Block,
        wording: Wording,
        linked: str | None = None,
        removed: Iterable[Span] = (),
    ) -> Edit | None:
        """The edit that introduces a note: its mark read as "Footnote 1.", or "Footnote."
        put before a note without one; none for a note already introduced or empty.
        `linked` is the first mark that links to the note; `removed` are the spans other
        edits remove from it (back-links, marks of other notes): the note starts after them,
        and a printed mark that overlaps one is not read as the note's mark."""
        text = block.text
        lead = _lead(text, removed)
        if lead == len(text) or _introduced(wording).match(_without(text, removed, lead)):
            return None
        label = block.label
        end = _printed_end(text, label, lead, removed)
        if end is not None:
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
        if not label and linked is not None:
            inner = _BRACKETED.fullmatch(linked)
            mark = next(g for g in inner.groups() if g is not None) if inner else linked
            spoken = (
                wording.footnote.format(mark)
                if _SPOKEN_MARK.fullmatch(mark)
                else wording.footnote_unnamed
            )
            return Edit(
                Span(index, lead, lead),
                EditKind.REPLACE,
                reason=f"footnote {linked} is introduced by the mark that links to it",
                step=self.id,
                replacement=spoken + " ",
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
        # the runs beside each run on its own line: a rise is measured on the line (#248 M1)
        beside = [
            (line.runs[k - 1] if k else None, line.runs[k + 1] if k + 1 < len(line.runs) else None)
            for _, _, line in _lines(items, block)
            for k in range(len(line.runs))
        ]
        edits = []
        for (page, offset, run), neighbours in zip(runs, beside, strict=True):
            mark = run.text.strip()
            key = (page, _same(mark))
            if not mark or key not in labels or key in found or NOTEREF_TAGS & set(run.tags):
                continue  # a noteref is a linked mark or read as printed (D-423, D-428)
            start = offset + run.text.index(mark)
            end = start + len(mark)
            if (
                (_set_small(run, main) or _raised(run, neighbours, main))
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


def _noteref_link(run: TextRun) -> str | None:
    """The item a noteref run links to; None for any other run (a back-link tagged as a
    noteref too is a back-link)."""
    tags = set(run.tags)
    if not NOTEREF_TAGS & tags or BACKLINK_TAGS & tags:
        return None
    return next((tag[len(_LINK) :] for tag in run.tags if tag.startswith(_LINK)), None)


def _printed_end(text: str, label: str, lead: int, removed: Iterable[Span]) -> int | None:
    """Where a note's printed mark ends, a "." or ")" after it included ("1. Text"); None
    if the note does not start with its label, or a removed span lies in it."""
    if not label or not text.startswith(label, lead):
        return None
    end = lead + len(label)
    if text[end : end + 1] in (".", ")") and not text[end + 1 : end + 2].strip():
        end += 1  # a note printed "1. Text" or "1) Text": the "." or ")" goes too
    if any(span.start < end and lead < span.end for span in removed):
        return None
    return end


def _without(text: str, removed: Iterable[Span], start: int) -> str:
    """The text from `start` on as it reads with the removed spans taken out."""
    kept, position = [], start
    for span in sorted(removed, key=lambda span: span.start):
        if span.end <= position:
            continue
        kept.append(text[position : max(position, span.start)])
        position = max(position, span.end)
    kept.append(text[position:])
    return "".join(kept)


def _lead(text: str, removed: Iterable[Span]) -> int:
    """Where a note's text starts: its first character that is not white space and not in
    a removed span; len(text) if there is none."""
    spans = sorted((span.start, span.end) for span in removed)
    position, next_span = 0, 0
    while position < len(text):
        while next_span < len(spans) and spans[next_span][1] <= position:
            next_span += 1
        if next_span < len(spans) and spans[next_span][0] <= position:
            position = spans[next_span][1]
        elif text[position].isspace():
            position += 1
        else:
            return position
    return len(text)


def _name(block: Block) -> str:
    return f"footnote {block.label}" if block.label else "a footnote"


def _lines(
    items: Mapping[str, tuple[Page, Item]], block: Block
) -> Iterator[tuple[int, int, TextLine]]:
    """Each text line of the block with its page and where its text starts in the block.

    A line whose text is not where its part says (it never should be) is skipped, so a span
    never points at other text.
    """
    for part in block.parts:
        page, item = items[part.item]
        if not isinstance(item, TextLine):
            continue
        if block.text[part.start : part.start + len(item.text)] != item.text:
            continue
        yield page.number, part.start, item


def _runs(
    items: Mapping[str, tuple[Page, Item]], block: Block
) -> Iterator[tuple[int, int, TextRun]]:
    """Each run of the block's lines with its page and where its text starts in the block."""
    for page, offset, line in _lines(items, block):
        for run in line.runs:
            yield page, offset, run
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


def _raised(run: TextRun, neighbours: Iterable[TextRun | None], main: float) -> bool:
    """A superior figure set in the text's own size: its box ends RISE em or more above the
    box of the run before or after it in the same text line (#212, D-519). The rise is
    measured only against a neighbour in the text's size, not one set small: a subscript
    would make the normal run beside it look raised (#248 S1)."""
    if run.box is None or main <= 0:
        return False
    return any(
        other is not None
        and other.box is not None
        and not _set_small(other, main)
        and other.box.y0 < run.box.y1  # the two still share a band of the line
        and run.box.y1 <= other.box.y1 - RISE * main
        for other in neighbours
    )


def _introduced(wording: Wording) -> re.Pattern[str]:
    """A note that already starts with the introduction's word ("Footnote", "Fußnote")."""
    return re.compile(re.escape(wording.footnote_unnamed.removesuffix(".")) + r"\b")


def _same(mark: str) -> str:
    """A mark as it is compared: an asterisk printed "*" in the text marks the note that
    layout labels with the asterisk operator (U+2217)."""
    return mark.replace("*", "\u2217")


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
