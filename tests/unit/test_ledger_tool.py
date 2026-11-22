"""The ledger's `fixed` decision (D-875, D-877): a should-fix finding fixed after its last review
round is settled by naming the commit, and an entry without one stays in triage, so no batch
starts on an unproved claim (THR-16)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_ledger_tool():
    path = ROOT / "governance" / "tools" / "ledger_tool.py"
    spec = importlib.util.spec_from_file_location("sci2audio_ledger_tool", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


LEDGER_TOOL = load_ledger_tool()


def entry(**fields: str) -> dict[str, str]:
    base = {"pr": "715", "date": "2026-11-22", "what": "S1: wall-clock bound in the fast suite"}
    return {**base, **fields, "_file": "pr715-1.yaml"}


def test_fixed_needs_a_commit() -> None:
    assert LEDGER_TOOL.deferred_problems(entry(decision="fixed", commit="266f10f")) == []
    for commit in ("", "not-a-sha", "266f1"):
        problems = LEDGER_TOOL.deferred_problems(entry(decision="fixed", commit=commit))
        assert any("`commit`" in p for p in problems), commit


def test_triage_lists_fixed_as_settled() -> None:
    todo, settled = LEDGER_TOOL.triage([], [entry(decision="fixed", commit="266f10f")], "")
    assert todo == []
    assert settled == [
        "deferred/pr715-1.yaml (PR #715): S1: wall-clock bound in the fast suite: fixed in 266f10f"
    ]
    todo, settled = LEDGER_TOOL.triage([], [entry(decision="fixed")], "")
    assert settled == []
    assert len(todo) == 1
