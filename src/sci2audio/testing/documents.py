"""Small valid documents for tests, built from block kinds and texts."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from sci2audio.core import (
    Block,
    BlockKind,
    Content,
    Document,
    Page,
    Part,
    ScriptPiece,
    Source,
    SourceFormat,
    TextLine,
    TextRun,
)

BlockLike = Block | tuple[BlockKind | str, str]


def make_document(
    blocks: Iterable[BlockLike], language: str = "en", name: str = "test.txt"
) -> Document:
    """A document of these blocks on one page, one text line per printed line.

    Each block is a `Block` (its parts are ignored and made new) or a `(kind, text)` pair.
    Captions keep `describes`, furniture keeps its role, labels are kept as given.
    """
    lines: list[TextLine] = []
    made: list[Block] = []
    for number, given in enumerate(blocks):
        block = given if isinstance(given, Block) else Block(BlockKind(given[0]), given[1])
        parts, start = [], 0
        for line_number, line in enumerate(block.text.split("\n")):
            if line:
                line_id = f"b{number}l{line_number}"
                lines.append(TextLine(line_id, (TextRun(line),)))
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
    return Document(content=content, language=language, blocks=tuple(made))


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
    rebuilt = make_document(blocks, document.language, document.content.source.name)
    return Document(
        content=rebuilt.content,
        language=rebuilt.language,
        blocks=rebuilt.blocks,
        sections=document.sections,
    )
