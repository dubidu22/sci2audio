# Review PR #519, round 2

Head reviewed: cbd3e9c (merge of main f2aea0e as cfc1762, plus fix commit cbd3e9c). Reviewer: web-lane review thread, 18 Nov 2026 16:35Z.
Branch updated by update-branch with main 94a4353 → 0f8506a; PR diff against its merge base unchanged (compared without index lines).

## Verdict
APPROVE. Merge on green Linux CI at 0f8506a.

## Verified
1. Fix commit: conftest.at_rest() waits for app.css (`.skip` position absolute; `.skip` is in base.html, so on every page) and for no font face `loading` with at least one loaded. Called by the reload helper (after the new-document wait), make_audiobook (after "Your audiobook is ready", which is server-rendered by _making.html, so the wait runs on the reloaded page) and the three Prepare-then-Make steps (Playwright's link click waits for the navigation to commit, so the wait runs on the new page). It does not release app.js: the "waits for the script" tests still act before the script runs. No skip, xfail, quarantine, timeout raise or removed assertion.
2. Cause is named with traces (44316533521: "element is not stable", fonts loading) and the same cause explains the setup-click failures in Firefox and WebKit.
3. Evidence, read from the job logs, not the job status: strict isolation jobs 134910893564 (Firefox), 134910893012 (WebKit Ubuntu), 134914650074 (Chromium): every item 40 PASSED, 0 FAILED lines. The scratch heads 3e74d80 and 746d238 differ from cbd3e9c only in .github/workflows/nightly.yml (GitHub compare), so they test this PR's code. WebKit macOS: no hosted runner in any run (stated in the PR comment); not a blocker for a non-critical tests-only PR. #518's fixed test had 40/40 on WebKit macOS in 44313065955.
4. Round 1 points 1-5 still hold. #542 added to Closes (duplicate of #506 seen on #538).
5. No closing keywords in commit messages.

## Findings
None. Round 1 N1 (PR body table) not addressed; cosmetic, no issue.

## Follow-ups (not this PR)
- #541 WebKit reading-mark flake: filed, one failure, no quarantine (TST-07).
- Scratch branches ci/isolate-reload-timing, -2 to -6, ci/isolate-keepalive-525: delete on GitHub (coordinator/Colin; threads cannot delete remote branches).
