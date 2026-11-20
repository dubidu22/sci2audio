# Review: PR #545, round 2 (final)

Head reviewed: b0dcb39 (fix commit b0dcb39 on merge 952d789 of main c3b79c2). Verdict: **approved**, merge pinned to b0dcb39.

## M1 (fuzz tests lose their nightly size): fixed
- `deep` marker registered in pyproject.toml and put on both token-soup fuzz tests; property-deep selects `(hypothesis or deep) and not slow and not benchmark and not browser`.
- Guard `test_every_test_that_reads_the_nightly_profile_runs_in_the_nightly_property_job` reads the expression from nightly.yml, finds readers of HYPOTHESIS_PROFILE by AST (direct reads and module-level names, decorators included), and collects the selection with pytest.
- Mutation check, locally on b0dcb39: (1) marker removed from the first fuzz test: guard fails; (2) property-deep expression put back to `hypothesis and ...`: guard fails; clean: tests/unit/test_ci_workflows.py 8 passed. Local collection of the expression: 144.

## Final-round evidence
- Dispatched Nightly 44366479952 on b0dcb39, default inputs, all 13 jobs green: property-deep "144 passed in 695.59s"; every browser shard "87 of 174", 86 or 87 passed (one skip on each shard 1), Chromium, Firefox, WebKit Ubuntu and WebKit macOS; slow tests 30 passed on ubuntu, macos, windows; benchmarks 7 passed.
- Check runs on b0dcb39: CI passed, tests (ubuntu, macos, windows) and browser green. One of the two CI runs had a macOS leg cancelled without a runner (#548); the other run's tests (macos-latest) succeeded.
- No closing keywords in the branch's commit messages.

## Ledger
Round 1: 1 must-fix (M1). Round 2: 0 findings.
