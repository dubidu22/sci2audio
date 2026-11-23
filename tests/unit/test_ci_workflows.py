"""The CI workflows' promises that a reader of the YAML can miss (#360, D-620): labels start
no CI run (one would cancel the run of the same commit), `ci:full` starts a run by hand with
the least permission, and "CI passed" stays strict, so no cancelled, skipped or failed job
ever leaves the required check green or skipped."""

from __future__ import annotations

import ast
import importlib.util
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"
CI = (WORKFLOWS / "ci.yml").read_text(encoding="utf-8")
LABEL = (WORKFLOWS / "ci-full-label.yml").read_text(encoding="utf-8")
NIGHTLY = (WORKFLOWS / "nightly.yml").read_text(encoding="utf-8")


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
    # (#364); it reports in a cancelled run too, never skipped
    assert re.search(r"^    if: always\(\)$", job, re.M), job
    assert "needs: [lint, licences, security, tests, browser, web-paths]" in job
    for result in ("failure", "cancelled", "skipped"):
        assert f"contains(needs.*.result, '{result}')" in job


def load_ci_passed():
    path = ROOT / ".github" / "scripts" / "ci_passed.py"
    spec = importlib.util.spec_from_file_location("sci2audio_ci_passed", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def job(name: str, status: str = "completed", conclusion: str | None = "success") -> dict:
    return {"name": name, "status": status, "conclusion": conclusion}


def test_ci_passed_reads_every_job_of_its_run_back() -> None:
    """#548: needs.tests.result read success while the macOS leg was cancelled, so the
    required check also reads every job of its run, each matrix leg on its own."""
    steps = block(CI, "  ci-passed:")
    permissions = block(steps, "    permissions:").strip().splitlines()
    assert [line.split("#")[0].strip() for line in permissions] == [
        "contents: read",
        "actions: read",
    ]
    assert "run: python3 .github/scripts/ci_passed.py" in steps
    assert "GH_TOKEN: ${{ github.token }}" in steps
    assert "RUN_ID: ${{ github.run_id }}" in steps


def run_ci_passed(monkeypatch: pytest.MonkeyPatch, *answers: list[dict]) -> list[float]:
    module = load_ci_passed()
    monkeypatch.setenv("REPO", "owner/repo")
    monkeypatch.setenv("RUN_ID", "7")
    calls = iter(answers)
    waits: list[float] = []
    module.main(get=lambda repo, run_id: next(calls), wait=waits.append)
    return waits


def test_ci_passed_passes_when_every_job_succeeded(monkeypatch: pytest.MonkeyPatch) -> None:
    jobs = [
        job("lint and layers"),
        job("tests (ubuntu-latest)"),
        job("CI passed", "in_progress", None),
    ]
    assert run_ci_passed(monkeypatch, jobs) == []


@pytest.mark.parametrize(
    "leg",
    [
        job("tests (macos-latest)", conclusion="cancelled"),  # no runner in time (#548)
        job("browser (Linux, Chromium, 2/2)", conclusion="failure"),
        job("tests (windows-latest)", conclusion="skipped"),
        job("tests (macos-latest)", "queued", None),
    ],
)
def test_ci_passed_fails_on_one_leg_that_did_not_succeed(
    monkeypatch: pytest.MonkeyPatch, leg: dict
) -> None:
    jobs = [job("tests (ubuntu-latest)"), leg, job("CI passed", "in_progress", None)]
    with pytest.raises(SystemExit, match=re.escape(str(leg["name"]))):
        run_ci_passed(monkeypatch, *[jobs] * 3)


def test_ci_passed_waits_for_a_job_that_is_still_ending(monkeypatch: pytest.MonkeyPatch) -> None:
    ending = [job("tests (ubuntu-latest)", "in_progress", None)]
    done = [job("tests (ubuntu-latest)")]
    assert run_ci_passed(monkeypatch, ending, done) == [10]


def test_ci_passed_fails_when_it_finds_no_other_job(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(SystemExit, match="no job of run 7"):
        run_ci_passed(monkeypatch, [job("CI passed", "in_progress", None)])


def test_the_pr_browser_tests_run_in_two_shards_that_all_must_pass() -> None:
    """D-759 item 3: same job id, so "CI passed" needs every shard; the shard script
    decides the tests, so a new browser test file needs no workflow change."""
    browser = block(CI, "  browser:")
    assert "    name: browser (Linux, Chromium, ${{ matrix.shard }}/2)" in browser
    assert "fail-fast: false" in browser
    assert "shard: [1, 2]" in browser
    assert 'browser_shard.py chromium "$SHARD" 2 "$RUNNER_TEMP/shard.txt"' in browser
    assert '"@$RUNNER_TEMP/shard.txt"' in browser


@pytest.mark.parametrize(
    "leg",
    [
        job("browser (Linux, webkit, 1/2, reported only)", conclusion="failure"),
        job("browser (Linux, firefox, 2/2, reported only)", "in_progress", None),
        job("browser (Linux, ${{ matrix.browser }}, reported only)", conclusion="skipped"),
    ],
)
def test_ci_passed_does_not_wait_for_a_reported_only_job(
    monkeypatch: pytest.MonkeyPatch, leg: dict
) -> None:
    jobs = [job("tests (ubuntu-latest)"), leg, job("CI passed", "in_progress", None)]
    assert run_ci_passed(monkeypatch, jobs) == []


WEB = [
    "src/sci2audio/web/static/app.js",
    "src/sci2audio/app/window.py",
    "tests/browser/test_flow.py",
]
NOT_WEB = ["src/sci2audio/textprep/links.py", "tests/unit/test_web_design.py", "docs/web.md"]


def test_firefox_and_webkit_run_on_a_pr_that_changes_a_web_path_reported_only() -> None:
    """D-759 item 4: Firefox and WebKit on Linux run in PR CI when the PR changes the web
    interface, the app window or the browser tests; reported only until #437 closes."""
    paths = block(CI, "  web-paths:")
    assert "pull-requests: read" in paths
    pattern = re.search(r"grep -E '([^']+)' files\.txt", paths)
    assert pattern, paths
    assert all(re.search(pattern[1], path) for path in WEB)
    assert not any(re.search(pattern[1], path) for path in NOT_WEB)
    assert ".previous_filename // empty" in paths  # a file moved out of a web path counts
    reported = block(CI, "  browser-reported:")
    name = re.search(r"^    name: (.+)$", reported, re.M)
    assert name, reported
    assert load_ci_passed().REPORTED in name[1]  # so "CI passed" does not wait for it
    assert "if: needs.web-paths.outputs.web == 'true'" in reported
    assert "browser: [firefox, webkit]" in reported
    assert "fail-fast: false" in reported
    assert "browser-reported" not in block(CI, "  ci-passed:")


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
    one_line = re.findall(r"^ +(?:- )?run: (?![|>])(.+)$", job, re.M)
    assert one_line  # `- run: uv sync --locked`: the pattern finds one-line steps
    for command in one_line:
        assert "${{" not in command, command
    assert "tests/browser/test_screens.py" in job


def reads_profile(tree: ast.AST) -> bool:
    """Whether `tree` reads the environment variable HYPOTHESIS_PROFILE (os.environ.get,
    os.getenv or os.environ[...]), not merely names it."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and ast.unparse(node.func) in ("os.environ.get", "os.getenv"):
            key = node.args[0] if node.args else None
        elif isinstance(node, ast.Subscript) and ast.unparse(node.value) == "os.environ":
            key = node.slice
        else:
            continue
        if isinstance(key, ast.Constant) and key.value == "HYPOTHESIS_PROFILE":
            return True
    return False


def profile_readers() -> set[tuple[str, str]]:
    """(file, test function) of every test that reads HYPOTHESIS_PROFILE, directly or through
    a module-level name assigned from it (in its body or its decorators)."""
    readers = set()
    for path in sorted((ROOT / "tests").rglob("test_*.py")):
        source = path.read_text(encoding="utf-8")
        if "HYPOTHESIS_PROFILE" not in source:
            continue
        tree = ast.parse(source)
        derived = set()
        for node in tree.body:
            assigned = isinstance(node, ast.Assign | ast.AnnAssign) and node.value is not None
            if assigned and reads_profile(node.value):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                derived |= {t.id for t in targets if isinstance(t, ast.Name)}
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name.startswith(
                "test_"
            ):
                names = {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}
                if reads_profile(node) or names & derived:
                    readers.add((path.relative_to(ROOT).as_posix(), node.name))
    return readers


def test_every_test_that_reads_the_nightly_profile_runs_in_the_nightly_property_job() -> None:
    """The nightly property job runs only the tests its -m expression selects (D-759), so a
    test that takes more inputs at night must be one of them (a Hypothesis test, or marked
    `deep`), or nothing runs it at its nightly size."""
    job = block(NIGHTLY, "  property-deep:")
    expression = re.search(r'uv run pytest -m "([^"]+)"', job)
    assert expression, job
    assert "HYPOTHESIS_PROFILE: nightly" in job
    readers = profile_readers()
    assert len(readers) >= 3, readers  # the two token-soup fuzzes and the Schemathesis test
    files = sorted({file for file, _ in readers})
    command = [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"]
    listing = subprocess.run(
        [*command, "-m", expression.group(1), *files],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    selected = {
        (line.split("::")[0], line.split("::")[-1].split("[")[0])
        for line in listing.splitlines()
        if "::" in line
    }
    assert readers <= selected, sorted(readers - selected)


def load_pr_checks():
    path = ROOT / ".github" / "governance" / "pr_checks.py"
    spec = importlib.util.spec_from_file_location("sci2audio_pr_checks", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def codeql_ignored() -> list[str]:
    config = (ROOT / ".github" / "codeql" / "codeql-config.yml").read_text(encoding="utf-8")
    return [line.strip()[2:] for line in block(config, "paths-ignore:").splitlines()]


def test_codeql_scans_the_languages_of_the_default_setup_with_the_config_file() -> None:
    """#664: only advanced setup takes paths-ignore; the categories keep the default setup's
    names, so the alert history and its dismissals carry over."""
    codeql = (WORKFLOWS / "codeql.yml").read_text(encoding="utf-8")
    assert "        language: [actions, javascript-typescript, python]" in codeql
    assert "          build-mode: none" in codeql
    assert "          config-file: ./.github/codeql/codeql-config.yml" in codeql
    assert '          category: "/language:${{ matrix.language }}"' in codeql
    assert block(codeql, "  push:").strip() == "branches: [main]"
    assert block(codeql, "  pull_request:").strip() == "branches: [main]"
    assert "schedule:" in block(codeql, "on:")


def test_codeql_runs_with_the_least_permission_and_pinned_actions() -> None:
    codeql = (WORKFLOWS / "codeql.yml").read_text(encoding="utf-8")
    assert re.search(r"^permissions: \{\}$", codeql, re.M), codeql
    job = block(codeql, "  analyze:")
    permissions = block(job, "    permissions:").strip().splitlines()
    assert sorted(line.strip() for line in permissions) == [
        "contents: read",
        "security-events: write",
    ]
    # the version comment is Dependabot's to rewrite, so only its shape is checked
    uses = re.findall(r"^\s+- uses: (.+)$", codeql, re.M)
    assert len(uses) == 3, uses
    assert all(re.fullmatch(r"[\w./-]+@[0-9a-f]{40} # v\d+(\.\d+)*", u) for u in uses), uses
    checkout = next(u for u in uses if u.startswith("actions/checkout@"))
    assert "persist-credentials: false" in block(job, f"      - uses: {checkout}")


def test_codeql_ignores_the_prototype_and_the_workspace_and_nothing_that_ships_or_runs() -> None:
    """The prototype and governance/ (with the template copy of pr_checks.py) neither ship nor
    run; .github/governance/ is the copy CI runs on every PR, so it stays scanned."""
    ignored = codeql_ignored()
    assert ignored == ["docs/design/prototype/**", "governance/**"]
    pr_checks = load_pr_checks()
    unshipped = tracked_files("docs/design/prototype", "governance")
    assert unshipped
    assert all(pr_checks.matches(p, ignored) for p in unshipped)
    scanned = tracked_files("src", ".github")
    assert ".github/governance/pr_checks.py" in scanned
    assert not [p for p in scanned if pr_checks.matches(p, ignored)]


GOVERNANCE = (WORKFLOWS / "governance-pr-checks.yml").read_text(encoding="utf-8")


def test_the_pr_body_reaches_the_promised_tests_check_only_through_the_environment() -> None:
    """#687: the body is text anyone opening a PR writes, so it never enters a script."""
    step = block(GOVERNANCE, "      - name: Check that the promised tests exist")
    assert "PR_BODY: ${{ github.event.pull_request.body }}" in block(step, "        env:")
    # shown beside a failing title or ownership step, not only after it is fixed
    assert "        if: ${{ !cancelled() }}" in step
    # without uv the step would report every promise missing beside the real failure
    setup_line = next(
        line for line in GOVERNANCE.splitlines() if "- uses: astral-sh/setup-uv@" in line
    )
    setup = block(GOVERNANCE, setup_line)
    assert "        if: ${{ !cancelled() }}" in setup
    script = block(step, "        run: |")
    assert "${{" not in script
    assert "printf '%s' \"$PR_BODY\"" in script
    assert "promised_tests.py files" in script
    assert "promised_tests.py check" in script
    assert "uv run --frozen pytest --collect-only -q" in script


def test_the_base_is_collected_from_the_environment_without_a_new_sync() -> None:
    """#711: the promises that already collect on the base are listed. The base's files are
    collected with the head's synced interpreter, so the list costs no second sync, and the
    base commit reaches the script only through the environment."""
    step = block(GOVERNANCE, "      - name: Check that the promised tests exist")
    assert "PR_BASE: ${{ github.event.pull_request.base.sha }}" in block(step, "        env:")
    script = block(step, "        run: |")
    assert 'git worktree add --detach --quiet "$RUNNER_TEMP/base" "$PR_BASE"' in script
    assert 'PYTHONPATH="$RUNNER_TEMP/base/src" "$GITHUB_WORKSPACE/.venv/bin/python"' in script
    assert script.count("uv run") == 1
    assert "uv sync" not in script
    check = next(line for line in script.splitlines() if "promised_tests.py check" in line)
    assert check.rstrip().endswith('"$RUNNER_TEMP/base-collected.txt"'), check


def test_the_governance_check_keeps_its_job_name_and_pins_setup_uv() -> None:
    assert "    name: governance pr checks" in block(GOVERNANCE, "  checks:")
    uses = re.findall(r"^\s+- uses: (.+)$", GOVERNANCE, re.M)
    assert any(u.startswith("astral-sh/setup-uv@") for u in uses), uses
    assert all(re.fullmatch(r"[\w./-]+@[0-9a-f]{40} # v\d+(\.\d+)*", u) for u in uses), uses


def test_the_governance_check_runs_pr_code_only_without_write_access() -> None:
    """Collecting the promised tests runs the PR's conftest code: never with a token that can
    write or with the base repository's secrets (pull_request_target)."""
    assert "pull_request_target" not in GOVERNANCE
    assert block(GOVERNANCE, "on:").strip().startswith("pull_request:")
    permissions = block(GOVERNANCE, "permissions:").strip().splitlines()
    assert sorted(line.strip() for line in permissions) == ["contents: read", "pull-requests: read"]
    assert "permissions:" not in block(GOVERNANCE, "jobs:")
    checkout = next(
        u for u in re.findall(r"^\s+- uses: (.+)$", GOVERNANCE, re.M) if "checkout@" in u
    )
    assert "persist-credentials: false" in block(
        block(GOVERNANCE, f"      - uses: {checkout}"), "        with:"
    )


def test_the_governance_check_gates_a_risk_high_pr_on_the_ledger_of_branch_governance() -> None:
    """D-882: a risk:high PR fails the required check until the latest round entry on branch
    governance approves its head. The ledger never comes from the PR and the judging tool comes
    from the base commit, so a PR cannot approve itself; nothing reaches the script but the
    environment."""
    header = "      - name: Check that a risk:high PR has an approving review round for its head"
    step = block(GOVERNANCE, header)
    # every later step runs the PR's code (pr_checks.py, the PR's conftest), which could rewrite
    # $GITHUB_ENV, $GITHUB_PATH or the runner for a step after it (review-745 M1)
    steps = re.findall(r"^      - (?:name|uses): (.+)$", block(GOVERNANCE, "    steps:"), re.M)
    assert steps[0].startswith("actions/checkout@"), steps
    assert steps[1] == header.removeprefix("      - name: "), steps
    for later in steps[2:]:
        if not later.startswith("astral-sh/setup-uv@"):
            assert "        if: ${{ !cancelled() }}" in block(GOVERNANCE, f"      - name: {later}")
    assert "        if: ${{ !cancelled() }}" in step
    env = block(step, "        env:")
    for line in (
        "PR_NUMBER: ${{ github.event.pull_request.number }}",
        "PR_LABELS: ${{ join(github.event.pull_request.labels.*.name, ',') }}",
        "PR_BASE: ${{ github.event.pull_request.base.sha }}",
        "PR_HEAD: ${{ github.event.pull_request.head.sha }}",
    ):
        assert line in env, line
    script = block(step, "        run: |")
    assert "${{" not in script
    assert script.strip().startswith("set -o pipefail")
    assert "*,risk:high,*) ;;" in script
    assert (
        "git fetch --no-tags origin +refs/heads/governance:refs/remotes/origin/governance" in script
    )
    assert "git archive origin/governance governance/ledger" in script
    assert 'git show "$PR_BASE:governance/tools/ledger_tool.py"' in script
    ledger = '--ledger "$RUNNER_TEMP/governance/governance/ledger"'
    assert f'approved "$PR_NUMBER" --head "$PR_HEAD" {ledger}' in script


def browser_shard():  # type: ignore[no-untyped-def]
    """`.github/scripts/browser_shard.py`, imported as a module."""
    script = ROOT / ".github" / "scripts" / "browser_shard.py"
    spec = importlib.util.spec_from_file_location("browser_shard", script)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_browser_shard_reads_only_test_ids_not_the_quarantine_banner() -> None:
    """The quarantine banner names a test with "::" too; read as a test it made the shard's
    argument file hold "#697 tests/..." and pytest exit 4 with no test run (#698)."""
    listing = "\n".join(
        [
            "1 quarantined test(s), all to be fixed before v1.0 (D-374, #80):",
            "  #697 tests/browser/test_flow.py::test_resume[firefox]",
            "tests/browser/test_flow.py::test_open[firefox]",
            "tests/browser/test_flow.py::test_resume[firefox]",
            "tests/browser/test_axe.py::test_start_page[firefox]",
            "",
            "3 tests collected in 0.42s",
        ]
    )
    assert browser_shard().browser_tests(listing) == [
        "tests/browser/test_flow.py::test_open[firefox]",
        "tests/browser/test_flow.py::test_resume[firefox]",
        "tests/browser/test_axe.py::test_start_page[firefox]",
    ]
