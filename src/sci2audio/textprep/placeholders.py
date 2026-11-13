"""Formulas, tables and figures are not read; a short notice says so (FX-01, FX-02, D-55).

Layout keeps each display formula, table and figure as a placeholder block (D-63), with its
caption as a block of its own that points at it (`describes`) and a formula's printed number
as its label. Each placeholder's whole text is replaced by one short notice that names it
(Q3, D-145): through the labels of the captions that describe it, as printed ("Table 2",
"Algorithm 1"; a short "Fig. 3" read "Figure 3"), else through a formula's own number
("Formula 16a"), else without a name ("A figure is skipped."). The caption is not repeated:
it reads as printed, in its printed place, and already starts with its label.

Formulas and tables-and-figures are separate categories (D-108), so they are two steps.
"""

from __future__ import annotations

from sci2audio.core import BlockKind, Document, Edit, EditKind, Span
from sci2audio.textprep.steps import Category, Stage, StepContext, TextStep
from sci2audio.textprep.wording import wording_for


class _NoticeStep(TextStep):
    """Replace each placeholder block of the given kinds by its notice."""

    kinds: frozenset[BlockKind]
    languages = ("en",)
    stage = Stage.BLOCK

    def find(self, document: Document, context: StepContext) -> list[Edit]:
        wording = wording_for(context.language)
        captions: dict[int, list[str]] = {}
        for block in document.blocks:
            if block.describes is not None and block.label:
                captions.setdefault(block.describes, []).append(wording.label(block.label))
        edits = []
        for index, block in enumerate(document.blocks):
            if block.kind not in self.kinds:
                continue
            names = captions.get(index, [])
            if not names and block.kind is BlockKind.FORMULA and block.label:
                names = [wording.formula.format(block.label)]
            notice = wording.skipped(names, block.kind)
            what = names[0] if len(names) == 1 else f"this {block.kind}"
            edits.append(
                Edit(
                    Span(index, 0, len(block.text)),
                    EditKind.REPLACE,
                    reason=f"{what} is not read; a short notice is read instead (D-55)",
                    step=self.id,
                    replacement=notice,
                )
            )
        return edits


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
