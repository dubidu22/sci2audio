"""Fails the nightly when pull requests wait too long for "CI passed" (#1131, #1133).

    python3 .github/scripts/pr_wait.py

Reads the newest completed pull-request runs of the CI workflow through the REST API (GH_TOKEN
and REPO from the environment) until RUNS of them have a finished "CI passed", looking at no
more than one page of LOOK_AT runs and none from before SINCE, and writes the median wait to
the job summary. Above the budget it exits 1, so the nightly goes red and a person decides
what to cut; the script has no right to write anything, so it opens no issue itself. It runs
on the runner's own Python, with only the standard library and the gh CLI, like ci_passed.py.
"""

from __future__ import annotations

import json
import os
import statistics
import subprocess
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

BUDGET = 6.0  # minutes to "CI passed" on an ordinary Linux PR (#1131)
RUNS = 20  # the median of 20 is not moved by one slow runner
LOOK_AT = 100  # one API page; cancelled and full runs leave fewer than that to count
# The merge of the three shards (#1132): runs before it waited for the old layout and would
# keep the nightly red until 20 newer ones exist. Older than the 20th run, it changes nothing.
SINCE = datetime(2026, 11, 27, 16, 4, tzinfo=UTC)
SELF = "CI passed"
FULL = "tests (macos-latest)"  # only a full run (ci:full) has it; the budget is a Linux PR's
WAITED = ("success", "failure")  # a red run kept the author waiting just as long

Run = dict[str, object]
Job = dict[str, object]


def gh(path: str) -> object:
    out = subprocess.run(  # noqa: S603 (gh of the runner, no shell)
        ["gh", "api", path],  # noqa: S607
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return json.loads(out)


def fetch_runs(repo: str) -> list[Run]:
    path = f"repos/{repo}/actions/workflows/ci.yml/runs"
    answer = gh(f"{path}?event=pull_request&status=completed&per_page={LOOK_AT}")
    return answer["workflow_runs"]  # type: ignore[index]


def fetch_jobs(repo: str, run_id: object) -> list[Job]:
    """The jobs of the run's latest attempt, which run_started_at also belongs to."""
    answer = gh(f"repos/{repo}/actions/runs/{run_id}/jobs?filter=latest&per_page=100")
    return answer["jobs"]  # type: ignore[index]


def moment(stamp: object) -> datetime:
    return datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))


def minutes_to_ci_passed(run: Run, jobs: list[Job]) -> float | None:
    """Minutes from the start of the run's latest attempt to the end of its "CI passed", or
    None for a full run and a run a newer push cancelled. "CI passed" runs `if: always()`, so
    a cancelled run still has one, red: its end is the next push, not a wait for CI."""
    if run["conclusion"] not in WAITED or any(job["name"] == FULL for job in jobs):
        return None
    done = next((job for job in jobs if job["name"] == SELF), None)
    if done is None or done["status"] != "completed" or done["conclusion"] not in WAITED:
        return None
    return (moment(done["completed_at"]) - moment(run["run_started_at"])).total_seconds() / 60


def verdict(waits: list[float]) -> tuple[float, bool]:
    """The median wait and whether it is within the budget; the median, so that one runner
    slow to start raises no alarm."""
    median = statistics.median(waits)
    return median, median <= BUDGET


def main(
    runs: Callable[[str], list[Run]] = fetch_runs,
    jobs: Callable[[str, object], list[Job]] = fetch_jobs,
) -> None:
    repo = os.environ["REPO"]
    waits: list[float] = []
    for run in runs(repo):
        if moment(run["run_started_at"]) < SINCE:
            break
        minutes = minutes_to_ci_passed(run, jobs(repo, run["id"]))
        if minutes is not None:
            waits.append(minutes)
        if len(waits) == RUNS:
            break
    if not waits:
        sys.exit(f"no pull-request run since {SINCE:%Y-%m-%d %H:%M} UTC has a finished {SELF!r}")
    median, within = verdict(waits)
    line = (
        f"Pull requests: median {median:.2f} min to {SELF!r} over the last {len(waits)} runs "
        f"since {SINCE:%Y-%m-%d %H:%M} UTC "
        f"(budget {BUDGET:g} min; `ci:full` runs and runs cancelled by a newer push left out)."
    )
    print(line)
    with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a", encoding="utf-8") as summary:
        summary.write(line + "\n")
    if not within:
        sys.exit(
            f"median wait {median:.2f} min to {SELF!r} over {len(waits)} runs is above the "
            f"budget of {BUDGET:g} min: open a speed issue under #1131"
        )


if __name__ == "__main__":
    main()
