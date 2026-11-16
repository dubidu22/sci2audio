"""The text-step conformance suite (#6) on the built-in steps, and that it catches bad steps."""

import socket
import subprocess
import sys
from contextlib import suppress
from itertools import count
from pathlib import Path

import pytest

from sci2audio.core import Block, BlockKind, Document, Edit, EditKind, Section, Span
from sci2audio.extraction import extract_pdf
from sci2audio.layout import build_document
from sci2audio.testing import (
    SAMPLE_DOCUMENTS,
    ConformanceError,
    NetworkUsedError,
    check_text_step,
    make_document,
    no_network,
    text_step_problems,
)
from sci2audio.textprep import (
    BUILT_IN_STEPS,
    Category,
    LineEndHyphenStep,
    Stage,
    StepContext,
    TextStep,
    UnicodeStep,
)


@pytest.mark.parametrize("step", BUILT_IN_STEPS, ids=lambda step: step.id)
def test_every_built_in_step_keeps_the_contract_and_never_asks(step: TextStep) -> None:
    check_text_step(step, allow_ask=False)


def test_the_sample_documents_cover_every_block_kind_and_three_languages() -> None:
    kinds = {block.kind for document in SAMPLE_DOCUMENTS for block in document.blocks}
    assert kinds == set(BlockKind)
    assert {document.language for document in SAMPLE_DOCUMENTS} == {"en", "en-GB", "de"}


class Bad(TextStep):
    """A paragraph step that misbehaves in one way, chosen by `how`."""

    id = "bad-step"
    languages = ("en",)
    category = Category.CITATIONS
    stage = Stage.INLINE

    def __init__(self, how: str) -> None:
        self.how = how
        self.calls = count()

    def find(self, document: Document, context: StepContext) -> list[Edit]:
        how, call = self.how, next(self.calls)
        if how == "raises":
            raise RuntimeError("boom")
        if how == "network":
            with suppress(NetworkUsedError):  # swallowed, but still seen
                socket.create_connection(("example.org", 80))
            return []
        edits = []
        for index, block in enumerate(document.blocks):
            if block.kind is not BlockKind.PARAGRAPH or len(block.text) < 4:
                continue
            whole = Span(index, 0, len(block.text))
            edit = {
                "tuple": Edit(whole, EditKind.REMOVE, "r", self.id),
                "other id": Edit(whole, EditKind.REMOVE, "r", "someone-else"),
                "outside": Edit(Span(index, 0, len(block.text) + 1), EditKind.REMOVE, "r", self.id),
                "ask": Edit(whole, EditKind.ASK, "unsure", self.id),
                "partial block": Edit(Span(index, 0, 2), EditKind.REMOVE, "r", self.id),
                "changes": Edit(Span(index, 0, 1 + call % 2), EditKind.REMOVE, "r", self.id),
                "not idempotent": Edit(Span(index, 0, 0), EditKind.REPLACE, "r", self.id, "Note: "),
                "overlap": Edit(Span(index, 1, 3), EditKind.REMOVE, "r", self.id),
                "move": Edit(whole, EditKind.MOVE, "r", self.id, to=Span(0, 0, 0)),
            }[how]
            edits.append(edit)
            if how == "overlap":
                edits.append(Edit(Span(index, 0, 2), EditKind.REMOVE, "r", self.id))
        return tuple(edits) if how == "tuple" else edits


@pytest.mark.parametrize(
    ("how", "problem"),
    [
        ("raises", "find raised RuntimeError: boom"),
        ("network", "tried to reach the network: create_connection"),
        ("tuple", "find must return a list of Edit, got tuple"),
        ("other id", "names step 'someone-else', not 'bad-step'"),
        ("outside", "invalid edits"),
        ("overlap", "invalid edits"),
        ("ask", "proposes an ask edit"),
        ("changes", "different edits the second time"),
        ("not idempotent", "not idempotent"),
        ("move", "only a move step proposes moves"),
    ],
)
def test_the_suite_catches_each_kind_of_bad_step(how: str, problem: str) -> None:
    with pytest.raises(ConformanceError) as caught:
        check_text_step(Bad(how), allow_ask=False)
    assert any(problem in found for found in caught.value.problems), caught.value.problems


class InsidePlaceholder(TextStep):
    """An inline step that removes one more character inside each placeholder every time it
    reads it: a second run rebuilds placeholders as printed (D-707), so only the check on
    its own output inside the placeholder sees it (D-710)."""

    id = "inside-placeholder"
    languages = ("en",)
    category = Category.CITATIONS
    stage = Stage.INLINE

    def find(self, document: Document, context: StepContext) -> list[Edit]:
        return [
            Edit(Span(index, 0, 1), EditKind.REMOVE, "r", self.id)
            for index, block in enumerate(document.blocks)
            if block.is_placeholder and len(block.text) > 1
        ]


def test_an_edit_inside_a_placeholder_must_be_idempotent_on_its_own_output() -> None:
    problems = text_step_problems(InsidePlaceholder())
    assert any("inside a placeholder is not idempotent" in p for p in problems), problems


def test_built_in_steps_may_clean_the_printed_text_inside_a_placeholder() -> None:
    """Unicode clean-up and line-end hyphens edit inside a formula, table, code block or
    figure: the text read when a notice is switched off. Those edits change nothing more on
    their own output, so every built-in step keeps the contract on such placeholders
    (review B1 of PR #450, D-710)."""
    samples = [d for d in SAMPLE_DOCUMENTS if d.content.source.name.startswith(("plac", "plat"))]
    assert len(samples) == 2
    inside = set()
    for document in samples:
        for step in BUILT_IN_STEPS:
            if step.handles(document.language):
                check_text_step(step, [document])
                for edit in step.find(document, StepContext(document.language)):
                    block = document.blocks[edit.span.block]
                    if block.is_placeholder and edit.span.end - edit.span.start < len(block.text):
                        inside.add((step.id, block.kind))
    assert {step for step, _ in inside} >= {"unicode-clean-up", "line-end-hyphens"}
    assert {kind for _, kind in inside} == {
        BlockKind.FORMULA,
        BlockKind.TABLE,
        BlockKind.CODE,
        BlockKind.FIGURE,
    }


class WholePlaceholder(TextStep):
    """A block step that reads each placeholder as "Skipped: " and its text, as a notice
    does: an edit of the whole block is made from the printed block, so it is not checked
    on its own output (D-710)."""

    id = "whole-placeholder"
    languages = ("en",)
    category = Category.CITATIONS
    stage = Stage.BLOCK

    def find(self, document: Document, context: StepContext) -> list[Edit]:
        return [
            Edit(Span(i, 0, len(b.text)), EditKind.REPLACE, "r", self.id, f"Skipped: {b.text}")
            for i, b in enumerate(document.blocks)
            if b.is_placeholder and b.text
        ]


def test_a_whole_block_edit_of_a_placeholder_keeps_the_contract() -> None:
    check_text_step(WholePlaceholder())


class FailsOnItsOwnOutput(TextStep):
    """An inline step that removes a leading "#" inside a placeholder and fails on a
    placeholder without one, which only its own output inside the placeholder shows."""

    id = "fails-on-own-output"
    languages = ("en",)
    category = Category.CITATIONS
    stage = Stage.INLINE

    def find(self, document: Document, context: StepContext) -> list[Edit]:
        edits = []
        for index, block in enumerate(document.blocks):
            if block.is_placeholder and block.text:
                if not block.text.startswith("#"):
                    raise ValueError("no mark")
                edits.append(Edit(Span(index, 0, 1), EditKind.REMOVE, "r", self.id))
        return edits


def test_a_step_failing_on_its_own_output_inside_a_placeholder_is_reported() -> None:
    document = make_document([(BlockKind.FORMULA, "#x=y"), (BlockKind.PARAGRAPH, "Text.")])
    problems = text_step_problems(FailsOnItsOwnOutput(), [document])
    assert any(
        "inside a placeholder, on its own output: find raised ValueError" in p for p in problems
    ), problems


class PluginCleanUp(UnicodeStep):
    """A plugin step that cleans characters as the built-in step does, under its own id:
    the contract is drawn by what a step does, not by which step it is (D-710)."""

    id = "plugin-clean-up"


PAPERS = Path(__file__).resolve().parents[1] / "corpus" / "papers"
NOWAK = PAPERS / "acl2023-nowak-prefix-probabilities.pdf"


@pytest.mark.parametrize("step", [UnicodeStep(), LineEndHyphenStep(), PluginCleanUp()], ids=str)
def test_a_step_cleaning_inside_placeholders_keeps_the_contract(step: TextStep) -> None:
    """On the sample documents and on a corpus paper whose figures hold
    ligatures and invisible characters (13 such edits by the clean-up step per run, 26 for
    both switch settings, review B1 of #450)."""
    paper = build_document(extract_pdf(NOWAK))
    check_text_step(step, [*SAMPLE_DOCUMENTS, paper])


def test_the_corpus_paper_has_edits_inside_its_placeholders() -> None:
    paper = build_document(extract_pdf(NOWAK))
    inside = [
        edit
        for edit in UnicodeStep().find(paper, StepContext("en"))
        if (block := paper.blocks[edit.span.block]).is_placeholder
        and (edit.span.start, edit.span.end) != (0, len(block.text))
    ]
    assert len(inside) >= 10  # 13 at the time of writing, all inside figures


@pytest.mark.parametrize(
    "kind", [BlockKind.FORMULA, BlockKind.TABLE, BlockKind.FIGURE, BlockKind.CODE]
)
def test_an_edit_inside_any_kind_of_placeholder_is_refused(kind: BlockKind) -> None:
    document = make_document([Block(kind, "x=y+z"), (BlockKind.PARAGRAPH, "Some text.")])
    problems = text_step_problems(InsidePlaceholder(), [document])
    assert any("inside a placeholder is not idempotent" in p for p in problems), problems


def test_a_block_step_must_cover_whole_blocks() -> None:
    step = Bad("partial block")
    step.stage = Stage.BLOCK
    problems = text_step_problems(step)
    assert any("does not cover its block" in problem for problem in problems)


class SwitchedOff(Bad):
    """A step that breaks the contract only while some category is switched off."""

    def find(self, document: Document, context: StepContext) -> list[Edit]:
        return super().find(document, context) if context.switched_off else []


def test_the_suite_also_runs_each_step_with_every_category_switched_off() -> None:
    # a step may read StepContext.switched_off, so it must keep the contract both ways (D-595)
    problems = text_step_problems(SwitchedOff("outside"))
    assert problems
    assert all("every category off" in problem for problem in problems), problems
    assert any("invalid edits" in problem for problem in problems), problems


class Mover(TextStep):
    """A move step that reads each footnote at the end of the block before it (#213)."""

    id = "mover"
    languages = ("*",)
    category = Category.FOOTNOTES
    stage = Stage.MOVE

    def __init__(self, plain: bool = False) -> None:
        self.plain = plain

    def find(self, document: Document, context: StepContext) -> list[Edit]:
        edits = []
        for index, block in enumerate(document.blocks):
            if block.kind is BlockKind.FOOTNOTE and index and block.text:
                end = len(document.blocks[index - 1].text)
                whole = Span(index, 0, len(block.text))
                if self.plain:
                    edits.append(Edit(whole, EditKind.REMOVE, "r", self.id))
                else:
                    to = Span(index - 1, end, end)
                    edits.append(Edit(whole, EditKind.MOVE, "read here", self.id, to=to))
        return edits


def test_a_move_step_keeps_the_contract_and_proposes_only_moves() -> None:
    check_text_step(Mover(), allow_ask=False)
    problems = text_step_problems(Mover(plain=True))
    assert any("a move step proposes only moves" in problem for problem in problems)


def test_ask_edits_are_allowed_for_plugins() -> None:
    check_text_step(Bad("ask"))


def test_bad_attributes_and_unknown_languages_are_named() -> None:
    step = Bad("raises")
    step.api_version = 0
    assert text_step_problems(step) == ["api_version must be 1, got 0"]
    step = Bad("raises")
    step.languages = ("xx",)
    assert "no sample document is in one of its languages" in text_step_problems(step)[0]


def test_no_network_refuses_connections_and_restores_the_socket_module() -> None:
    original = socket.create_connection
    with no_network() as attempts, pytest.raises(NetworkUsedError):
        socket.getaddrinfo("example.org", 443)
    assert attempts == ["getaddrinfo('example.org', 443)"]
    assert socket.create_connection is original


def test_the_testing_package_imports_neither_pytest_nor_hypothesis() -> None:
    code = (
        "import sys, sci2audio.testing, sci2audio.testing.regression; "
        "print(sorted({'pytest', 'hypothesis', '_pytest'} & set(sys.modules)))"
    )
    found = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    ).stdout.strip()
    assert found == "[]"


@pytest.mark.parametrize("step", BUILT_IN_STEPS, ids=[step.id for step in BUILT_IN_STEPS])
def test_the_sample_documents_give_every_built_in_step_work(step: TextStep) -> None:
    """Otherwise the contract checks above would check a step that proposes nothing."""
    assert any(
        step.find(document, StepContext(document.language))
        for document in SAMPLE_DOCUMENTS
        if step.handles(document.language)
    )


def test_make_document_cuts_tagged_ranges_into_runs_of_their_own() -> None:
    document = make_document(
        [(BlockKind.PARAGRAPH, "ab1\ncd2"), (BlockKind.HEADING, "R")],
        tags={0: [(2, 3, "sup"), (6, 7, "sup")]},
        sections=[Section("R", 1, 1, 2)],
    )
    lines = document.content.pages[0].lines
    assert [[(r.text, r.tags) for r in line.runs] for line in lines[:2]] == [
        [("ab", ()), ("1", ("sup",))],
        [("cd", ()), ("2", ("sup",))],
    ]
    assert document.sections == (Section("R", 1, 1, 2),)
    with pytest.raises(ValueError, match="inside one line"):
        make_document([(BlockKind.PARAGRAPH, "ab\ncd")], tags={0: [(1, 4, "sup")]})
