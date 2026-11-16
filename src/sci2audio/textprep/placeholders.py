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

from collections.abc import Mapping

from sci2audio.core import Block, BlockKind, Document, Edit, EditKind, Item, Page, Picture, Span
from sci2audio.textprep.numbers_de import label_numbers_read
from sci2audio.textprep.steps import Category, Stage, StepContext, TextStep
from sci2audio.textprep.wording import Wording, wording_for

_NAMES = {BlockKind.CODE: "code block"}  # how a reason names a kind, if not by its value


def _label(wording: Wording, block: Block, numbers: bool) -> str:
    """A caption label as the notice names it: its word in full, and with `numbers` (German,
    the numbers step switched on) its numbers read as the German numbers step reads them in
    the caption, in the caption's own context (#249)."""
    label = wording.label(block.label)
    if not numbers:
        return label
    after = block.text[len(block.label) :] if block.text.startswith(block.label) else ""
    return label_numbers_read(label, after)


class _NoticeStep(TextStep):
    """Replace each placeholder block of the given kinds by its notice."""

    kinds: frozenset[BlockKind]
    languages = ("en", "de")
    stage = Stage.BLOCK

    def find(self, document: Document, context: StepContext) -> list[Edit]:
        wording = wording_for(context.language)
        # the label's numbers as the German numbers step reads the caption, unless it is off
        numbers = (
            context.language.split("-", 1)[0].lower() == "de"
            and Category.NUMBERS_AND_UNITS not in context.switched_off
        )
        captions: dict[int, list[str]] = {}
        for block in document.blocks:
            if block.describes is not None and block.label:
                captions.setdefault(block.describes, []).append(_label(wording, block, numbers))
        items = document.content.items()
        edits = []
        for index, block in enumerate(document.blocks):
            if block.kind not in self.kinds:
                continue
            names = captions.get(index, [])
            if not names and block.kind is BlockKind.FORMULA and block.label:
                names = [wording.formula.format(block.label)]
            notice = wording.skipped(names, block.kind)
            what = names[0] if len(names) == 1 else f"this {_NAMES.get(block.kind, block.kind)}"
            shown = ""
            if not names and block.kind is BlockKind.FIGURE and (alt := _alt_text(items, block)):
                notice += " " + wording.shows.format(alt)
                shown = " with its alt text"
            edits.append(
                Edit(
                    Span(index, 0, len(block.text)),
                    EditKind.REPLACE,
                    reason=f"{what} is not read; a short notice{shown} is read instead (D-55)",
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
