# Review of PR #277, round 2 (issue #276, D-540)

Head reviewed: b370b08, then the main merge 46a7a45 (update-branch by this review thread, merge commit, main 407f5bd #288). Date: 14 Nov 2026.

## Verdict

Clean. F1 fixed, N1 fixed. No new findings. Merge once CI on 46a7a45 is green.

## Fixes checked

- **F1 fixed (b370b08).** The `deep-brackets` case left `test_long_german_blocks_take_linear_time`. A new test, `test_a_deep_german_nest_takes_about_as_long_as_plain_citations`, times the 20,000-deep nest against `("(Müller 2019) " * 3000)[: len(deep)]` through LINKS + CITATIONS (de) with a new helper `assert_near` (best of 3, gc off, same 2 ms floor), limit 16. Its docstring names the cap and the measured ratios.
  - Today's code: passes (ratio about 6).
  - `_MAX_BRACKET = 8000`: fails, 21.0 (0.098 s vs 2.056 s).
  - `_MAX_BRACKET = 16000`: fails, 89.2 (8.561 s): meets the acceptance.
  - no cap (`10**9`): fails, 575.1 (56.7 s).
- **`assert_near` fake-clock tests are real.** Raising its limit ×100 or timing the text as its own reference each make one of the two new tests fail.
- **N1 fixed.** `test_a_long_block_takes_linear_time` (citations) has ids `numeric`, `author-year`.

## Runs

- b370b08, `HYPOTHESIS_PROFILE=ci`, fast suite `-n 24` on 4 cores: 4292 passed, 1 skipped (184 s).
- The 40 timing tests (all converted cases, the new deep-nest test and the helper tests) under `-n 24`: passed 5 times out of 5 on b370b08, and once more on the merge 46a7a45.
- Ratios after the main merge (#288 changed links.py and others): 5.3 to 9.2 across the converted cases, serial.
- GitHub CI on b370b08: all green. On 46a7a45: see merge note in the thread.

## Process note

The author's fix list was not posted on the PR. The commit covers exactly F1 and N1 (4 files: helper, helper tests, citations ids, German links/citations test), checked above.

## Merge

Main moved twice during the review (#288 at 407f5bd, then #290 at 1d4fb56, which touched only the web player). Both times the review thread updated the branch with a merge commit (46a7a45, then 95f182e). CI was green on 95f182e. Squash-merged at 2026-11-14 14:02:21 UTC as 4cfff38. #276 closed.

## After the merge

At 14:02:40 UTC, 19 s after the merge, the author pushed fb447bb (the timing helpers measure process CPU time instead of the wall clock) and bb815ff (a 62.5 ms floor on Windows for its CPU-time tick). That push replaced the branch history: 95f182e is not an ancestor of bb815ff. Neither commit is in main and neither was reviewed. The author was asked to open a new PR from main under a new issue, to be reviewed in this thread.
