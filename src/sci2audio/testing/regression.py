"""The English regression cases (#4, PE-03): input blocks and the script they must give.

A case file is TOML with one `[[case]]` table per case:

    [[case]]
    id = "numeric-citations"      # unique, kebab-case
    audit = 2                     # row of the English audit (KB), 0 if not from it
    issue = 66                    # the issue whose rule handles it
    goal = "removed"              # what that rule must reach; a note, not exact wording
    language = "en"               # optional, default "en"
    blocks = [{ kind = "paragraph", text = "..." }]  # optional: role, label, describes
    expected = ["..."]            # the script today, one line per block that is read
    utterances = ["...", "..."]   # optional: how the cutter cuts the script, where it matters

`expected` pins what the built-in steps produce now. A rule PR changes the cases its rule
touches first (test-first) and the diff shows the before and after (tests.md).
"""

from __future__ import annotations

import difflib
import re
import tomllib
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from sci2audio.core import Block, BlockKind, Document, FurnitureRole, ScriptPiece
from sci2audio.testing.documents import make_document
from sci2audio.textprep import PAUSE_MARK, StepRun, cut_utterances, spoken_text

_CASE_ID = re.compile(r"\A[a-z0-9]+(?:-[a-z0-9]+)*\Z")
_CASE_KEYS = {"id", "audit", "issue", "goal", "language", "blocks", "expected", "utterances"}
_BLOCK_KEYS = {"kind", "text", "role", "label", "describes"}


@dataclass(frozen=True)
class Case:
    """One regression case."""

    id: str
    audit: int
    issue: int
    goal: str
    document: Document
    expected: tuple[str, ...]
    utterances: tuple[str, ...] | None = None  # None: not checked for this case


def load_cases(path: Path) -> list[Case]:
    """Read and check a case file; raise ValueError naming the case that is wrong."""
    with path.open("rb") as file:
        data = tomllib.load(file)
    if set(data) != {"case"}:
        raise ValueError(f"{path.name}: expected only [[case]] tables, got {sorted(data)}")
    cases, seen = [], set()
    for number, raw in enumerate(data["case"], start=1):
        name = raw.get("id", f"number {number}")
        try:
            case = _case(raw)
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"{path.name}: case {name}: {error}") from error
        if case.id in seen:
            raise ValueError(f"{path.name}: case id {case.id!r} is used twice")
        seen.add(case.id)
        cases.append(case)
    return cases


def _case(raw: dict) -> Case:
    if unknown := set(raw) - _CASE_KEYS:
        raise ValueError(f"unknown keys {sorted(unknown)}")
    if not _CASE_ID.match(raw["id"]):
        raise ValueError(f"id must be kebab-case, got {raw['id']!r}")
    blocks = []
    for given in raw["blocks"]:
        if unknown := set(given) - _BLOCK_KEYS:
            raise ValueError(f"unknown block keys {sorted(unknown)}")
        role = given.get("role")
        blocks.append(
            Block(
                BlockKind(given["kind"]),
                given["text"],
                describes=given.get("describes"),
                role=FurnitureRole(role) if role else None,
                label=given.get("label", ""),
            )
        )
    expected = raw["expected"]
    if not isinstance(expected, list) or not all(isinstance(line, str) for line in expected):
        raise TypeError("expected must be a list of strings, one per block that is read")
    utterances = raw.get("utterances")
    if utterances is not None and (
        not isinstance(utterances, list) or not all(isinstance(u, str) for u in utterances)
    ):
        raise TypeError("utterances must be a list of strings")
    if not isinstance(raw["goal"], str) or not raw["goal"].strip():
        raise ValueError("goal must say what the owning issue's rule must reach")
    return Case(
        id=raw["id"],
        audit=int(raw["audit"]),
        issue=int(raw["issue"]),
        goal=raw["goal"],
        document=make_document(blocks, raw.get("language", "en"), f"{raw['id']}.txt"),
        expected=tuple(expected),
        utterances=None if utterances is None else tuple(utterances),
    )


def render(run: StepRun) -> list[str]:
    """The script, one line per block that is read; pauses show as "[pause]"."""
    by_block: list[list[ScriptPiece]] = [[] for _ in run.document.blocks]
    for piece in run.script():
        by_block[piece.span.block].append(piece)
    lines = [spoken_text(pieces, show_pauses=True) for pieces in by_block]
    return [line for line in lines if line]


def said(run: StepRun) -> list[str]:
    """The utterances the cutter makes of the script; pauses show as "[pause]"."""
    language = run.document.language
    return [u.text or PAUSE_MARK for u in cut_utterances(run.script(), language)]


def diff(expected: Sequence[str], got: Sequence[str]) -> str:
    """A readable before/after of two scripts, line by line."""
    return "\n".join(
        difflib.unified_diff(
            list(expected), list(got), "expected", "got", lineterm="", n=len(expected)
        )
    )
