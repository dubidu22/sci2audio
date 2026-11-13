"""Footnote marks tied by link tags on the corpus Markdown note and The Time Machine (#189,
D-420 to D-428).

Every noteref mark is left out of the running text, every note is introduced by its mark
("Footnote 1."), and no back-link arrow is read. The golden file lists each footnote edit
with the text around it (D-427), so a reviewer can check it against the files. Accept a
wanted change with `uv run pytest --snapshot-update` and explain it in the PR.
"""

from functools import cache
from pathlib import Path

import pytest
from syrupy.assertion import SnapshotAssertion

from sci2audio.core import BlockKind, Document, EditKind, TextLine
from sci2audio.extraction import extract_epub, extract_markdown
from sci2audio.layout import build_document
from sci2audio.textprep import StepContext, StepRun, run_steps, spoken_text

pytestmark = pytest.mark.timeout(120)

CORPUS = Path(__file__).resolve().parents[1] / "corpus"
EPUB = CORPUS / "epub" / "wells-the-time-machine.epub"
MARKDOWN = CORPUS / "markdown" / "sci2audio-sample-note.md"
SAMPLES = [MARKDOWN, EPUB]
READERS = {".epub": extract_epub, ".md": extract_markdown}
NOTE_REF = {"role:doc-noteref", "epub:noteref"}
BACK_LINK = {"role:doc-backlink", "epub:backlink"}
AROUND = 30


@cache
def document(sample: Path) -> Document:
    return build_document(READERS[sample.suffix](sample))


@cache
def run(sample: Path) -> StepRun:
    doc = document(sample)
    return run_steps(doc, StepContext(doc.language), strict=True)


def spoken(sample: Path, index: int) -> str:
    return spoken_text(p for p in run(sample).script() if p.span.block == index)


def tagged_runs(doc: Document, tags: set[str]) -> list[tuple[int, int, int]]:
    """(block, start, end) of every run with one of these tags, in reading order."""
    items = doc.content.items()
    found = []
    for index, block in enumerate(doc.blocks):
        for part in block.parts:
            item = items[part.item][1]
            if not isinstance(item, TextLine):
                continue
            offset = part.start
            for run_ in item.runs:
                if tags & set(run_.tags) and run_.text.strip():
                    found.append((index, offset, offset + len(run_.text)))
                offset += len(run_.text)
    return found


@pytest.mark.parametrize("sample", SAMPLES, ids=[s.stem for s in SAMPLES])
def test_every_footnote_edit_is_as_recorded(sample: Path, snapshot: SnapshotAssertion) -> None:
    doc = document(sample)
    shown = []
    for edit in run(sample).accepted:
        if edit.step != "footnotes":
            continue
        text = doc.blocks[edit.span.block].text
        before = text[max(edit.span.start - AROUND, 0) : edit.span.start].replace("\n", " ")
        after = text[edit.span.end : edit.span.end + AROUND].replace("\n", " ")
        cut = text[edit.span.start : edit.span.end]
        said = f" -> {edit.replacement!r}" if edit.kind is EditKind.REPLACE else ""
        shown.append(f"{edit.kind.value} block {edit.span.block}: {before}[{cut}]{after}{said}")
    assert shown == snapshot


@pytest.mark.parametrize("sample", SAMPLES, ids=[s.stem for s in SAMPLES])
def test_no_mark_or_back_link_is_read_and_every_note_is_introduced_by_its_number(
    sample: Path,
) -> None:
    doc = document(sample)
    accepted = {
        (e.span.block, e.span.start, e.span.end)
        for e in run(sample).accepted
        if e.step == "footnotes"
    }
    marks = tagged_runs(doc, NOTE_REF)
    assert marks  # both files have noterefs
    for mark in marks:
        assert mark in accepted, mark  # each noteref here is one mark of its own run
    for block, start, end in tagged_runs(doc, BACK_LINK):
        assert any(b == block and s <= start and end <= e for b, s, e in accepted)
    notes = [i for i, block in enumerate(doc.blocks) if block.kind is BlockKind.FOOTNOTE]
    assert [spoken(sample, i).split(".")[0] for i in notes] == [
        f"Footnote {n}" for n in range(1, len(notes) + 1)
    ]
    assert all("↩" not in spoken(sample, i) for i in notes)


def test_the_samples_have_the_marks_the_plan_counted() -> None:
    assert [len(tagged_runs(document(s), NOTE_REF)) for s in SAMPLES] == [3, 1]
    assert [len(tagged_runs(document(s), BACK_LINK)) for s in SAMPLES] == [0, 1]
