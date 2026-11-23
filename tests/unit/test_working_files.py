"""Working files live on branch governance only (THR-13, D-874, #746): the copies main kept from
the workspace move (#657) were never updated and read as stale state. The check in
`.github/scripts/working_files.py` fails CI when one is tracked on the branch under test; branch
governance is exempt because CI never runs there, not because the script knows its name."""

from __future__ import annotations

import importlib.util
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / ".github" / "scripts" / "working_files.py"
CI = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")


def load_working_files():
    spec = importlib.util.spec_from_file_location("sci2audio_working_files", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


WF = load_working_files()

WORKING = [
    "governance/plans/docs-b-d2-plan.md",
    "governance/plans/review-pr746-round1.md",
    "governance/plans/batch-004.md",
    "governance/plans/b8-review/test_zz_probe_fold.py",
    "governance/ledger/prs/pr-1.yaml",
    "governance/ledger/rounds/pr1-round1.yaml",
    "governance/ledger/deferred/pr1-1.yaml",
    "governance/ledger/implementation.md",
    "governance/project-state.yaml",
    "governance/kb/pending-decisions.md",
]
# written on main by the ruleset generator through ruleset PRs, so main holds the copy that counts
GENERATED = [
    "governance/plans/README.md",
    "governance/ledger/README.md",
    "governance/ledger/deferred/since.txt",
]
OTHERS = [
    "governance/kb/decision-log.md",
    "governance/kb/README.md",
    "governance/kb/merged-batches/kb-batch-2026-11-20-pending.md",
    "governance/memory/MEMORY-archive-2026-11-18.md",
    "governance/release/zap-summary-release-1.0-b25f192.md",
    "governance/workflow-export.md",
    "governance/claude-project-rules.yaml",
    "governance/tools/ledger_tool.py",
    "governance/github-setup/pr_checks.py",
    "governance/plans.md",
    "governance/project-state.yaml.bak",
    "docs/plans/x.md",
]


def git_repo(tmp_path: Path, files: list[str]) -> Path:
    git = shutil.which("git")
    assert git is not None
    for name in files:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x\n", encoding="utf-8")
    subprocess.run([git, "init", "-q", str(tmp_path)], check=True)
    subprocess.run([git, "-C", str(tmp_path), "add", "-A"], check=True)
    return tmp_path


def run_check(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root)],
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize("path", WORKING)
def test_a_working_file_is_found(path: str) -> None:
    assert WF.working_files([path]) == [path]


@pytest.mark.parametrize("path", GENERATED)
def test_the_generated_files_stay_on_main(path: str) -> None:
    assert WF.working_files([path]) == []


@pytest.mark.parametrize("path", OTHERS)
def test_other_governance_files_are_not_working_files(path: str) -> None:
    assert WF.working_files([path]) == []


def test_the_check_fails_on_a_tracked_working_file(tmp_path: Path) -> None:
    root = git_repo(
        tmp_path, ["README.md", "governance/plans/x-plan.md", "governance/plans/README.md"]
    )
    result = run_check(root)
    assert result.returncode == 1
    lines = result.stdout.splitlines()
    assert lines == ["working file on this branch: governance/plans/x-plan.md", WF.POINTER]


def test_the_check_passes_on_a_clean_tree(tmp_path: Path) -> None:
    root = git_repo(tmp_path, ["README.md", *GENERATED, *OTHERS])
    result = run_check(root)
    assert result.returncode == 0, result.stdout
    assert result.stdout.strip() == "no working files on this branch"


def test_the_pointer_file_is_the_line_the_check_prints() -> None:
    """A KB index record (D-884): a lane owns it and the KB test counts it as a record."""
    assert WF.POINTER_FILE == "governance/kb/00-index/working-files.md"
    assert WF.working_files([WF.POINTER_FILE]) == []
    assert (ROOT / WF.POINTER_FILE).read_text(encoding="utf-8") == WF.POINTER + "\n"
    assert "branch `governance`" in WF.POINTER


def test_ci_runs_the_check_in_the_lint_job() -> None:
    lint = CI[CI.index("\n  lint:\n") : CI.index("\n  licences:\n")]
    assert "run: python3 .github/scripts/working_files.py\n" in lint
    passed = CI[CI.index("    name: CI passed\n") :]
    assert re.search(r"needs: \[lint\b", passed)


def test_ci_pushes_run_on_main_and_release_branches_only() -> None:
    """Branch governance holds the working files, so CI must never run on its pushes."""
    on = CI[CI.index("\non:\n") : CI.index("\npermissions:\n")]
    push = on[on.index("  push:\n") :]
    assert re.search(r'^    branches: \[main, "release/\*\*"\]$', push, re.M)
    assert "governance" not in on
