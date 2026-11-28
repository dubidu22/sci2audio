"""Writes the tests of one CI shard to a pytest arguments file (D-759, #1132).

    python .github/scripts/shard.py MARKERS SHARD TOTAL OUT [PYTEST_ARG ...]

Collects `pytest -m MARKERS PYTEST_ARG ...` (a browser job adds `--browser NAME`) and keeps
every TOTAL-th test, starting at SHARD (1-based), so a test file's tests are spread over the
shards and a new test file needs no workflow change. OUT is read back with `pytest @OUT`.
Fails if the shard would be empty. The browser jobs and the fast suite share it, so there is
one way to shard and a fix to it reaches every sharded job (#698, #1132).
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable
from pathlib import Path


def test_ids(listing: str) -> list[str]:
    """The test ids of `pytest --collect-only -q` output: the lines that start with `tests/`.
    The quarantine banner (tests/conftest.py) names tests with "::" too, indented and after
    the issue number; read as a test, it made pytest exit 4 with nothing run (#698)."""
    return [line for line in listing.splitlines() if line.startswith("tests/") and "::" in line]


def shard(tests: list[str], number: int, total: int) -> list[str]:
    """Every `total`-th of `tests` from the `number`-th on; never empty."""
    if not 1 <= number <= total:
        sys.exit(f"shard {number} is not between 1 and {total}")
    mine = tests[number - 1 :: total]
    if not mine:
        sys.exit(f"shard {number} of {total} has no tests ({len(tests)} collected)")
    return mine


def collect_only(args: list[str]) -> str:
    """A collection runs no test, so syrupy reads every snapshot as unused and would exit 1.
    A collection that fails stops the step with pytest's own output: the file that failed
    to import and its error (#1256)."""
    ran = subprocess.run(  # noqa: S603 (this Python running pytest, no shell)
        [
            sys.executable,
            "-m",
            "pytest",
            *args,
            "--collect-only",
            "-q",
            "-p",
            "no:cacheprovider",
            "--snapshot-warn-unused",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if ran.returncode != 0:
        sys.stderr.write(ran.stdout + ran.stderr)
        sys.exit(
            f"collecting the tests failed (pytest exit {ran.returncode}); see its output above"
        )
    return ran.stdout


def main(
    markers: str,
    number: int,
    total: int,
    out: Path,
    pytest_args: list[str],
    collect: Callable[[list[str]], str] = collect_only,
) -> None:
    tests = test_ids(collect(["-m", markers, *pytest_args]))
    mine = shard(tests, number, total)
    out.write_text("\n".join(mine) + "\n", encoding="utf-8")
    print(f"shard {number} of {total}: {len(mine)} of {len(tests)} tests (-m {markers!r})")


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), Path(sys.argv[4]), sys.argv[5:])
