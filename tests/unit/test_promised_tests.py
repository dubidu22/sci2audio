"""A test the plan promises is on the PR head (#687, META-03): the PR body lists the promises
as pytest node IDs under a fixed heading, and the governance check fails when one does not
collect. A body without the heading passes, until the plan template requires it."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

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
