# Review PR #433, round 3 (final round, critical)

Head reviewed: **2d1e998**, one commit on 45b6457 (round 2: review-pr433-round2.md). After the update from main 8fb51ac (#439) the head is **d8b060f**, a plain merge. The PR's diff against main is byte for byte the reviewed one (`git diff f063454 2d1e998` = `git diff 8fb51ac d8b060f`), and #439 touches no file of this PR.

**Verdict: approved and merged.** The fix has the right cause, it is in the code, and its test fails without it. Every run is green apart from known failures. Squash-merged as **fbc4d12** on the coordinator's go, pinned to d8b060f.

## The fix (round 2 fix list item 1)

- **Cause.** WebKit focuses and scrolls to the address's fragment a second time, when the page has finished loading. A page reloaded at `#result` or `#step-check` therefore loses a focus move made before the load event (the keyboard main flow's "Free the speech cache"), and a click can lose its target because the page scrolls under it (the Make test in #437). A fast person can hit this, so it is a code cause and was rightly fixed in code, not quarantined (D-374).
- **Change.** `focusTarget()` in app.js focuses the target as before, then drops the fragment with `history.replaceState(null, "", location.pathname + location.search)`. player.js already does the same with `#continue`.
  - Nothing reads `location.hash` after `focusTarget()`. It is the last call in the `DOMContentLoaded` handler. The two `!location.hash` checks (lines 541 and 682) run before it, in the same handler, so they still see the fragment.
  - `reloadAt()` sets its fragment again before every reload, so the reload-at-step flows keep working.
  - No browser test waits for a URL with a fragment.
- **Test.** `test_a_move_made_while_the_page_loads_stays_where_it_was_made`:
  - an init script adds an image at `DOMContentLoaded`, and the test holds that image, so the load event waits;
  - the test opens the document at `#step-check` and checks that the heading is focused and that `readyState` is not yet `complete`;
  - it moves the focus to `#update`, then lets the image through (404) and waits for load plus 500 ms;
  - it checks that `#update` keeps the focus and that the fragment is gone.
- **Mutant** (D-676): the `replaceState` line removed.
  - Command: `python b433r3.py <clean worktree at 2d1e998> "tests/browser/test_flow.py tests/browser/test_keyboard.py" "a_move_made_while or main_flow_by_keyboard or make_starts_nothing"` (Chromium). Baseline: 3 passed.
  - Result: **killed** by the new test, at its fragment check.
  - In WebKit the focus check also fails without the fix. That is the author's claim; I have no WebKit here, so I did not rerun it. The nightly below shows that the fix works in WebKit.

## Runs

- **Local, clean worktree at 2d1e998:** fast suite 6,320 passed, 2 skipped; browser suite (Chromium) 108 passed, 1 skipped (screens without their label).
- **Checks on 2d1e998** (label `ci:full`): tests passed on ubuntu, macos and windows, plus the browser job, lint and layers, licences, security, ZAP, CodeQL and CI passed.
- **Checks on d8b060f:** all green on ubuntu, macos and windows, plus the browser job, lint and layers, licences, security, ZAP, CodeQL and CI passed. Mergeable state: clean.
- **`ui:screens`:** not rendered again. The commit changes only the fragment after focusing, which draws nothing differently, so round 2's comparison holds.
- **Nightly on 2d1e998, run 43826716185:**
  - **WebKit Ubuntu: green**, 108 passed. That includes `test_the_main_flow_by_keyboard` and `test_make_starts_nothing_until_the_report_matches_and_has_a_chapter`.
  - Chromium and benchmarks: green.
  - WebKit macOS: only `test_player_speed::test_the_speed_by_keyboard` (known).
  - Firefox: only the known speed crash and the position error.
  - Property-based tests (many examples): green.
  - Slow tests on all three systems: only `test_cli_end_to_end::test_convert_reads_an_epub_and_keeps_its_cover` (#410, known).

## Leftovers

- #437 stays open: its acceptance is five green WebKit-Ubuntu nightlies in a row. The Make failure it names has the same cause as the keyboard failure and is now fixed by this PR, so I added that to the issue (comment on #437).
- #435 (the report download during load), #432 (the CLI chapter numbers): open, v1.3 or later.

## Merge

- Squash-merged on the coordinator's go: **fbc4d12** on main, pinned to d8b060f (2d1e998 plus the main merge 8fb51ac).
- The commit message names `Closes #391 #427 #429 #430 #422`. I checked beforehand that the branch commit messages contain no closing keywords.
- After the merge, I checked that #391, #427, #429, #430 and #422 are closed (completed).
