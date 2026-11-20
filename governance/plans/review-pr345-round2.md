# Review of PR #345, round 2: read PDFs in a separate process (#185, #28, D-581)

Review thread "Review PDF subprocess PR 345", 15 Nov 2026. Reviewed head **872e634** (main 79d0cdb merged in). Round 1: `plans/review-pr345-round1.md` (D-608). Fix commits: 8d16eae (B1), 26bb59a (S1, S2, S5, N1), 797a457 (S3, S4, N2), 872e634 (S2 test made fast enough to start on Windows).

**Verdict: one small test still needed (R2-1), then approvable.** All round-1 items are fixed, and my own mutants confirm each one. CI is green on all three systems on 872e634. The S2 fix adds a new behaviour: the child restarts its own clock at each reported step. Nothing tests that restart, and a mutant that removes it survives, even though breaking it would stop every long book after 120 s.

## Round-1 items

| Item | Fixed? | How I checked |
|---|---|---|
| B1 the watch and the hard limit each proven | yes | Mutants "no `_hard_limit`" and "no `RLIMIT_AS`" each fail only `test_the_hard_limit_stops_an_allocation_the_watch_does_not_see`. Mutants "no watch thread" and "watch ignores memory" fail `test_the_watch_stops_a_child_that_grows_past_the_limit`, plus the Flate-bomb tests. On Windows the hard-limit test ran and passed on 872e634 (3 unrelated skips), so the job object is proven there. On macOS only that test is skipped. |
| S1 unpicklable child errors | yes | Mutant "dumps without loads" fails `test_an_error_that_cannot_cross_to_this_process_arrives_named` |
| S2 orphaned child ends | yes | Mutant "no step clock in the watch" fails the orphan test. Mutant "`TIME_EXIT` not mapped" fails `test_a_child_ended_by_its_own_watch_for_time_is_named`. See R2-1 for the clock restart. |
| S3 outline step and time messages | yes | Mutant "no `report("outline")`" fails `test_a_read_reports_each_page_and_then_the_outline`, and the outline wording mutant fails the parametrized message test |
| S4 production reader cap | yes | Mutant `Readers(3)` fails `test_the_limits_are_the_decided_ones` |
| S5 start message only for a failed start, no pipe leak | yes | Mutant "`NotStarted` or `OSError`" fails `test_an_os_error_in_the_child_is_not_a_failed_start`. Mutant "receive end not closed" fails `test_a_child_that_cannot_start_is_named_and_leaves_no_pipe_open`. |
| N1 docstring on the reader wait | yes | read |
| N2 `freeze_support` | yes | Mutant "no `freeze_support`" fails `test_the_command_hands_a_packaged_reader_start_to_the_reader` |
| D1, D2, D3 | filed | #354 (layout), #355, #356, listed in the PR body |

Mutants: 14 run against the process, broken-file, CLI-error and web-refusal tests. 13 were killed and 1 survived (R2-1).

## What I ran on the new heads

| Check | Result |
|---|---|
| CI on 872e634 (run 43695270269, `ci:full`) | all green. tests (ubuntu-latest): 5206 passed. **tests (windows-latest): 5204 passed, 3 unrelated skips.** tests (macos-latest): 5205 passed, with only the hard-limit test and the junction test skipped. Browser, lint and layers, licences and security also green, and the ZAP scan passed. |
| Lint, format, layers, deptry (8dca21e, same `src` as 872e634) | clean, 3 contracts kept |
| Fast suite locally, `-n auto`, on 8dca21e | 5206 passed, 1 skipped, 6 xfailed in 152.5 s. That is about +14 s against main's 138 s at 99b8166, still under the 15 s rule. 872e634 only rewrites the one orphan test. |
| Bombs on 872e634 | The 3 GB and 8 GB Flate bombs and the forms nested 8 deep each stop with the 1 GB memory message in 1 to 2 s. 1M rectangles are refused at the page limit. 10,000 pages read in 2.3 s. 5 × 100,000 drawings read, parent +349 MB this run (tracked in #355). A 400-page book (3,000 characters a page) reads in 26.9 s, so the child's 120 s clock is restarted at each page. |
| Child start on Linux | 0.12 to 0.18 s from `run` to the child's work |
| Closing keywords | no "fixes/closes #N" in the branch's commit messages. The PR body has `Closes #185` and `Closes #28` only. The deferred issues are listed without keywords. |

## Fix list

**R2-1 (required). Prove that a reported step restarts the child's own clock.** The mutant that drops `_step_started = time.monotonic()` from `started` survives every test. With that mutation, any read taking longer than twice `STEP_SECONDS` in total (120 s, about 1,800 pages) would end with `TIME_EXIT` and the time message, although each page is fast. Add a test with a target that reports a step every 0.2 s eight times at `step_seconds=0.5` and returns. I prototyped it: as is it returns 8; with the mutant it returns `Stopped("time", "page 6")`. The target must live in a module that imports little, as the 872e634 orphan test does, or in the test module if the child start stays under 0.5 s on Windows. The safer choice is a light module.

## Notes (no action)

- The orphan test runs with a 0.5 s step. It passed on Windows once, on 872e634. If it fails there twice without a code cause, quarantine it under the D-374 rule. Raising the step to 1 s would cost about 2 s of suite time.
- After R2-1 lands I need to see a green Linux, macOS and Windows run on that exact head before I say "approvable".

## Round 3 (head 3743c7a, 15 Nov 2026)

- **R2-1 resolved.** `test_each_reported_step_starts_the_childs_own_clock_anew` (8 steps of 0.2 s at a 0.5 s limit; the child's work in a light module under `tmp_path`) passes. With `_step_started = time.monotonic()` removed from `started`, it fails. The 28 process tests pass locally, and ruff is clean.
- **CI on 3743c7a (run 43695798175, `ci:full`):** all green. tests (ubuntu-latest) 5207 passed. tests (windows-latest) 5205 passed, 3 unrelated skips. tests (macos-latest) 5206 passed, 2 skipped (the hard-limit and junction tests). Browser, lint and layers, licences, security and the ZAP scan also passed. `mergeable_state` is clean.
- No closing keywords in the new commit.

**Verdict: approvable at 3743c7a.**
