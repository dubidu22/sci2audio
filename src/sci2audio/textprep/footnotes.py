"""Footnotes: marks left out of the running text, notes read after their mark's sentence (TP-05).

A note is introduced by its mark ("Footnote 1.", in a German job "Fußnote 1.", #212), and its
mark is left out of the running text. `FootnotePlaceStep` (#213, D-558) then moves the note's
block to where the white space after the sentence holding its mark starts, by the utterance
cutter's sentence rule on the block's text without its marks, or to the block's end if that
sentence runs on. A note whose mark is not found, whose mark stands only in another note, or
whose place another rule rewrote, is read where layout placed it (the foot of its column, in
reading order), as before #213 (Q2).

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

`AffiliationMarkStep` (#93) removes the marks that tie an author to an affiliation in a
paper's title block ("Jianfeng Chi¹˒²", "¹Meta AI"), in the same "Footnotes" category. The
title block is the first page's PARAGRAPH blocks up to the first heading. A mark there is a
run of digits, commas and note symbols, set small and raised (a `sup` tag, or the size and
rise the footnote marks use), that is no footnote mark, and that stands after a name or
before an affiliation (`_after_name`, `_before_affiliation`). A mark before an affiliation
counts only after the author line: once a mark after a name (or a footnote mark after a
name) has been seen in the title block, so a title's "¹³CO and C¹⁸O" keeps its mass
numbers (#448). Numbers printed in the text's own size are
read ("1 Center for Neural Science"): nothing tells them from a number in the text.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Collection, Iterable, Iterator, Mapping

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
from sci2audio.textprep.furniture import HiddenRunStep, removed_span
from sci2audio.textprep.steps import ANY_LANGUAGE, Category, Stage, StepContext, TextStep
from sci2audio.textprep.utterances import sentence_end
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
# (Swiss guillemets close with it; #212, #248 S2), and the single guillemets U+203A and U+2039
# that quote inside them (PR #333 review R1-4)
_CLOSING = frozenset(".,;:!?)]}\u2019\u201d\u201c\u2018\u00ab\u00bb\u203a\u2039\"'")
_OPERATORS = frozenset("+=−×·|<>≤≥∈∉⊂⊆∑∏/^_")  # noqa: RUF001 (the minus sign is meant)
_WORD_END = re.compile(r"[^\W\d_]{2,}\d*\Z")  # two letters or more, then maybe digits
_SPOKEN_MARK = re.compile(r"[0-9A-Za-z]+")  # a mark that can be read: a number or letters
_BRACKETED = re.compile(r"\[([^\[\]]+)\]|\(([^()]+)\)")  # "[1]" or "(1)": one pair
# what a mark's removal says about its note (#213)
_READ_AFTER = "the note is read after the sentence that holds it"


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


def found_marks(document: Document, context: StepContext) -> dict[int, list[tuple[int, int]]]:
    """The footnote marks the footnotes step removes, by block: the earlier inline steps read
    the text without them, as a second run does ("bzw.¹", "z. B.¹", "Abschnitt 2.¹"; #316,
    D-577). Each step finds them again; no cache is shared between steps (D6). None while
    the "Footnotes" category is switched off: the marks then stay and are read (D-595)."""
    step = FootnoteStep()
    if not step.handles(context.language) or step.category in context.switched_off:
        return {}
    marks: dict[int, list[tuple[int, int]]] = {}
    for edit, _ in step.marked(document, context)[1]:
        marks.setdefault(edit.span.block, []).append((edit.span.start, edit.span.end))
    return marks


def unread_marks(document: Document, context: StepContext) -> dict[int, list[tuple[int, int]]]:
    """What the inline steps after the footnotes step read the text without, by block, as a
    second run reads it (D-577): the footnote marks (`found_marks`), and the hidden runs
    (#193) and affiliation marks (#93) those steps' switches leave out. So "Müller¹˒² m²"
    reads its unit as "Müller m²" does, and "37 °C" before a hidden run as without it."""
    marks = found_marks(document, context)
    removed: dict[int, list[tuple[int, int]]] = {}
    for index, spans in marks.items():
        removed.setdefault(index, []).extend(spans)
    found: list[Edit] = []
    if HiddenRunStep.category not in context.switched_off:
        found += HiddenRunStep().find(document, context)
    if AffiliationMarkStep.category not in context.switched_off:
        found += AffiliationMarkStep().marks(document, marks)
    for edit in found:
        removed.setdefault(edit.span.block, []).append((edit.span.start, edit.span.end))
    return removed


class FootnoteStep(TextStep):
    """Remove footnote marks from the running text and introduce each note."""

    id = "footnotes"
    languages = ("en", "de")
    category = Category.FOOTNOTES
    stage = Stage.INLINE

    def find(self, document: Document, context: StepContext) -> list[Edit]:
        return self.marked(document, context)[0]

    def marked(
        self, document: Document, context: StepContext
    ) -> tuple[list[Edit], list[tuple[Edit, int]]]:
        """The step's edits, and each mark it removes with the note block it marks (for the
        footnote-places step, #213)."""
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
        pairs: list[tuple[Edit, int]] = []  # each mark removed, with its note
        if notes:
            for index, block in enumerate(document.blocks):
                if block.kind in LINKED_KINDS:
                    for page, edit, note in self._linked_marks(items, index, block, notes):
                        marks.setdefault(index, []).append(edit)
                        pairs.append((edit, note))
                        mark = document.text_of(edit.span)
                        linked.setdefault(note, mark)
                        if label := document.blocks[note].label:
                            found.add((page, _same(label)))
        edits = []
        labels: dict[tuple[int, str], int] = {}  # (page, label) of a note -> its first block
        for index, block in enumerate(document.blocks):
            if block.kind is BlockKind.FOOTNOTE:
                backlinks = list(self._backlinks(items, index, block))
                edits += backlinks
                # the note starts after what is removed: back-links and marks of other notes
                removed = [e.span for e in (*backlinks, *marks.get(index, ()))]
                if edit := self._introduction(index, block, wording, linked.get(index), removed):
                    edits.append(edit)
                if block.label and block.parts:
                    key = (items[block.parts[0].item][0].number, _same(block.label))
                    labels.setdefault(key, index)
        for index in sorted(marks):
            edits += marks[index]
        for index, block in enumerate(document.blocks):
            if block.kind in MARKED_KINDS and labels:
                for edit, key in self._marks(items, index, block, labels.keys(), found):
                    edits.append(edit)
                    pairs.append((edit, labels[key]))
        return edits, pairs

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
                reason=f"footnote mark {mark} is not read; {_READ_AFTER}",
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
        labels: Collection[tuple[int, str]],
        found: set[tuple[int, str]],
    ) -> list[tuple[Edit, tuple[int, str]]]:
        """Remove-edits for the footnote marks in one block of running text, each with the
        (page, label) of the note it marks."""
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
                    (
                        Edit(
                            Span(index, start, end),
                            EditKind.REMOVE,
                            reason=f"footnote mark {mark} is not read; {_READ_AFTER}",
                            step=self.id,
                        ),
                        key,
                    )
                )
        return edits


# an affiliation mark: digits, commas and note symbols only (white space at the ends aside)
_AFFILIATION_MARK = re.compile(r"\s*[0-9,\u2217*\u2020\u2021\u00a7\u00b6]+\s*")
# a name before the mark: a capitalised word of two letters or more ("Chi", "Ångström")
_NAME_END = re.compile(r"[^\W\d_]{2,}\Z")
# after a name: the block's end, white space, a comma, a semicolon or a note mark
_AFTER_NAME = re.compile(r"\Z|[\s,;\u2217*\u2020\u2021\u00a7\u00b6]")
# an affiliation after the mark: a capital, after at most one space ("¹Meta AI", "² Univ")
_AFFILIATION = re.compile(r" ?([^\W\d_]{2,})")
# the chemical elements whose symbol has two letters: a raised number before one is its mass
# number ("⁸⁷Rb", "³He"), not an affiliation's mark (#436 review round 2, B1, D-57); a symbol
# of one letter ("¹H", "¹⁸F-FDG") is already too short for an affiliation
# fmt: off
ELEMENTS = frozenset({
    "He", "Li", "Be", "Ne", "Na", "Mg", "Al", "Si", "Cl", "Ar", "Ca", "Sc", "Ti",
    "Cr", "Mn", "Fe", "Co", "Ni", "Cu", "Zn", "Ga", "Ge", "As", "Se", "Br", "Kr",
    "Rb", "Sr", "Zr", "Nb", "Mo", "Tc", "Ru", "Rh", "Pd", "Ag", "Cd", "In", "Sn",
    "Sb", "Te", "Xe", "Cs", "Ba", "La", "Ce", "Pr", "Nd", "Pm", "Sm", "Eu", "Gd",
    "Tb", "Dy", "Ho", "Er", "Tm", "Yb", "Lu", "Hf", "Ta", "Re", "Os", "Ir", "Pt",
    "Au", "Hg", "Tl", "Pb", "Bi", "Po", "At", "Rn", "Fr", "Ra", "Ac", "Th", "Pa",
    "Np", "Pu", "Am", "Cm", "Bk", "Cf", "Es", "Fm", "Md", "No", "Lr", "Rf", "Db",
    "Sg", "Bh", "Hs", "Mt", "Ds", "Rg", "Cn", "Nh", "Fl", "Mc", "Lv", "Ts", "Og",
})
# fmt: on


class AffiliationMarkStep(TextStep):
    """Remove the affiliation marks of a paper's title block (#93)."""

    id = "affiliation-marks"
    languages = (ANY_LANGUAGE,)
    category = Category.FOOTNOTES
    stage = Stage.INLINE

    def find(self, document: Document, context: StepContext) -> list[Edit]:
        return self.marks(document, found_marks(document, context))

    def marks(
        self, document: Document, footnote_marks: Mapping[int, Collection[tuple[int, int]]]
    ) -> list[Edit]:
        """The removals, given the footnote marks the footnotes step removes."""
        items = document.content.items()
        edits = []
        authors = False  # affiliations follow the authors (#448)
        for index in _title_block(document, items):
            block = document.blocks[index]
            # a footnote mark stays with the footnotes step, which introduces its note
            taken = footnote_marks.get(index, [])
            line_starts = {offset for _, offset, _ in _lines(items, block)}
            # a footnote mark after a name (a corresponding author's) shows the author line too
            noted = sorted(
                (start, end) for start, end in taken if _after_name(block.text, start, end)
            )
            for start, end in _raised_marks(items, block, taken):
                if noted and noted[0][0] < start:
                    authors = True
                if _after_name(block.text, start, end):
                    authors = True
                elif not (
                    authors and _before_affiliation(block.text, start, end, start in line_starts)
                ):
                    continue
                mark = block.text[start:end].strip()
                start, end = removed_span(block.text, start, end)
                edits.append(
                    Edit(
                        Span(index, start, end),
                        EditKind.REMOVE,
                        reason=f'affiliation mark "{mark}" is not read',
                        step=self.id,
                    )
                )
            authors = authors or bool(noted)
        return edits


def _title_block(document: Document, items: Mapping[str, tuple[Page, Item]]) -> Iterator[int]:
    """The PARAGRAPH blocks of the first page, in reading order, up to its first heading. The
    first page is the page of the first block that has parts."""
    first = None
    for index, block in enumerate(document.blocks):
        if not block.parts:
            continue
        page = items[block.parts[0].item][0].number
        if first is None:
            first = page
        if page != first or block.kind is BlockKind.HEADING:
            return
        if block.kind is BlockKind.PARAGRAPH:
            yield index


def _raised_marks(
    items: Mapping[str, tuple[Page, Item]], block: Block, taken: Collection[tuple[int, int]]
) -> Iterator[tuple[int, int]]:
    """Where the block holds a run (or runs side by side) of mark characters set small and
    raised: tagged `sup`, or smaller than the block's main size and RISE em above a run in
    the main size on its line. A run that overlaps a `taken` span is no such run."""
    lines = list(_lines(items, block))
    main = _main_size(run for _, _, line in lines for run in line.runs)
    open_mark: tuple[int, int] | None = None
    for _, offset, line in lines:
        for run in line.runs:
            end = offset + len(run.text)
            if (
                _AFFILIATION_MARK.fullmatch(run.text)
                and _set_small(run, main)
                and _superscript(run, line, main)
                and not any(s < end and offset < e for s, e in taken)
            ):
                if open_mark and open_mark[1] == offset:
                    open_mark = (open_mark[0], end)
                else:
                    if open_mark:
                        yield open_mark
                    open_mark = (offset, end)
            offset = end
    if open_mark:
        yield open_mark


def _superscript(run: TextRun, line: TextLine, main: float) -> bool:
    """Raised: tagged `sup`, or its box ends RISE em or more above the box of a run in the
    main size on the same line."""
    if "sup" in run.tags:
        return True
    if run.box is None or main <= 0:
        return False
    return any(
        other.box is not None
        and not _set_small(other, main)
        and run.box.y1 <= other.box.y1 - RISE * main
        for other in line.runs
    )


def _after_name(text: str, start: int, end: int) -> bool:
    """The mark stands after a name ("Chi¹˒² Wasi", "Biggs ¹, Matthew", "Ahmad³*")."""
    word = _NAME_END.search(text[:start].rstrip())
    return bool(word and word[0][0].isupper() and _AFTER_NAME.match(text, end))


def _before_affiliation(text: str, start: int, end: int, line_start: bool) -> bool:
    """The mark stands before an affiliation: at the block's or a line's start, or after a
    comma or semicolon, and before a capitalised word of two letters or more ("¹Meta AI",
    "², University", "²Österreichische Akademie", "¹AI Lab") that is no element symbol. So
    "x²", "N³", "size³ + 1", "small.¹", a "⁵ is first" and the mass numbers of "¹H NMR of
    ¹³C", "¹⁸F-FDG" and "⁸⁷Rb" stay (D-57). `AffiliationMarkStep` asks this only after the
    author line (#448)."""
    kept = text[:start].rstrip()
    at_start = not kept or line_start or kept[-1] in ",;"
    affiliation = _AFFILIATION.match(text, end)
    if not at_start or affiliation is None or affiliation[1] in ELEMENTS:
        return False
    return affiliation[1][0].isupper()


class FootnotePlaceStep(TextStep):
    """Read each footnote right after the sentence that holds its mark (#213, D-558).

    The marks are the ones `FootnoteStep` leaves out; a note marked more than once (D-421)
    goes to its first mark. Only marks in running text move a note (`MARKED_KINDS`): a mark
    inside another note leaves its note where it is printed, so moves never chain. The
    sentence end comes from the utterance cutter's own rule (`sentence_end`), with the
    block's marks read as left out; when the sentence runs to the end of the block the note
    goes after the block. A note whose mark is not found stays where it is printed.
    """

    id = "footnote-places"
    languages = ("en", "de")
    category = Category.FOOTNOTES
    stage = Stage.MOVE

    def find(self, document: Document, context: StepContext) -> list[Edit]:
        _, pairs = FootnoteStep().marked(document, context)
        removed: dict[int, list[tuple[int, int]]] = {}  # block -> its marks
        first: dict[int, Span] = {}  # note block -> its first mark in running text
        for edit, note in pairs:
            span = edit.span
            removed.setdefault(span.block, []).append((span.start, span.end))
            if document.blocks[span.block].kind not in MARKED_KINDS:  # not in a note
                continue
            if note not in first or (span.block, span.start) < (
                first[note].block,
                first[note].start,
            ):
                first[note] = span
        edits = []
        for note, mark in sorted(first.items()):
            block = document.blocks[note]
            if not block.text:
                continue
            text = document.blocks[mark.block].text
            at = sentence_end(text, mark.end, removed[mark.block], context.language)
            edits.append(
                Edit(
                    Span(note, 0, len(block.text)),
                    EditKind.MOVE,
                    reason=f"{_name(block)} is read after the sentence that holds its mark",
                    step=self.id,
                    to=Span(mark.block, at, at),
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
