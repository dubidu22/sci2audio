# Review of PR #572, round 3

Reviewer: B2 review thread (critical, Opus high). Reviewed head **ddb1519** (one tests-only commit
on de21173). Result: **APPROVED**, merge pinned to ddb1519 once its three-system run is green.

- F3 done exactly: `test_a_raised_mass_number_at_the_block_start_is_a_mass_number` (F3a) and the
  case `"1"` + sup `"4"` + `"K and more"` in
  `test_a_raised_run_glued_after_a_letter_or_digit_is_no_mass_number` (F3b). Diff de21173..ddb1519:
  `tests/unit/test_textprep_units_abbreviations.py` only, 18 added, 1 changed line; no `src/` change.
- Mutants 24 (`or text[start - 1].isalnum()`) and 25 (`start > 1`) killed by those tests (author's
  run, mut3.py, ROOT at ddb1519, baseline PASS); both kills hit the intended tests by name.
- Linux CI 44425760173 green. Three-system run of ddb1519: see the merge note below.
- Main moved to 5a605e5 (#569) after de21173: it changes `CHANGELOG.md` under "Changed" only; the
  PR's line is under "Fixed". GitHub reports the PR mergeable (clean). No other file in common;
  no branch update (MRG-03: a non-code file with no overlapping hunk).

Totals over three rounds: 3 must-fix findings (F1 second-run break, F2 CHANGELOG, F3 two
boundary tests), 0 deferred from the PR; filed #576, #578; comment on #567.
