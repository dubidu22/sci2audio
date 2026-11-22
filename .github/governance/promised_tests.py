#!/usr/bin/env python3
"""
Checks that every test a plan promises exists on the pull request's head (#687, META-03).

    python3 promised_tests.py files BODY            the test files to collect, one per line
    python3 promised_tests.py check BODY COLLECTED [BASE]
                                                    compares the promises with the collected tests

    BODY       the pull request body
    COLLECTED  output of `pytest --collect-only -q <the files>` (may be absent when there is no promise)
    BASE       the same output for the promised files on the base commit (optional, may be absent)

The promises are the backticked pytest node IDs (`tests/unit/test_x.py::test_name`) in the section
under the level-2 heading HEADING, up to the next heading of level 1 or 2. A body without the
heading passes, since PRs without a plan (decision log, Dependabot) carry none. A line that is
almost the heading fails, because PLAN-01 requires the exact heading in a plan's PR (D-849) and a
near miss would otherwise pass as absent. So does another level-2 heading that names tests
("## Plan tests", "## How it was tested") when its section lists a node ID (#708): those are
promises under the wrong heading. A heading that lists no node ID fails, so an empty promise never passes, and so does any `.py::` in the section that is
not a backticked node ID, so no listed promise is dropped unread. Lines in fenced code blocks are not read. A parametrized test may be promised without its
parameters and a class without its methods. Standard library only, like pr_checks.py.

The check proves that each promise collects on the head, not that it is new: a section that
lists only tests already on main passes. Whether the promises are the plan's is the reviewer's
call against the plan, so the promises that already collect on the base are printed as a note
beside the result (#711). Only lines that start with `tests/` are collected tests: a quarantine
banner (`  #697 tests/...::...`) names a test without being one (#698).
"""

from __future__ import annotations

import re
import sys
from collections.abc import Iterator
from pathlib import Path

HEADING = "## Tests promised in the plan"
# parameters may hold spaces (`test_x[a b]`); names may not
NODE_RE = re.compile(r"[\w./-]+\.py(::\w+)+(\[[^`\]]*\])?")
TOKEN_RE = re.compile(r"`([^`]*\.py::[^`]*)`")
BARE_RE = re.compile(r"\S*\.py::\S*")
END_RE = re.compile(r"^#{1,2}(\s|$)")
TESTS_HEADING_RE = re.compile(r"##\s.*test", re.I)
FENCE_RE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
# another level, case, a leading space, bold, a missing "the", a trailing colon or full stop
NEAR_RE = re.compile(r"\s*(#{1,6}\s*)?(\*\*|__)?\s*tests\s+promised\s+in\s+(the\s+)?plan\s*(\*\*|__)?\s*[:.]?\s*", re.I)


def outside_fences(lines: list[str]) -> Iterator[tuple[int, str]]:
    """(line number, line) for each line outside fenced code blocks."""
    fence = ""
    for number, line in enumerate(lines, 1):
        opened = FENCE_RE.match(line)
        if fence:
            if opened and opened.group(1)[0] == fence[0] and len(opened.group(1)) >= len(fence):
                fence = ""
            continue
        if opened:
            fence = opened.group(1)
            continue
        yield number, line


def section(body: str) -> list[str] | None:
    """The lines under HEADING outside fenced code blocks, where a `#` line is no heading and
    HEADING shown as an example does not start the section."""
    out: list[str] = []
    started = False
    for _, line in outside_fences(body.replace("\r\n", "\n").split("\n")):
        if not started:
            started = line.rstrip() == HEADING
        elif END_RE.match(line):
            break
        else:
            out.append(line)
    return out if started else None


def near_miss(body: str) -> str | None:
    """The first line outside fenced code blocks that is almost HEADING, when HEADING is absent."""
    lines = [line for _, line in outside_fences(body.replace("\r\n", "\n").split("\n"))]
    if HEADING in (line.rstrip() for line in lines):
        return None
    return next((line.strip() for line in lines if NEAR_RE.fullmatch(line)), None)


def misnamed(body: str) -> str | None:
    """The first level-2 heading that names tests and whose section lists a node ID, as
    '"<heading>" (line N)', when HEADING is absent (#708)."""
    lines = list(outside_fences(body.replace("\r\n", "\n").split("\n")))
    if HEADING in (line.rstrip() for _, line in lines):
        return None
    heading = ""
    for number, line in lines:
        if END_RE.match(line):
            heading = f'"{line.strip()}" (line {number})' if TESTS_HEADING_RE.match(line) else ""
        elif heading and TOKEN_RE.search(line):
            return heading
    return None


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


def collected(listing: str) -> list[str]:
    return [line.strip() for line in listing.splitlines() if line.startswith("tests/")]


def read_listing(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


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
    if len(argv) in (3, 4) and argv[0] == "check":
        body = Path(argv[1]).read_text(encoding="utf-8")
        promises = promised(body)
        if promises is None:
            near = near_miss(body)
            if near is not None:
                print(f'FAIL promised tests: near-miss heading "{near}"; write it exactly as {HEADING}')
                return 1
            elsewhere = misnamed(body)
            if elsewhere is not None:
                print(f"FAIL promised tests: {elsewhere} lists node IDs; list the plan's tests under {HEADING}")
                return 1
            print(f'ok   promised tests: no "{HEADING}" section (opt-in)')
            return 0
        bad = unreadable(body)
        if bad:
            print(f"FAIL promised tests: not read as a node ID: {', '.join(bad)}")
            return 1
        if not promises:
            print(f"FAIL promised tests: the section lists no node ID; name each test as `tests/...py::test_name` under {HEADING}")
            return 1
        text = read_listing(Path(argv[2]))
        on_head = collected(text)
        absent = missing(promises, on_head)
        if absent:
            print(f"FAIL promised tests: not collected on the PR head: {', '.join(absent)}")
            if not on_head:
                # a failed sync or a collection error leaves no test ID: show why instead of blaming the IDs
                print("     the collection gave no test; its last lines:")
                for line in [line for line in text.splitlines() if line.strip()][-5:]:
                    print(f"     {line}")
            return 1
        print(f"ok   promised tests: {len(promises)} of {len(promises)} collect")
        if len(argv) == 4:
            on_base = collected(read_listing(Path(argv[3])))
            old = [node for node in promises if node not in missing(promises, on_base)]
            if old:
                print(f"note promised tests: already collect on the base: {', '.join(old)}")
        return 0
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
