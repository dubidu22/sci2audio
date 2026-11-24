"""Small valid documents for tests, built from block kinds and texts."""

from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping, Sequence

from sci2audio.core import (
    Block,
    BlockKind,
    Content,
    Document,
    Item,
    Page,
    Part,
    Picture,
    ScriptPiece,
    Section,
    Source,
    SourceFormat,
    TextLine,
    TextRun,
)
from sci2audio.textprep import read_over
from sci2audio.textprep.footnotes import raised_exponents

BlockLike = Block | tuple[BlockKind | str, str]


def make_document(
    blocks: Iterable[BlockLike],
    language: str = "en",
    name: str = "test.txt",
    *,
    tags: Mapping[int, Sequence[tuple[int, int, str | tuple[str, ...]]]] | None = None,
    sections: Sequence[Section] = (),
    pages: Mapping[int, int] | None = None,
    pictures: Mapping[int, Sequence[str]] | None = None,
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
    (D-426). `pictures` gives, per block index, the alt texts of the block's pictures ("" for
    none): each becomes a `Picture` on the block's page, id `b<block>p<picture>`, with a part
    at the end of the block's text, after its lines (#191).
    """
    tags = tags or {}
    pages = pages or {}
    pictures = pictures or {}
    lines: dict[int, list[TextLine]] = {}
    images: dict[int, list[Picture]] = {}
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
        for picture_number, alt in enumerate(pictures.get(number, ())):
            picture = Picture(f"b{number}p{picture_number}", alt=alt)
            images.setdefault(page, []).append(picture)
            parts.append(Part(picture.id, len(block.text)))
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
        tuple(
            Page(n, tuple(lines.get(n, ())), tuple(images.get(n, ())))
            for n in range(1, last_page + 1)
        ),
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


def rebuilt_from_script(
    document: Document, script: Sequence[ScriptPiece], *, own_output: Collection[int] = ()
) -> Document:
    """The document as it reads after the edits: same blocks and kinds, the script's text.

    Each block's text is its pieces' text joined (line breaks kept); pauses carry no text.
    A label stays while the new text prints it; a caption label a step rewrote becomes what
    the script reads over its printed words (`textprep.read_over`: "Abb. 1" spelled out
    reads "Abbildung 1", #324); any other label is dropped. A placeholder (formula, table,
    figure, code) comes back as printed, with its label, not as its notice: a notice is made
    from the printed placeholder and its captions only, so the second run makes it again,
    however it reads the label ("Formel 3 Punkt 2", D-707); its text is unchanged, so its
    runs keep their tags, and a hidden run or page-break marker in it is seen again (#463).
    The section tree is kept, and so is each block's pictures' alt text, which the script
    cannot carry (#191).
    Used to check that running the steps a second time changes nothing more (idempotence).

    The placeholders whose indices are in `own_output` come back as the script reads them
    instead, like any other block, without run tags: the conformance suite checks on them
    that a step's edits inside a placeholder change nothing more when it reads its own
    output (D-710).
    """
    pieces: list[list[ScriptPiece]] = [[] for _ in document.blocks]
    for piece in script:
        pieces[piece.span.block].append(piece)
    items = document.content.items()
    blocks, pictures, tags = [], {}, {}
    raised = raised_exponents(document)
    for index, (block, own) in enumerate(zip(document.blocks, pieces, strict=True)):
        if alts := [
            item.alt for part in block.parts if isinstance(item := items[part.item][1], Picture)
        ]:
            pictures[index] = alts
        if block.is_placeholder and index not in own_output:
            # a notice is made from the printed placeholder and its captions only, so the
            # placeholder comes back as printed and the second run makes the same notice
            # again, however the notice reads its label (D-707)
            blocks.append(Block(block.kind, block.text, role=block.role, label=block.label))
            if kept := _raised_tags(_run_tags(block, items), raised.get(index, ())):
                tags[index] = kept  # the printed text is unchanged, so its run tags still fit
            continue
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
        blocks,
        document.language,
        document.content.source.name,
        sections=document.sections,
        pictures=pictures,
        tags=tags,
    )


def _raised_tags(
    kept: list[tuple[int, int, str | tuple[str, ...]]], raised: Iterable[tuple[int, int]]
) -> list[tuple[int, int, str | tuple[str, ...]]]:
    """The tagged runs with each raised exponent that only its size and rise show tagged
    `sup` too, so a placeholder rebuilt as printed reads its powers again (#576, #589): the
    rebuilt runs carry tags, not sizes or boxes."""
    added = [
        (start, end, "sup")
        for start, end in raised
        if not any(s < end and start < e for s, e, _ in kept)
    ]
    return sorted([*kept, *added], key=lambda found: (found[0], found[1]))


def _run_tags(
    block: Block, items: Mapping[str, tuple[Page, Item]]
) -> list[tuple[int, int, str | tuple[str, ...]]]:
    """The block's tagged runs as (start, end, tags) in its text, so a placeholder rebuilt
    as printed keeps its hidden runs and page-break markers (#463)."""
    found: list[tuple[int, int, str | tuple[str, ...]]] = []
    for part in block.parts:
        line = items[part.item][1]
        if not isinstance(line, TextLine):
            continue
        if block.text[part.start : part.start + len(line.text)] != line.text:
            continue  # never point at other text
        offset = part.start
        for run in line.runs:
            if run.tags:
                # a tagged range may not cross a line break or go back over one before it
                start = offset
                for piece in run.text.split("\n"):
                    if piece and (not found or start >= found[-1][1]):
                        found.append((start, start + len(piece), tuple(run.tags)))
                    start += len(piece) + 1
            offset += len(run.text)
    return found


def _rebuilt_label(block: Block, pieces: Sequence[ScriptPiece], text: str) -> str:
    """The block's label as the rebuilt text prints it, or "" if its words went (#324).

    A label the new text still prints stays. Otherwise only a caption's label is mapped
    through the script: kept characters of its printed span stay, and a replacement lying
    inside the span stands for its part ("Abb. 1" spelled out becomes "Abbildung 1"). A
    replacement running past the label's edge cannot be mapped, and the label goes. Other
    labels are not mapped: a step replaces a footnote's mark with its introduction or a
    placeholder's text with a notice, which is no label (#353).
    """
    if not block.label:
        return ""
    if block.label in text:
        return block.label
    start = block.text.find(block.label)
    if block.kind is not BlockKind.CAPTION or start < 0:
        return ""
    label = read_over(block.text, pieces, start, start + len(block.label))
    # defensive: `Block` raises on a label that is untrimmed, more than one line or not in
    # the text; such a mapped label is dropped instead (mapped pieces run in script order,
    # so their text is in the new text)
    if label and label == label.strip() and len(label.splitlines()) == 1 and label in text:
        return label
    return ""
