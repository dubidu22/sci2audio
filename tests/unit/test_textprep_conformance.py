"""The text-step conformance suite (#6) on the built-in steps, and that it catches bad steps."""

import socket
import subprocess
import sys
from contextlib import suppress
from itertools import count

import pytest

from sci2audio.core import BlockKind, Document, Edit, EditKind, Span
from sci2audio.testing import (
    SAMPLE_DOCUMENTS,
    ConformanceError,
    NetworkUsedError,
    check_text_step,
    no_network,
    text_step_problems,
)
from sci2audio.textprep import BUILT_IN_STEPS, Category, Stage, StepContext, TextStep


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
    ],
)
def test_the_suite_catches_each_kind_of_bad_step(how: str, problem: str) -> None:
    with pytest.raises(ConformanceError) as caught:
        check_text_step(Bad(how), allow_ask=False)
    assert any(problem in found for found in caught.value.problems), caught.value.problems


def test_a_block_step_must_cover_whole_blocks() -> None:
    step = Bad("partial block")
    step.stage = Stage.BLOCK
    problems = text_step_problems(step)
    assert any("does not cover its block" in problem for problem in problems)


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
