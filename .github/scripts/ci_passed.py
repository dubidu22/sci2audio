"""Fails "CI passed" when any job of its own run did not succeed (#548, D-759).

    python3 .github/scripts/ci_passed.py

`needs.<job>.result` of a matrix job can read success while one of its legs was cancelled,
for example a macOS leg that never got a runner. So this reads every job of the run back
through the REST API (GH_TOKEN, REPO and RUN_ID from the environment; the latest attempt of
each job) and fails unless each one but "CI passed" itself and the jobs named "reported only"
(Firefox and WebKit on web PRs until #437 closes, D-759) ended `success`. It runs on the
runner's own Python, with only the standard library and the gh CLI.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from collections.abc import Callable

SELF = "CI passed"
REPORTED = "reported only"  # in the name of a job "CI passed" does not wait for
TRIES = 3  # a job that just ended can still read in_progress for a moment
WAIT = 10  # seconds between tries

Job = dict[str, object]


def fetch(repo: str, run_id: str) -> list[Job]:
    pages = subprocess.run(  # noqa: S603 (gh of the runner, no shell)
        [  # noqa: S607
            "gh",
            "api",
            "--paginate",
            "--slurp",
            f"repos/{repo}/actions/runs/{run_id}/jobs?filter=latest&per_page=100",
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return [job for page in json.loads(pages) for job in page["jobs"]]


def others(jobs: list[Job]) -> list[Job]:
    return [job for job in jobs if job["name"] != SELF and REPORTED not in str(job["name"])]


def not_succeeded(jobs: list[Job]) -> list[str]:
    return [
        f"{job['name']}: {job['status']}, {job['conclusion']}"
        for job in others(jobs)
        if job["status"] != "completed" or job["conclusion"] != "success"
    ]


def main(
    get: Callable[[str, str], list[Job]] = fetch, wait: Callable[[float], None] = time.sleep
) -> None:
    repo, run_id = os.environ["REPO"], os.environ["RUN_ID"]
    for attempt in range(1, TRIES + 1):
        jobs = get(repo, run_id)
        if all(job["status"] == "completed" for job in others(jobs)) or attempt == TRIES:
            break
        wait(WAIT)
    for job in others(jobs):
        print(f"{job['name']}: {job['status']}, {job['conclusion']}")
    if not others(jobs):
        sys.exit(f"no job of run {run_id} besides {SELF!r} was found")
    bad = not_succeeded(jobs)
    if bad:
        sys.exit("Not every job of this run succeeded:\n" + "\n".join(bad))
    print(f"All {len(others(jobs))} jobs of this run succeeded.")


if __name__ == "__main__":
    main()
