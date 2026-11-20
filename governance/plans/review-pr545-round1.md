# Review: PR #545 (nightly on all cores, sharded browsers, parts by hand), round 1

Reviewer thread "Review the CI speed-up PRs", 18 Nov 2026. Head reviewed: 5c91fa5 (base 2cb10c5). Critical (CI), up to 4 rounds.
Verdict: **changes needed** (1 must-fix).

## Must fix

**M1. Two fixed-seed fuzz tests lose their nightly size.**
`tests/unit/test_textprep_units_abbreviations.py::test_random_token_soup_never_gives_overlapping_or_bad_edits` (line 588) and `::test_random_german_token_soup_never_gives_overlapping_or_bad_edits` (line 998) run 30,000 texts when `HYPOTHESIS_PROFILE == "nightly"` and 2,000 otherwise. They are plain functions, so Hypothesis's plugin does not mark them `hypothesis`; with `-m "hypothesis and ..."` no job runs them at 30,000 any more (PR CI runs 2,000). The PR body's "the other ~6,900 take the same inputs on every PR" is not true for these two.
Checked: `grep -rn HYPOTHESIS_PROFILE tests src scripts` finds three readers besides conftest: these two and `tests/unit/test_web_schemathesis.py:33` (module level, EXAMPLES 300 vs 25). The Schemathesis test is marked `hypothesis` (collected with `-m hypothesis`), so it stays covered.
Fix, exactly:
1. Register a marker in `pyproject.toml` `[tool.pytest.ini_options] markers`, e.g. `"deep: runs with more inputs in the nightly property job (HYPOTHESIS_PROFILE=nightly)"`, and put it on both tests.
2. property-deep selects `-m "(hypothesis or deep) and not slow and not benchmark and not browser" -n auto`; reword the comment above it.
3. A guard in `tests/unit/test_ci_workflows.py` that fails when a test reads `HYPOTHESIS_PROFILE` but would not be selected by property-deep's `-m` expression (read the expression from nightly.yml, not a copy). Suggested: AST-scan `tests/**/test_*.py` for test functions whose body names `HYPOTHESIS_PROFILE`, or that use a module-level name assigned from it; run `pytest --collect-only -q -m <expression>` (or `pytester`) and assert each such test is in the selection. Name the change in the PR body (test-harness change).
I will check it by removing the marker from one test and expecting the guard to fail, and by counting property-deep's tests in the final dispatched Nightly (144 expected at today's main, plus any new ones).

## Verified (no action)

- **Shards are complete and deterministic.** Locally on 5c91fa5, for chromium, firefox and webkit, `browser_shard.py` with PYTHONHASHSEED=1 and 777 gave identical files; shard 1 + shard 2 = 87 + 87 = 174 unique node ids, equal to `pytest -m browser --browser X --collect-only -q`; `pytest @shard.txt --collect-only` returns exactly the file's ids (chromium, webkit). Run 44349103475 logs show "shard N of 2: 87 of 174" and 86 or 87 run (1 skip) on every shard.
- **A red shard fails the run**: matrix `fail-fast: false`, each shard its own job, no summary job in nightly; run 44349103475 is red from WebKit-Ubuntu 1/2 alone.
- **Property job**: `-m hypothesis` and the full expression both collect 142; run 44349103475 "142 passed in 710.68s".
- **Inputs default to the full run**: four booleans default true; scheduled runs skip the `inputs` check. Concurrency: only dispatches on non-main refs cancel.
- **"CI passed" (#548)**: ci.yml is untouched, so the cancelled-leg problem is neither better nor worse.
- 63b16d7..5c91fa5 changes only the slow-tests line and its comment. Check runs on 5c91fa5: CI passed, tests (ubuntu, macos, windows), browser all green.
- The red WebKit-Ubuntu shard 1/2 failed with different tests on its two attempts; I accept the reading as #437 (D-731).

## Notes for the coordinator (no change asked in this PR)

- Job names now carry the shard: "browser (webkit, macos-latest, 1/2)". A green WebKit nightly for #437's count of five means both shards green.
- Nightly now takes 3 macOS jobs (two WebKit shards plus slow tests) of the account's 5, was 2.
- Two dispatches on the same branch with different parts cancel each other; fine while only the lane's own thread dispatches on its branch.

## Final round (when M1 is in)

Merge main into the branch (it is behind), Linux CI and ci:full green on the new head, and one dispatched Nightly with default inputs on that head: every job's pass count read from the log, shards adding up to the full browser collection, property-deep count including the two `deep` tests.
