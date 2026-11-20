# Review PR #692, round 1 (batch B-I2, #687)

Thread: review-infra-b-i2 (Opus 5.5). Head reviewed: 7817c14. Date: 2026-11-20.
**Critical: yes** (CRIT-01: a step in the required `governance pr checks` workflow that runs PR code, and new governance check code under `.github/**`; `risk:high` set). Plan `plans/infra-b-i2-plan.md`, section "#687", approved as D-846.

**Verdict: changes requested** (0 must-fix, 1 should-fix, 6 notes).

## Verified

- (1) Plan and scope: 4 files, exactly the plan's PR B list (`.github/governance/promised_tests.py`, `.github/workflows/governance-pr-checks.yml`, `tests/unit/test_promised_tests.py`, two tests plus the D-846 test in `tests/unit/test_ci_workflows.py`). All are lane:infra or tests; `pr_checks.py` is unchanged. No file of #691 is touched. #687's acceptance criteria are met: a node ID that does not collect fails `governance pr checks` naming it; a body without the heading passes; parser and comparison have unit tests; zizmor is clean. The issue proposed putting the check in `pr_checks.py`; the plan chose a separate script so the template copy stays identical, and D-846 approved that.
- (2) Workflow security, `.github/workflows/governance-pr-checks.yml`:
  - The trigger is `pull_request` only; there is no `pull_request_target`.
  - Permissions are workflow-level `contents: read` and `pull-requests: read`, with no job-level override. Checkout keeps `persist-credentials: false`.
  - `PR_BODY: ${{ github.event.pull_request.body }}` is in `env:` only. The `run:` script has no `${{ }}`, and the body reaches a file through `printf '%s' "$PR_BODY"`. File names go to pytest as a quoted bash array (`mapfile`), so a body cannot add arguments with spaces.
  - `astral-sh/setup-uv@68559e9…` is the tag v10.3.3, a lightweight tag on commit 68559e9, released 2026-10-28. It is the same pin as `ci.yml`.
  - `uv run zizmor --offline .github/workflows` at 7817c14: no findings. The auditor persona gives the same two low findings on this file as on `main` (undocumented permissions, no concurrency group), so the PR adds none.
  - `test_the_governance_check_runs_pr_code_only_without_write_access` pins the D-846 condition: no `pull_request_target`, `on:` starts with `pull_request:`, exactly the two read permissions, no job-level `permissions:`, and `persist-credentials: false`.
- (3) Parser and `missing()` against the plan, read and probed by hand:
  - The heading must match exactly, with only trailing whitespace stripped. `###`, a trailing colon or a leading space count as no heading.
  - The section ends at the next `#` or `##` line, and a `###` subheading stays inside it.
  - Duplicates are dropped and order is kept. CRLF is normalised.
  - A heading with no node ID fails with its own message. With no heading, the check prints the opt-in line and exits 0.
  - `missing()` accepts an exact match, the promise followed by `[`, or the promise followed by `::`. `test_one` is not kept by `test_one_more`, so a prefix of a name is not enough.
  - A promise in a file that does not exist is not passed to pytest and is reported missing.
- (4) Promises: all 11 node IDs the plan named exist, and two more were added (the opt-in check and the D-846 test). The PR body's `## Tests promised in the plan` section lists all 13. 37 passed for the two touched test files.
- (5) The PR's own runs: `ok   promised tests: 13 of 13 collect` appears in governance pr checks runs 44790713517, 44790713867, 44790714377, 44792045831 and 44793159422, all on 7817c14. The step took about 5 s, including a 33 MiB CPython download and `Installed 165 packages`.
- (6) Local run in the review worktree at 7817c14 (macOS M4):
  - ruff check: clean. ruff format --check: 385 files formatted.
  - lint-imports: 3 kept, 0 broken. deptry src: no issues.
  - Fast suite with `-k "not espeak"` (with `-n auto`): 8598 passed, 6 skipped, 6 xfailed in 123 s.
- CI at 7817c14: `CI passed`, `tests (ubuntu-latest)`, `governance pr checks`, `security`, `licences`, `lint and layers`, both browser shards and the three CodeQL analyses are green. `ci:full` run 44792070062 (workflow_dispatch, headSha 7817c14) is green: `tests (ubuntu-latest)`, `tests (macos-latest)` and `tests (windows-latest)` succeeded.
- (7) Licences: no new dependency. `setup-uv` is already pinned in `ci.yml`.

## Findings

### S1 (should-fix, correctness): some listed promises are skipped silently, and the check still says "N of N"
`.github/governance/promised_tests.py:25-26,37-41`. A listed promise is not checked in two cases, and the output stays `ok   promised tests: N of N collect`, with N smaller than the list a reviewer reads:
- `END_RE` treats a `# ` line inside a fenced code block as a heading. Probe: `## Tests promised in the plan`, then `` `tests/a.py::t1` ``, then a fenced bash block holding `# comment in a fence`, then `` `tests/a.py::t2` ``. This gives `['tests/a.py::t1']`, and `t2` is never checked. A body that shows a local command with a shell comment between promises loses every promise below it. In Markdown that line is not a heading, so this also departs from the plan's "section runs to the next heading of level 1 or 2".
- `NODE_RE` stops at whitespace, so a backticked parametrized ID with a space in its parameters is not read at all. For example, `` `tests/a.py::t[a b]` `` gives `[]`. Next to other promises it is dropped. On its own it gives the misleading "lists no node ID".

Fix:
- Skip lines inside a fenced code block when looking for the end of the section.
- Fail on any backticked token in the section that contains `.py::` but is not read as a promise, or accept spaces inside `[...]`.
- Add one test per case to `tests/unit/test_promised_tests.py`.

### Notes
- N1: a near-miss heading (`### Tests promised in the plan`, a trailing colon, or a leading space) passes as opt-in with only a log line. That is what the plan specifies. Once the plan template makes the heading mandatory (Colin's list, META-01), a near-miss should fail instead.
- N2: a promise written as `./tests/...` or as an absolute path never equals pytest's rootdir-relative ID, so it is reported missing. This fails closed, and the message names the ID, so it is acceptable.
- N3: the new step has the default `if: success()`. When the title, label or ownership step fails, the promised-tests result is not shown until that is fixed. `if: ${{ !cancelled() }}` would show both at once. This is optional.
- N4: a failed `uv sync` or Python download makes every promise "not collected on the PR head". This fails closed, and uv's error is in the step log above the FAIL line. The message could say "collection failed" when `collected.txt` holds no `::` line at all.
- N5: `setup-uv` runs with `enable-cache: auto` and without `cache-python`, so it downloads CPython on every run that has the heading. That is cheap (about 1 s), and a `pull_request` cache is scoped to the PR ref, so it cannot poison `main`'s cache. The cache restore and save run even without the heading.
- N6: the D-846 test asserts `persist-credentials: false` anywhere in the file. Asserting it inside the `actions/checkout` step's `with:` block would be tighter. This is minor.

Verdict: changes requested. No must-fix; S1 needs one fix commit with two tests.
