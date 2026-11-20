# Review of PR #218, round 2

Reviewed head: 4ff05f1 (0 behind main 31b6d16). Answer: plans/review-pr218-round1-answer.md.

## Round 1 must-fix items

1. macOS WebKit player test: fixed. `TAB`/`tab_key` moved from `test_keyboard.py` to `conftest.py`; `test_player.py` presses `tab_key(page)` at all three places (lines 174, 192, 332). The assertion message now also lists the order so far. No assertion weakened.
2. macOS WebKit reload cancel: fixed at the cause. `open_paper` (test_flow.py) now ends with `settled(page)`, which waits until the page no longer follows the analysis (its own `reloadAt`) and is loaded. `open_paper` already waited for the report, so no test that used it loses a check.
3. Nightly re-dispatched on the branch: run 43537596420, head 4ff05f1: browser chromium/ubuntu, firefox/ubuntu, webkit/ubuntu, webkit/macos each 48 passed (counts from the job logs).

## Rest

- Diff vs main: still only `nightly.yml` and four files in `tests/browser/`; no `src` change.
- Fast CI on 4ff05f1: CI passed green (tests on three OSes, Chromium browser, lint and layers, licences, security, CodeQL). ZAP baseline red: the job failed with "The audiobook files exist already", the known flaky walk #177 (v1.1, D-379, not a required check).

## Findings

None. Merge.
