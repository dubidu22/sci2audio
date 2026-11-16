"""Footnotes read after their mark's sentence on the corpus (#213, D-558, plan Q4, Q8).

Measured before the step was written: on the corpus PDFs every one of the 69 labelled notes
has its mark found, and the sentence holding it ends where the utterance cutter ends it. These
tests keep both true: every note whose mark is found moves, no move is set aside, and each
note is read where the cutter ends its mark's sentence (or at the block's end), past the marks
that stand right there. The tagged samples (the Markdown note, The Time Machine) move every
linked note to its first mark, an endnote into the chapter of its mark too.
"""

from functools import cache
from pathlib import Path

import pytest

from sci2audio.core import BlockKind, Document, EditKind, Span
from sci2audio.extraction import extract_epub, extract_markdown, extract_pdf
from sci2audio.layout import build_document
from sci2audio.textprep import (
    BUILT_IN_STEPS,
    Status,
    StepContext,
    StepRun,
    cut_utterances,
    run_steps,
)
from sci2audio.textprep.footnotes import MARKED_KINDS, FootnoteStep

pytestmark = pytest.mark.timeout(180)

CORPUS = Path(__file__).resolve().parents[1] / "corpus"
PAPERS = sorted((CORPUS / "papers").glob("*.pdf"))
EPUB = CORPUS / "epub" / "wells-the-time-machine.epub"
MARKDOWN = CORPUS / "markdown" / "sci2audio-sample-note.md"
READERS = {".pdf": extract_pdf, ".epub": extract_epub, ".md": extract_markdown}


@cache
def document(sample: Path) -> Document:
    return build_document(READERS[sample.suffix](sample))


@cache
def run(sample: Path, *, moves: bool = True) -> StepRun:
    doc = document(sample)
    steps = BUILT_IN_STEPS if moves else BUILT_IN_STEPS[:-1]
    return run_steps(doc, StepContext(doc.language), steps, strict=True)


def first_marks(sample: Path) -> dict[int, Span]:
    """Each note block with its first mark in running text, as `FootnoteStep` finds them."""
    doc = document(sample)
    _, pairs = FootnoteStep().marked(doc, StepContext(doc.language))
    first: dict[int, Span] = {}
    for edit, note in pairs:
        span = edit.span
        if doc.blocks[span.block].kind not in MARKED_KINDS or not doc.blocks[note].text:
            continue
        if note not in first or (span.block, span.start) < (first[note].block, first[note].start):
            first[note] = span
    return first


def moves(sample: Path) -> dict[int, Span]:
    """Each moved note block with where it is read."""
    found = [o for o in run(sample).outcomes if o.edit.step == "footnote-places"]
    assert [o for o in found if o.status is not Status.ACCEPTED] == []
    return {o.edit.span.block: o.edit.to for o in found if o.edit.to is not None}


def cutter_end(sample: Path, mark: Span) -> int:
    """Where the cutter ends the sentence holding the mark, in the run without moves, past
    the removed marks that start right there: footnote marks and affiliation marks (#93)."""
    plain = run(sample, moves=False)
    utterances = cut_utterances(document(sample), plain.script())
    spoken = [u for u in utterances if u.span.block == mark.block and not u.pause]
    # the last utterance starting before the mark: it holds the mark, or the mark follows it
    # after white space ("sets. 1")
    holding = [k for k, u in enumerate(spoken) if u.span.start <= mark.start]
    assert holding, f"no utterance comes before the mark at {mark}"
    last = holding[-1]
    while last + 1 < len(spoken) and spoken[last + 1].continues:
        last += 1
    end = spoken[last].span.end
    removed = sorted(
        (e.span.start, e.span.end)
        for e in plain.accepted
        if e.kind is EditKind.REMOVE
        and e.span.block == mark.block
        and e.step in ("footnotes", "affiliation-marks")
    )
    for start, stop in removed:
        if start == end:
            end = stop
    return end


@pytest.mark.parametrize("paper", PAPERS, ids=[paper.stem for paper in PAPERS])
def test_every_note_with_a_found_mark_is_read_where_the_cutter_ends_its_sentence(
    paper: Path,
) -> None:
    marks = first_marks(paper)
    moved = moves(paper)
    assert moved.keys() == marks.keys()
    for note, mark in marks.items():
        assert moved[note].block == mark.block
        assert moved[note].start == cutter_end(paper, mark), document(paper).blocks[note].text


def test_all_69_labelled_notes_of_the_corpus_papers_move() -> None:
    assert sum(len(moves(paper)) for paper in PAPERS) == 69


@pytest.mark.parametrize("sample", [MARKDOWN, EPUB], ids=["markdown", "epub"])
def test_every_linked_note_is_read_after_its_first_mark(sample: Path) -> None:
    marks = first_marks(sample)
    assert marks
    moved = moves(sample)
    assert moved.keys() == marks.keys()
    for note, mark in marks.items():
        assert moved[note].block == mark.block
        assert run(sample).read_at(note) == mark.block


def test_the_time_machine_endnote_is_read_in_its_mark_s_chapter() -> None:
    doc = document(EPUB)
    starts = sorted(section.start for section in doc.sections)

    def chapter(block: int) -> int:
        return sum(1 for start in starts if start <= block)

    crossing = [note for note in moves(EPUB) if chapter(note) != chapter(run(EPUB).read_at(note))]
    assert crossing
    assert all(doc.blocks[note].kind is BlockKind.FOOTNOTE for note in crossing)
