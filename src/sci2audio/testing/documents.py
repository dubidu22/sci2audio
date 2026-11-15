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
    tags: Mapping[int, Sequence[tuple[int, int, str | tuple[str, ...]]]] | None = None,
    sections: Sequence[Section] = (),
    pages: Mapping[int, int] | None = None,
) -> Document:
    """A document of these blocks, one text line per printed line, all on page 1 unless
    `pages` says otherwise.

    Each block is a `Block` (its parts are ignored and made new) or a `(kind, text)` pair.
    Captions keep `describes`, furniture keeps its role, labels are kept as given.
    `tags` gives, per block index, character ranges `(start, end, tag)` that become runs of
    their own with that source tag, e.g. `(10, 11, "sup")` for a superscript footnote mark,
    or with several tags, e.g. `(10, 11, ("sup", "role:doc-noteref", "link:b3l0"))`; a range
    may not cross a line break. Line ids are `b<block>l<line>` (line counted in the block's
    text from 0), so a `link:` tag can point at a block's first line. `sections` is the
    document's section tree. `pages` gives, per block index, the page a block stands on (1
    if not given); pages may not go back, and a page in between with no block is empty
    (D-426).
    """
    tags = tags or {}
    pages = pages or {}
    lines: dict[int, list[TextLine]] = {}
    made: list[Block] = []
    last_page = 1
    for number, given in enumerate(blocks):
        page = pages.get(number, 1)
        if page < last_page:
            raise ValueError(f"block {number} is on page {page}, after page {last_page}")
        last_page = page
        block = given if isinstance(given, Block) else Block(BlockKind(given[0]), given[1])
        ranges = sorted(tags.get(number, ()), key=lambda r: (r[0], r[1]))
        parts, start = [], 0
        for line_number, line in enumerate(block.text.split("\n")):
            if line:
                line_id = f"b{number}l{line_number}"
                lines.setdefault(page, []).append(TextLine(line_id, _runs(line, start, ranges)))
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
    content = Content(
        Source(name, SourceFormat.TEXT),
        tuple(Page(n, tuple(lines.get(n, ()))) for n in range(1, last_page + 1)),
    )
    return Document(
        content=content, language=language, blocks=tuple(made), sections=tuple(sections)
    )


def _runs(
    line: str, offset: int, ranges: Sequence[tuple[int, int, str | tuple[str, ...]]]
) -> tuple[TextRun, ...]:
    """The line cut into runs: each tagged range that lies in it is a run with its tags."""
    runs, cursor = [], 0
    for start, end, tag in ranges:
        a, b = start - offset, end - offset
        if b <= 0 or a >= len(line):
            continue
        if a < cursor or b > len(line) or a >= b:
            raise ValueError(f"tagged range {start}-{end} must lie inside one line, in order")
        if a > cursor:
            runs.append(TextRun(line[cursor:a]))
        runs.append(TextRun(line[a:b], tags=(tag,) if isinstance(tag, str) else tuple(tag)))
        cursor = b
    if cursor < len(line):
        runs.append(TextRun(line[cursor:]))
    return tuple(runs)


def rebuilt_from_script(document: Document, script: Sequence[ScriptPiece]) -> Document:
    """The document as it reads after the edits: same blocks and kinds, the script's text.

    Each block's text is its pieces' text joined (line breaks kept); pauses carry no text.
    A label stays while the new text prints it; one a step rewrote becomes what the script
    reads over its printed words ("Abb. 1" spelled out reads "Abbildung 1", #324); a label
    whose words were all removed is dropped. The section tree is kept. Used to check that
    running the steps a second time changes nothing more (idempotence).
    """
    pieces: list[list[ScriptPiece]] = [[] for _ in document.blocks]
    for piece in script:
        pieces[piece.span.block].append(piece)
    blocks = []
    for block, own in zip(document.blocks, pieces, strict=True):
        text = "".join(piece.text for piece in own)
        blocks.append(
            Block(
                block.kind,
                text,
                describes=block.describes,
                role=block.role,
                label=_rebuilt_label(block, own, text),
            )
        )
    return make_document(
        blocks, document.language, document.content.source.name, sections=document.sections
    )


def _rebuilt_label(block: Block, pieces: Sequence[ScriptPiece], text: str) -> str:
    """The block's label as the rebuilt text prints it, or "" if its words went (#324).

    A label the new text still prints stays. Otherwise, in a block that is read (not a
    placeholder, whose whole text a notice replaces), the label is mapped through the
    script: kept characters of its printed span stay, and a replacement lying inside the
    span stands for its part ("Abb. 1" spelled out becomes "Abbildung 1"). A replacement
    running past the label's edge cannot be mapped, and the label goes.
    """
    if not block.label:
        return ""
    if block.label in text:
        return block.label
    start = block.text.find(block.label)
    if block.is_placeholder or start < 0:
        return ""
    label = _mapped(block.text, pieces, start, start + len(block.label))
    if label and label == label.strip() and len(label.splitlines()) == 1 and label in text:
        return label
    return ""


def _mapped(printed: str, pieces: Sequence[ScriptPiece], start: int, end: int) -> str | None:
    """What the script reads over characters `start` to `end` of the printed text, or None
    if a replacement runs past either edge."""
    read = []
    for piece in pieces:
        span = piece.span
        if piece.pause or span.end <= start or span.start >= end:
            continue
        if piece.text == printed[span.start : span.end]:  # kept as printed
            read.append(printed[max(start, span.start) : min(end, span.end)])
        elif start <= span.start and span.end <= end:
            read.append(piece.text)
        else:
            return None
    return "".join(read)
