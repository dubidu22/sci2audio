"""Every file has one lane (#665): `.github/lanes.yml` says which lane owns a path, and
`.github/governance/pr-checks.json` is the copy the governance PR check reads, so the two
must agree, and the labeler must mark the same critical paths the check demands risk:high for."""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
GITHUB = ROOT / ".github"
CONFIG = json.loads((GITHUB / "governance" / "pr-checks.json").read_text(encoding="utf-8"))


def load_pr_checks():
    path = GITHUB / "governance" / "pr_checks.py"
    spec = importlib.util.spec_from_file_location("sci2audio_pr_checks_lanes", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PR_CHECKS = load_pr_checks()


def lanes() -> dict[str, list[str]]:
    """lanes.yml's `paths:` flow lists by lane. A line parser, because PyYAML is only a
    transitive dev dependency; a lane whose paths it cannot read fails the test."""
    text = (GITHUB / "lanes.yml").read_text(encoding="utf-8")
    out: dict[str, list[str]] = {}
    lane = ""
    pending = ""
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        name = re.fullmatch(r"  (\w+):", line)
        if name:
            lane = name.group(1)
            continue
        if line.startswith("    paths: [") or pending:
            pending += line.split("#")[0].strip() + " "
            if "]" in pending:
                inner = pending.split("[", 1)[1].rsplit("]", 1)[0]
                out[lane] = [g.strip().strip('"') for g in inner.split(",") if g.strip()]
                pending = ""
    return out


def tracked_files(*folders: str) -> list[str]:
    git = shutil.which("git")
    assert git is not None
    listing = subprocess.run(
        [git, "ls-files", "--", *folders],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return listing.splitlines()


def test_lanes_yml_has_the_lanes_of_the_ownership_labels() -> None:
    assert sorted(f"lane:{lane}" for lane in lanes()) == sorted(CONFIG["ownership_labels"])


def test_every_file_of_the_workspace_and_the_design_record_has_exactly_one_lane() -> None:
    files = tracked_files("governance", "docs/design")
    assert len(files) > 100, files
    by_lane = lanes()
    owners = {
        p: [lane for lane, globs in by_lane.items() if PR_CHECKS.matches(p, globs)] for p in files
    }
    wrong = {p: o for p, o in owners.items() if len(o) != 1}
    assert not wrong, wrong


def test_the_governance_check_reads_the_same_lanes_as_lanes_yml() -> None:
    assert {f"lane:{lane}": globs for lane, globs in lanes().items()} == CONFIG["label_paths"]


def test_the_labeler_marks_the_paths_the_check_holds_critical() -> None:
    labeler = (GITHUB / "labeler.yml").read_text(encoding="utf-8")
    assert re.findall(r'^\s+- "(.+)"$', labeler, re.M) == CONFIG["critical_paths"]


RULES = [
    "governance/claude-project-rules.yaml",
    "governance/rules/implementation.yaml",
    "governance/project_instructions.md",
    "governance/governance-config.json",
]


def check(paths: list[str], labels: list[str]) -> dict[str, str]:
    results = PR_CHECKS.run_checks(
        CONFIG, "infra: sample (#1)", labels, [("M", p) for p in paths], "commit"
    )
    return {r["check"]: r["status"] for r in results}


@pytest.mark.parametrize(
    "path", [*RULES, "governance/github-setup/pr_checks.py", "governance/tools/ledger_tool.py"]
)
def test_the_rules_and_the_governance_tools_need_the_infra_lane(path: str) -> None:
    assert check([path], ["lane:docs", "risk:high"])["ownership"] == "FAIL"
    assert check([path], ["lane:infra", "risk:high"])["ownership"] == "ok"


@pytest.mark.parametrize("path", RULES)
def test_a_rules_change_needs_risk_high(path: str) -> None:
    assert check([path], ["lane:infra"])["critical"] == "FAIL"
    assert check([path], ["lane:infra", "risk:high"])["critical"] == "ok"


@pytest.mark.parametrize(
    "path",
    [
        "governance/kb/decision-log.md",
        "governance/plans/infra-b-i1-plan.md",
        "governance/ledger/prs/pr-1.yaml",
        "governance/project-state.yaml",
        "governance/memory/MEMORY-archive-2026-11-18.md",
        "governance/release/zap-summary.md",
        "governance/workflow-export.md",
    ],
)
def test_the_working_files_alone_skip_the_lane_checks(path: str) -> None:
    assert check([path], [])["scope"] == "ok"


@pytest.mark.parametrize(
    "path", ["docs/design/DESIGN.md", "docs/design/prototype/app.js", "governance/plans/x.md"]
)
def test_the_design_record_and_the_working_files_belong_to_the_docs_lane(path: str) -> None:
    results = check([path, "docs/README.md"], ["lane:docs"])
    assert results["ownership"] == "ok"
    assert "unowned" not in results
    assert check([path, "src/sci2audio/cli.py"], ["lane:cli"])["ownership"] == "ok"
