"""Runs named browser tests many times over several runners (isolate.yml, D-759, TST-08).

    python .github/scripts/isolate.py matrix   # writes the job matrix to $GITHUB_OUTPUT
    python .github/scripts/isolate.py run      # this runner's share of the runs
    python .github/scripts/isolate.py summary FOLDER  # adds up every runner's counts

Every input comes from the environment (never from the workflow text, so no value is run
as code): TESTS (node ids, one per line or space-separated, all under tests/browser/),
BROWSERS (any of chromium firefox webkit), WEBKIT_MACOS (true/false), RUNS, RUNNERS,
SLICE (1-based), BROWSER, MODE (`stop` ends at the first failure, `full` runs them all).

A run counts as passed only when pytest exits 0 and every test in it passed: a failure,
an error, a skip (a quarantined test is run with --run-quarantined) or a missing test
fails the job.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

BROWSERS = ("chromium", "firefox", "webkit")


def env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        sys.exit(f"{name} is not set")
    return value


def tests() -> list[str]:
    ids = env("TESTS").split()
    for node in ids:
        if not node.startswith("tests/browser/") or node.startswith("-"):
            sys.exit(f"not a browser test node id: {node!r}")
    return ids


def matrix() -> None:
    names = env("BROWSERS").replace(",", " ").split()
    unknown = [n for n in names if n not in BROWSERS]
    if unknown or not names:
        sys.exit(f"browsers must be some of {', '.join(BROWSERS)}; got {names}")
    runners = int(env("RUNNERS"))
    runs = int(env("RUNS"))
    if not 1 <= runners <= 4 or not runners <= runs <= 400:
        sys.exit(f"need 1 <= runners ({runners}) <= 4 and runners <= runs ({runs}) <= 400")
    tests()  # refuse bad ids before any runner starts
    cells = [
        {"os": "ubuntu-latest", "browser": name, "slice": k}
        for name in dict.fromkeys(names)
        for k in range(1, runners + 1)
    ]
    if os.environ.get("WEBKIT_MACOS", "false") == "true":
        cells += [
            {"os": "macos-latest", "browser": "webkit", "slice": k} for k in range(1, runners + 1)
        ]
    with Path(env("GITHUB_OUTPUT")).open("a", encoding="utf-8") as out:
        out.write(f"matrix={json.dumps({'include': cells})}\n")
    print(f"{len(cells)} runners, {runs} runs per browser, tests: {' '.join(tests())}")


def results(junit: Path) -> dict[str, str]:
    """Each test case of one run and how it ended: passed, failed, error or skipped."""
    found: dict[str, str] = {}
    if not junit.exists():
        return found
    for case in ET.parse(junit).getroot().iter("testcase"):  # noqa: S314 (our own pytest's file)
        name = f"{case.get('classname')}::{case.get('name')}"
        ending = "passed"
        for child in case:
            if child.tag in ("failure", "error", "skipped"):
                ending = {"failure": "failed", "error": "error", "skipped": "skipped"}[child.tag]
        found[name] = ending
    return found


def run() -> None:
    ids = tests()
    browser, mode = env("BROWSER"), env("MODE")
    runs, runners, share = int(env("RUNS")), int(env("RUNNERS")), int(env("SLICE"))
    out = Path(env("OUT"))
    out.mkdir(parents=True, exist_ok=True)
    counts: Counter[str] = Counter()
    red_runs: list[int] = []
    done = 0
    for number in range(share, runs + 1, runners):
        junit = out / f"run-{number}.xml"
        print(f"=== run {number} of {runs} ({browser}, runner {share} of {runners})", flush=True)
        command = [
            sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-q", "-rA",
            "-m", "browser", "--browser", browser, "--run-quarantined",
            "--tracing", "retain-on-failure", "--screenshot", "only-on-failure",
            "--output", str(out / f"run-{number}"), f"--junitxml={junit}", *ids,
        ]  # fmt: skip
        code = subprocess.run(command, check=False).returncode  # noqa: S603 (no shell)
        found = results(junit)
        done += 1
        for name, ending in found.items():
            counts[f"{name}\t{ending}"] += 1
        if code != 0 or not found or any(e != "passed" for e in found.values()):
            red_runs.append(number)
            print(f"=== run {number} is red (pytest exit {code})", flush=True)
            if mode == "stop":
                break
    (out / "counts.json").write_text(
        json.dumps({"browser": browser, "os": os.environ.get("RUNNER_OS", ""), "runs": done,
                    "red_runs": red_runs, "counts": dict(counts)}),
        encoding="utf-8",
    )  # fmt: skip
    print(f"=== {done} runs, red: {red_runs or 'none'}")
    if red_runs:
        sys.exit(1)


def summary(folder: Path) -> None:
    rows: dict[tuple[str, str], Counter[str]] = {}
    runs: Counter[tuple[str, str]] = Counter()
    red: dict[tuple[str, str], list[int]] = {}
    for file in sorted(folder.rglob("counts.json")):
        data = json.loads(file.read_text(encoding="utf-8"))
        where = (data["browser"], data["os"])
        runs[where] += data["runs"]
        red.setdefault(where, []).extend(data["red_runs"])
        for key, n in data["counts"].items():
            name, ending = key.split("\t")
            rows.setdefault((f"{where[0]} ({where[1]})", name), Counter())[ending] += n
    lines = ["## Isolation runs (TST-08)", "", "| browser | runs | red runs |", "|---|---|---|"]
    for where in sorted(runs):
        reds = sorted(red[where])
        lines.append(f"| {where[0]} ({where[1]}) | {runs[where]} | {len(reds)}: {reds or 'none'} |")
    lines += [
        "",
        "| browser | test | passed | failed | error | skipped |",
        "|---|---|---|---|---|---|",
    ]
    for (where, name), c in sorted(rows.items()):
        lines.append(
            f"| {where} | `{name}` | {c['passed']} | {c['failed']} | {c['error']} "
            f"| {c['skipped']} |"
        )
    text = "\n".join(lines) + "\n"
    print(text)
    target = os.environ.get("GITHUB_STEP_SUMMARY")
    if target:
        with Path(target).open("a", encoding="utf-8") as out:
            out.write(text)


if __name__ == "__main__":
    if sys.argv[1:2] == ["matrix"]:
        matrix()
    elif sys.argv[1:2] == ["run"]:
        run()
    elif sys.argv[1:2] == ["summary"] and len(sys.argv) == 3:
        summary(Path(sys.argv[2]))
    else:
        sys.exit(__doc__)
