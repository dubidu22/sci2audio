"""Unit tests for the core objects (issue #17): examples, refused values, export golden file.

When the export format changes on purpose, accept the new golden file with
`uv run pytest --snapshot-update` and explain the diff in the PR (D-60).
"""

import dataclasses

import pytest
from syrupy.assertion import SnapshotAssertion

from sci2audio.core import (
    AudioChunk,
    Block,
    BlockKind,
    Document,
    Edit,
    EditKind,
    Metadata,
    Origin,
    OverlappingEditsError,
    Region,
    ScriptPiece,
    Section,
    Source,
    SourceFormat,
    Span,
    SpanError,
    apply_edits,
    from_data,
    to_data,
)

# A made-up two-page paper with one block of every kind.
PAPER = Document(
    source=Source("paper.pdf", SourceFormat.PDF, sha256="ab12"),
    language="en",
    metadata=Metadata(title="A Small Paper", authors=("A. Author", "B. Author"), date="2024"),
    blocks=(
        Block(BlockKind.HEADING, "1 Introduction", Origin((Region(1, 72, 90, 300, 104),))),
        Block(
            BlockKind.PARAGRAPH,
            "Sound helps [3]. It runs on.",
            Origin((Region(1, 72, 700, 300, 760), Region(2, 72, 72, 300, 90, start=17))),
        ),
        Block(BlockKind.FORMULA, "E = mc^2", Origin((Region(2, 100, 100, 200, 120),))),
        Block(BlockKind.TABLE, "", Origin((Region(2, 72, 130, 540, 300),))),
        Block(BlockKind.CAPTION, "Table 1: Results.", Origin((Region(2, 72, 310, 540, 324),))),
        Block(BlockKind.LIST_ITEM, "First point", Origin(chapter=3)),
        Block(BlockKind.FOOTNOTE, "1 A note.", Origin(line=12)),
    ),
    sections=(Section("1 Introduction", 1, 0, 7, (Section("1.1 Results", 2, 2, 7),)),),
)

CITATION = Edit(Span(1, 11, 15), EditKind.REMOVE, reason="numeric citation", step="citations")
FORMULA = Edit(Span(2, 0, 8), EditKind.REPLACE, "formula skipped (D-55)", "formulas", "A formula.")
TABLE = Edit(Span(3, 0, 0), EditKind.REPLACE, "table skipped", "tables", "A table.")
PAUSE = Edit(Span(0, 14, 14), EditKind.PAUSE, reason="after a heading", step="pauses")


def test_apply_edits_builds_the_script() -> None:
    pieces = apply_edits(PAPER, [FORMULA, CITATION, TABLE, PAUSE])
    assert pieces[:5] == (
        ScriptPiece("1 Introduction", Span(0, 0, 14)),
        ScriptPiece("", Span(0, 14, 14), pause=True),
        ScriptPiece("Sound helps", Span(1, 0, 11)),
        ScriptPiece(". It runs on.", Span(1, 15, 28)),
        ScriptPiece("A formula.", Span(2, 0, 8)),
    )
    assert pieces[5] == ScriptPiece("A table.", Span(3, 0, 0))


def test_region_tells_the_page_of_a_position() -> None:
    paragraph = PAPER.blocks[1]
    assert paragraph.origin.page == 1
    assert [r.page for r in paragraph.origin.regions if r.start <= 20][-1] == 2
    assert PAPER.blocks[5].origin.page is None


def test_placeholders() -> None:
    assert [b.kind for b in PAPER.blocks if b.is_placeholder] == [
        BlockKind.FORMULA,
        BlockKind.TABLE,
    ]


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
    with pytest.raises(SpanError, match="block 9"):
        apply_edits(PAPER, [Edit(Span(9, 0, 1), EditKind.REMOVE, "r", "s")])
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
        lambda: Source("dir/paper.pdf", SourceFormat.PDF),
        lambda: Source("C:\\paper.pdf", SourceFormat.PDF),
        lambda: Region(0, 0, 0, 1, 1),
        lambda: Region(1, 5, 0, 1, 1),
        lambda: Region(1, float("nan"), 0, 1, 1),
        lambda: Origin((Region(1, 0, 0, 1, 1, start=2),)),
        lambda: Origin((Region(1, 0, 0, 1, 1), Region(1, 0, 0, 1, 1))),
        lambda: Origin(chapter=0),
        lambda: Block(
            BlockKind.PARAGRAPH, "ab", Origin((Region(1, 0, 0, 1, 1), Region(2, 0, 0, 1, 1, 3)))
        ),
        lambda: Section("A", 0, 0, 1),
        lambda: Section("A", 1, 0, 2, (Section("B", 2, 1, 3),)),
        lambda: Section("A", 1, 0, 4, (Section("B", 2, 0, 2), Section("C", 2, 1, 3))),
        lambda: Section("A", 2, 0, 2, (Section("B", 2, 0, 1),)),
        lambda: Document(PAPER.source, "", ()),
        lambda: Document(PAPER.source, "en", (), sections=(Section("A", 1, 0, 1),)),
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
