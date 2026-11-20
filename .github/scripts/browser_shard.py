"""Writes the browser tests of one CI shard to a pytest arguments file (D-759).

    python .github/scripts/browser_shard.py BROWSER SHARD TOTAL OUT

Collects `pytest -m browser --browser BROWSER` and keeps every TOTAL-th test, starting at
SHARD (1-based), so a test file's tests are spread over the shards and a new test file needs
no workflow change. OUT is read back with `pytest @OUT`. Fails if the shard would be empty.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def browser_tests(listing: str) -> list[str]:
    """The test ids of `pytest --collect-only -q` output: the lines that start with `tests/`.
    The quarantine banner (tests/conftest.py) names tests with "::" too, indented and after
    the issue number; read as a test, it made pytest exit 4 with nothing run (#698)."""
    return [line for line in listing.splitlines() if line.startswith("tests/") and "::" in line]


def main(browser: str, shard: int, total: int, out: Path) -> None:
    if not 1 <= shard <= total:
        sys.exit(f"shard {shard} is not between 1 and {total}")
    listing = subprocess.run(  # noqa: S603 (this Python running pytest, no shell)
        [
            sys.executable,
            "-m",
            "pytest",
            "-m",
            "browser",
            "--browser",
            browser,
            "--collect-only",
            "-q",
            "-p",
            "no:cacheprovider",
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    tests = browser_tests(listing)
    mine = tests[shard - 1 :: total]
    if not mine:
        sys.exit(f"shard {shard} of {total} has no tests ({len(tests)} collected)")
    out.write_text("\n".join(mine) + "\n", encoding="utf-8")
    print(f"shard {shard} of {total}: {len(mine)} of {len(tests)} browser tests ({browser})")


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), Path(sys.argv[4]))
