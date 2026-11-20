# Review of PR #325 (lean CI, D-580), round 1

Reviewed head: 846111f (base main 334e5a8). Plan: plans/ci-lean-plan.md (approved).

## Verdict

Changes requested: three exact fixes (R1-1 to R1-3), then the `ci:full` run on all three systems. The rest matches the plan.

## Fix list

**R1-1 (must): pending runs on main and release/* still get cancelled.**
`cancel-in-progress: false` only protects the run that is already running. GitHub keeps at most one *pending* run per concurrency group and cancels the older pending one when a newer run joins the group, whatever `cancel-in-progress` says. With the group `ci-CI-refs/heads/main`, three merges in a row leave the middle commit's run cancelled (never tested on macOS/Windows, red X on main), and every main run also waits for the previous one to finish. The plan says "On main, release/* or dispatch, nothing is cancelled".
Fix in `ci.yml`: give non-PR runs a group of their own, e.g.
`group: ci-${{ github.workflow }}-${{ github.event.pull_request.number || github.run_id }}`.
Do the same in `zap.yml` (`zap-${{ github.event.pull_request.number || github.run_id }}`), so scheduled and manual scans are never dropped either. Fix the comments above both blocks if they change meaning. Leave `nightly.yml` and `mutation.yml` as they are (waiting there is the intent; a dropped third manual run is fine).

**R1-2 (must): the uv and Python cache key does not contain the Python version.**
The lint job log shows the key `setup-uv-2-x86_64-unknown-linux-gnu-ubuntu-26.04-unknown-py-<hash>` (and `...-python`). "unknown-py": setup-uv gets no Python version, and `.python-version` is not in its dependency glob. After a bump of `.python-version`, the restored Python cache holds the old CPython, uv downloads the new one on every run, and the hit key is never saved again until `uv.lock` or `pyproject.toml` changes.
Fix: on every setup-uv step with `cache-python: true`, add `cache-suffix: py-${{ hashFiles('.python-version') }}` (or an equivalent that puts `.python-version` into the key). Show one key from the new run in the PR.

**R1-3 (must): CLAUDE.md step 8 should say which checks prove the three-system run.**
"CI passed" is created only when its job starts, after all other jobs. When `ci:full` is added after a green Linux-only run, the old green "CI passed" stays the latest check on that head until the macOS and Windows tests finish, so the ruleset lets a merge through in that window. Append to step 8: "check that `tests (macos-latest)` and `tests (windows-latest)` succeeded on that head; `CI passed` alone can still show the earlier Linux-only run." Put the same half-sentence after "a PR is merged only on a green run on all three systems of the reviewed head" in CONTRIBUTING.md.

## Checked and fine (no change)

- "CI passed": name and logic unchanged; a matrix leg left out never exists, so it is not "skipped"; a failed macOS or Windows leg makes `needs.tests.result` "failure" and the job fail. The summary step runs with `always()`, also after the `exit 1`.
- Matrix expression: full for push, dispatch and a PR carrying `ci:full` (labels in the payload include the label just added).
- `labeled` trigger: every label starts a run. On #325 opening with two labels started four CI runs; three were cancelled within a second by the PR concurrency group, and their "CI passed" check runs show "failure" on 846111f until the surviving run reports. That is cosmetic and was already true before for quick pushes; skipping runs for other labels instead would leave a skipped "CI passed" that the ruleset counts as success, so no change.
- Playwright cache: keyed on runner OS, browser and the installed playwright version (from `uv.lock`), so a Playwright bump invalidates it; `PLAYWRIGHT_BROWSERS_PATH` points browser install and launch at the cached folder. Same in `ci.yml`, nightly `browsers` (macOS WebKit gets its own key through `runner.os`) and `zap.yml`.
- The one zizmor ignore (`cache-poisoning` in `ci.yml` browser) is documented and holds: CI publishes nothing, PR caches stay in the PR's scope, and `release.yml` uses no cache.
- `release.yml` is unchanged (`enable-cache: false` three times, no concurrency).
- Docs: tests.md lines 7 and 10, CONTRIBUTING "What CI runs" and labels, CLAUDE.md step 8. Old CHANGELOG lines about "every PR" are history and stay.

## Before merge

1. R1-1 to R1-3 pushed.
2. Label `ci:full` on #325: a green run of the new head on Linux, macOS and Windows, with the summary line "Tests ran on Linux, macOS and Windows."
3. A second run (re-run or next push) showing Python and Playwright cache hits.

## Outcome (round 2 check)

- R1-1, R1-2 and R1-3 fixed in 55cecda as asked (checked in the diff; `release.yml` byte-identical to main).
- ci:full run 43620950949 on 55cecda: green on Linux, macOS and Windows; summary step ran with FULL=true. Attempt 2 of the same run: green again, with Python and uv cache hits on all three systems and the Playwright cache hit on Linux. Cache keys differ per system and carry the `.python-version` hash (Windows hashes differ because of CRLF checkout, harmless).
- One note, no change: the browser job and the ZAP scan share the Playwright key `ms-playwright-Linux-chromium-<version>`; the first save by either serves both (same Chromium).
- Squash-merged pinned to 55cecda as e3610f4. Nothing deferred.
