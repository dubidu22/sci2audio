# Review: PR #551 (scoped mutation runs, #549), round 1

Reviewer thread "Review the CI speed-up PRs", 18 Nov 2026. Head reviewed: 325be81 (base c3b79c2). Critical (CI, pytest/mutmut config), up to 4 rounds.
Verdict: **changes needed** (2 must-fix).

## Must fix

**M1. The summary hides every mutant that was not tested.** `report()` lists only status `survived`. mutmut 3.8.1 also gives `no tests` (no selected test covers the mutant), `not checked`, `suspicious`, `skipped`, `segfault` and `check was interrupted by user` (mutmut/stats.py `status_by_exit_code`), and the headline says "Survived: 0".
Reproduced locally on 325be81 (HYPOTHESIS_PROFILE=ci, MUTANTS=`sci2audio.textprep.links.x__words*`, TESTS=`tests/unit/test_core_moves.py`): `run` exit 0, `report` exit 0, table "no tests | 9", "Survived: 0". A reviewer who passes the wrong test paths gets a green job that reads like full coverage (review lesson: a green job whose numbers do not show what ran is no evidence).
Fix, exactly: (1) the headline becomes "Not killed: N", where N counts every matched mutant whose status is not `killed`, `timeout` or `caught by type check`; (2) list those mutants grouped by status (keep the 300 cap per status, and say when it cut the list); (3) `report` exits 1 when any matched mutant is `not checked`, or when every matched mutant is `no tests`. Survived and partial `no tests` stay green, as information for the reviewer.

**M2. The mutmut run uses the dev Hypothesis profile.** The workflow sets no HYPOTHESIS_PROFILE, so mutmut's runs use `dev` (tests/conftest.py: 50 examples, random seed, Hypothesis's default 200 ms deadline, health checks on). Under mutmut's trampolines the code is slower:
- Locally on 325be81, TESTS=`tests/unit/test_core_moves.py` without a profile: the first, unmutated run failed with `FailedHealthCheck: Input generation is slow` in `test_valid_moves_never_raise_and_their_order_is_irrelevant` ("failed to collect stats"). With HYPOTHESIS_PROFILE=ci the same run passed.
- A deadline or health-check failure on a mutant counts as a kill, so the dev profile can also turn survivors into false kills, and the random seed makes two runs of the same request disagree.
Fix: set `HYPOTHESIS_PROFILE: ci` (derandomized, no deadline, too_slow suppressed) on the mutation run step, with a comment saying why.

## Verified (no action)

- **#549 fixed.** Locally, TESTS=`tests/unit/test_web_design.py`, profile ci: the unmutated run passes with the new also_copy; with `THIRD_PARTY_LICENSES.md` taken back out it fails `test_every_font_is_the_licence_tables_file_byte_for_byte` ("failed to collect stats", exit 1). So a broken baseline fails the job.
- Inputs reach the script only through env (workflow-level env from inputs, no `${{ }}` in run lines). Globs must fullmatch `sci2audio(\.[\w*?\[\]ǁ]+)+` (no leading "-"), test paths start with `tests/` and contain no `..`. The selection is written to pyproject.toml in the runner's checkout only.
- Globs are dealt out round-robin; runners = min(asked, number of globs); overlapping globs on two runners only double work.
- `timeout 300m` inside `timeout-minutes: 350`: a cut run exits 124, the job is red, and the report step still runs (`always()`).
- Dispatched run 44374963395 on 325be81: green; runner 1 "killed 12, survived 7" with the 7 listed; runner 2 "killed 9".
- Concurrency: the same request waits, a different one runs beside it (cancel false).

## Notes (no change asked)

- The default `tests/` selection can still fail the unmutated run on main through #550 (a Hypothesis find, random under the dev profile); with M2's ci profile it is derandomized, so it either always fails or never does for a given main. Pre-existing, not this PR.
- `no tests` for part of a module glob is real information (those functions are not covered by the chosen tests); the reviewer's report should quote it.

## Final round (when M1 and M2 are in)

Merge main (the branch is behind), Linux CI and ci:full green on the new head, and two dispatched runs on it: (a) the links.py globs of 44374963395 again, numbers comparable; (b) the same glob with a test path that does not cover it, showing the "no tests" mutants listed and the job red.
