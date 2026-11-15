"""The CI workflows' promises that a reader of the YAML can miss (#360, D-620): labels start
no CI run (one would cancel the run of the same commit), `ci:full` starts a run by hand with
the least permission, and "CI passed" stays strict, so no cancelled, skipped or failed job
ever leaves the required check green or skipped."""

from __future__ import annotations

import re
from pathlib import Path

WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"
CI = (WORKFLOWS / "ci.yml").read_text(encoding="utf-8")
LABEL = (WORKFLOWS / "ci-full-label.yml").read_text(encoding="utf-8")


def block(text: str, header: str) -> str:
    """The lines under `header` (a line of the file) up to the next line indented as
    little or less."""
    lines = text.splitlines()
    start = lines.index(header)
    indent = len(header) - len(header.lstrip())
    out = []
    for line in lines[start + 1 :]:
        if line.strip() and len(line) - len(line.lstrip()) <= indent:
            break
        out.append(line)
    return "\n".join(out)


def test_ci_runs_on_no_label() -> None:
    trigger = block(CI, "  pull_request:")
    assert re.search(r"^\s+types: \[opened, synchronize, reopened\]$", trigger, re.M), trigger
    assert "labeled" not in block(CI, "on:")


def test_ci_passed_fails_on_any_job_that_did_not_succeed() -> None:
    job = block(CI, "  ci-passed:")
    assert "    name: CI passed" in job  # the ruleset's required check: never renamed
    # the job's own condition, at the job's indent: a step's "if: always()" does not count
    # (review round 1 of PR #364, S1); it reports in a cancelled run too, never skipped
    assert re.search(r"^    if: always\(\)$", job, re.M), job
    assert "needs: [lint, licences, security, tests, browser]" in job
    for result in ("failure", "cancelled", "skipped"):
        assert f"contains(needs.*.result, '{result}')" in job


def test_only_the_ci_full_label_of_this_repository_starts_a_run() -> None:
    assert re.search(r"^  pull_request:\n    types: \[labeled\]$", LABEL, re.M)
    assert re.search(r"^permissions: \{\}$", LABEL, re.M)  # nothing by default
    job = block(LABEL, "  dispatch:")
    condition = re.search(r"^    if: (.+)$", job, re.M)
    assert condition is not None
    assert condition[1] == (
        "github.event.label.name == 'ci:full' && "
        "github.event.pull_request.head.repo.full_name == github.repository"
    )
    permissions = block(job, "    permissions:").strip().splitlines()
    assert [line.split("#")[0].strip() for line in permissions] == ["actions: write"]


def test_the_run_by_hand_is_of_ci_on_the_prs_branch_without_template_injection() -> None:
    job = block(LABEL, "  dispatch:")
    assert 'gh workflow run ci.yml --repo "$REPO" --ref "$BRANCH"' in job
    assert "BRANCH: ${{ github.event.pull_request.head.ref }}" in job
    script = block(job, "        run: |")
    assert "${{" not in script  # every value comes in through the environment
    assert "actions/checkout" not in LABEL  # it reads no code of the PR


def test_a_run_by_hand_tests_all_three_systems_and_is_never_cancelled() -> None:
    assert "  workflow_dispatch:" in block(CI, "on:")
    assert "github.event_name != 'pull_request' ||" in CI  # the matrix: all three
    concurrency = block(CI, "concurrency:")
    assert "github.event.pull_request.number || github.run_id" in concurrency
    assert "cancel-in-progress: ${{ github.event_name == 'pull_request' }}" in concurrency


SCREENS = (WORKFLOWS / "ui-screens.yml").read_text(encoding="utf-8")


def test_only_the_ui_screens_label_of_this_repository_renders_the_pages() -> None:
    # #386 (D-627): a label-triggered workflow, run once on the PR's head, reading only
    assert re.search(r"^on:\n  pull_request:\n    types: \[labeled\]\n\n", SCREENS, re.M)
    assert re.search(r"^permissions: \{\}$", SCREENS, re.M)
    job = block(SCREENS, "  screens:")
    condition = re.search(r"^    if: (.+)$", job, re.M)
    assert condition is not None
    assert condition[1] == (
        "github.event.label.name == 'ui:screens' && "
        "github.event.pull_request.head.repo.full_name == github.repository"
    )
    permissions = block(job, "    permissions:").strip().splitlines()
    assert [line.split("#")[0].strip() for line in permissions] == ["contents: read"]
    assert "ref: ${{ github.event.pull_request.head.sha }}" in job
    assert "persist-credentials: false" in job
    assert "name: screens-${{ github.event.pull_request.head.sha }}" in job


def test_the_screens_workflow_runs_no_value_into_a_script() -> None:
    job = block(SCREENS, "  screens:")
    for match in re.finditer(r"^        run: \|\n((?:          .*\n|\n)*)", job + "\n", re.M):
        assert "${{" not in match[1]
    assert "tests/browser/test_screens.py" in job
