"""A test the plan promises is on the PR head (#687, META-03): the PR body lists the promises
as pytest node IDs under a fixed heading, and the governance check fails when one does not
collect. A body without the heading passes, until the plan template requires it."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / ".github" / "governance" / "promised_tests.py"
HERE = "tests/unit/test_promised_tests.py"


def load():
    spec = importlib.util.spec_from_file_location("sci2audio_promised_tests", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PROMISED = load()

BODY = """## What and why

Closes #1. Not a promise: `tests/unit/test_a.py::test_outside`.

## Tests promised in the plan

- `tests/unit/test_a.py::test_one`
- `tests/unit/test_a.py::test_two`, and again `tests/unit/test_a.py::test_one`
- `tests/unit/test_b.py::TestKind::test_three[x-1]`

### A subheading stays in the section

- `tests/unit/test_b.py::test_four` (no `uv run` or `ruff` counts)

## Risk

`tests/unit/test_a.py::test_after` is not a promise.
"""


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_a_body_without_the_heading_promises_nothing() -> None:
    assert PROMISED.promised("## What and why\n\n- `tests/unit/test_a.py::test_one`\n") is None
    assert PROMISED.promised("") is None
    assert PROMISED.promised("### Tests promised in the plan\n- `t.py::x`\n") is None


def test_the_node_ids_under_the_heading_are_the_promises() -> None:
    assert PROMISED.promised(BODY) == [
        "tests/unit/test_a.py::test_one",
        "tests/unit/test_a.py::test_two",
        "tests/unit/test_b.py::TestKind::test_three[x-1]",
        "tests/unit/test_b.py::test_four",
    ]


def test_the_section_ends_at_the_next_heading() -> None:
    promised = PROMISED.promised(BODY)
    assert promised is not None
    assert "tests/unit/test_a.py::test_after" not in promised
    assert "tests/unit/test_a.py::test_outside" not in promised
    body = "## Tests promised in the plan\n- `t.py::a`\n# Top\n- `t.py::b`\n"
    assert PROMISED.promised(body) == ["t.py::a"]


def test_a_heading_that_lists_no_node_id_fails(tmp_path: Path) -> None:
    body = tmp_path / "body.md"
    body.write_text("## Tests promised in the plan\n\nAll of them, trust me.\n", encoding="utf-8")
    (tmp_path / "collected.txt").write_text("", encoding="utf-8")
    assert PROMISED.promised(body.read_text(encoding="utf-8")) == []
    result = run("check", str(body), str(tmp_path / "collected.txt"))
    assert result.returncode == 1
    assert "FAIL promised tests: the section lists no node ID" in result.stdout


def test_a_crlf_body_reads_like_an_lf_body() -> None:
    assert PROMISED.promised(BODY.replace("\n", "\r\n")) == PROMISED.promised(BODY)


def test_a_parametrized_or_class_promise_is_kept_by_its_collected_tests() -> None:
    collected = [
        "tests/unit/test_a.py::test_one[p0]",
        "tests/unit/test_a.py::test_one[p1]",
        "tests/unit/test_b.py::TestKind::test_three",
        "tests/unit/test_b.py::test_four",
    ]
    promised = [
        "tests/unit/test_a.py::test_one",
        "tests/unit/test_b.py::TestKind",
        "tests/unit/test_b.py::test_four",
    ]
    assert PROMISED.missing(promised, collected) == []


def test_a_promise_that_does_not_collect_is_named_as_missing() -> None:
    collected = ["tests/unit/test_a.py::test_one_more", "tests/unit/test_a.py::test_two"]
    promised = ["tests/unit/test_a.py::test_one", "tests/unit/test_a.py::test_two"]
    assert PROMISED.missing(promised, collected) == ["tests/unit/test_a.py::test_one"]


def test_the_check_collects_the_real_files_and_names_the_missing_id(tmp_path: Path) -> None:
    real = f"{HERE}::test_a_body_without_the_heading_promises_nothing"
    invented = f"{HERE}::test_nobody_wrote_this"
    body = tmp_path / "body.md"
    body.write_text(
        f"## Tests promised in the plan\n- `{real}`\n- `{invented}`\n", encoding="utf-8"
    )
    files = run("files", str(body))
    assert files.returncode == 0
    assert files.stdout.split() == [HERE]
    listing = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", HERE],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    collected = tmp_path / "collected.txt"
    collected.write_text(listing, encoding="utf-8")
    result = run("check", str(body), str(collected))
    assert result.returncode == 1, result.stdout
    assert result.stdout.strip() == f"FAIL promised tests: not collected on the PR head: {invented}"
    body.write_text(f"## Tests promised in the plan\n- `{real}`\n", encoding="utf-8")
    result = run("check", str(body), str(collected))
    assert result.returncode == 0, result.stdout
    assert result.stdout.strip() == "ok   promised tests: 1 of 1 collect"


def test_a_promised_file_that_does_not_exist_is_missing(tmp_path: Path) -> None:
    gone = "tests/unit/test_nothing_here.py::test_x"
    body = tmp_path / "body.md"
    body.write_text(f"## Tests promised in the plan\n- `{gone}`\n- `{HERE}::t`\n", encoding="utf-8")
    assert run("files", str(body)).stdout.split() == [HERE]
    collected = tmp_path / "collected.txt"
    collected.write_text(f"{HERE}::t\n\n1 test collected in 0.01s\n", encoding="utf-8")
    result = run("check", str(body), str(collected))
    assert result.returncode == 1
    assert result.stdout.strip() == f"FAIL promised tests: not collected on the PR head: {gone}"


def test_a_body_without_the_heading_passes_the_check(tmp_path: Path) -> None:
    body = tmp_path / "body.md"
    body.write_text("## What and why\n\nCloses #1.\n", encoding="utf-8")
    assert run("files", str(body)).stdout == ""
    result = run("check", str(body), str(tmp_path / "absent.txt"))
    assert result.returncode == 0
    assert 'no "## Tests promised in the plan" section (opt-in)' in result.stdout


def test_a_hash_line_inside_a_code_block_does_not_end_the_section() -> None:
    """A shell comment in a fence is not a heading."""
    body = (
        "## Tests promised in the plan\n- `tests/a.py::t1`\n\n```bash\n# comment in a fence\n"
        "## nor this\n```\n\n~~~\n# tilde fence\n~~~\n- `tests/a.py::t2`\n"
        "## Risk\n- `tests/a.py::t3`\n"
    )
    assert PROMISED.promised(body) == ["tests/a.py::t1", "tests/a.py::t2"]


def test_a_promise_that_cannot_be_read_fails(tmp_path: Path) -> None:
    """A listed promise is never dropped without a word."""
    spaced = "tests/a.py::t[a b]"
    assert PROMISED.promised(f"## Tests promised in the plan\n- `{spaced}`\n") == [spaced]
    body = tmp_path / "body.md"
    body.write_text(
        f"## Tests promised in the plan\n- `{HERE}::t`\n- `{HERE}:: t`\n- `{HERE}::t[open`\n",
        encoding="utf-8",
    )
    collected = tmp_path / "collected.txt"
    collected.write_text(f"{HERE}::t\n", encoding="utf-8")
    result = run("check", str(body), str(collected))
    assert result.returncode == 1
    assert result.stdout.strip() == (
        f"FAIL promised tests: not read as a node ID: {HERE}:: t, {HERE}::t[open"
    )


def test_a_collection_that_gives_no_test_says_so(tmp_path: Path) -> None:
    body = tmp_path / "body.md"
    body.write_text(f"## Tests promised in the plan\n- `{HERE}::t`\n", encoding="utf-8")
    collected = tmp_path / "collected.txt"
    collected.write_text("ERROR: something broke\nno tests ran in 0.01s\n", encoding="utf-8")
    result = run("check", str(body), str(collected))
    assert result.returncode == 1
    assert result.stdout.splitlines() == [
        f"FAIL promised tests: not collected on the PR head: {HERE}::t",
        "     the collection gave no test; its last lines:",
        "     ERROR: something broke",
        "     no tests ran in 0.01s",
    ]


def test_a_promise_without_both_backticks_fails(tmp_path: Path) -> None:
    body = tmp_path / "body.md"
    body.write_text(
        f"## Tests promised in the plan\n- `{HERE}::t`\n- {HERE}::bare\n- `{HERE}::unclosed\n",
        encoding="utf-8",
    )
    collected = tmp_path / "collected.txt"
    collected.write_text(f"{HERE}::t\n", encoding="utf-8")
    result = run("check", str(body), str(collected))
    assert result.returncode == 1
    assert result.stdout.strip() == (
        f"FAIL promised tests: not read as a node ID: {HERE}::bare, `{HERE}::unclosed"
    )


@pytest.mark.parametrize(
    "heading",
    [
        "### Tests promised in the plan",
        "## Tests promised in the plan:",
        " ## Tests promised in the plan",
        "## tests promised in the plan",
        "**Tests promised in the plan**",
        "Tests promised in plan.",
    ],
)
def test_a_near_miss_heading_fails(tmp_path: Path, heading: str) -> None:
    """The heading is mandatory in a plan's PR (D-849): a misspelt one must not pass as absent."""
    body = tmp_path / "body.md"
    body.write_text(
        f"## What and why\n\nCloses #1.\n\n{heading}\n\n- `{HERE}::t`\n", encoding="utf-8"
    )
    assert run("files", str(body)).stdout == ""
    result = run("check", str(body), str(tmp_path / "absent.txt"))
    assert result.returncode == 1
    assert result.stdout.startswith(f'FAIL promised tests: near-miss heading "{heading.strip()}"')
    assert "## Tests promised in the plan" in result.stdout


def test_a_near_miss_inside_a_code_block_is_not_a_heading(tmp_path: Path) -> None:
    body = tmp_path / "body.md"
    body.write_text(
        "## What and why\n\n```\n### Tests promised in the plan\n```\n", encoding="utf-8"
    )
    result = run("check", str(body), str(tmp_path / "absent.txt"))
    assert result.returncode == 0
    assert "(opt-in)" in result.stdout


def test_the_exact_heading_wins_over_a_near_miss(tmp_path: Path) -> None:
    body = tmp_path / "body.md"
    body.write_text(
        f"### Tests promised in the plan:\n\n## Tests promised in the plan\n\n- `{HERE}::t`\n",
        encoding="utf-8",
    )
    collected = tmp_path / "collected.txt"
    collected.write_text(f"{HERE}::t\n", encoding="utf-8")
    result = run("check", str(body), str(collected))
    assert result.returncode == 0
    assert result.stdout.strip() == "ok   promised tests: 1 of 1 collect"


def test_a_fenced_example_of_the_heading_does_not_start_the_section() -> None:
    """A body that explains PLAN-01 shows the heading in a fence before its real section."""
    body = (
        "## What and why\n\n```\n## Tests promised in the plan\n- `tests/a.py::example`\n```\n\n"
        "## Tests promised in the plan\n\n- `tests/a.py::t1`\n\n## Risk\n"
    )
    assert PROMISED.promised(body) == ["tests/a.py::t1"]


def test_a_fenced_heading_does_not_hide_a_near_miss(tmp_path: Path) -> None:
    body = tmp_path / "body.md"
    body.write_text(
        "```\n## Tests promised in the plan\n```\n\n### Tests promised in the plan\n\n"
        f"- `{HERE}::t`\n",
        encoding="utf-8",
    )
    result = run("check", str(body), str(tmp_path / "absent.txt"))
    assert result.returncode == 1
    assert result.stdout.startswith('FAIL promised tests: near-miss heading "### Tests promised')


PR_689 = """Closes #667
Closes #669

Batch B-W2, PR B (app). Plan: `governance/plans/web-b-w2-plan.md` §2 (branch `governance`).

## What changes

- `JobSettings.plugins: bool = True`, checked like `subtitles`.

## Plan tests

Plan: `governance/plans/web-b-w2-plan.md`. Each was written first and failed before the change.

- T1 `tests/unit/test_cli_script.py::test_no_plugins_runs_only_the_built_in_steps`
- T2 `tests/unit/test_cli_convert.py::test_no_plugins_makes_the_audiobook_without_plugins`
- T11 `tests/unit/test_cli_golden.py::test_command_help_text`: snapshot updated (see below)

**One existing test changed on purpose:** `test_app_settings.py::test_the_file_keeps_every_setting`.

## Licence

No new dependency, copied file, model or text.
"""


def test_the_body_shape_of_pr_689_fails(tmp_path: Path) -> None:
    """#708: #689 listed its plan's tests under "## Plan tests" and passed as no section."""
    body = tmp_path / "body.md"
    body.write_text(PR_689, encoding="utf-8")
    assert run("files", str(body)).stdout == ""
    result = run("check", str(body), str(tmp_path / "absent.txt"))
    assert result.returncode == 1
    assert result.stdout.strip() == (
        'FAIL promised tests: "## Plan tests" (line 10) lists node IDs; '
        "list the plan's tests under ## Tests promised in the plan"
    )


@pytest.mark.parametrize(
    "heading",
    [
        "## Plan tests",
        "## Tests",
        "## How it was tested",
        "## Tests (written first; each failed on main)",
        "## TESTS",
    ],
)
def test_node_ids_under_a_test_named_heading_fail_as_a_near_miss(
    tmp_path: Path, heading: str
) -> None:
    body = tmp_path / "body.md"
    body.write_text(
        f"## What and why\n\nCloses #1.\n\n{heading}\n\n- `{HERE}::t`\n\n## Risk\n",
        encoding="utf-8",
    )
    result = run("check", str(body), str(tmp_path / "absent.txt"))
    assert result.returncode == 1
    assert result.stdout.startswith(f'FAIL promised tests: "{heading}" (line 5) lists node IDs')


def test_a_test_named_heading_without_node_ids_passes(tmp_path: Path) -> None:
    """A docs or decision-log PR says how it was tested without naming a test."""
    body = tmp_path / "body.md"
    body.write_text(
        "## How it was tested\n\nRead the page; `uv run pytest` is green.\n", encoding="utf-8"
    )
    result = run("check", str(body), str(tmp_path / "absent.txt"))
    assert result.returncode == 0
    assert "(opt-in)" in result.stdout


def test_a_fenced_node_id_under_a_test_named_heading_passes(tmp_path: Path) -> None:
    body = tmp_path / "body.md"
    body.write_text(f"## Tests\n\n```\n- `{HERE}::t`\n```\n", encoding="utf-8")
    result = run("check", str(body), str(tmp_path / "absent.txt"))
    assert result.returncode == 0
    assert "(opt-in)" in result.stdout


@pytest.mark.parametrize("heading", ["## What and why", "### Plan tests", "# Tests"])
def test_node_ids_under_another_heading_pass(tmp_path: Path, heading: str) -> None:
    """Only a level-2 heading that names tests is taken for a misnamed promise (#708)."""
    body = tmp_path / "body.md"
    body.write_text(f"## Summary\n\n{heading}\n\n- `{HERE}::t`\n", encoding="utf-8")
    result = run("check", str(body), str(tmp_path / "absent.txt"))
    assert result.returncode == 0
    assert "(opt-in)" in result.stdout


def test_the_exact_heading_wins_over_a_test_named_section(tmp_path: Path) -> None:
    body = tmp_path / "body.md"
    body.write_text(
        f"## Tests promised in the plan\n\n- `{HERE}::t`\n\n"
        f"## Test summary\n\n- `{HERE}::old` still passes\n",
        encoding="utf-8",
    )
    collected = tmp_path / "collected.txt"
    collected.write_text(f"{HERE}::t\n", encoding="utf-8")
    result = run("check", str(body), str(collected))
    assert result.returncode == 0
    assert result.stdout.strip() == "ok   promised tests: 1 of 1 collect"


def test_a_section_of_tests_already_on_main_passes(tmp_path: Path) -> None:
    """The check proves presence, not novelty: whether the promises are the plan's is the
    reviewer's call (#708)."""
    old = f"{HERE}::test_a_body_without_the_heading_promises_nothing"
    body = tmp_path / "body.md"
    body.write_text(f"## Tests promised in the plan\n- `{old}`\n", encoding="utf-8")
    collected = tmp_path / "collected.txt"
    collected.write_text(f"{old}\n", encoding="utf-8")
    result = run("check", str(body), str(collected))
    assert result.returncode == 0
    assert result.stdout.strip() == "ok   promised tests: 1 of 1 collect"
