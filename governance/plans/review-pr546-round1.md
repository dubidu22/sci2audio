# Review: PR #546 (isolate.yml, isolation runs over several runners), round 1

Reviewer thread "Review the CI speed-up PRs", 18 Nov 2026. Head reviewed: 311e4eb (base 2cb10c5). Critical (CI), up to 4 rounds.
Verdict: **changes needed** (3 must-fix, plus a try run of the shipped code).

## Must fix

**M1. The summary must find missing runs itself.** Try run 44349709407 (scratch head 6b86525): two WebKit-macOS runners were cancelled, and the table says `webkit (macOS) | 4 | 0: none` although 8 runs were asked. Only the separate step made the job red, from `needs.runs.result`, which read `abandoned` (not a documented value). #548 shows a matrix result can read `success` with a cancelled leg, so that step alone is not enough evidence (review lesson: a repeat-run job reports real pass counts and fails on anything less).
Fix, exactly: the summary knows the expected cells and runs (from the plan job's matrix output, or RUNS/RUNNERS/BROWSERS/WEBKIT_MACOS in its env), shows "runs done / runs asked" per browser and OS, lists each runner without a counts.json as "did not report", and exits 1 itself when any runner did not report, when done < asked in `full` mode, or when any run is red. Keep the `needs.runs.result != 'success'` step as a second check.

**M2. Write counts.json after every run, not only at the end.** Today a runner cut by the 120-min timeout or a cancel leaves no counts, so its finished runs vanish from the table. Rewrite the file after each run (with a `finished: false/true` field) so the summary can show partial counts and M1 can tell "cut short" from "never started".

**M3. Concurrency cancels unrelated isolation runs.** `group: isolate-${{ github.ref }}` with `cancel-in-progress: true`: two threads isolating different tests on main (where flakes are usually checked) cancel each other, and the first sees only a cancelled run. Put the request into the group, e.g. `isolate-${{ github.ref }}-${{ inputs.tests }}-${{ inputs.browsers }}-${{ inputs.webkit_macos }}-${{ inputs.mode }}`, so only a repeat of the same request cancels the older one.

## Proof needed for the next round

The try run tested 6b86525, not the shipped code: the `runners` input (default 2), the plain `inputs.*` values and `fail-fast: ${{ inputs.mode == 'stop' }}` never ran on GitHub. On the round-2 head, refresh `ci/isolate-workflow-try` with that head plus only the push trigger and input fallbacks (I will compare the two heads), and post two runs:
- (a) `mode=full`, 2 runners, 2 tests, 3 browsers, 8 runs: table with done/asked per browser.
- (b) `mode=stop` with one real test and one missing id (e.g. `tests/browser/test_axe.py::no_such_test`): red run on the first iteration, the other runners cancelled, "pass counts" red and naming the runners that did not report.

## Verified (no action)

- Strictness of a run: red on pytest exit != 0, an empty junit, or any test failed/error/skipped. An unknown node id gives pytest exit 4. A named browser test cannot be deselected by `-m browser`: tests/browser/conftest.py:55 marks every item there.
- Run numbers: runner k runs k, k+R, ... so R runners cover 1..RUNS once each. Plan refuses runners outside 1..4 and runs outside runners..400.
- Inputs reach the scripts only through env; node ids must start with tests/browser/ and not with "-". zizmor clean per PR body.
- Try run 44349709407: 8/8 per Linux browser and 4 macOS runs in the table, which matches the job list (macOS runners 1 and 3 cancelled).
- Check runs on 311e4eb: green (per PR body; I read the CI on the next head).

## Notes for the coordinator (rules)

- TST-08's record must use `mode=full` and quote the done/asked line; `stop` is for a gating check.
- Default 2 runners, WebKit-macOS off by default: fine for the 20-job / 5-macOS account limit.
- Scratch branch `ci/isolate-workflow-try` needs deleting by hand after the merge.
