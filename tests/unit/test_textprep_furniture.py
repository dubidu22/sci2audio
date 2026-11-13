"""Page furniture is not read (TP-01, #63): unit cases and the corpus papers.

The golden file holds, per corpus paper, how many edits each category of all built-in steps
proposed and what became of them, so later rule PRs show their effect on real papers as a
small diff.
Accept a wanted change with `uv run pytest --snapshot-update` and explain it in the PR.
"""

from collections import Counter
from functools import cache
from pathlib import Path

import pytest
from syrupy.assertion import SnapshotAssertion

from sci2audio.core import Block, BlockKind, Document, EditKind, FurnitureRole, Span
from sci2audio.extraction import extract_pdf
from sci2audio.layout import build_document
from sci2audio.testing import make_document
from sci2audio.textprep import FurnitureStep, Status, StepContext, run_steps

pytestmark = pytest.mark.timeout(120)

PAPERS = sorted((Path(__file__).resolve().parents[1] / "corpus" / "papers").glob("*.pdf"))
EN = StepContext("en")


def test_each_furniture_block_with_text_is_removed_with_its_role_as_reason() -> None:
    document = make_document(
        [
            Block(BlockKind.FURNITURE, "12", role=FurnitureRole.PAGE_NUMBER),
            (BlockKind.PARAGRAPH, "Body text."),
            Block(BlockKind.FURNITURE, "Journal\n(2024)", role=FurnitureRole.RUNNING_HEAD),
            Block(BlockKind.FURNITURE, "", role=FurnitureRole.RUNNING_HEAD),
            (BlockKind.FURNITURE, "No role"),
        ]
    )
    edits = FurnitureStep().find(document, EN)
    assert [(e.span, e.kind, e.reason) for e in edits] == [
        (Span(0, 0, 2), EditKind.REMOVE, "page furniture (page number) is not read"),
        (Span(2, 0, 14), EditKind.REMOVE, "page furniture (running head) is not read"),
        (Span(4, 0, 7), EditKind.REMOVE, "page furniture (unknown kind) is not read"),
    ]
    assert all(edit.step == "page-furniture" for edit in edits)


@pytest.mark.parametrize("role", FurnitureRole)
def test_every_role_has_a_name(role: FurnitureRole) -> None:
    document = make_document([Block(BlockKind.FURNITURE, "x", role=role)])
    (edit,) = FurnitureStep().find(document, EN)
    assert "unknown" not in edit.reason
    assert "_" not in edit.reason


@cache
def document(paper: Path) -> Document:
    return build_document(extract_pdf(paper))


@pytest.mark.parametrize("paper", PAPERS, ids=[paper.stem for paper in PAPERS])
def test_on_the_corpus_only_furniture_is_removed_and_the_rest_reads_as_printed(
    paper: Path, snapshot: SnapshotAssertion
) -> None:
    doc = document(paper)
    # the furniture step alone: every other block reads exactly as printed
    alone = run_steps(doc, StepContext(doc.language), (FurnitureStep(),), strict=True)
    furniture = {i for i, block in enumerate(doc.blocks) if block.kind is BlockKind.FURNITURE}
    assert {edit.span.block for edit in alone.accepted} == {
        i for i in furniture if doc.blocks[i].text
    }
    read: dict[int, str] = {}
    for piece in alone.script():
        read[piece.span.block] = read.get(piece.span.block, "") + piece.text
    for index, block in enumerate(doc.blocks):
        assert read.get(index, "") == ("" if index in furniture else block.text)
    # all built-in steps: the summary shows each rule's effect on the paper
    run = run_steps(doc, StepContext(doc.language), strict=True)
    assert not run.problems
    assert not run.not_run
    summary = Counter(f"{o.category}: {o.status}" for o in run.outcomes)
    assert dict(sorted(summary.items())) == snapshot
    assert summary[f"page-furniture: {Status.ACCEPTED}"] > 0
