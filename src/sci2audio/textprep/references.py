"""The reference list is not read (TP-06, D-146).

A section whose title is a usual name of a reference list (`REFERENCE_TITLES`), after a
printed number if there is one ("7 References"), is left out one block at a time,
its heading included, at any level of the section tree. The "Reference list" switch keeps
it. Footnotes inside the section are kept, since their marks stand in the body text (a note
at the foot of the page where the list starts), and furniture is the furniture step's.

A reference list printed without a heading (PRL style) is not found here (issue filed).
"""

from __future__ import annotations

import re
from collections.abc import Iterator

from sci2audio.core import BlockKind, Document, Edit, EditKind, Section, Span
from sci2audio.textprep.steps import Category, Stage, StepContext, TextStep

# the usual names of a reference list, English only for v1.0: D-83's two and the rest of
# D-132's English list, so the step and the app's chapter choice (#70) agree (layout keeps
# its own list in its settings; textprep may not import layout)
REFERENCE_TITLES = (
    "References",
    "Bibliography",
    "Reference list",
    "Works cited",
    "Literature cited",
)

# Matched as the app matches a chapter title (`app.chapters.is_reference_title`, D-132), so
# the step and the chapter choice agree; a test keeps the two equal: white space read as one
# space, an optional printed number ("7", "7.", "8.1", "A", "A.1", "IV.") taken off, then the
# name without case and without a closing "." or ":" ("REFERENCES", "References:").
_NUMBER = re.compile(r"\A(?:\d{1,2}|[A-Z]|[IVX]{1,5})(?:\.\d{1,2})*\.?\s+")
_NAMES = frozenset(name.casefold() for name in REFERENCE_TITLES)


def is_reference_title(title: str) -> bool:
    """True if a section title names a reference list ("7 References", "Bibliography:")."""
    name = _NUMBER.sub("", " ".join(title.split()), count=1)
    return name.casefold().rstrip(".:") in _NAMES


_KEPT = frozenset({BlockKind.FOOTNOTE, BlockKind.FURNITURE})


class ReferenceListStep(TextStep):
    """Remove every block of a reference-list section, one edit per block."""

    id = "reference-list"
    languages = ("en",)
    category = Category.REFERENCES
    stage = Stage.BLOCK

    def find(self, document: Document, context: StepContext) -> list[Edit]:
        edits = []
        indexes: set[int] = set()
        for section in _sections(document.sections):
            if is_reference_title(section.title):
                indexes.update(range(section.start, section.end))
        for index in sorted(indexes):
            block = document.blocks[index]
            if block.text and block.kind not in _KEPT:
                edits.append(
                    Edit(
                        Span(index, 0, len(block.text)),
                        EditKind.REMOVE,
                        reason="the reference list is not read",
                        step=self.id,
                    )
                )
        return edits


def _sections(sections: tuple[Section, ...]) -> Iterator[Section]:
    for section in sections:
        yield section
        yield from _sections(section.children)
