# Review of PR #363, round 1: a child's start is not counted as its first step (D-616)

Review thread "Review PDF subprocess PR 345" (reopened for this follow-up), 15 Nov 2026. Reviewed head **89accb1** (on main 87c6503). Follow-up to PR #345 after main 6c91465 failed on macOS in `test_each_reported_step_starts_the_childs_own_clock_anew` (`Stopped("time", "opening")`). Run 43696317547 shows that the child's start-up took longer than the 0.5 s step on a busy runner.

**Verdict: changes needed (2 small items).** The mechanism is right and fixes the macOS failure. But `START_SECONDS` only takes effect when it is larger than the step limit. With the real 60 s step, a start may take 60 s, while the message says "within 30 seconds". The 30 s value is not pinned either.

## What I ran

| Check | Result |
|---|---|
| CI with `ci:full` on 89accb1 (run 43697789550) | all green. tests (ubuntu-latest): 5247 passed. tests (windows-latest): 5245 passed, 3 unrelated skips. tests (macos-latest): 5246 passed, 2 skipped (the hard-limit test as designed, plus the junction test). Browser, lint and layers, licences and security green. |
| Process tests locally | 30 passed in 29.9 s |
| Fast suite locally, `-n auto` | 5247 passed, 1 skipped, 6 xfailed in 166.2 s (main has grown with #357 subtitles; this PR adds two tests of about 1 s each) |
| Mutants (7, against the process, broken-file and web-refusal tests) | 5 killed, 2 survived (below) |

Mutants:
- killed: the clock counts the start again (`step = "opening"` initially), by both new tests;
- killed: the child sends no `"opening"`, by four tests whose `Stopped(..., "opening")` would read `"starting"`;
- killed: no start limit (`limit = step_seconds`), by `test_a_slow_start_is_not_counted_as_a_step`;
- killed: no start message in `_stopped`, by `test_a_child_that_does_not_start_in_time_is_named`;
- killed: the child's own clock not restarted at each report (the #345 R2-1 mutant), by `test_each_reported_step_starts_the_childs_own_clock_anew`;
- **survived: `START_SECONDS = 3.0` and `START_SECONDS = 300.0`** (R1-2).

## Fix list

**R1-1 (required). The start limit is `START_SECONDS`, not the larger of it and the step limit.** `_wait` uses `max(step_seconds, START_SECONDS)` while the step is "starting". With `STEP_SECONDS = 60` the start therefore gets 60 s, yet `_stopped` says "it did not start within 30 seconds". I checked this with a target whose module takes 1 s to import, `START_SECONDS = 0.3` and a 5 s step: the read completed in 1.19 s, where it should have been stopped with `Stopped("time", "starting")`.
- Fix: `limit = START_SECONDS if step == "starting" else step_seconds`.
- If the author keeps the max on purpose, the message must name the limit actually used.
- Test: change `test_a_child_that_does_not_start_in_time_is_named` to a step limit above `START_SECONDS` (for example `step_seconds=5` with `START_SECONDS` at 0.3). Today it uses 0.1 s, which is below `START_SECONDS`, so it cannot tell the two forms apart. With the max, the test must fail.

**R1-2 (required). Pin `START_SECONDS`.** Add `isolate.START_SECONDS == 30` to `test_the_limits_are_the_decided_ones`. The tests only lower it, so a tenfold change either way survives.

## The coordinator's three questions

- **Risk label.** The repository has no `risk:medium` label; only `risk:low` and `risk:high` exist. Since this PR changes a safety mechanism and is reviewed as critical, I replaced `risk:low` with `risk:high`. I did not create a new label.
- **30 s against a cold macOS runner.** Linux starts a child in 0.12 to 0.18 s. On macOS CI the start sometimes went past 0.5 s under full `-n auto` load, and its full suite took 4 min 55 s on this run. No runner has shown anything near 30 s, which leaves roughly a 60-fold margin over the slowest start seen, and it is the right order for a first, cold start that also checks the pypdfium2 library. A start that fails gets the honest start message, not one that blames the PDF. A measured macOS and Windows start time belongs in #356 (the baseline rows for both systems); I suggest the author adds "child start time" to that issue.
- **Is "starting" covered by the memory limits?** No, and it need not be. Before `_child` runs, the child only unpickles its process object: it imports `sci2audio.extraction` and the target's module and receives the path string and the limits dictionary. No byte of the PDF is read. The hard limit and the watch are set as the first steps of `_child`, right after the `"opening"` message and before the target touches the file, so every PDF-handling instruction runs under both limits. (Setting them before the `"opening"` message would make no difference.)

## Notes (no action)

- The child imports neither pytest nor the test module. Both new targets live in a tmp module that imports only `time`, as in the #345 orphan and clock tests.
- Timing margins on macOS:
  - The slow-start test's 0.3 s step only needs to cover `_hard_limit`, a thread start and returning 7, which takes milliseconds.
  - The "not started" test relies on a 1 s import against a 0.3 s start limit, and cannot pass early.
  - The clock test now has its steps start after the start-up, with 0.3 s of slack on each 0.5 s step. That is the case that failed before.
- The two tests share the module name `slow_start`. The second import in a worker returns the cached module from the first test's `tmp_path`, while the child imports the same file from the second `tmp_path`. This is harmless.

## Round 2 (head 31913ff, 15 Nov 2026)

- **R1-1 fixed.** `_wait` uses `START_SECONDS` alone while "starting". `test_a_child_that_does_not_start_in_time_is_named` runs at a 5 s step, and with the max put back it fails (mutant killed).
- **R1-2 fixed.** `START_SECONDS == 30` is pinned. The mutants at 3 and 300 are killed by `test_the_limits_are_the_decided_ones`.
- All 8 mutants are now killed: old clock, no "opening", no start limit, max put back, 3, 300, no start message, no clock restart. The 30 process tests pass, and ruff is clean.
- **CI on 31913ff (run 43698631380):**
  - tests (ubuntu-latest): 5247 passed. tests (windows-latest): 5245 passed, 3 unrelated skips. tests (macos-latest): 5246 passed, 2 skipped. Lint, licences and security are green.
  - Attempt 1 of browser (Linux, Chromium) failed once in `test_flow.py::test_pasted_text_opens_and_is_analysed` ("Execution context was destroyed, most likely because of a navigation"). That is a pasted-text page and has no PDF reading. Attempt 2 passed, and `CI passed` is green. I count it as one flake. If it fails again without a code cause, quarantine it under D-374.
- Label `risk:high`. No closing keywords in the commits; the PR closes no issue.
- **Before the merge:** the PR is `behind` main (bd3be17, #353, merged after its base 87c6503). The strict "CI passed" rule needs an update-branch merge commit first, then a green three-system run on the new head.

**Verdict: approvable at 31913ff.** The merge itself goes on the updated head once its CI is green.
