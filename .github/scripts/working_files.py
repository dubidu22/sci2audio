"""Fails CI when a working file is tracked on the branch under test (THR-13, D-874, #746).

    python3 .github/scripts/working_files.py [--root DIR]

Working files (plans, round reports, batch files, ledger entries, the state file and the pending
decisions) live on branch governance only. Copies on main are never updated, so a thread that
reads them reads stale state. CI runs on pull requests and on pushes to main and release/**,
never on branch governance, which is how that branch stays exempt. Standard library and git only.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path

WORKING_DIRS = ("governance/plans/", "governance/ledger/")
WORKING_FILES = ("governance/project-state.yaml", "governance/kb/pending-decisions.md")
# the ruleset generator writes these on main through ruleset PRs, so main holds the copy that counts
KEPT = (
    "governance/plans/README.md",
    "governance/ledger/README.md",
    "governance/ledger/deferred/since.txt",
)
POINTER_FILE = "governance/README.md"
POINTER = (
    "Working files (plans, round reports, batch files, ledger entries, `project-state.yaml`, "
    "`kb/pending-decisions.md`) live only on branch `governance` (THR-13, D-874): "
    "`git worktree add ../sci2audio-governance governance`."
)


def working_files(paths: Iterable[str]) -> list[str]:
    return [
        p for p in paths if p not in KEPT and (p in WORKING_FILES or p.startswith(WORKING_DIRS))
    ]


def tracked(root: Path) -> list[str]:
    git = shutil.which("git")
    if git is None:
        raise SystemExit("git not found")
    listing = subprocess.run(  # noqa: S603 (git of the runner, no shell)
        [git, "-C", str(root), "ls-files", "-z"], check=True, capture_output=True, text=True
    ).stdout
    return [p for p in listing.split("\0") if p]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, default=Path("."), help="the checkout (default: .)")
    args = ap.parse_args(argv)
    hits = working_files(tracked(args.root))
    for path in hits:
        print(f"working file on this branch: {path}")
    if hits:
        print(POINTER)
        return 1
    print("no working files on this branch")
    return 0


if __name__ == "__main__":
    sys.exit(main())
