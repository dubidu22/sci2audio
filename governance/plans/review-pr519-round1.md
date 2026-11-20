# Review PR #519, round 1

Head reviewed: 17c1ba6 (base main 96de4a3, mergeable clean). Reviewer: web-lane review thread, 18 Nov 2026 13:45Z.
PR: tests only (tests/browser/test_flow.py, test_german.py, test_markers.py; +15 −2). Non-critical. Closes #506 #509 #518.

## Verdict
APPROVE, no fix commit. Merge waits only on the dispatched evidence (below).

## Verified
1. #506: `saveNote` (player.js:789) awaits the PATCH before `closeNote`, and the row draws `.mk-note` only from the stored marker (player.js:711), so the new `expect(... .mk-note).to_have_text(...)` really waits for the server write. The post-reload assertion is kept, so the test still checks that a note survives a reload. Same wait added after Ctrl+Enter in the axe test. Not weakened.
2. #509: `reload_holding_back_app_js` sets `window.beforeReload` on the old page, reloads with `commit`, waits for `!window.beforeReload && readyState !== 'loading'`. With app.js held back the new document stays at "interactive", so this returns on the new, parsed document before the deferred script runs; the held-script contract of the 9 callers is unchanged. Docstring explains why not `domcontentloaded`. Correct.
3. #518: `press_on(..., back=True)` uses `tab_to`'s Shift+Tab path, which still asserts a visible focus ring at every stop and still activates the switch by Enter. The test still covers what it was for (the Settings link and the language switch reached and used by keyboard, both languages, axe); only the direction changed, and the wrap-around is not a product requirement. Not weakened.
4. No skip, xfail, quarantine marker, timeout raise or deleted assertion. No src, golden, regression case or CI file changed.
5. No closing keyword in commit messages (only in the PR body, intended).
6. Linux CI on 17c1ba6: CI passed, tests (ubuntu), lint and layers, licences, security, browser (Linux, Chromium), CodeQL all success.

## Findings
- N1 (note, no change needed): PR body has an empty line inside the issue table, so the #518 row renders as a separate table. Cosmetic.
- N2 (note): WebKit macOS was cancelled in isolation run 44310725768 and in the old branch nightly 44310729411. The merge needs a WebKit macOS result from 44313070888 (branch nightly at 17c1ba6); if cancelled again, name the cause in the PR comment.

## Merge conditions (from the coordinator's hand-off)
- Isolation 44310725768 (11 tests + #517, at 9424f79 = 8813e19-based; the #506/#509 lines are unchanged at 17c1ba6): Firefox Ubuntu and WebKit Ubuntu green.
- Isolation 44313065955 (fixed #518 test, 40x): green.
- Branch nightly 44313070888 at 17c1ba6: the fixed tests green in Firefox and WebKit; any other red job must also fail on main (name the main run).
- Author posts the results as a PR comment.

## Addendum 13:41Z (author's isolation results)
Merge withdrawn until round 2. Isolation 44310725768: Firefox Ubuntu 40/40 green; WebKit Ubuntu 11/40 runs red (test_the_removal_button_waits_for_the_script 8x [document], 3x [library]: summary clicked, button.remove-now stays hidden; test_replace_waits_until_the_page_script_runs 1x). The job reported success only because the loop ends in "|| true", so isolation job status is not evidence: read the per-run counts. WebKit macOS never ran (no hosted macOS arm64 runner within 15 min).
Round 2 needs: the one fix commit with its cause named; a fresh isolation whose summary gives pass/fail counts per test and browser (or fails the job on any red run); WebKit Ubuntu and Firefox Ubuntu 40/40; WebKit macOS if a runner is available, else stated as unavailable (not a blocker for a non-critical tests-only PR).
