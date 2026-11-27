"""Runs named browser tests many times over several runners (isolate.yml, D-759, TST-08).

    python .github/scripts/isolate.py matrix   # the job matrix and request name to $GITHUB_OUTPUT
    python .github/scripts/isolate.py run      # this runner's share of the runs
    python .github/scripts/isolate.py summary FOLDER  # adds up every runner's counts

Every input comes from the environment (never from the workflow text, so no value is run
as code): TESTS (node ids, one per line or space-separated, all under tests/browser/),
BROWSERS (any of chromium firefox webkit), WEBKIT_MACOS (true/false), RUNS, RUNNERS,
SLICE (1-based), BROWSER, RUNNER_LABEL (the runner's os label), MODE (`stop` ends at the
first failure, `full` runs them all), GITHUB_REF (set by GitHub).

A run counts as passed only when pytest exits 0 and every test in it passed: a failure,
an error, a skip (a quarantined test is run with --run-quarantined) or a missing test
fails the job.
"""

from __future__ import annotations

import hashlib
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


def plan() -> tuple[list[dict[str, object]], int, int]:
    """The runners asked for (os, browser, slice), runs per browser and runners per browser."""
    names = env("BROWSERS").replace(",", " ").split()
    unknown = [n for n in names if n not in BROWSERS]
    if unknown or not names:
        sys.exit(f"browsers must be some of {', '.join(BROWSERS)}; got {names}")
    runners = int(env("RUNNERS"))
    runs = int(env("RUNS"))
    if not 1 <= runners <= 4 or not runners <= runs <= 400:
        sys.exit(f"need 1 <= runners ({runners}) <= 4 and runners <= runs ({runs}) <= 400")
    cells: list[dict[str, object]] = [
        {"os": "ubuntu-latest", "browser": name, "slice": k}
        for name in dict.fromkeys(names)
        for k in range(1, runners + 1)
    ]
    if os.environ.get("WEBKIT_MACOS", "false") == "true":
        cells += [
            {"os": "macos-latest", "browser": "webkit", "slice": k} for k in range(1, runners + 1)
        ]
    return cells, runs, runners


def request(
    ref: str, ids: list[str], browsers: list[str], webkit_macos: str, runs: int, mode: str
) -> str:
    """A short name for one request, the same for a repeat of it: the concurrency group
    holds this, never the ids, whose length has no bound (#1076). The runner count is
    left out, as it was of the group before, so a repeat with other runners cancels too."""
    asked = json.dumps([ref, ids, browsers, webkit_macos, runs, mode])
    return hashlib.sha256(asked.encode("utf-8")).hexdigest()[:16]


def matrix() -> None:
    cells, runs, _ = plan()
    ids = tests()  # refuse bad ids before any runner starts
    browsers = list(dict.fromkeys(env("BROWSERS").replace(",", " ").split()))
    webkit_macos = os.environ.get("WEBKIT_MACOS", "false")
    name = request(env("GITHUB_REF"), ids, browsers, webkit_macos, runs, env("MODE"))
    with Path(env("GITHUB_OUTPUT")).open("a", encoding="utf-8") as out:
        out.write(f"matrix={json.dumps({'include': cells})}\n")
        out.write(f"request={name}\n")
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
    browser, mode, where = env("BROWSER"), env("MODE"), env("RUNNER_LABEL")
    runs, runners, share = int(env("RUNS")), int(env("RUNNERS")), int(env("SLICE"))
    out = Path(env("OUT"))
    out.mkdir(parents=True, exist_ok=True)
    counts: Counter[str] = Counter()
    red_runs: list[int] = []
    done = 0

    def save(finished: bool) -> None:
        """Rewritten after every run, so a runner cut short still reports what it ran."""
        record = {
            "browser": browser, "os": where, "slice": share, "runs": done,
            "red_runs": red_runs, "finished": finished, "counts": dict(counts),
        }  # fmt: skip
        (out / "counts.json").write_text(json.dumps(record), encoding="utf-8")

    save(finished=False)
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
        red = code != 0 or not found or any(e != "passed" for e in found.values())
        if red:
            red_runs.append(number)
            print(f"=== run {number} is red (pytest exit {code})", flush=True)
        save(finished=red and mode == "stop")
        if red and mode == "stop":
            break
    save(finished=True)
    print(f"=== {done} runs, red: {red_runs or 'none'}")
    if red_runs:
        sys.exit(1)


def summary(folder: Path) -> None:
    """Adds up the runners' counts against what was asked, and fails unless every runner
    reported, finished and found no red run (and in "full" mode ran every run asked)."""
    cells, runs_asked, runners = plan()
    mode = env("MODE")
    reports: dict[tuple[str, str, int], dict] = {}
    for file in sorted(folder.rglob("counts.json")):
        data = json.loads(file.read_text(encoding="utf-8"))
        reports[(data["browser"], data["os"], data["slice"])] = data
    problems: list[str] = []
    done: Counter[tuple[str, str]] = Counter()
    red: dict[tuple[str, str], list[int]] = {}
    rows: dict[tuple[str, str], Counter[str]] = {}
    for cell in cells:
        key = (str(cell["browser"]), str(cell["os"]), int(str(cell["slice"])))
        where = key[:2]
        red.setdefault(where, [])
        data = reports.get(key)
        if data is None:
            problems.append(f"{key[0]}, {key[1]}, runner {key[2]}: did not report")
            continue
        if not data["finished"]:
            problems.append(
                f"{key[0]}, {key[1]}, runner {key[2]}: cut short, runs done: {data['runs']}"
            )
        done[where] += data["runs"]
        red[where].extend(data["red_runs"])
        for item, n in data["counts"].items():
            name, ending = item.split("\t")
            rows.setdefault((f"{where[0]} ({where[1]})", name), Counter())[ending] += n
    lines = [
        "## Isolation runs (TST-08)",
        "",
        f"Mode: {mode}; {runners} runners per browser.",
        "",
        "| browser | runs done / asked | red runs |",
        "|---|---|---|",
    ]
    for where in sorted(red):
        reds = sorted(red[where])
        lines.append(
            f"| {where[0]} ({where[1]}) | {done[where]} / {runs_asked} "
            f"| {len(reds)}: {reds or 'none'} |"
        )
        if reds:
            problems.append(f"{where[0]}, {where[1]}: red runs {reds}")
        elif mode == "full" and done[where] < runs_asked:
            problems.append(f"{where[0]}, {where[1]}: {done[where]} of {runs_asked} runs")
    lines += [
        "",
        "| browser | test | passed | failed | error | skipped |",
        "|---|---|---|---|---|---|",
    ]
    for (where_text, name), c in sorted(rows.items()):
        lines.append(
            f"| {where_text} | `{name}` | {c['passed']} | {c['failed']} | {c['error']} "
            f"| {c['skipped']} |"
        )
    lines += ["", "**Red:**" if problems else "**Green:** every runner reported and finished."]
    lines += [f"- {problem}" for problem in problems]
    text = "\n".join(lines) + "\n"
    print(text)
    target = os.environ.get("GITHUB_STEP_SUMMARY")
    if target:
        with Path(target).open("a", encoding="utf-8") as out:
            out.write(text)
    if problems:
        sys.exit(1)


if __name__ == "__main__":
    if sys.argv[1:2] == ["matrix"]:
        matrix()
    elif sys.argv[1:2] == ["run"]:
        run()
    elif sys.argv[1:2] == ["summary"] and len(sys.argv) == 3:
        summary(Path(sys.argv[2]))
    else:
        sys.exit(__doc__)
