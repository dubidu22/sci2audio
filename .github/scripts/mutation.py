"""Scoped mutation runs for mutation.yml (D-759, #246, #549).

    python .github/scripts/mutation.py matrix   # runners for $GITHUB_OUTPUT
    python .github/scripts/mutation.py run      # this runner's share of the mutants
    python .github/scripts/mutation.py report   # counts and survivors for the job summary

Inputs come from the environment only: MUTANTS (mutmut mutant-name globs such as
`sci2audio.textprep.links.x_name*` or `sci2audio.textprep.links*`, separated by spaces or
new lines), TESTS (test paths under tests/ that mutmut runs, default the whole suite),
RUNNERS (1 to 4; the globs are dealt out in turn), SLICE (1-based).

The whole project has about 43,000 mutants, about a day on one runner (measured 18 Nov:
the 1,567 mutants of textprep/links.py took 50 min), so a run names what it mutates.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

GLOB = re.compile(r"sci2audio(\.[\w*?\[\]ǁ]+)+")
PYPROJECT = Path("pyproject.toml")
SELECTION = re.compile(r"^pytest_add_cli_args_test_selection = .*$", re.M)
# mutmut 3.8.1 results that mean a test noticed the mutant; every other result
# (survived, no tests, not checked, suspicious, skipped, segfault, ...) is listed.
KILLED = {"killed", "timeout", "caught by type check"}
LISTED = 300  # names listed per result


def env(name: str, default: str = "") -> str:
    value = os.environ.get(name, "").strip() or default
    if not value:
        sys.exit(f"{name} is not set")
    return value


def globs() -> list[str]:
    found = env("MUTANTS").split()
    for glob in found:
        if not GLOB.fullmatch(glob):
            sys.exit(f"not a mutant name glob under sci2audio: {glob!r}")
    return found


def tests() -> list[str]:
    found = env("TESTS", "tests/").split()
    for path in found:
        if not path.startswith("tests/") or ".." in path:
            sys.exit(f"not a test path under tests/: {path!r}")
    return found


def runners() -> int:
    count = int(env("RUNNERS", "1"))
    if not 1 <= count <= 4:
        sys.exit(f"runners must be 1 to 4, not {count}")
    return min(count, len(globs()))


def request_key(mutants: str, test_paths: str) -> str:
    """A short name for one request, for its concurrency group: the inputs themselves grow
    past what GitHub accepts in a group name and the run then starts no job (#1093)."""
    request = "\n".join(mutants.split()) + "\0" + "\n".join(test_paths.split())
    return hashlib.sha256(request.encode("utf-8")).hexdigest()[:16]


def matrix() -> None:
    tests()
    cells = [{"slice": k} for k in range(1, runners() + 1)]
    key = request_key(env("MUTANTS"), env("TESTS", "tests/"))
    with Path(env("GITHUB_OUTPUT")).open("a", encoding="utf-8") as out:
        out.write(f"matrix={json.dumps({'include': cells})}\n")
        out.write(f"key={key}\n")
    print(f"{len(cells)} runners; mutants: {' '.join(globs())}; tests: {' '.join(tests())}")


def mine() -> list[str]:
    return globs()[int(env("SLICE")) - 1 :: runners()]


def run() -> None:
    # mutmut reads its test selection only from pyproject.toml: set it in this checkout
    # (never committed) to the paths asked for, so its first, unmutated run is short too.
    text = PYPROJECT.read_text(encoding="utf-8")
    if len(SELECTION.findall(text)) != 1:
        sys.exit("pyproject.toml has no single pytest_add_cli_args_test_selection line")
    selection = f"pytest_add_cli_args_test_selection = {json.dumps(tests())}"
    PYPROJECT.write_text(SELECTION.sub(selection, text), encoding="utf-8")
    print(f"mutants: {' '.join(mine())}\n{selection}", flush=True)
    command = [sys.executable, "-m", "mutmut", "run", *mine()]
    sys.exit(subprocess.run(command, check=False).returncode)  # noqa: S603 (no shell)


def report() -> None:
    """Counts the results of this runner's mutants and lists every one not killed; red
    when any was not checked, or when no test asked for covers any of them."""
    listing = subprocess.run(
        [sys.executable, "-m", "mutmut", "results", "--all", "true"],
        check=False,
        capture_output=True,
        text=True,
    ).stdout
    Path("mutation-results.txt").write_text(listing, encoding="utf-8")
    rows = []
    for line in listing.splitlines():
        name, _, status = line.strip().rpartition(": ")
        if name and any(fnmatch.fnmatchcase(name, glob) for glob in mine()):
            rows.append((name, status))
    counts = Counter(status for _, status in rows)
    not_killed: dict[str, list[str]] = {}
    for name, status in rows:
        if status not in KILLED:
            not_killed.setdefault(status, []).append(name)
    lines = [
        f"## Mutation run, runner {env('SLICE')}: {' '.join(mine())}",
        "",
        "| result | mutants |",
        "|---|---|",
        *(f"| {status} | {n} |" for status, n in sorted(counts.items())),
        "",
        f"Not killed: {sum(map(len, not_killed.values()))} "
        "(`mutmut show NAME` in a local run prints the change)",
    ]
    for status, names in sorted(not_killed.items()):
        cut = f", the first {LISTED} listed" if len(names) > LISTED else ""
        lines += ["", f"{status} ({len(names)}{cut}):", ""]
        lines += [f"- `{name}`" for name in names[:LISTED]]
    problems = []
    if counts["not checked"]:
        problems.append(f"{counts['not checked']} mutants not checked (the run did not finish)")
    if rows and counts["no tests"] == len(rows):
        problems.append("no test asked for covers any of these mutants: check the test paths")
    if not rows:
        problems.append("no mutant matched the globs asked for")
    lines += ["", *(f"**Red:** {problem}" for problem in problems)]
    text = "\n".join(lines) + "\n"
    print(text)
    target = os.environ.get("GITHUB_STEP_SUMMARY")
    if target:
        with Path(target).open("a", encoding="utf-8") as out:
            out.write(text)
    if problems:
        sys.exit(1)


if __name__ == "__main__":
    commands = {"matrix": matrix, "run": run, "report": report}
    if len(sys.argv) != 2 or sys.argv[1] not in commands:
        sys.exit(__doc__)
    commands[sys.argv[1]]()
