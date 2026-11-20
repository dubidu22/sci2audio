# Review PR #361, round 2 (textprep follow-ups PR 3, English numbers #336 #340 #210)

Heads: 56508a4 (the fixes) and 2e3d50d (main 739f69c merged in). Answer: plans/review-pr361-round1-answer.md.

**Verdict: approvable at 2e3d50d.**

- **S1, fixed.** `10^-250 000 000`, `10^+250 000 000` and `10^−250 000 000` read "10 to the power of (minus) 250,000,000" on both runs. The grouped-digits skip takes the sign too.
- **N1:** the row "It is 10^250 000 000 5 here." is pinned. With the grouped look-ahead removed it still stays as printed, so the look-ahead is redundant and defensive, not load-bearing as the answer says. That is harmless, and no fix is asked.
- **N2, done.** The tilde changes are listed in the PR body.
- **Merge of main 739f69c:** the PR diff on main adds only its own lines, and #359's tests and cases are kept. `It is −↵3/4 s⁻¹` now reads the same on both runs.
- **Probes**, the round-1 set plus the signed rows and the #359 set, whole chain twice: the only differences are the two known #358 rows.
- **Fast suite:** 5347 passed, 1 skipped, 0 xfailed. Regression cases EN/DE twice: 579 passed both times. The corpus second-run test passes on 13 of 13. ruff, format, lint-imports and deptry are clean.
- **The 13 sample documents** (main 739f69c vs 2e3d50d): all 39 files are byte-identical.
- **Mutants:** 9 of 10 fail the tests. They covered: `\n` dropped from `_MINUS`; the sign removed from grouped; one plain group allowed; the narrow alternative removed; the grouped-digits skip removed; the skip without a sign; "^" dropped from `_TIMES_TEN`; groups joined with spaces; `\n?` dropped from `_TILDE`. The survivor is the redundant look-ahead (N1 above).
- **Nightly seeds** 7 (it fails on main before this PR) and 2024 are clean.
- **Commit messages:** 63a4409, 3f56c76 and 56508a4 carry no closing keywords.
- **CI on 2e3d50d:** tests (ubuntu-latest), (macos-latest) and (windows-latest) are green.

Fix list: none. Deferred: none. D-614 is accepted as decided.
