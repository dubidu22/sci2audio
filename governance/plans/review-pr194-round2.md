# Review of PR #194, round 2

Reviewed head 9aa0f75, 13 Nov 2026 ~21:15 UTC, against round 1 (`review-pr194-round1.md`) and the author's answer (`review-pr194-round1-answer.md`).

## Round 1 items, checked

- S1 to S5: fixed as described. The new tests are in `test_textprep_footnotes_linked.py` and the `page = true` row is in `test_textprep_regression.py`. `regression._case` now refuses a bool page.
- All seven named mutants (#0, #3, #10, #24, #27, #28, #38) are now killed, and so is a new mutant that drops the bool check. I re-ran them myself.
- N1: the guard is kept with a comment. N2: unchanged. Both are fine.
- Ruff, lint-imports (3 kept) and deptry are clean. CI on 9aa0f75 is all green.

## Must fix

- **M1. `test_many_marks_and_notes_take_linear_time` is flaky under load.** My first fast-suite run on 9aa0f75 (`-n 8` on 4 cores) failed it. The second run passed (3164 passed). Run alone, it passes every time.
  - Measured on this machine, eight pairs per setting:
    - Idle: 2,000 marks take 0.019 to 0.071 s and 20,000 marks take 0.28 to 0.42 s, a ratio of 3.9 to 20.1.
    - With 7 busy processes: the ratio is 4.7 to 16.8.
  - The test asserts a ratio under 25, so one slow "large" timing or one fast "small" timing near the margin fails it. On a busy CI runner that becomes a quarantined test by D-374.
  - Fix suggestion: time each size as the best of 3 runs (`min`), with `gc.disable()` around the timing. Either keep 25 with that, or loosen it to 40 (quadratic would give about 100). Keep the absolute bound as it is (`large < 2.0`).
  - After the fix, run the fast suite twice with `-n 8` (or with the CPU otherwise loaded) and give the counts.

## Nothing else

There are no other findings. Once M1 is pushed and CI is green, I merge.

## M1 fix, checked (head 7945b65, then 6b81f5e)

- 7945b65 times each size as the best of 3 runs with gc off, uses a ratio limit of 40 and keeps `large < 2.0`. Nothing else changed.
- With 7 busy processes on 4 cores the test passed 5 runs out of 5. The fast suite with `-n 8` gave 3164 passed, 1 skipped.
- Main had moved to a37c18e (#197, #198, both layout). I merged it into the branch through GitHub's update-branch (a merge commit, no force-push), which gave head 6b81f5e.
- On 6b81f5e:
  - The fast suite gives 3165 passed, 1 skipped.
  - Main a37c18e vs the PR head: the 7 PDFs and the text sample are byte-identical in the script, report.json, report.md and job.json files. The Markdown and EPUB diffs are still exactly the plan's lines.
- Round 2 is clean. I merge once CI is green on 6b81f5e.
