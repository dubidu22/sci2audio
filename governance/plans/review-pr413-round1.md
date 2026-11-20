# Review PR #413, round 1 (WebKit quarantine for #411)

Head reviewed: 228205e (branch test/webkit-quarantine-411, on main e517873). Not critical, so one round at medium depth.

**Verdict: changes needed.** The quarantine is too narrow, because the race is not WebKit's alone. It is also cheap to fix outright, which beats quarantining it. The `browser=` marker itself is sound.

## What I found

**1. The test is flaky in Chromium too, and only since #409.** I ran `test_make_starts_nothing_until_the_report_matches_and_has_a_chapter` alone, in Chromium, in a clean worktree:

| Code | Runs | Failed |
|---|---|---|
| main a9e0e2d (before #409) | 40 | 0 |
| 228205e (main e517873 plus the marker; Chromium unaffected by it) | 30 + 50 = 80 | **7** |

Every failure looks like the WebKit nightly one (run 43776619822): after `update(page)` and `make.click(force=True)`, `#message` stays empty ("Choose at least one chapter and update the analysis." never appears). Chromium runs this test on every PR, so at this rate it would turn PR CI red about one time in eleven. A WebKit-only quarantine leaves that in place.

**2. The cause is the test helper `update()`, which does not wait for the settled page.** `update()` (`tests/browser/test_flow.py:54`) waits until `#changed` is hidden and `#step-check` is focused. The old page satisfies the first, and a page drawn while the analysis job is still the running one satisfies both. That page reloads itself once more when the job ends, and its deferred app.js may not have wired the Make button yet. This is the race `settled()` exists for (#138, #166), and `open_paper()` and `listen_to()` already call it.

With one line added at the end of `update()`, `settled(page)`, the same test passed **60 of 60** in Chromium on 228205e. That is 0 of 60 against 7 of 80 without it.

Why #409 widened the window is a guess I did not prove: app.css grew (a deferred script waits for the stylesheet before it), and the fonts make the load later. ZAP showed the same effect (6b71762).

**3. The keyboard failure from the same nightly is the same race.** `test_keyboard.py::test_the_main_flow_by_keyboard` presses "Update the analysis" and then checks only `#changed` hidden and `#step-check` focused (lines 77–79). In WebKit, Tab then landed on `h2#step-check` after a late reload. Adding `settled(page)` after line 79 keeps the test passing in Chromium (10 of 10). I can't run WebKit here; the nightly will show it.

**4. The player failure is a different cause.** `test_player.py::test_a_skipped_code_block_…`: `listen_to()` already calls `settled()` before Make, so its `wait_for_url` timeout in WebKit is not this race. It has failed once, so no quarantine is due. It stays open in #411.

**5. The marker change is correct and tested.** Clean run of `tests/unit/test_quarantine.py`: 9 passed. Each mutant was killed:

| Mutant | Result |
|---|---|
| No browser filter on the skip | 1 failed |
| No browser filter on the list | 1 failed |
| `browser` refused as a keyword | 1 failed |
| `--run-quarantined` ignored | 2 failed |

One gap: a misspelt browser (`browser="WebKit"`) is accepted silently, and the test is then quarantined nowhere (checked with `--collect-only`).

## Fix list

1. `tests/browser/test_flow.py` `update()`: add `settled(page)` after `expect(page.locator("#step-check")).to_be_focused()`.
2. Remove the `@pytest.mark.quarantined(issue=411, …, browser="webkit")` marker from `test_make_starts_nothing_until_the_report_matches_and_has_a_chapter`. The race is fixed, so nothing is hidden.
3. `tests/browser/test_keyboard.py::test_the_main_flow_by_keyboard`: add `settled(page)` after the `#step-check` focus check that follows "Update the analysis" (import `settled` from conftest).
4. Keep the `browser=` support with its unit test, and add one case: a `browser=` value outside `chromium`, `firefox`, `webkit` raises the same `pytest.UsageError` as a missing issue number.
5. Proof in the PR body:
   - the exact command;
   - Chromium on the unfixed head: at least 60 runs of the chapter test, reporting how many failed;
   - the same 60 runs with the fix: 0 failed;
   - a nightly dispatch on the branch for WebKit.
6. Title and body:
   - Title: "tests: wait for the settled document page after an analysis (#411)".
   - Body: "Refs #411". #411 stays open for the player test (point 4).
   - Update #411's text: the race affects every browser; two of the three tests are fixed by this PR; the player test remains.

## Ledger

Round 1, 228205e: the quarantine was too narrow (Chromium 7/80 since #409, 0/40 before); the test wait in `update()` is the cause, and the one-line fix gives 0/60; the same wait goes into the keyboard test; the marker mutants were 4/4 killed, and a typo check is missing.
