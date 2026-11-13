# ruff: noqa: RUF001  (dashes, quotes and symbols are meant as papers print them)
"""Citations, URLs, DOIs and e-mail addresses on the corpus papers (#66, D-167 to D-175).

The golden file lists, per paper, every edit the `links` and `citations` steps propose: the
block, the text as printed with 20 characters on each side, what is read instead and what
became of the edit, so a reviewer can check each one against the PDF and a later change
shows as a small diff. Accept a wanted change with `uv run pytest --snapshot-update` and
explain it in the PR.
"""

import re
from functools import cache
from pathlib import Path

import pytest
from syrupy.assertion import SnapshotAssertion

from sci2audio.core import BlockKind, Document
from sci2audio.extraction import extract_pdf
from sci2audio.layout import build_document
from sci2audio.textprep import (
    DEFAULT_SWITCHED_OFF,
    Category,
    Status,
    StepContext,
    StepRun,
    is_reference_title,
    run_steps,
    spoken_text,
)

pytestmark = pytest.mark.timeout(120)

PAPERS = sorted((Path(__file__).resolve().parents[1] / "corpus" / "papers").glob("*.pdf"))
IDS = [paper.stem for paper in PAPERS]
STEPS = ("links", "citations")
PLACEHOLDERS = {BlockKind.FURNITURE, BlockKind.TABLE, BlockKind.FORMULA, BlockKind.FIGURE}
LEFT = re.compile(
    r"https?:|www\.|\S@\S|\b10\.\d{4,9}/|arxiv:\d|"  # links
    r"(?<![\w)\]])\[\s*[1-9]\d{0,3}(?:\s*[-–,;]\s*[1-9]\d{0,3})*\s*\]",  # numeric citations
    re.IGNORECASE,
)
# what a careless removal leaves behind; no repair may add one of these
LEFTOVERS = (" .", " ,", " ;", "()", "( )", "[]", " at.", " at,", ":.", " in.", " by.", "..")


@cache
def document(paper: Path) -> Document:
    return build_document(extract_pdf(paper))


@cache
def run(paper: Path, *, off: bool = False) -> StepRun:
    doc = document(paper)
    switched_off = DEFAULT_SWITCHED_OFF | ({Category.CITATIONS, Category.LINKS} if off else set())
    return run_steps(doc, StepContext(doc.language), switched_off=switched_off, strict=True)


def said(paper: Path, *, off: bool = False) -> list[str]:
    script = run(paper, off=off).script()
    by_block: list[list] = [[] for _ in document(paper).blocks]
    for piece in script:
        by_block[piece.span.block].append(piece)
    return [spoken_text(pieces) for pieces in by_block]


def reference_list(doc: Document) -> set[int]:
    blocks: set[int] = set()

    def walk(sections: tuple) -> None:
        for section in sections:
            if is_reference_title(section.title):
                blocks.update(range(section.start, section.end))
            walk(section.children)

    walk(doc.sections)
    return blocks


def shown(text: str) -> str:
    return re.sub(r"\s+", " ", text)


@pytest.mark.parametrize("paper", PAPERS, ids=IDS)
def test_every_citation_and_link_edit_is_as_recorded(
    paper: Path, snapshot: SnapshotAssertion
) -> None:
    doc = document(paper)
    lines = []
    for outcome in run(paper).outcomes:
        edit = outcome.edit
        if edit.step not in STEPS:
            continue
        text = doc.blocks[edit.span.block].text
        before = shown(text[max(edit.span.start - 20, 0) : edit.span.start])
        after = shown(text[edit.span.end : edit.span.end + 20])
        printed = shown(text[edit.span.start : edit.span.end])
        lines.append(
            f"{edit.span.block} {edit.step} {outcome.status}: "
            f"…{before}[{printed}]{after}… -> {edit.replacement!r}"
        )
    assert lines == snapshot


@pytest.mark.parametrize("paper", PAPERS, ids=IDS)
def test_no_link_or_numeric_citation_is_read_outside_the_reference_list(paper: Path) -> None:
    doc = document(paper)
    skip = reference_list(doc)
    left = [
        (index, match.group())
        for index, text in enumerate(said(paper))
        if index not in skip and doc.blocks[index].kind not in PLACEHOLDERS
        for match in LEFT.finditer(text)
    ]
    assert left == []


@pytest.mark.parametrize("paper", PAPERS, ids=IDS)
def test_no_repair_leaves_a_broken_sentence_behind(paper: Path) -> None:
    on, off = said(paper), said(paper, off=True)
    for index, (now, before) in enumerate(zip(on, off, strict=True)):
        for leftover in LEFTOVERS:
            assert now.count(leftover) <= before.count(leftover), (index, leftover, now)


@pytest.mark.parametrize("paper", PAPERS, ids=IDS)
def test_narrative_citations_keep_their_names(paper: Path) -> None:
    on = said(paper)
    for edit in run(paper).accepted:
        if edit.step == "citations" and edit.reason.startswith("year of the citation"):
            names = re.search(r'"(.*?) \(', edit.reason)
            assert names is not None
            assert names.group(1).split()[-1] in on[edit.span.block], edit.reason


def test_the_corpus_has_the_citations_and_links_the_plan_counted() -> None:
    # accepted edits outside headed reference lists; Liu's list has no heading (#92), so its
    # numbers and years count too. A subject citation is two or more edits.
    counts = {"links": 0, "citations": 0, "read as references": 0, "names kept": 0}
    for paper in PAPERS:
        skip = reference_list(document(paper))
        for outcome in run(paper).outcomes:
            edit = outcome.edit
            if (
                edit.step not in STEPS
                or edit.span.block in skip
                or outcome.status is not Status.ACCEPTED
            ):
                continue
            counts[edit.step] += 1
            counts["read as references"] += (
                edit.reason.endswith("(TP-04)") and "read as" in edit.reason
            )
            counts["names kept"] += edit.reason.startswith("year of the citation")
    assert counts == {"links": 13, "citations": 328, "read as references": 21, "names kept": 39}
