"""Unit tests for the core objects (issue #17): examples, refused values, export golden file.

When the export format changes on purpose, accept the new golden file with
`uv run pytest --snapshot-update` and explain the diff in the PR (D-60).
"""

import dataclasses
from dataclasses import replace

import pytest
from syrupy.assertion import SnapshotAssertion

from sci2audio.core import (
    AudioChunk,
    Block,
    BlockKind,
    Box,
    Content,
    Document,
    Drawing,
    Edit,
    EditKind,
    FurnitureRole,
    Metadata,
    OverlappingEditsError,
    Page,
    Part,
    Picture,
    ScriptPiece,
    Section,
    Source,
    SourceFormat,
    Span,
    SpanError,
    TextLine,
    TextRun,
    apply_edits,
    from_data,
    to_data,
)


def line(item: str, text: str, y: float, size: float = 10) -> TextLine:
    return TextLine(item, (TextRun(text, "Times-Roman", size),), Box(72, y, 540, y + size))


# A made-up two-page paper, recorded by extraction and laid out with one block of every kind.
CONTENT = Content(
    source=Source("paper.pdf", SourceFormat.PDF, sha256="ab12"),
    metadata=Metadata(title="A Small Paper", authors=("A. Author", "B. Author"), date="2024"),
    pages=(
        Page(
            1,
            (line("p1-l1", "1 Introduction", 90, 14), line("p1-l2", "Sound helps [3].", 760)),
            width=612,
            height=792,
        ),
        Page(
            2,
            lines=(
                line("p2-l1", "It runs on.", 72),
                line("p2-l2", "E = mc^2 (1)", 100),
                line("p2-l3", "Table 1: Results.", 310),
                line("p2-l4", "A Small Paper", 20, 8),
                line("p2-l5", "Figure 1: A chart.", 600),
                line("p2-l6", "First point", 650),
                line("p2-l7", "1 A note.", 760, 8),
            ),
            pictures=(Picture("p2-pic1", Box(72, 400, 540, 590)),),
            drawings=(
                Drawing("p2-d1", Box(72, 130, 540, 130.5)),
                Drawing("p2-d2", Box(72, 300, 540, 300.5)),
            ),
            width=612,
            height=792,
        ),
    ),
)

PAPER = Document(
    content=CONTENT,
    language="en",
    blocks=(
        Block(BlockKind.HEADING, "1 Introduction", (Part("p1-l1"),), label="1"),
        Block(
            BlockKind.PARAGRAPH, "Sound helps [3].\nIt runs on.", (Part("p1-l2"), Part("p2-l1", 17))
        ),
        Block(BlockKind.FORMULA, "E = mc^2 (1)", (Part("p2-l2"),), label="1"),
        Block(BlockKind.TABLE, "", (Part("p2-d1"), Part("p2-d2"))),
        Block(
            BlockKind.CAPTION, "Table 1: Results.", (Part("p2-l3"),), describes=3, label="Table 1"
        ),
        Block(BlockKind.FIGURE, "", (Part("p2-pic1"),)),
        Block(
            BlockKind.CAPTION,
            "Figure 1: A chart.",
            (Part("p2-l5"),),
            describes=5,
            label="Figure 1",
        ),
        Block(BlockKind.LIST_ITEM, "First point", (Part("p2-l6"),)),
        Block(BlockKind.FOOTNOTE, "1 A note.", (Part("p2-l7"),), label="1"),
        Block(
            BlockKind.FURNITURE,
            "A Small Paper",
            (Part("p2-l4"),),
            role=FurnitureRole.RUNNING_HEAD,
        ),
    ),
    sections=(Section("1 Introduction", 1, 0, 10, (Section("1.1 Results", 2, 2, 9),)),),
    page_labels=("39", ""),
)

CITATION = Edit(Span(1, 11, 15), EditKind.REMOVE, reason="numeric citation", step="citations")
FORMULA = Edit(Span(2, 0, 12), EditKind.REPLACE, "formula skipped (D-55)", "formulas", "A formula.")
TABLE = Edit(Span(3, 0, 0), EditKind.REPLACE, "table skipped", "tables", "A table.")
PAUSE = Edit(Span(0, 14, 14), EditKind.PAUSE, reason="after a heading", step="pauses")


def test_apply_edits_builds_the_script() -> None:
    pieces = apply_edits(PAPER, [FORMULA, CITATION, TABLE, PAUSE])
    assert pieces[:5] == (
        ScriptPiece("1 Introduction", Span(0, 0, 14)),
        ScriptPiece("", Span(0, 14, 14), pause=True),
        ScriptPiece("Sound helps", Span(1, 0, 11)),
        ScriptPiece(".\nIt runs on.", Span(1, 15, 28)),
        ScriptPiece("A formula.", Span(2, 0, 12)),
    )
    assert pieces[5] == ScriptPiece("A table.", Span(3, 0, 0))


def test_part_at_finds_the_page_of_a_position() -> None:
    items = CONTENT.items()
    paragraph = PAPER.blocks[1]
    pages = [items[paragraph.part_at(offset).item][0].number for offset in (0, 16, 17, 27)]
    assert pages == [1, 1, 2, 2]
    assert Block(BlockKind.PARAGRAPH, "x").part_at(0) is None


def test_placeholders() -> None:
    kinds = [b.kind for b in PAPER.blocks if b.is_placeholder]
    assert kinds == [BlockKind.FORMULA, BlockKind.TABLE, BlockKind.FIGURE]


def test_furniture_keeps_its_role_and_pages_their_printed_labels() -> None:
    """#31: what each furniture block is, and the page numbers as printed."""
    roles = [b.role for b in PAPER.blocks if b.role]
    assert roles == [FurnitureRole.RUNNING_HEAD]
    assert [PAPER.page_label(n) for n in (1, 2)] == ["39", ""]
    assert replace(PAPER, page_labels=()).page_label(1) == ""
    for missing in (0, 3):
        with pytest.raises(ValueError, match=r"not in 1\.\.2"):
            PAPER.page_label(missing)


def test_blocks_keep_their_printed_labels() -> None:
    """#21: heading numbers, formula numbers, caption labels and footnote marks, as printed."""
    labels = [(b.kind, b.label) for b in PAPER.blocks if b.label]
    assert labels == [
        (BlockKind.HEADING, "1"),
        (BlockKind.FORMULA, "1"),
        (BlockKind.CAPTION, "Table 1"),
        (BlockKind.CAPTION, "Figure 1"),
        (BlockKind.FOOTNOTE, "1"),
    ]
    assert PAPER.blocks[7].label == ""  # a list item printed without a marker
    Block(BlockKind.LIST_ITEM, "(a) First", label="(a)")


def test_captions_link_to_what_they_describe() -> None:
    linked = {i: b.describes for i, b in enumerate(PAPER.blocks) if b.describes is not None}
    assert {PAPER.blocks[t].kind for t in linked.values()} == {BlockKind.TABLE, BlockKind.FIGURE}


def test_objects_are_frozen() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        PAPER.blocks[0].text = "changed"  # type: ignore[misc]


def test_overlap_error_names_both_steps() -> None:
    other = Edit(Span(1, 12, 13), EditKind.REPLACE, "digit", "numbers", "three")
    with pytest.raises(OverlappingEditsError, match=r"'citations'.*'numbers'"):
        apply_edits(PAPER, [other, CITATION])


@pytest.mark.parametrize(
    "span",
    [Span(1, 0, 0), Span(1, 28, 28), Span(1, 11, 11)],
    ids=["start", "end", "at-removed-span-start"],
)
def test_a_position_at_the_edge_of_a_span_is_no_overlap(span: Span) -> None:
    pause = Edit(span, EditKind.PAUSE, "pause", "pauses")
    apply_edits(PAPER, [CITATION, pause])


def test_two_edits_at_one_position_overlap() -> None:
    insert = Edit(Span(0, 14, 14), EditKind.REPLACE, "colon", "headings", ":")
    with pytest.raises(OverlappingEditsError):
        apply_edits(PAPER, [PAUSE, insert])


def test_edit_outside_the_document_is_refused() -> None:
    with pytest.raises(SpanError, match="block 12"):
        apply_edits(PAPER, [Edit(Span(12, 0, 1), EditKind.REMOVE, "r", "s")])
    with pytest.raises(SpanError, match="ends after"):
        PAPER.text_of(Span(0, 0, 99))


@pytest.mark.parametrize(
    "make",
    [
        lambda: Span(0, 3, 2),
        lambda: Span(-1, 0, 0),
        lambda: Edit(Span(0, 0, 1), EditKind.REMOVE, "", "step"),
        lambda: Edit(Span(0, 0, 1), EditKind.REMOVE, "reason", " "),
        lambda: Edit(Span(0, 0, 0), EditKind.REMOVE, "reason", "step"),
        lambda: Edit(Span(0, 0, 1), EditKind.REMOVE, "reason", "step", "text"),
        lambda: Edit(Span(0, 0, 1), EditKind.REPLACE, "reason", "step"),
        lambda: Edit(Span(0, 0, 1), EditKind.PAUSE, "reason", "step"),
        lambda: Block(BlockKind.PARAGRAPH, "ab", (Part("a", 1), Part("b", 0))),
        lambda: Block(BlockKind.PARAGRAPH, "ab", (Part("a", 3),)),
        lambda: Block(BlockKind.PARAGRAPH, "ab", (Part("a", -1),)),
        lambda: Block(BlockKind.PARAGRAPH, "ab", describes=0),
        lambda: Block(BlockKind.PARAGRAPH, "ab", role=FurnitureRole.PAGE_NUMBER),
        lambda: Block(BlockKind.PARAGRAPH, "1 ab", label="1"),  # paragraphs carry no label
        lambda: Block(BlockKind.FURNITURE, "39", label="39"),  # a page label is the page's
        lambda: Block(BlockKind.FIGURE, "1", label="1"),  # its caption carries the label
        lambda: Block(BlockKind.HEADING, "2 Setup", label="3"),  # not printed in the block
        lambda: Block(BlockKind.HEADING, "2 Setup", label=" 2"),  # not trimmed
        lambda: Block(BlockKind.CAPTION, "Table\n2: x", label="Table\n2"),  # a line break
        lambda: replace(PAPER, page_labels=("39",)),  # one label for each of the two pages
        lambda: Section("A", 0, 0, 1),
        lambda: Section("A", 1, 0, 2, (Section("B", 2, 1, 3),)),
        lambda: Section("A", 1, 0, 4, (Section("B", 2, 0, 2), Section("C", 2, 1, 3))),
        lambda: Section("A", 2, 0, 2, (Section("B", 2, 0, 1),)),
        lambda: replace(PAPER, language=""),
        lambda: replace(PAPER, sections=(Section("A", 1, 0, 11),)),
        lambda: replace(PAPER, blocks=PAPER.blocks[:-1]),  # the running head would be lost
        lambda: replace(
            PAPER, blocks=(*PAPER.blocks, Block(BlockKind.PARAGRAPH, "x", (Part("p1-l1"),)))
        ),
        lambda: replace(
            PAPER, blocks=(*PAPER.blocks, Block(BlockKind.PARAGRAPH, "x", (Part("nope"),)))
        ),
        lambda: replace(
            PAPER,
            blocks=(
                *PAPER.blocks[:-1],
                replace(PAPER.blocks[-1], kind=BlockKind.CAPTION, describes=1),
            ),
        ),
        lambda: AudioChunk(Span(0, 0, 1), "/tmp/a.wav", 1.0),  # noqa: S108
        lambda: AudioChunk(Span(0, 0, 1), "C:/a.wav", 1.0),
        lambda: AudioChunk(Span(0, 0, 1), "audio\\a.wav", 1.0),
        lambda: AudioChunk(Span(0, 0, 1), "../a.wav", 1.0),
        lambda: AudioChunk(Span(0, 0, 1), "", 1.0),
        lambda: AudioChunk(Span(0, 0, 1), "a.wav", -1.0),
        lambda: AudioChunk(Span(0, 0, 1), "a.wav", float("inf")),
    ],
)
def test_invalid_values_are_refused(make: object) -> None:
    with pytest.raises(ValueError):  # noqa: PT011 - each case has its own message
        make()  # type: ignore[operator]


@pytest.mark.parametrize(
    "data",
    [
        {"block": 0, "start": 0, "end": 1, "extra": 1},
        {"block": "0", "start": 0, "end": 1},
        {"block": True, "start": 0, "end": 1},
        [0, 0, 1],
    ],
)
def test_from_data_refuses_data_that_does_not_fit(data: object) -> None:
    with pytest.raises(ValueError):  # noqa: PT011
        from_data(Span, data)  # type: ignore[arg-type]


def test_export_golden_file(snapshot: SnapshotAssertion) -> None:
    chunk = AudioChunk(Span(1, 0, 28), "audio/0001.wav", 2.5)
    export = {
        "document": to_data(PAPER),
        "edits": to_data((CITATION, FORMULA, TABLE, PAUSE)),
        "chunks": to_data((chunk,)),
        "script": to_data(apply_edits(PAPER, [CITATION, FORMULA, TABLE, PAUSE])),
    }
    assert export == snapshot
    assert from_data(Document, export["document"]) == PAPER
