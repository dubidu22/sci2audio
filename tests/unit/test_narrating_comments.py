"""No comment or docstring tells the history of the code (PR-05, D-891). The review-tag test (#695)
sees one form of it only, so this scan of the tree fails on a precise phrase list in the fast
suite, before review.

A phrase list cannot tell a comment that says what the code does from one that says why it is so;
that stays the reviewer's finding."""

from __future__ import annotations

import ast
import io
import re
import tokenize
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCANNED = ("src", "tests", "scripts", ".github")
# it quotes the phrases to define and test them
QUOTING = {Path(__file__).resolve()}
# the history of the change or of the conversation: precise enough to fail on (D-891)
HISTORY_RE = re.compile(
    r"\b(?:previously|as (?:requested|discussed|agreed)|"
    r"per (?:the )?(?:review|feedback|request)\b(?! rounds?\b)|"
    r"was changed|changed (?:from|to)\b|now uses?\b|now we\b|we now\b|"
    r"(?:the )?(?:old|new) (?:implementation|code|approach|behaviou?r)\b|"
    r"in this (?:PR|commit|change)\b|(?:before|after) this (?:PR|commit|change)\b|"
    r"this (?:PR|commit) (?:adds|removes|changes|fixes|moves|replaces)\b|"
    r"reviewer (?:asked|wanted|said|found)\b|"
    r"(?:ended|went away|was dropped|were dropped) (?:with|in) the move\b|"
    r"(?:was|were) (?:added|removed|renamed|moved|replaced|rewritten) "
    r"(?:in|by|for|when) (?:#\d|PR|the review|D-\d)|"
    r"used to (?:be|call|use|read|write|return|live|sit|run)\b)",
    re.IGNORECASE,
)


def comments_and_docstrings(source: str) -> list[tuple[int, str]]:
    found = [
        (token.start[0], token.string)
        for token in tokenize.generate_tokens(io.StringIO(source).readline)
        if token.type == tokenize.COMMENT
    ]
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            docstring = ast.get_docstring(node, clean=False)
            if docstring is not None:
                found.append((node.body[0].lineno, docstring))
    return found


def test_no_comment_or_docstring_narrates_the_change() -> None:
    hits = []
    for top in SCANNED:
        for path in sorted((ROOT / top).rglob("*.py")):
            if path.resolve() in QUOTING or ".venv" in path.parts:
                continue
            source = path.read_text(encoding="utf-8")
            for line, text in comments_and_docstrings(source):
                for match in HISTORY_RE.finditer(text):
                    where = line + text.count("\n", 0, match.start())
                    hits.append(f"{path.relative_to(ROOT)}:{where}: {match.group(0)!r}")
    assert hits == [], (
        "comments and docstrings say why the code is as it is, not how it came to be (PR-05):\n"
        + "\n".join(hits)
    )


@pytest.mark.parametrize(
    "text",
    [
        # the change history the review-tag test let through (D-891)
        "Its THR-10 and THR-05 texts (subagent hosting, D-881) ended with the move to the "
        "claude.ai Project (D-888, ruleset 1.14.0); the D888 pins below replace them.",
        "previously this read the whole file",
        "as requested, the limit is 214",
        "per the review, the lock is taken first",
        "the parser now uses the spaCy tokens",
        "The old implementation joined the pages first.",
        "In this PR the cache moves to the job folder.",
        "this commit removes the retry",
        "The timeout was changed from 5 to 10 seconds.",
        "the helper was renamed in #612",
        "it used to call ffmpeg twice",
        "the reviewer asked for a second check",
    ],
)
def test_the_history_list_catches_change_history(text: str) -> None:
    assert HISTORY_RE.search(text), text


@pytest.mark.parametrize(
    "text",
    [
        "an old position no longer fits and is dropped",
        "The limits in force in this process hold in the child too",
        "this run already replaced cannot be restored: the old versions are gone",
        "a footnote moved to its mark is read after it",
        "stderr is a terminal: progress is rewritten in one line",
        "Each file put in place is added to `committed` with its inode.",
        "a second run no longer sees that link",
        "Used to check that running the steps a second time changes nothing.",
    ],
)
def test_the_history_list_leaves_why_comments_alone(text: str) -> None:
    assert not HISTORY_RE.search(text), text
