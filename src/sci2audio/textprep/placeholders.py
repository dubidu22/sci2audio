"""Formulas, tables, figures and code are not read; a short notice says so (FX-01, FX-02,
D-55, D-545).

Layout keeps each display formula, table and figure as a placeholder block (D-63), with its
caption as a block of its own that points at it (`describes`) and a formula's printed number
as its label. Each placeholder's whole text is replaced by one short notice that names it
(Q3, D-145): through the labels of the captions that describe it, as printed ("Table 2",
"Algorithm 1"; a short "Fig. 3" read "Figure 3"), else through a formula's own number
("Formula 16a"), else without a name ("A figure is skipped."). The caption is not repeated:
it reads as printed, in its printed place, and already starts with its label.

A figure that no caption names but whose pictures carry alternative text (an EPUB or
Markdown image, #191) is read by it after the notice: "A figure is skipped. It shows: A bar
chart of minutes per group." Several pictures' texts are joined by "; ". The alt text is
part of the notice, so later steps do not read it again, as for any notice.

Formulas, tables-and-figures (D-108) and code blocks (D-545) are separate categories, so
they are three steps. A code block is named by nothing yet ("A code block is skipped.");
the player shows its code (D-546).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace

from sci2audio.core import (
    Block,
    BlockKind,
    Document,
    Edit,
    EditKind,
    Item,
    Page,
    Picture,
    ScriptPiece,
    Span,
)
from sci2audio.textprep.steps import Category, Stage, StepContext, TextStep
from sci2audio.textprep.wording import wording_for

_NAMES = {BlockKind.CODE: "code block"}  # how a reason names a kind, if not by its value


def read_over(printed: str, script: Sequence[ScriptPiece], start: int, end: int) -> str | None:
    """What the script of one block reads over characters `start` to `end` of its printed
    text, or None if a replacement runs past either edge. Kept characters stay, and a
    replacement lying inside the span stands for its part ("Abb. 1" spelled out reads
    "Abbildung 1"). A pause adds nothing: it has no text and an empty span, so it reads as
    kept and empty. The notice steps name a figure by it, and the second-run check
    (`sci2audio.testing.rebuilt_from_script`) maps a caption's label by it (#324, D-707)."""
    read = []
    for piece in script:
        span = piece.span
        if span.end <= start or span.start >= end:
            continue
        if piece.text == printed[span.start : span.end]:  # kept as printed
            read.append(printed[max(start, span.start) : min(end, span.end)])
        elif start <= span.start and span.end <= end:
            read.append(piece.text)
        else:
            return None
    return "".join(read)


def _read_in_place(
    document: Document,
    context: StepContext,
    wanted: Sequence[tuple[Block, str]],
    *,
    printed_if_left_out: bool = True,
) -> list[str]:
    """Each (block, name) with the name as the built-in inline steps read it in that block,
    with the job's language and switches: a caption's label in its caption, as a second run
    names the figure by the caption's reading (#374, #370), or a formula's name in its own
    notice ("Formel 3 Punkt 2", #362). The blocks are read on their own, in a small document
    of them (a caption with the placeholder it describes). A name a replacement runs past,
    or one the steps leave out, keeps its printed form (D-707); with `printed_if_left_out`
    False, one the steps leave out reads "" (a figure's alt text that is only a link, #464)."""
    if not wanted:
        return []
    # imported here: the registry and the runner import this module
    from sci2audio.textprep.registry import BUILT_IN_STEPS
    from sci2audio.textprep.runner import run_steps

    blocks: list[Block] = []
    where = []
    described: dict[int, int] = {}  # a described placeholder's index here, by its own
    for block, _ in wanted:
        if (target := block.describes) is not None:
            if target not in described:
                described[target] = len(blocks)
                blocks.append(document.blocks[target])
            block = replace(block, describes=described[target])
        where.append(len(blocks))
        blocks.append(block)
    used = {part.item for block in blocks for part in block.parts}
    pages = tuple(
        replace(
            page,
            lines=tuple(line for line in page.lines if line.id in used),
            pictures=tuple(picture for picture in page.pictures if picture.id in used),
            drawings=tuple(drawing for drawing in page.drawings if drawing.id in used),
            order=tuple(item for item in page.order if item in used),
        )
        for page in document.content.pages
    )
    content = replace(document.content, pages=pages, outline=())
    small = replace(document, content=content, blocks=tuple(blocks), sections=())
    inline = [step for step in BUILT_IN_STEPS if step.stage is Stage.INLINE]
    script = run_steps(small, context, inline, context.switched_off).script()
    read = []
    for (block, name), position in zip(wanted, where, strict=True):
        start = block.text.find(name)
        own = [piece for piece in script if piece.span.block == position]
        reading = read_over(block.text, own, start, start + len(name)) if start >= 0 else None
        if reading is None:
            read.append(name)
        elif not printed_if_left_out and not any(char.isalnum() for char in reading):
            read.append("")
        else:
            read.append(" ".join(reading.split()) or name)
    return read


class _NoticeStep(TextStep):
    """Replace each placeholder block of the given kinds by its notice."""

    kinds: frozenset[BlockKind]
    languages = ("en", "de")
    stage = Stage.BLOCK

    def find(self, document: Document, context: StepContext) -> list[Edit]:
        wording = wording_for(context.language)
        ours = {index for index, block in enumerate(document.blocks) if block.kind in self.kinds}
        captions_of = [
            (index, block)
            for index, block in enumerate(document.blocks)
            if block.describes in ours and block.label
        ]
        captions: dict[int, list[str]] = {}
        for (_, block), label in zip(
            captions_of,
            _read_in_place(document, context, [(block, block.label) for _, block in captions_of]),
            strict=True,
        ):
            if block.describes is not None:  # always: a caption of one of ours
                captions.setdefault(block.describes, []).append(wording.label(label))
        formulas = [
            (index, wording.formula.format(block.label))
            for index, block in enumerate(document.blocks)
            if index in ours
            and block.kind is BlockKind.FORMULA
            and block.label
            and index not in captions
        ]
        notices = [
            (Block(BlockKind.PARAGRAPH, wording.skipped([name], BlockKind.FORMULA)), name)
            for _, name in formulas
        ]
        named = dict(
            zip(
                (index for index, _ in formulas),
                _read_in_place(document, context, notices),
                strict=True,
            )
        )
        items = document.content.items()
        # an unnamed figure's alt text, read as the inline steps read a paragraph (#464)
        alts = [
            (index, alt)
            for index, block in enumerate(document.blocks)
            if index in ours
            and block.kind is BlockKind.FIGURE
            and index not in captions
            and index not in named
            and (alt := _alt_text(items, block))
        ]
        shows = dict(
            zip(
                (index for index, _ in alts),
                _read_in_place(
                    document,
                    context,
                    [(Block(BlockKind.PARAGRAPH, alt), alt) for _, alt in alts],
                    printed_if_left_out=False,
                ),
                strict=True,
            )
        )
        edits = []
        for index, block in enumerate(document.blocks):
            if block.kind not in self.kinds:
                continue
            names = captions.get(index, []) or ([named[index]] if index in named else [])
            notice = wording.skipped(names, block.kind)
            what = names[0] if len(names) == 1 else f"this {_NAMES.get(block.kind, block.kind)}"
            shown = why = ""
            if not names and shows.get(index):
                notice += " " + wording.shows.format(shows[index])
                shown = " with its alt text"
            elif not names and index in shows:
                # read as a paragraph, the alt text is all left out (a link or citation alone)
                why = ", as its alt text holds nothing read aloud (a link or citation alone)"
            edits.append(
                Edit(
                    Span(index, 0, len(block.text)),
                    EditKind.REPLACE,
                    reason=f"{what} is not read; a short notice{shown} is read instead{why} (D-55)",
                    step=self.id,
                    replacement=notice,
                )
            )
        return edits


def _alt_text(items: Mapping[str, tuple[Page, Item]], block: Block) -> str:
    """The alt texts of the block's pictures, white space folded, joined by "; ", ending in
    a full stop unless it ends in other sentence punctuation; "" if none has any."""
    alts = []
    for part in block.parts:
        picture = items[part.item][1]
        if isinstance(picture, Picture) and (alt := " ".join(picture.alt.split())):
            alts.append(alt)
    joined = "; ".join(alts)
    return joined if not joined or joined[-1] in ".!?\u2026" else joined + "."


class FormulaNoticeStep(_NoticeStep):
    """A display formula is read as "Formula 4 is skipped." (FX-01)."""

    id = "formula-notices"
    category = Category.FORMULAS
    kinds = frozenset({BlockKind.FORMULA})


class TableFigureNoticeStep(_NoticeStep):
    """A table or figure is read as "Table 2 is skipped." (FX-02)."""

    id = "table-figure-notices"
    category = Category.TABLES_AND_FIGURES
    kinds = frozenset({BlockKind.TABLE, BlockKind.FIGURE})


class CodeNoticeStep(_NoticeStep):
    """A code block is read as "A code block is skipped." (#280, D-545)."""

    id = "code-notices"
    category = Category.CODE
    kinds = frozenset({BlockKind.CODE})


# the notice steps, to ask which placeholder a run replaces by its notice
_NOTICE_STEPS = (FormulaNoticeStep(), TableFigureNoticeStep(), CodeNoticeStep())


def notice_read(block: Block, context: StepContext) -> bool:
    """True if a notice is read in place of the block: a notice step for its kind handles the
    job's language and its category is on. Otherwise a placeholder's printed text is read, and
    the steps that clean text clean it like any block's (#463)."""
    return any(
        block.kind in step.kinds
        and step.category not in context.switched_off
        and step.handles(context.language)
        for step in _NOTICE_STEPS
    )
