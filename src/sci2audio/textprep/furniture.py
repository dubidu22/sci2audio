"""Page furniture is not read (TP-01).

Layout marks running heads, page numbers, line numbers, side stamps and the like as
FURNITURE blocks (D-63, #31). This step proposes one `remove` edit per furniture block, so
the report lists each one and the "Page furniture" switch can bring them back.
"""

from __future__ import annotations

from sci2audio.core import BlockKind, Document, Edit, EditKind, FurnitureRole, Span
from sci2audio.textprep.steps import ANY_LANGUAGE, Category, Stage, StepContext, TextStep

_ROLE_NAMES = {
    FurnitureRole.PAGE_NUMBER: "page number",
    FurnitureRole.RUNNING_HEAD: "running head",
    FurnitureRole.FOOTER: "footer",
    FurnitureRole.SIDE_STAMP: "side stamp",
    FurnitureRole.LINE_NUMBER: "line numbers",
    FurnitureRole.CONTENTS: "table of contents",
    FurnitureRole.SIDEBAR: "sidebar",
}


class FurnitureStep(TextStep):
    """Remove every furniture block that has text; one edit per block."""

    id = "page-furniture"
    languages = (ANY_LANGUAGE,)
    category = Category.PAGE_FURNITURE
    stage = Stage.BLOCK

    def find(self, document: Document, context: StepContext) -> list[Edit]:
        edits = []
        for index, block in enumerate(document.blocks):
            # a furniture block without text (a logo on every page, D-91) has nothing to read
            if block.kind is BlockKind.FURNITURE and block.text:
                what = _ROLE_NAMES[block.role] if block.role else "unknown kind"
                edits.append(
                    Edit(
                        Span(index, 0, len(block.text)),
                        EditKind.REMOVE,
                        reason=f"page furniture ({what}) is not read",
                        step=self.id,
                    )
                )
        return edits
