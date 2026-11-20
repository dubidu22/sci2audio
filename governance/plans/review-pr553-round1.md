# Review: PR #553 (PR browser shards; "CI passed" reads every job, #548), round 1

Reviewer thread "Review the CI speed-up PRs", 18 Nov 2026. Head reviewed: 4081013 (base 2cad344, current main). Critical (required CI workflow), up to 4 rounds; final-round evidence is already in.
Verdict: **approved**, no findings.

## Checked
- **#548 fixed, against the real runs.** `ci_passed.py` from 4081013 run here with REPO/RUN_ID: on 44349877322 (the #548 run) it exits 1 naming "tests (macos-latest): completed, cancelled"; on 44382819875 it exits 0, "All 6 jobs of this run succeeded".
- **No legitimately skipped or unlisted job can turn it red.** Every ci.yml job is in `ci-passed.needs` (lint, licences, security, tests, browser); the tests matrix is computed (one or three systems), not skipped by `if:`, so no job of a normal run ends `skipped`. Jobs are read with `filter=latest`, so a re-run of failed jobs is judged on its latest attempt. API failure fails closed (red, re-run fixes it).
- **Required check unchanged.** Ruleset main 26932142 requires only "CI passed" (strict policy now false, D-760); no ruleset or doc names "browser (Linux, Chromium)".
- **Shards.** Same job id `browser` in needs; run 44382819875 logs: "shard 1 of 2: 87 of 174" (86 passed, 1 skipped) and "shard 2 of 2: 87 of 174" (87 passed). Shard determinism was checked for #545 (same script).
- **ci:full** 44382746054 (workflow_dispatch on 4081013): all 8 jobs green including tests (macos-latest) and tests (windows-latest); CI passed log "All 8 jobs of this run succeeded".
- **Tests bite.** Locally on 4081013: test_ci_workflows.py 17 passed. Hand mutants: `not_succeeded` reduced to `conclusion == "failure"` gives 3 failed; the wait loop made to never wait gives 1 failed. zizmor: no findings.
- Permissions: `contents: read`, `actions: read` on the ci-passed job only; inputs none; checkout without credentials, sparse to .github/scripts.

## Notes (no change asked)
- Wall time: Linux PR CI 5.2 min (was about 9).
- PR 4 is stacked on this branch and changes the same lines; it is reviewed after this merges.

## Ledger
Round 1: 0 findings.
