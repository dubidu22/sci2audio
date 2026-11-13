"""Small valid documents for tests, built from block kinds and texts."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence

from sci2audio.core import (
    Block,
    BlockKind,
    Content,
    Document,
    Page,
    Part,
    ScriptPiece,
    Section,
    Source,
    SourceFormat,
    TextLine,
    TextRun,
)

BlockLike = Block | tuple[BlockKind | str, str]


def make_document(
    blocks: Iterable[BlockLike],
    language: str = "en",
    name: str = "test.txt",
    *,
    tags: Mapping[int, Sequence[tuple[int, int, str]]] | None = None,
    sections: Sequence[Section] = (),
) -> Document:
    """A document of these blocks on one page, one text line per printed line.

    Each block is a `Block` (its parts are ignored and made new) or a `(kind, text)` pair.
    Captions keep `describes`, furniture keeps its role, labels are kept as given.
    `tags` gives, per block index, character ranges `(start, end, tag)` that become runs of
    their own with that source tag, e.g. `(10, 11, "sup")` for a superscript footnote mark;
    a range may not cross a line break. `sections` is the document's section tree.
    """
    tags = tags or {}
    lines: list[TextLine] = []
    made: list[Block] = []
    for number, given in enumerate(blocks):
        block = given if isinstance(given, Block) else Block(BlockKind(given[0]), given[1])
        ranges = sorted(tags.get(number, ()))
        parts, start = [], 0
        for line_number, line in enumerate(block.text.split("\n")):
            if line:
                line_id = f"b{number}l{line_number}"
                lines.append(TextLine(line_id, _runs(line, start, ranges)))
                parts.append(Part(line_id, start))
            start += len(line) + 1
        made.append(
            Block(
                block.kind,
                block.text,
                tuple(parts),
                describes=block.describes,
                role=block.role,
                label=block.label,
            )
        )
    content = Content(Source(name, SourceFormat.TEXT), (Page(1, tuple(lines)),))
    return Document(
        content=content, language=language, blocks=tuple(made), sections=tuple(sections)
    )


def _runs(line: str, offset: int, ranges: Sequence[tuple[int, int, str]]) -> tuple[TextRun, ...]:
    """The line cut into runs: each tagged range that lies in it is a run with its tag."""
    runs, cursor = [], 0
    for start, end, tag in ranges:
        a, b = start - offset, end - offset
        if b <= 0 or a >= len(line):
            continue
        if a < cursor or b > len(line) or a >= b:
            raise ValueError(f"tagged range {start}-{end} must lie inside one line, in order")
        if a > cursor:
            runs.append(TextRun(line[cursor:a]))
        runs.append(TextRun(line[a:b], tags=(tag,)))
        cursor = b
    if cursor < len(line):
        runs.append(TextRun(line[cursor:]))
    return tuple(runs)


def rebuilt_from_script(document: Document, script: Sequence[ScriptPiece]) -> Document:
    """The document as it reads after the edits: same blocks and kinds, the script's text.

    Each block's text is its pieces' text joined (line breaks kept); pauses carry no text.
    A label no longer printed in the text is dropped; the section tree is kept. Used to
    check that running the steps a second time changes nothing more (idempotence).
    """
    texts = [""] * len(document.blocks)
    for piece in script:
        texts[piece.span.block] += piece.text
    blocks = []
    for block, text in zip(document.blocks, texts, strict=True):
        label = block.label if block.label and block.label in text else ""
        blocks.append(
            Block(block.kind, text, describes=block.describes, role=block.role, label=label)
        )
    return make_document(
        blocks, document.language, document.content.source.name, sections=document.sections
    )
