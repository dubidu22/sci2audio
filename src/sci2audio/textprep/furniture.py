"""Page furniture is not read (TP-01).

Layout marks running heads, page numbers, line numbers, side stamps and the like as
FURNITURE blocks (D-63, #31). `FurnitureStep` proposes one `remove` edit per furniture block,
so the report lists each one and the "Page furniture" switch can bring them back.

`HiddenRunStep` (#193) removes text that the file keeps from being shown or read inside a
line: a run tagged `hidden` or `aria-hidden` (D-306 records both), and an inline page-break
marker (`epub:pagebreak`, `role:doc-pagebreak`), which marks where a printed page began.
A whole-block edit would claim the block (D-105), so this is an inline step of its own, in
the same category: the "Page furniture" switch brings these runs back too. It is the first
inline step, so a link or citation inside a hidden run never wins over it. The links and
citations steps read the text without these runs (`hidden_removals`, `read_around`), as a
second run does, so a link with a page-break marker glued to it goes too (#434); the later
steps read it without them through `footnotes.unread_marks`.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import replace

from sci2audio.core import BlockKind, Document, Edit, EditKind, FurnitureRole, Span, TextLine
from sci2audio.textprep.placeholders import notice_read
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


# the tags of a run the file hides from the reader, and of an inline page-break marker
HIDDEN_TAGS = frozenset({"hidden", "aria-hidden"})
PAGE_BREAK_TAGS = frozenset({"epub:pagebreak", "role:doc-pagebreak"})
# a removal before one of these takes the white space before it ("text x." reads "text.")
_CLOSING = frozenset(",;:.!?)]")
# a reason quotes at most this many characters of the hidden text, so a long hidden passage
# gives a report line of usual length (#436)
QUOTED = 60


def removed_span(text: str, start: int, end: int) -> tuple[int, int]:
    """What removing `text[start:end]` covers: its text without the white space at its ends,
    and the white space before it too when the block ends, closing punctuation follows, or
    white space follows: "5 [run] m²" leaves "5 m²", the text without the run, which is what
    a second run reads (#445)."""
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    if end == len(text) or text[end] in _CLOSING or text[end].isspace():
        while start > 0 and text[start - 1].isspace():
            start -= 1
    return start, end


class HiddenRunStep(TextStep):
    """Remove hidden runs and inline page-break markers; one edit per stretch of them."""

    id = "hidden-runs"
    languages = (ANY_LANGUAGE,)
    category = Category.PAGE_FURNITURE
    stage = Stage.INLINE

    def find(self, document: Document, context: StepContext) -> list[Edit]:
        items = document.content.items()
        edits = []
        for index, block in enumerate(document.blocks):
            # furniture goes whole; a placeholder goes whole while its notice is read (#463)
            if block.kind is BlockKind.FURNITURE or notice_read(block, context):
                continue
            stretches: list[tuple[int, int, bool]] = []  # runs side by side make one
            for part in block.parts:
                line = items[part.item][1]
                if not isinstance(line, TextLine):
                    continue
                if block.text[part.start : part.start + len(line.text)] != line.text:
                    continue  # never point at other text
                offset = part.start
                for run in line.runs:
                    tags = set(run.tags)
                    end = offset + len(run.text)
                    if (HIDDEN_TAGS | PAGE_BREAK_TAGS) & tags and run.text.strip():
                        hidden = bool(HIDDEN_TAGS & tags)
                        if stretches and stretches[-1][1] == offset:
                            first, _, before = stretches.pop()
                            stretches.append((first, end, before or hidden))
                        else:
                            stretches.append((offset, end, hidden))
                    offset = end
            # the white space a removal takes before it stops at the text of the one before
            for start, end, hidden in stretches:
                start, end = removed_span(block.text, start, end)
                shown = " ".join(block.text[start:end].split())
                if len(shown) > QUOTED:
                    shown = shown[: QUOTED - 1].rstrip() + "\u2026"
                edits.append(
                    Edit(
                        Span(index, start, end),
                        EditKind.REMOVE,
                        reason=(
                            f'hidden text "{shown}" is not read (hidden in the file)'
                            if hidden
                            else f'page-break marker "{shown}" is not read'
                        ),
                        step=self.id,
                    )
                )
        return edits


def hidden_removals(document: Document, context: StepContext) -> dict[int, list[tuple[int, int]]]:
    """The spans `HiddenRunStep` removes, by block; none while "Page furniture" is switched
    off, as the runs are then read. The links and citations steps read the text without
    them, as a second run does (#434)."""
    if HiddenRunStep.category in context.switched_off:
        return {}
    removals: dict[int, list[tuple[int, int]]] = {}
    for edit in HiddenRunStep().find(document, context):
        removals.setdefault(edit.span.block, []).append((edit.span.start, edit.span.end))
    return removals


def read_around(text: str, unread: Sequence[tuple[int, int]]) -> tuple[str, list[int]]:
    """The text without the `unread` spans, and where each of its characters stands in
    `text`, with one more entry for its end."""
    skipped = {at for start, end in unread for at in range(start, end)}
    kept = [at for at in range(len(text)) if at not in skipped]
    return "".join(text[at] for at in kept), [*kept, len(text)]


def edits_around(
    edits: Iterable[Edit], kept: Sequence[int], unread: Sequence[tuple[int, int]]
) -> list[Edit]:
    """Edits of a text read without its `unread` spans (`read_around`), put back on the
    printed text. An edit covers what it covers there but the unread spans inside, which
    `HiddenRunStep` removes, so it never overlaps them: a link with a page-break marker
    inside becomes the pieces either side of it. The first piece keeps a replacement; the
    others are removed with the same reason."""
    placed = []
    for edit in edits:
        span = edit.span
        start = kept[span.start]
        end = kept[span.end - 1] + 1 if span.end > span.start else start
        pieces, at = [], start
        for skip_start, skip_end in sorted(unread):
            if at <= skip_start and skip_end <= end:
                if skip_start > at:
                    pieces.append((at, skip_start))
                at = skip_end
        if at < end or not pieces:
            pieces.append((at, end))
        for number, (piece_start, piece_end) in enumerate(pieces):
            if number == 0:
                placed.append(replace(edit, span=Span(span.block, piece_start, piece_end)))
            else:
                placed.append(
                    Edit(
                        Span(span.block, piece_start, piece_end),
                        EditKind.REMOVE,
                        edit.reason,
                        edit.step,
                    )
                )
    return placed
