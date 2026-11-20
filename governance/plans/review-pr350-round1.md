# Review PR #350, round 1 (ZAP flake fix, #177, D-602)

PR: dubidu22/sci2audio #350, branch `ci/zap-replace-ready`, head `a11dfe8`, base main `99b8166`. Not critical (web template, app.js, one browser test).

## Verdict

**Changes requested: one fix (R1-1), then approvable.** The fix itself is correct and well tested. But the very next click in the same ZAP walk step ("Free the speech cache") and two other job-page buttons have the identical race, so #177 would not really be closed by this PR alone.

## What I checked

1. **Diff.** `job.html` renders `#job-replace` with `disabled`; `jobPage()` in `app.js` attaches the click and then sets `disabled = false`, in that order. Correct: the button can only become clickable once the handler exists. `zap_scan.py` is unchanged.
2. **Test fails without the fix.** I reverted `app.js` and `job.html` to main and ran `test_replace_waits_until_the_page_script_runs`. It failed at `tests/browser/test_flow.py:549` with "Locator expected to be disabled, Actual value: enabled". With the fix it passes.
3. **Test stability.** I ran the new test 25 times in a loop locally (Chromium): 25 passed, 0 failed. (`until()` sleeps without pumping Playwright events, but the route event has always been dispatched during the preceding `expect(...).to_be_disabled()` call, because the parser requests `app.js` from `<head>` before the button exists.)
4. **Page paths.**
   - If `app.js` fails to load or throws before `jobPage()` runs (for example in `startPage()`/`documentPage()`, which run first on DOMContentLoaded), the button stays disabled. On main it stayed a dead button that did nothing, so this is no regression, and a disabled button is the more honest state.
   - Reload and back/forward: a reload runs `app.js` again and enables it. Firefox restores form-control state on reload, which could have defeated the guard there, so I ran the nightly workflow on the branch (run 43693235989): browser Firefox (ubuntu), WebKit (ubuntu), WebKit (macOS) and Chromium jobs all passed, 55/55 in Firefox, including the new test.
5. **Accessibility.** The button is disabled only until the deferred script runs (milliseconds). Focus goes to `#result` (by `app.js`), not to the button, so no focus is lost. The axe checks in the browser suite pass.
6. **Browser suite locally.** `uv run pytest -m browser` (Chromium): 55 passed.
7. **CI on head a11dfe8.** Linux CI run 43692620492 passed. Five ZAP baseline scans are green on this head: the PR run 43692620235 and the dispatched runs 43692587584, 43692589481, 43692592722 and 43692595002. The red "CI passed" check comes from runs 43692620296 and 43692620400, which the PR concurrency group cancelled. I ignored it.
8. **ci:full.** I added the label. Run 43693214092 passed every job, including `tests (macos-latest)` and `tests (windows-latest)` on a11dfe8.

## Fix list

**R1-1 (must-fix). Give the other server-drawn job-page buttons the same guard.** `job.html` also server-renders three more buttons whose click handlers `jobPage()` only attaches later:
- `#cache-free` ("Free the speech cache", job.html:61),
- `#job-again` (job.html:56),
- `#job-cancel` (job.html:15).

`zap_scan.py:739` clicks "Free the speech cache" right after the replaced job's page reloads, and then expects `#message`. That is the same race as #177, one line later in the same walk step. Fix:
- Render all three buttons `disabled`.
- Set `disabled = false` in `jobPage()` right after each `addEventListener`, as done for `#job-replace`.
- Extend the new test, or add one alongside it, so that it holds back `app.js` on a finished audio job page that has a speech cache and asserts that "Free the speech cache" is disabled until the script runs and works after it.
- Show that this test fails before the change.

For `#job-cancel`, a test is optional, but it must keep working in the existing cancel tests.

No other findings.

## After R1-1

Re-run the browser suite, push, and keep the `ci:full` label. I will check the macOS and Windows test jobs and one ZAP run on the new head, then report "approvable" with that hash.
