#!/usr/bin/env python3
"""
Checks that every test a plan promises exists on the pull request's head (#687, META-03).

    python3 promised_tests.py files BODY            the test files to collect, one per line
    python3 promised_tests.py check BODY COLLECTED  compares the promises with the collected tests

    BODY       the pull request body
    COLLECTED  output of `pytest --collect-only -q <the files>` (may be absent when there is no promise)

The promises are the backticked pytest node IDs (`tests/unit/test_x.py::test_name`) in the section
under the level-2 heading HEADING, up to the next heading of level 1 or 2. A body without the
heading passes: the check is opt-in until the plan template requires it. A heading that lists no
node ID fails, so an empty promise never passes, and so does any `.py::` in the section that is
not a backticked node ID, so no listed promise is dropped unread. Lines in fenced code blocks are not read. A parametrized test may be promised without its
parameters and a class without its methods. Standard library only, like pr_checks.py.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

HEADING = "## Tests promised in the plan"
# parameters may hold spaces (`test_x[a b]`); names may not
NODE_RE = re.compile(r"[\w./-]+\.py(::\w+)+(\[[^`\]]*\])?")
TOKEN_RE = re.compile(r"`([^`]*\.py::[^`]*)`")
BARE_RE = re.compile(r"\S*\.py::\S*")
END_RE = re.compile(r"^#{1,2}(\s|$)")
FENCE_RE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")


def section(body: str) -> list[str] | None:
    """The lines under HEADING outside fenced code blocks, where a `#` line is no heading."""
    lines = body.replace("\r\n", "\n").split("\n")
    try:
        start = [line.rstrip() for line in lines].index(HEADING)
    except ValueError:
        return None
    out: list[str] = []
    fence = ""
    for line in lines[start + 1 :]:
        opened = FENCE_RE.match(line)
        if fence:
            if opened and opened.group(1)[0] == fence[0] and len(opened.group(1)) >= len(fence):
                fence = ""
            continue
        if opened:
            fence = opened.group(1)
            continue
        if END_RE.match(line):
            break
        out.append(line)
    return out


def read(body: str) -> tuple[list[str], list[str]] | None:
    """(promises, unreadable): a `.py::` in the section that is not a backticked node ID is
    unreadable, whether its backticks are missing, unpaired or around something else."""
    lines = section(body)
    if lines is None:
        return None
    good: list[str] = []
    bad: list[str] = []
    for line in lines:
        for token in TOKEN_RE.findall(line):
            into = good if NODE_RE.fullmatch(token) else bad
            if token not in into:
                into.append(token)
        for rest in BARE_RE.findall(TOKEN_RE.sub(" ", line)):
            if rest not in bad:
                bad.append(rest)
    return good, bad


def promised(body: str) -> list[str] | None:
    found = read(body)
    return None if found is None else found[0]


def unreadable(body: str) -> list[str]:
    found = read(body)
    return [] if found is None else found[1]


def missing(promises: list[str], collected: list[str]) -> list[str]:
    def kept(node: str) -> bool:
        return any(c == node or c.startswith((node + "[", node + "::")) for c in collected)

    return [node for node in promises if not kept(node)]


def files(promises: list[str]) -> list[str]:
    # a file that does not exist is not passed to pytest, which would stop at it: its promises are missing
    out: list[str] = []
    for node in promises:
        path = node.split("::", 1)[0]
        if path not in out and Path(path).is_file():
            out.append(path)
    return out


def main(argv: list[str]) -> int:
    if len(argv) == 2 and argv[0] == "files":
        promises = promised(Path(argv[1]).read_text(encoding="utf-8")) or []
        for path in files(promises):
            print(path)
        return 0
    if len(argv) == 3 and argv[0] == "check":
        body = Path(argv[1]).read_text(encoding="utf-8")
        promises = promised(body)
        if promises is None:
            print(f'ok   promised tests: no "{HEADING}" section (opt-in)')
            return 0
        bad = unreadable(body)
        if bad:
            print(f"FAIL promised tests: not read as a node ID: {', '.join(bad)}")
            return 1
        if not promises:
            print(f"FAIL promised tests: the section lists no node ID; name each test as `tests/...py::test_name` under {HEADING}")
            return 1
        listing = Path(argv[2])
        text = listing.read_text(encoding="utf-8") if listing.is_file() else ""
        collected = [line.strip() for line in text.splitlines() if "::" in line]
        absent = missing(promises, collected)
        if absent:
            print(f"FAIL promised tests: not collected on the PR head: {', '.join(absent)}")
            if not collected:
                # a failed sync or a collection error leaves no test ID: show why instead of blaming the IDs
                print("     the collection gave no test; its last lines:")
                for line in [line for line in text.splitlines() if line.strip()][-5:]:
                    print(f"     {line}")
            return 1
        print(f"ok   promised tests: {len(promises)} of {len(promises)} collect")
        return 0
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
