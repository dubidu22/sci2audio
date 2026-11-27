"""The CI workflows' promises that a reader of the YAML can miss (#360, D-620): labels start
no CI run (one would cancel the run of the same commit), `ci:full` starts a run by hand with
the least permission, and "CI passed" stays strict, so no cancelled, skipped or failed job
ever leaves the required check green or skipped."""

from __future__ import annotations

import ast
import importlib.util
import json
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


FULL = (
    "github.event_name != 'pull_request' || "
    "contains(github.event.pull_request.labels.*.name, 'ci:full')"
)
FAST = "not slow and not benchmark and not browser"


def legs() -> tuple[list[dict], list[dict]]:
    """The legs of the job `tests`: of a full run (push to main and release/*, by hand,
    `ci:full`) and of a PR without `ci:full`."""
    tests = block(CI, "  tests:")
    include = re.search(
        r"^        include: \$\{\{ fromJSON\(\((.+)\) && '([^']+)' \|\| '([^']+)'\) \}\}$",
        tests,
        re.M,
    )
    assert include, tests
    assert include[1] == FULL
    return json.loads(include[2]), json.loads(include[3])


def leg_name(leg: dict) -> str:
    """The job name a leg gets from `name:` below, checked against the literal names."""
    shard = f", {leg['shard']}/3" if "shard" in leg else ""
    python = f", py{leg['python']}" if "python" in leg else ""
    return f"tests ({leg['os']}{shard}{python})"


def test_a_pr_runs_the_linux_fast_suite_in_three_shards() -> None:
    """#1132: the Linux fast suite no longer sets the length of a PR's run. Same job id, so
    "CI passed" needs every shard; the shard script decides the tests."""
    tests = block(CI, "  tests:")
    assert (
        "    name: tests (${{ matrix.os }}"
        "${{ matrix.shard && format(', {0}/3', matrix.shard) || '' }}"
        "${{ matrix.python && format(', py{0}', matrix.python) || '' }})"
    ) in tests
    assert "fail-fast: false" in tests
    _, pr = legs()
    assert [leg_name(leg) for leg in pr] == [
        "tests (ubuntu-latest, 1/3)",
        "tests (ubuntu-latest, 2/3)",
        "tests (ubuntu-latest, 3/3)",
    ]
    shard = block(tests, "      - name: The fast tests of this shard")
    assert re.search(r"^        if: matrix\.shard$", shard, re.M), shard
    assert f'shard.py "{FAST}" "$SHARD" 3 "$RUNNER_TEMP/shard.txt"' in shard
    assert "HYPOTHESIS_PROFILE: ci" in shard  # collected as it is run
    fast = block(tests, "      - name: Fast tests (unit, property-based, golden files)")
    assert f'uv run pytest -m "{FAST}" -n auto --durations=25 "$@"' in fast
    # only a shard leg reads the file; macOS, Windows and 3.13 run the suite whole
    assert 'if [ -n "$SHARD" ]; then set -- "@$RUNNER_TEMP/shard.txt"; fi' in fast
    assert "HYPOTHESIS_PROFILE: ci" in fast
    # the first shard and the whole-suite legs of 3.12: once per system, never on 3.13
    smoke = block(tests, "      - name: Smoke test (sci2audio script on a corpus PDF)")
    assert "        if: matrix.shard == 1 || (!matrix.shard && !matrix.python)" in smoke


def test_a_full_run_keeps_macos_and_windows_whole_and_adds_python_3_13() -> None:
    """D-580 and #69: "tests (macos-latest)" and "tests (windows-latest)" keep their names
    and the whole fast suite. #1132 moves Python 3.13 (#792) off ordinary PRs to where a
    break is still caught before a release: pushes to main and release/*, by hand, `ci:full`."""
    full, pr = legs()
    assert full[: len(pr)] == pr  # Linux 3.12 in the same three shards
    assert [leg_name(leg) for leg in full[len(pr) :]] == [
        "tests (macos-latest)",
        "tests (windows-latest)",
        "tests (ubuntu-latest, py3.13)",
    ]
    tests = block(CI, "  tests:")
    # UV_PYTHON wins over .python-version for uv sync and uv run; unset on the other legs
    assert "          python-version: ${{ matrix.python }}" in tests
    version = block(tests, "      - name: The tests run on Python 3.13")
    assert "        if: matrix.python == '3.13'" in version
    # should a later change let .python-version win, the leg would test 3.12 twice unseen
    assert "sys.version_info[:2] == (3, 13)" in version


def test_python_3_13_is_no_need_of_ci_passed_where_it_does_not_run() -> None:
    """A leg of `tests` exists only where it runs, so "CI passed" waits for it there and
    never meets it skipped; a job of its own would read skipped on every ordinary PR."""
    assert "tests-py313" not in CI
    full, pr = legs()
    assert not [leg for leg in pr if "python" in leg]
    assert [leg for leg in full if "python" in leg] == [{"os": "ubuntu-latest", "python": "3.13"}]


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
        job("browser (Linux, Chromium, 2/3)", conclusion="failure"),
        job("tests (ubuntu-latest, 3/3)", conclusion="failure"),  # one fast-suite shard
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


def test_the_pr_browser_tests_run_in_three_shards_that_all_must_pass() -> None:
    """D-759 item 3, three shards since #1132 (two had become the slowest job): same job
    id, so "CI passed" needs every shard; the shard script decides the tests, so a new
    browser test file needs no workflow change."""
    browser = block(CI, "  browser:")
    assert "    name: browser (Linux, Chromium, ${{ matrix.shard }}/3)" in browser
    assert not re.search(r"^    if:", browser, re.M), browser  # on every PR
    assert "fail-fast: false" in browser
    assert "shard: [1, 2, 3]" in browser
    assert 'shard.py browser "$SHARD" 3 "$RUNNER_TEMP/shard.txt" --browser chromium' in browser
    assert '"@$RUNNER_TEMP/shard.txt"' in browser


def test_firefox_webkit_and_the_nightly_keep_two_browser_shards() -> None:
    """#1132 changes Chromium on PRs only; Firefox and WebKit stay as D-759 left them."""
    reported = block(CI, "  browser-reported:")
    assert "    name: browser (Linux, ${{ matrix.browser }}, ${{ matrix.shard }}/2, " in reported
    assert "shard: [1, 2]" in reported
    command = 'shard.py browser "$SHARD" 2 "$RUNNER_TEMP/shard.txt" --browser "$BROWSER"'
    assert command in reported
    nightly = block(NIGHTLY, "  browsers:")
    assert "shard: [1, 2]" in nightly
    assert command in nightly


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


def test_codeql_ignores_the_prototype_and_the_archive_and_nothing_that_ships_or_runs() -> None:
    """The prototype and the archived KB in governance/ neither ship nor run."""
    ignored = codeql_ignored()
    assert ignored == ["docs/design/prototype/**", "governance/**"]
    prefixes = tuple(glob.removesuffix("**") for glob in ignored)
    assert tracked_files("docs/design/prototype", "governance")
    scanned = tracked_files("src", ".github")
    assert scanned
    assert not [p for p in scanned if p.startswith(prefixes)]


def shard_script():  # type: ignore[no-untyped-def]
    """`.github/scripts/shard.py`, imported as a module."""
    script = ROOT / ".github" / "scripts" / "shard.py"
    spec = importlib.util.spec_from_file_location("sci2audio_shard", script)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_one_shard_script_serves_the_browser_jobs_and_the_fast_suite() -> None:
    """#1132: one way to shard, so no job keeps an older copy of its rules (#698)."""
    assert not (ROOT / ".github" / "scripts" / "browser_shard.py").exists()
    for text in (CI, NIGHTLY):
        assert "browser_shard.py" not in text


def test_the_shard_reads_only_test_ids_not_the_quarantine_banner() -> None:
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
    assert shard_script().test_ids(listing) == [
        "tests/browser/test_flow.py::test_open[firefox]",
        "tests/browser/test_flow.py::test_resume[firefox]",
        "tests/browser/test_axe.py::test_start_page[firefox]",
    ]


SLOW_FILE = [f"tests/unit/test_slow.py::test_case[{n}]" for n in range(6)]
TESTS = ["tests/unit/test_a.py::test_one", *SLOW_FILE, "tests/unit/test_z.py::test_last"]


def test_a_files_tests_are_spread_over_the_shards() -> None:
    """Every third test from the shard's number on, so one slow file never fills one shard."""
    shards = [shard_script().shard(TESTS, number, 3) for number in (1, 2, 3)]
    assert shards == [
        [TESTS[0], SLOW_FILE[2], SLOW_FILE[5]],
        [SLOW_FILE[0], SLOW_FILE[3], TESTS[-1]],
        [SLOW_FILE[1], SLOW_FILE[4]],
    ]
    assert all(len(set(SLOW_FILE) & set(tests)) == 2 for tests in shards)


@pytest.mark.parametrize("total", [1, 2, 3, 4])
def test_the_shards_together_hold_every_collected_test_exactly_once(total: int) -> None:
    shards = [shard_script().shard(TESTS, number, total) for number in range(1, total + 1)]
    together = [test for tests in shards for test in tests]
    assert sorted(together) == sorted(TESTS)


def test_an_empty_shard_fails_with_a_clear_message() -> None:
    with pytest.raises(SystemExit, match=r"^shard 3 of 3 has no tests \(2 collected\)$"):
        shard_script().shard(TESTS[:2], 3, 3)


@pytest.mark.parametrize("number", [0, 4])
def test_a_shard_number_out_of_range_fails(number: int) -> None:
    with pytest.raises(SystemExit, match=f"^shard {number} is not between 1 and 3$"):
        shard_script().shard(TESTS, number, 3)


def test_the_shard_collects_with_the_marker_expression_and_writes_its_tests(
    tmp_path: Path,
) -> None:
    """The marker expression and any further pytest arguments (a browser) go to the
    collection; the shard's test ids go to the file `pytest @OUT` reads back."""
    calls: list[list[str]] = []

    def collect(args: list[str]) -> str:
        calls.append(args)
        return "\n".join(TESTS) + "\n\n8 tests collected in 0.1s\n"

    out = tmp_path / "shard.txt"
    shard_script().main("browser", 2, 3, out, ["--browser", "chromium"], collect=collect)
    assert calls == [["-m", "browser", "--browser", "chromium"]]
    assert out.read_text(encoding="utf-8").splitlines() == TESTS[1::3]


def test_the_shard_collects_tests_with_golden_files(tmp_path: Path) -> None:
    """A collection runs no test, so syrupy reads every snapshot as unused and fails it;
    the fast suite's shards collect golden-file tests (#1132), the browser ones never did."""
    out = tmp_path / "shard.txt"
    golden = "tests/unit/test_core_objects.py"
    shard_script().main(FAST, 1, 1, out, [golden])
    tests = out.read_text(encoding="utf-8").splitlines()
    assert tests
    assert all(test.startswith(f"{golden}::") for test in tests)
