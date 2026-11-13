"""The #64 steps on the corpus papers, on `apply_edits` output until the script job (#70).

No formula, table or figure text is read: each placeholder reads its notice, named as the
truth files name the item. No reference list is read. Every footnote is introduced, and
every footnote mark is left out of the running text; the golden file lists each removed mark
with the text around it, so a reviewer can check it against the PDFs. Accept a wanted change
with `uv run pytest --snapshot-update` and explain it in the PR.
"""

import re
import tomllib
from collections import Counter
from functools import cache
from pathlib import Path

import pytest
from syrupy.assertion import SnapshotAssertion

from sci2audio.core import BlockKind, Document, EditKind, Section
from sci2audio.extraction import extract_pdf
from sci2audio.layout import build_document
from sci2audio.textprep import (
    StepContext,
    StepRun,
    is_reference_title,
    run_steps,
    spoken_text,
    whole_block,
)

pytestmark = pytest.mark.timeout(120)

CORPUS = Path(__file__).resolve().parents[1] / "corpus"
PAPERS = sorted((CORPUS / "papers").glob("*.pdf"))
IDS = [paper.stem for paper in PAPERS]


@cache
def document(paper: Path) -> Document:
    return build_document(extract_pdf(paper))


@cache
def run(paper: Path) -> StepRun:
    doc = document(paper)
    return run_steps(doc, StepContext(doc.language), strict=True)


@cache
def spoken(paper: Path) -> tuple[str, ...]:
    script = run(paper).script()
    return tuple(
        spoken_text(p for p in script if p.span.block == index)
        for index in range(len(document(paper).blocks))
    )


def truth(paper: Path) -> dict:
    return tomllib.loads((CORPUS / "truth" / f"{paper.stem}.toml").read_text(encoding="utf-8"))


@pytest.mark.parametrize("paper", PAPERS, ids=IDS)
def test_no_placeholder_text_is_read_and_each_notice_names_the_truth_item(paper: Path) -> None:
    doc, said = document(paper), spoken(paper)
    notices = [said[i] for i, block in enumerate(doc.blocks) if block.is_placeholder]
    assert all(re.fullmatch(r"[^\n]* (is|are) skipped\.", notice) for notice in notices)
    names: Counter[str] = Counter()
    for notice in notices:
        listed = notice.removeprefix("A ").rsplit(" ", 2)[0]
        names.update(re.split(r", | and ", listed))
    facts = truth(paper)
    expected: Counter[str] = Counter()
    for key in ("tables", "figures", "algorithms"):
        expected.update(label for entry in facts.get(key, []) for label in entry["labels"] if label)
    expected.update(
        f"Formula {number}"
        for entry in facts.get("formula_numbers", [])
        for number in entry["numbers"]
    )
    unnumbered = sum(entry["count"] for entry in facts.get("unnumbered_formulas", []))
    assert names["formula"] == unnumbered
    del names["formula"], names["table"], names["figure"]
    assert names == expected


def all_sections(sections: tuple[Section, ...]) -> list[Section]:
    return [s for section in sections for s in (section, *all_sections(section.children))]


@pytest.mark.parametrize("paper", PAPERS, ids=IDS)
def test_no_reference_list_is_read(paper: Path) -> None:
    doc, said = document(paper), spoken(paper)
    sections = [s for s in all_sections(doc.sections) if is_reference_title(s.title)]
    headings = [h["text"] for h in truth(paper)["headings"]]
    # every paper that prints a reference-list heading has its section found
    assert len(sections) == sum(is_reference_title(h) for h in headings)
    for section in sections:
        for index in range(section.start, section.end):
            if doc.blocks[index].kind is not BlockKind.FOOTNOTE:
                assert said[index] == "", (index, doc.blocks[index].text[:60])
        # what follows the list (appendices) is read
        assert section.end == len(doc.blocks) or any(said[section.end :])


@pytest.mark.parametrize("paper", PAPERS, ids=IDS)
def test_every_footnote_is_introduced_and_its_mark_left_out(
    paper: Path, snapshot: SnapshotAssertion
) -> None:
    doc, said = document(paper), spoken(paper)
    items = doc.content.items()
    notes = {}
    # a note holding nothing but its mark and links reads nothing at all (D-168, #66)
    only_links = {
        edit.span.block
        for edit in run(paper).accepted
        if edit.step == "links" and edit.span == whole_block(doc, edit.span.block)
    }
    for index, block in enumerate(doc.blocks):
        if block.kind is BlockKind.FOOTNOTE:
            if index in only_links:
                assert said[index] == ""
            else:
                assert said[index].startswith("Footnote"), said[index][:60]
            if block.label:
                notes[(items[block.parts[0].item][0].number, block.label)] = index
    removed = []
    for edit in run(paper).accepted:
        if edit.step == "footnotes" and edit.kind is EditKind.REMOVE:
            text = doc.blocks[edit.span.block].text
            before = text[max(edit.span.start - 12, 0) : edit.span.start].replace("\n", " ")
            after = text[edit.span.end : edit.span.end + 12].replace("\n", " ")
            removed.append(f"{before}[{text[edit.span.start : edit.span.end]}]{after}")
    # each labelled note's mark is found in the running text, once (all 39 on the corpus)
    assert len(removed) == len(notes)
    assert removed == snapshot


def test_the_corpus_has_the_footnote_marks_the_plan_counted() -> None:
    labelled = sum(
        1 for paper in PAPERS for b in document(paper).blocks
        if b.kind is BlockKind.FOOTNOTE and b.label
    )  # fmt: skip
    assert labelled == 39
