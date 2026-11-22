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


# D-882: a critical merge go is the coordinator's file gos/pr-<N>.yaml; `approved` is what the
# governance check asks for a risk:high PR; a merge recorded only in the PR entry counts (#737).
HEAD = "3f9c2ab"


def pr(**fields: str) -> dict[str, str]:
    base = {"pr": "12", "opened": "2026-11-22", "thread": "impl-1", "lane": "infra"}
    return {
        **base,
        "labels": "lane:infra",
        "critical": "yes",
        "compactions": "0",
        **fields,
        "_file": "pr-12.yaml",
    }


def review(**fields: str) -> dict[str, str]:
    base = {"pr": "12", "round": "1", "date": "2026-11-22", "thread": "review-1", "head": HEAD}
    return {
        **base,
        "critical": "yes",
        "verdict": "approved",
        "must_fix": "0",
        "should_fix": "0",
        "report": "plans/review-pr12-round1.md",
        **fields,
        "_file": f"pr12-round{fields.get('round', '1')}.yaml",
    }


def go(**fields: str) -> dict[str, str]:
    base = {
        "pr": "12",
        "head": HEAD,
        "by": "coordinator (session coordinator-1)",
        "time": "2026-11-22T19:00Z",
    }
    return {**base, **fields, "_file": "pr-12.yaml"}


def test_gate_stops_a_critical_pr_without_a_go_file() -> None:
    ok, reasons = LEDGER_TOOL.gate("12", [pr()], [review()], [], "", [])
    assert not ok
    assert "no gos/pr-12.yaml records the coordinator's merge go" in reasons[0]


def test_gate_passes_a_critical_pr_with_a_go_for_its_head() -> None:
    ok, reasons = LEDGER_TOOL.gate("12", [pr()], [review()], [], "", [go(head=HEAD + "0d1e")])
    assert ok, reasons
    assert "Merge go by coordinator (session coordinator-1)" in reasons[0]


def test_gate_stops_a_go_for_another_head() -> None:
    ok, reasons = LEDGER_TOOL.gate("12", [pr()], [review()], [], "", [go(head="aaaaaaa")])
    assert not ok
    assert "does not carry over to another head" in reasons[0]
    ok, reasons = LEDGER_TOOL.gate("12", [pr()], [review()], [], "", [go(by="dispatcher-b004")])
    assert not ok
    assert "`by` names the coordinator" in reasons[0]


def test_gate_needs_no_go_file_for_a_non_critical_pr() -> None:
    ok, reasons = LEDGER_TOOL.gate("12", [pr(critical="no")], [review(critical="no")], [], "", [])
    assert ok, reasons
    assert "dispatcher" in reasons[0]


def test_gate_and_approved_take_the_updated_head() -> None:
    updated = review(updated_head="bbbbbbb")
    assert LEDGER_TOOL.gate("12", [pr()], [updated], [], "", [go(head="bbbbbbb")])[0]
    assert LEDGER_TOOL.approved("12", [updated], [], "bbbbbbb")[0]
    assert LEDGER_TOOL.approved("12", [updated], [], HEAD)[0]
    assert not LEDGER_TOOL.approved("12", [review()], [], "bbbbbbb")[0]


def test_approved_passes_only_the_head_the_latest_round_approved() -> None:
    rounds = [
        review(),
        review(round="2", head="ccccccc", verdict="changes_requested", must_fix="1"),
    ]
    ok, why = LEDGER_TOOL.approved("12", rounds, [], "ccccccc")
    assert not ok
    assert "changes_requested" in why
    # round 1 approved HEAD, but round 2 is the latest: an older approval does not count
    assert not LEDGER_TOOL.approved("12", rounds, [], HEAD)[0]
    assert not LEDGER_TOOL.approved("12", [], [], HEAD)[0]
    assert not LEDGER_TOOL.approved("12", [review(must_fix="1")], [], HEAD)[0]
    assert LEDGER_TOOL.approved("12", [review()], [], HEAD)[0]
    assert not LEDGER_TOOL.approved("13", [review()], [], HEAD)[0]


def test_approved_takes_an_owner_override_for_this_head() -> None:
    override = {
        "pr": "12",
        "date": "2026-11-22",
        "by": "owner, chat message",
        "head": "ddddddd",
        "reason": "hotfix for the broken release build",
        "_file": "pr-12.yaml",
    }
    assert LEDGER_TOOL.approved("12", [], [override], "ddddddd")[0]
    assert not LEDGER_TOOL.approved("12", [], [override], "eeeeeee")[0]


def test_check_reports_a_malformed_go_file() -> None:
    found = LEDGER_TOOL.problems([pr()], [review()], [], [], [go(head="not-a-sha", time="")])
    assert "gos/pr-12.yaml: `time` is missing" in found
    assert any(line.startswith("gos/pr-12.yaml: `head` must be") for line in found)
    assert LEDGER_TOOL.problems([pr()], [review()], [], [], [go()]) == []


def test_a_merge_recorded_only_in_the_pr_entry_counts_as_merged() -> None:
    """#737: merged by owner override after a changes-requested round, so no round records it."""
    prs = [
        pr(merged="1bebb96940cd1c0c6ec7d340cbb79fcbe9a6ac89 (2026-11-22T18:55:59Z, squash by hand)")
    ]
    rounds = [review(verdict="changes_requested", must_fix="2")]
    assert "merged: 1." in LEDGER_TOOL.stats(prs, rounds)
    assert "#12" not in LEDGER_TOOL.status(prs, rounds, [], "")
    assert "| merged 1bebb9694 |" in LEDGER_TOOL.table(prs, rounds)
    ok, reasons = LEDGER_TOOL.gate("12", prs, rounds, [], "", [])
    assert not ok
    assert reasons[0].startswith("already merged (1bebb96")
    # free text that does not start with a commit SHA is no merge record
    assert "merged: 0." in LEDGER_TOOL.stats([pr(merged="not yet")], rounds)
