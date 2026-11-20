# Review: PR #551, round 2 (final)

Head reviewed: 9ea1ddf (fix commit 9ea1ddf on merge 381b338 of main f126875). Verdict: **approved**.

## Round 1 findings
- **M1 fixed.** `report()` lists every matched mutant whose result is not killed, timeout or caught by type check, grouped by result (300 per result, says when cut); headline "Not killed: N"; red when any mutant is not checked, when every matched mutant is "no tests", or when no mutant matched.
- **M2 fixed.** `HYPOTHESIS_PROFILE: ci` on the mutation run step, with the reason in a comment.

## Final-round evidence (both on 9ea1ddf)
- (a) 44379406170, the links.py globs of round 1: green; runner 1 killed 12, survived 7, "Not killed: 7" with the 7 listed (same names as 44374963395); runner 2 killed 9, "Not killed: 0".
- (b) 44379412456, `x__words*` with tests/unit/test_core_moves.py: "no tests | 9", all 9 listed, "Red: no test asked for covers any of these mutants", job red. (This is the red "mutmut, runner 1" check on the head commit; it is meant to be red.)
- Check runs on 9ea1ddf: CI passed, tests (ubuntu, macos, windows), browser, ZAP green.
- No closing keyword in the branch commits other than the PR body's "Closes #549".

## Ledger
Round 1: 2 must-fix (M1, M2). Round 2: 0 findings.
