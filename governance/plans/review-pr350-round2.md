# Review PR #350, round 2 (#177)

Head `a55e237` (one new commit on a11dfe8), base main `99b8166`, mergeable state clean.

## Verdict

**Approved at a55e237.** No new findings.

## R1-1 check

- **Diff.** `#job-cancel`, `#job-again` and `#cache-free` are now drawn `disabled`, like `#job-replace`. `jobPage()` sets `disabled = false` on each one directly after its `addEventListener`. All four server-drawn buttons in job.html are covered.
- **The test catches the bug.** I removed `disabled` from `#cache-free` only and ran the test. It failed at `tests/browser/test_flow.py:558` with "Locator expected to be disabled, Actual value: enabled". With the change restored, it passes.
- **Stability.** The new test passed 15 of 15 runs in a loop locally. The browser suite (Chromium) passed 55 of 55 locally. The helper `reload_holding_back_app_js` unroutes after release, so later page loads get app.js normally.
- **Closing keywords.** No closes/fixes/resolves in the branch commit messages. "Closes #177" is only in the PR body, as intended.

## CI on a55e237

- CI run 43693870101: every job passed: lint and layers, licences, security, browser (Linux, Chromium), tests (ubuntu-latest), tests (macos-latest), tests (windows-latest), and CI passed.
- ZAP baseline scan run 43693870162 passed.
- In round 1, Firefox and WebKit passed on a11dfe8 in the nightly run on the branch (run 43693235989). Round 2 adds the same pattern to more buttons, so I did not run it again.

Ready for the merge go: squash, pinned to sha a55e237.
