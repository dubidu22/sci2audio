"""The ledger's `fixed` decision (D-875, D-877): a should-fix finding fixed after its last review
round is settled by naming the commit, and an entry without one stays in triage, so no batch
starts on an unproved claim (THR-16)."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
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
HEAD = "3f9c2ab" + "0" * 33  # a full SHA: `approved` takes no prefix (review-745 S1)


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
    ok, reasons = LEDGER_TOOL.gate("12", [pr()], [review()], [], "", [go(head=HEAD[:7])])
    assert ok, reasons
    assert "Merge go by coordinator (session coordinator-1)" in reasons[0]


def test_gate_stops_a_go_for_another_head() -> None:
    ok, reasons = LEDGER_TOOL.gate(
        "12", [pr()], [review()], [], "", [go(head="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")]
    )
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
    updated = review(updated_head="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")
    assert LEDGER_TOOL.gate(
        "12", [pr()], [updated], [], "", [go(head="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")]
    )[0]
    assert LEDGER_TOOL.approved("12", [updated], [], "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")[0]
    assert LEDGER_TOOL.approved("12", [updated], [], HEAD)[0]
    assert not LEDGER_TOOL.approved(
        "12", [review()], [], "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    )[0]


def test_approved_passes_only_the_head_the_latest_round_approved() -> None:
    rounds = [
        review(),
        review(
            round="2",
            head="cccccccccccccccccccccccccccccccccccccccc",
            verdict="changes_requested",
            must_fix="1",
        ),
    ]
    ok, why = LEDGER_TOOL.approved("12", rounds, [], "cccccccccccccccccccccccccccccccccccccccc")
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
        "head": "dddddddddddddddddddddddddddddddddddddddd",
        "reason": "hotfix for the broken release build",
        "_file": "pr-12.yaml",
    }
    assert LEDGER_TOOL.approved("12", [], [override], "dddddddddddddddddddddddddddddddddddddddd")[0]
    assert not LEDGER_TOOL.approved(
        "12", [], [override], "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
    )[0]


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


def test_approved_needs_the_full_head() -> None:
    """A 7-character prefix is cheap to collide with, so the check the merge depends on takes
    only full SHAs, in the round entry and on the command line (review-745 S1)."""
    assert not LEDGER_TOOL.approved("12", [review(head=HEAD[:7])], [], HEAD)[0]
    assert not LEDGER_TOOL.approved("12", [review()], [], HEAD[:7])[0]
    override = {
        "pr": "12",
        "date": "2026-11-22",
        "by": "owner, chat message",
        "head": HEAD[:7],
        "reason": "hotfix for the broken release build",
        "_file": "pr-12.yaml",
    }
    assert not LEDGER_TOOL.approved("12", [], [override], HEAD)[0]
    assert LEDGER_TOOL.approved("12", [review(head=HEAD.upper())], [], HEAD)[0]


def run_approved(*args: str) -> int:
    tool = ROOT / "governance" / "tools" / "ledger_tool.py"
    return subprocess.run(
        [sys.executable, str(tool), "approved", *args], capture_output=True, check=False
    ).returncode


def test_the_approved_command_exits_0_1_or_2(tmp_path: Path) -> None:
    """As `governance pr checks` runs it: 0 lets the PR through, 1 stops it, 2 is a usage error
    that stops it too (review-745 S2)."""
    ledger = tmp_path / "ledger"
    (ledger / "prs").mkdir(parents=True)
    (ledger / "rounds").mkdir()
    (ledger / "prs" / "pr-12.yaml").write_text(
        "pr: 12\nopened: 2026-11-22\ncritical: yes\n", encoding="utf-8"
    )
    (ledger / "rounds" / "pr12-round1.yaml").write_text(
        f"pr: 12\nround: 1\nhead: {HEAD}\ncritical: yes\nverdict: approved\nmust_fix: 0\n",
        encoding="utf-8",
    )
    assert run_approved("12", "--head", HEAD, "--ledger", str(ledger)) == 0
    assert run_approved("12", "--head", "b" * 40, "--ledger", str(ledger)) == 1
    assert run_approved("13", "--head", HEAD, "--ledger", str(ledger)) == 1
    assert run_approved("12", "--head", HEAD[:7], "--ledger", str(ledger)) == 2
    assert run_approved("12", "--ledger", str(ledger)) == 2
    assert run_approved("12", "--head", HEAD, "--ledger", str(tmp_path / "missing")) == 2


def test_the_ledger_readme_documents_the_d882_formats() -> None:
    """A refresh from the skill rewrites the README; this makes it fail loudly (review-745 S3)."""
    text = (ROOT / "governance" / "ledger" / "README.md").read_text(encoding="utf-8")
    for fragment in (
        "| `gos/pr-<N>.yaml` | the coordinator | when it gives the merge go for critical PR N",
        "`gos/pr-<N>.yaml` (the coordinator's merge go for a critical PR):",
        "# the merge commit SHA, only when no round records the merge",
        'updated_head: ""              # MRG-01: the new head after merging main into a behind PR',
        "python3 tools/ledger_tool.py approved 12 --head <full sha>",
        "it counts only a full 40-character SHA",
    ):
        assert fragment in text, fragment


# D-891 F1: #741 and #721 were merged by hand and their entries kept `merged: ""`, so `stats`
# and `status` counted them as open. The squash subjects on main and release/* know better.
def merged_rounds(pr_number: str, **fields: str) -> dict[str, str]:
    return {
        "pr": pr_number,
        "round": "1",
        "date": "2026-11-23",
        "thread": "review-1",
        "head": HEAD,
        "critical": "no",
        "verdict": "approved",
        "must_fix": "0",
        "should_fix": "0",
        "deferred": "0",
        "report": "plans/review.md",
        **fields,
        "_file": f"pr{pr_number}-round1.yaml",
    }


def ledger_pr(number: str, **fields: str) -> dict[str, str]:
    base = {"pr": number, "opened": "2026-11-22", "thread": "impl-1", "lane": "infra"}
    return {
        **base,
        "labels": "lane:infra",
        "critical": "no",
        "compactions": "0",
        **fields,
        "_file": f"pr-{number}.yaml",
    }


def merge_problems(prs, rounds, subjects) -> list[str]:
    numbers = LEDGER_TOOL.squash_numbers(subjects)
    return [p for p in LEDGER_TOOL.problems(prs, rounds, merged_numbers=numbers) if "squash" in p]


def test_check_fails_on_a_merged_pr_whose_entry_records_no_merge() -> None:
    found = merge_problems(
        [ledger_pr("741", merged="")], [], ["governance: pin the ruleset (#741)"]
    )
    assert len(found) == 1
    assert found[0].startswith("prs/pr-741.yaml: PR #741 is merged")


def test_check_passes_when_the_merge_is_recorded() -> None:
    subjects = ["governance: pin the ruleset (#741)", "voices: a fix (#744) (#753)"]
    in_pr = ledger_pr("741", merged="3fb4d1b (squash, 2026-11-22)")
    in_round = ledger_pr("753")
    rounds = [merged_rounds("753", merged="8965914")]
    assert merge_problems([in_pr, in_round], rounds, subjects) == []


def test_check_takes_the_last_number_of_a_squash_subject() -> None:
    assert LEDGER_TOOL.squash_numbers(["voices: a fix (#744) (#753)"]) == {"753"}
    assert merge_problems([ledger_pr("744")], [], ["voices: a fix (#744) (#753)"]) == []
    assert LEDGER_TOOL.squash_numbers(["Merge branch 'release/1.4' into main", "docs: (#12) note"]) == set()


def test_check_counts_a_squash_subject_on_a_release_branch(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    ledger = repo / "ledger"
    (ledger / "prs").mkdir(parents=True)
    (ledger / "rounds").mkdir()
    (ledger / "prs" / "pr-721.yaml").write_text(
        "pr: 721\nopened: 2026-11-21\nthread: impl-1\nlane: release\nlabels: lane:app\n"
        'critical: no\ncompactions: 0\nmerged: ""\n',
        encoding="utf-8",
    )

    def git(*args: str) -> None:
        subprocess.run(
            ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
            cwd=repo,
            check=True,
            capture_output=True,
        )

    git("init", "-q", "-b", "main")
    git("commit", "-q", "--allow-empty", "-m", "start")
    git("update-ref", "refs/remotes/origin/main", "HEAD")
    git("commit", "-q", "--allow-empty", "-m", "release: R1 for 1.4 (#721)")
    git("update-ref", "refs/remotes/origin/release/1.4", "HEAD")
    result = run_check("--ledger", str(ledger))
    assert result.returncode == 1
    assert "prs/pr-721.yaml: PR #721 is merged" in result.stdout


def run_check(*args: str) -> subprocess.CompletedProcess[str]:
    tool = ROOT / "governance" / "tools" / "ledger_tool.py"
    return subprocess.run(
        [sys.executable, str(tool), "check", *args], capture_output=True, text=True, check=False
    )


def test_check_exits_2_when_the_subjects_cannot_be_read(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger"
    (ledger / "prs").mkdir(parents=True)
    (ledger / "rounds").mkdir()
    result = run_check("--ledger", str(ledger))
    assert result.returncode == 2
    assert "--subjects" in result.stderr
    subjects = tmp_path / "subjects.txt"
    subjects.write_text("docs: a note (#3)\n", encoding="utf-8")
    assert run_check("--ledger", str(ledger), "--subjects", str(subjects)).returncode == 0
    missing = run_check("--ledger", str(ledger), "--subjects", str(tmp_path / "none.txt"))
    assert missing.returncode == 2


# D-891 F2: #745's approving round set S4 aside with `should_fix: 0`, so nothing in the ledger
# said a deferred/ entry was owed. `deferred` counts what a round sets aside.
NEW = str(LEDGER_TOOL.DEFERRED_FROM_PR)


def deferred_entry(pr_number: str, k: int) -> dict[str, str]:
    return {
        "pr": pr_number,
        "date": "2026-11-23",
        "what": f"S{k}: left for later",
        "decision": "planned",
        "issue": "#747",
        "_file": f"pr{pr_number}-{k}.yaml",
    }


def deferral_problems(rounds, deferred) -> list[str]:
    prs = [ledger_pr(r["pr"]) for r in rounds]
    return [
        p
        for p in LEDGER_TOOL.problems(prs, rounds, deferred=deferred, merged_numbers=set())
        if "deferred" in p
    ]


def test_check_fails_when_fewer_deferred_files_than_the_rounds_defer() -> None:
    rounds = [
        merged_rounds(NEW, deferred="1"),
        {**merged_rounds(NEW, round="2", deferred="1"), "_file": f"pr{NEW}-round2.yaml"},
    ]
    found = deferral_problems(rounds, [deferred_entry(NEW, 1)])
    assert found == [
        f"PR #{NEW}: its rounds set aside 2 finding(s) (`deferred`), deferred/ holds 1 entry for it"
    ]


def test_check_passes_when_every_deferral_has_a_file() -> None:
    rounds = [merged_rounds(NEW, deferred="2")]
    assert deferral_problems(rounds, [deferred_entry(NEW, 1), deferred_entry(NEW, 2)]) == []


def test_a_new_round_entry_without_deferred_fails() -> None:
    entry_ = merged_rounds(NEW)
    del entry_["deferred"]
    assert deferral_problems([entry_], []) == [f"rounds/pr{NEW}-round1.yaml: `deferred` is missing"]


def test_an_old_round_entry_without_deferred_passes() -> None:
    old = str(LEDGER_TOOL.DEFERRED_FROM_PR - 1)
    entry_ = merged_rounds(old)
    del entry_["deferred"]
    assert deferral_problems([entry_], []) == []


def test_deferred_must_be_a_whole_number() -> None:
    assert deferral_problems([merged_rounds(NEW, deferred="one")], []) == [
        f"rounds/pr{NEW}-round1.yaml: `deferred` must be a whole number, got 'one'"
    ]


def test_triage_lists_a_round_that_deferred_without_a_file() -> None:
    todo, _ = LEDGER_TOOL.triage([merged_rounds(NEW, deferred="1", merged="abc1234")], [], "")
    assert todo == [
        f"PR #{NEW}: its rounds set aside 1 finding(s) (`deferred`), 0 recorded in deferred/: "
        "write one entry per finding from plans/review.md"
    ]
