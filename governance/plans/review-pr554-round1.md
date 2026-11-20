# Review: PR #554 (Firefox and WebKit on Linux for web PRs, reported only), round 1

Reviewer thread "Review the CI speed-up PRs", 18 Nov 2026. Head reviewed: 38b7166 (base 025b67a, current main). Critical (required CI workflow), up to 4 rounds; final-round evidence is in.
Verdict: **approved**, no findings. Gating as ruled for O4: option (b), reported only until #437 closes.

## Checked
- **Reported legs ran on a web PR.** PR run 44384884112 (pull_request, 38b7166): "web paths" printed `tests/browser/conftest.py` and set web=true; four legs "browser (Linux, firefox|webkit, 1/2|2/2, reported only)" each "87 of 174", all green in both attempts.
- **#548 check working on this PR.** Attempt 1: tests (macos-latest) cancelled without a runner, CI passed red. Attempt 2: all jobs success, CI passed "All 9 jobs of this run succeeded" (lint, licences, security, 3 tests, 2 Chromium shards, web paths: the 4 reported legs and itself left out).
- **Not a PR.** Run by hand 44384884225: web paths green (web=false), the reported job skipped under its unexpanded name "browser (Linux, ${{ matrix.browser }}, ${{ matrix.shard }}/2, reported only)", CI passed green; the name still contains "reported only", so ci_passed.py ignores it (also a unit-test case).
- **Required set unchanged except web-paths.** CI passed needs [lint, licences, security, tests, browser, web-paths]; web-paths has no `if:`, so it is never skipped; a failed files call fails it, so CI passed fails closed.
- **Tests bite.** Locally on 38b7166: test_ci_workflows.py 21 passed; with the "reported only" exclusion removed from ci_passed.py, 3 failed. zizmor: no findings. Renamed files count by their old name too (`previous_filename`), pinned in the test.
- Only .github/ and tests/ change (tests/browser/conftest.py docstring, which also makes this PR a web PR for its own proof).

## Notes for the coordinator (rules, no change asked)
- When a reported leg fails, "CI passed" stays green but the workflow run's overall conclusion is red, and the PR shows a red check under the leg's name. Reviewers read those legs like a nightly browser result (D-731, #437); a fail that repeats is a fix, not a re-run.
- The nightly practice "re-run the branch Nightly before merging a web PR" can now read these legs instead, except WebKit on macOS (nightly only).
- Paths that change browser behaviour without a web path (a Playwright bump in uv.lock, .github/scripts/browser_shard.py) do not start the reported legs; the nightly covers them.

## Ledger
Round 1: 0 findings.
