# infra-b-i5 plan: #709, #710, #711, #734 (batch 004, slot A)

Thread `infra-b-i5`, Opus 5.5 high. Batch 004 (D-876), ruleset 1.10.0 (D-877).
**Critical** (CRIT-01): PR A changes `.github/workflows/governance-pr-checks.yml`
and `.github/governance/promised_tests.py` (CI workflow, a safety check); PR B
changes English and German regression cases (golden files). Both get `risk:high`
and a `ci:full` run before review (D-698). Waits for the coordinator's approval.

## 1. PR split (`.github/lanes.yml`, D-75)

| PR | Lane label | Items | Files |
|---|---|---|---|
| A `infra: ... (#710, #711, #734)` | `lane:infra`, `risk:high` | #710, #711, #734 | `.github/workflows/governance-pr-checks.yml`, `.github/governance/promised_tests.py`, `governance/github-setup/{labeler.yml,labeler-workflow.yml,pr-checks-workflow.yml}`, tests (lane-free): `tests/unit/test_promised_tests.py`, `test_ci_workflows.py`, `test_lanes.py`, new `test_clock_bounds.py`, one allowance or bound line in 12 existing `tests/unit/test_*.py` |
| B `textprep: ... (#709)` | `lane:textprep`, `risk:high` | #709 | `tests/regression/english.toml`, `tests/regression/german.toml` (goal strings only), `tests/unit/test_review_tags.py` |

No file is in both PRs, so they can be reviewed and merged in either order. PR A
is the lane:infra lock; PR B does not touch infra paths. Neither touches layout or
voices files (slot B).

## 2. #734: the brittle-test check (META-03 for kind `brittle-test`, #680, #715)

New file `tests/unit/test_clock_bounds.py`, same shape as `test_review_tags.py`
(a fast test that reads the test sources with `ast`; no new dependency, no CI
wiring, since the fast suite already runs it on every PR on three systems).

Rules (decided here):

1. **Clock value**: a call to `time.monotonic`, `time.perf_counter`, `time.time`
   or their `_ns` forms (as `time.x()` or imported bare); a name or attribute
   containing `elapsed`; or a name that, in the same top-level function (nested
   functions included), is assigned, augmented, subscript-stored or passed to a
   method call (`decided.append(...)`, `started.setdefault(k, ...)`) from an
   expression that holds a clock value, to a fixed point. This catches
   `took = decided[0] - started[...]` in `test_extraction_pdf_progress.py`.
2. **Upper bound**: inside an `assert`, a comparison step `L < R` or `L <= R`
   whose `L` holds a clock value, or `L > R` / `L >= R` whose `R` does. Lower
   bounds (`took >= 1.0`, `1.0 <= took`) pass: a slow runner only makes them
   safer. `==`, `in` and `is` are not read.
3. **Not read**: test functions or classes decorated with `pytest.mark.slow` or
   `pytest.mark.benchmark`; a module whose `pytestmark` holds either; every file
   under `tests/browser/` (its conftest marks all of it `browser`, outside the
   fast suite); `tests/corpus`, snapshots. Helper functions (`web_helpers.py`,
   `conftest.py`) are read, since fast tests call them.
4. **Allowance**: a comment `# clock-bound: <reason>` on any line of the assert
   statement or the line just above it. An allowance with an empty reason fails,
   and so does one that stands next to no upper bound (no stale allowances).
5. One failure message lists every hit as `path:line: <assert source>`.

Limits, on purpose: `datetime.now()`, `loop.time()`, `thread.join(timeout)`
followed by `is_alive()`, and `pytest.mark.timeout` are not read: they are not
the asserted wall-clock bounds the two findings were about.

**Today's 24 hits** (prototype run on 880b170), handled in PR A one by one:

- 7 wait-loop deadlines (`assert time.monotonic() < deadline, "... did not start"`)
  in `test_app_audio_faults`, `test_app_chunks`, `test_app_pdf_progress`,
  `test_cli_convert`, `test_extraction_pdf_progress`, `test_web_pdf_progress`,
  `test_web_prepare`: allowance, reason "a wait loop's way out; N s for what takes
  milliseconds".
- 12 "did not wait for X" bounds whose limit is far below the failure they guard
  (`< 3` against a 60 s hang behind a 0.2 s limit in the four plugin tests and
  `test_app_plugins`; `< 30` / `< 25` against a 30 s read; `< 5` against a 10 s
  sentence; `SHUTDOWN_WAIT + 2`; `< 10` for the EPUB bomb; `ended[a] < ended[b]`,
  an event order): allowance naming the failure's time.
- 5 tight ones, where the bound is within about 2x of what the code takes on a
  fast machine: the three cancel latencies `< 1.0` (`test_app_pdf_progress:151`,
  `test_extraction_pdf_progress:190`, `:225`), `test_web_pdf_progress:102 < 2.0`,
  `test_extraction_pdf_progress:148 took < 1.5`, and
  `test_extraction_pdf_broken:468 < 1.0` (linear-time search, #188: 53 s before).
  Each is loosened to a bound that still sits well below the failure it guards
  (the 60 s step, the 30 s read, the 53 s search), and the allowance names both
  numbers. No assert is removed, and every test still fails on its bug (TST-02).
  Where the failure's time is not clear from the test, I read the code first and
  keep the bound if loosening it would hide the bug.

## 3. #711: the promised-tests check

1. `promised_tests.py check`: the collected list keeps only lines that start with
   `tests/` (the `browser_shard.py` rule of #698), so a banner line
   `  #697 tests/...::...` is never a test.
2. Novelty, without failing: `check BODY COLLECTED [BASE_COLLECTED]`. With the
   third file, it prints `note promised tests: already collect on the base: <ids>`
   and still passes. The workflow step gets `PR_BASE` through `env` (never a
   `${{ }}` in `run`), adds `git worktree add --detach "$RUNNER_TEMP/base"
   "$PR_BASE"`, asks `promised_tests.py files` there for the promised files that
   exist on the base, and collects them with the head's synced interpreter
   (`PYTHONPATH="$RUNNER_TEMP/base/src"`, cwd the base worktree, `|| true`). No
   second `uv sync`; no token; permissions stay `contents: read`,
   `pull-requests: read`. A body without promises still costs nothing.
3. zizmor offline clean.

## 4. #710: the scaffold copies

The three stale copies become byte-equal to their live files (`.github/labeler.yml`,
`.github/workflows/labeler.yml`, `.github/workflows/governance-pr-checks.yml`,
the last one after the #711 change). Kept, not removed: the README tells the owner
to copy them, and #706 chose the same for `pr-checks.json`. One parametrized test
covers all five kept copies (`pr_checks.py`, `pr-checks.json`,
`pr-check-exemptions.json` and the three); the existing #706 test stays.
`CODEOWNERS` and `create-labels.sh` have no live twin and are not compared.

## 5. #709: the regression goal strings

1. Test first: `test_no_regression_goal_carries_a_review_tag` reads every `goal`
   with `tomllib` from `tests/regression/*.toml` and applies `REVIEW_TAG` (one
   pattern). Today: 24 English and 34 German hits.
2. `REVIEW_TAG` learns the German form the goals use, "Review von PR #377,
   Runde 2" (5 more goals), with cases in the known-forms test and a plain German
   sentence with "Runde" in the plain-words test.
3. Each goal drops only the review tag and keeps the issue, PR or D-number:
   "(D-168, review of PR #103)" becomes "(D-168, PR #103)"; "(review round 1 of PR
   #382)" becomes "(PR #382)". Goals are not compared to output (only `expected`
   and `blocks` are), so no snapshot changes; the PR body shows the goal-only diff
   and a check that no `blocks`/`expected` value differs (parsed before and after).

## 6. Tests promised

PR A:
- `tests/unit/test_clock_bounds.py::test_no_fast_test_asserts_an_upper_wall_clock_bound`
- `tests/unit/test_clock_bounds.py::test_every_known_form_of_a_clock_bound_is_caught`
- `tests/unit/test_clock_bounds.py::test_lower_bounds_and_other_comparisons_pass`
- `tests/unit/test_clock_bounds.py::test_a_clock_value_stored_in_a_nested_function_is_followed`
- `tests/unit/test_clock_bounds.py::test_slow_benchmark_and_browser_tests_are_not_read`
- `tests/unit/test_clock_bounds.py::test_an_allowance_with_a_reason_lets_the_bound_pass`
- `tests/unit/test_clock_bounds.py::test_an_allowance_without_a_reason_fails`
- `tests/unit/test_clock_bounds.py::test_an_allowance_beside_no_clock_bound_fails`
- `tests/unit/test_promised_tests.py::test_a_banner_line_is_not_read_as_a_test`
- `tests/unit/test_promised_tests.py::test_promises_already_on_the_base_are_listed_without_failing`
- `tests/unit/test_ci_workflows.py::test_the_base_is_collected_from_the_environment_without_a_new_sync`
- `tests/unit/test_lanes.py::test_each_scaffold_copy_equals_its_live_file`

PR B:
- `tests/unit/test_review_tags.py::test_no_regression_goal_carries_a_review_tag`

Each new test runs red first on 880b170's code (the clock-bound scan red on the
24 hits; the banner and base tests red on today's `promised_tests.py`; the copy
test red on three files; the goal test red on 58 goals).

## 7. Size

PR A: about 200 lines of check and tests, about 30 lines of workflow and
`promised_tests.py`, 24 one-line changes in test files, three copied files.
PR B: about 60 goal lines and 15 lines of test.

Ledger: `prs/pr-<A>.yaml` with `fixes_kinds: "brittle-test"`; `prs/pr-<B>.yaml`.

## Handoff (THR-07)

- Goal: PR A #740 (#710 #711 #734) and PR B #742 (#709), both critical, through review.
- Done: approved as D-878. #740 open, `ci:full` green on 465b96f, label removed, branch frozen. #742 open with `ci:full`. Ledger entries `prs/pr-740.yaml` (`fixes_kinds: brittle-test`) and `prs/pr-742.yaml`. Local fast suites: 8824 passed (A, before the rebase onto 1bebb96), 8797 passed (B, on 1bebb96).
- Next: when #742's `ci:full` run is green, remove the label. Review rounds go to a new thread: this thread has handled 2 PRs (THR-02). Kept notes: the 25 clock bounds and their reasons are listed in #740's body. The 5 bounds loosened to 5 s each name the failure they still catch. PR B also dropped one bare "(F2)" that the pattern does not match.
