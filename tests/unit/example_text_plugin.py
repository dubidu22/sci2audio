"""A text-step plugin as a third party writes it: public names only (#216, docs/plugins.md)."""

import re

from sci2audio.textprep.api import (
    BlockKind,
    Category,
    Document,
    Edit,
    EditKind,
    Span,
    Stage,
    StepContext,
    TextStep,
)

_AMPERSAND = re.compile(r"(?<= )&(?= )")


class AmpersandStep(TextStep):
    """Reads a free-standing "&" in a paragraph as "and"."""

    id = "ampersand-and"
    languages = ("en",)
    category = Category.CHARACTERS
    stage = Stage.INLINE
    api_version = 1

    def find(self, document: Document, context: StepContext) -> list[Edit]:
        edits = []
        for index, block in enumerate(document.blocks):
            if block.kind is not BlockKind.PARAGRAPH:
                continue
            for match in _AMPERSAND.finditer(block.text):
                edits.append(
                    Edit(
                        Span(index, match.start(), match.end()),
                        EditKind.REPLACE,
                        reason='"&" is read as "and"',
                        step=self.id,
                        replacement="and",
                    )
                )
        return edits


def make_step() -> AmpersandStep:
    """A factory, the other form an entry point may name."""
    return AmpersandStep()
