# Review PR #413, round 2 (final, non-critical)

Head reviewed: **69c1e3a** (on main e517873). Round 1: review-pr413-round1.md.

**Verdict: approvable.** Nothing is left for this PR. I added new WebKit data to #411 as a comment. I have not merged.

## Round 1 fix list, rechecked

1. `update()` ends with `settled(page)`, with a comment pointing to #411 and open_paper. Done.
2. The quarantine marker on the chapter test is gone. Done.
3. `test_the_main_flow_by_keyboard` calls `settled(page)` after the `#step-check` focus check. `settled` is already imported. Done.
4. `browser=` refuses values outside `BROWSERS = ("chromium", "firefox", "webkit")` with a `UsageError`. The two new cases are `browser="WebKit"` and `browser="safari"`. Check: the clean run of `test_quarantine.py` gives 11 passed. With the check disabled (`if False:`), both new cases fail and the rest pass.
5. The PR body has the 60-run Chromium counts. My own round 1 counts (7/80 before the wait, 0/60 with it) agree.
6. The title is "tests: wait for the settled document page after an analysis (#411)". The body says "Refs #411". The #411 text is updated: two of three tests are fixed, and the player test stays open.

## The author's 1-in-10 failure of test_flow.py plus test_keyboard.py

I ran both files together 24 times in Chromium on 69c1e3a, in a clean worktree (`pytest -m browser --browser chromium -p no:randomly tests/browser/test_flow.py tests/browser/test_keyboard.py`). All 24 runs gave 17 passed and 1 skipped (the #365 quarantine), so 408 test runs and no failure. I could not reproduce or name the author's failure. It is not attributable to this PR, which only adds waits. If it comes back, #411 is where it goes, with the test name and error kept.

## Checks

- PR checks on 69c1e3a are all green: CI passed, tests (ubuntu), browser (Linux, Chromium), ZAP, CodeQL, licences, lint, security.
- Nightly on the branch, run 43787351861:
  - Chromium is green.
  - **WebKit Linux and macOS:** the chapter test and the keyboard flow pass. That is the fix working where it failed before.
  - **New single WebKit failures, not touched by this PR:**
    - `test_flow.py::test_a_german_book_keeps_the_remembered_english_voice` (Linux): `wait_for_url` to the job page timed out after Make. This is the same symptom as the #411 player test.
    - `test_subtitles.py::test_subtitles_are_chosen_on_the_page_and_chromium_reads_them` (macOS): `#summary` was not visible after opening the second document without `settled()`.

    Both are added to #411 (comment 6905222540). Each has failed once, so no quarantine is due.
  - **Known, being fixed on the release branch:** Firefox player position and speed, and WebKit-on-macOS speed by keyboard.
  - The slow tests and the property-based job were still running when this was written. This PR changes only browser tests and `tests/conftest.py`, so they don't bear on the verdict.

## Merge

Squash with the PR title. The body says "Refs #411" and no commit message closes an issue, so #411 stays open (checked the two commit messages).
