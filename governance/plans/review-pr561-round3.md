# Review PR #561 (#466), round 3 (final)

- Head reviewed: ad82259 (ad8225947ca847082d3b23efd1d5d08439120ec1), test-only fix commit on df587f7. Answer: `plans/answer-pr561-round2.md`.
- **Verdict: approved and merged** as 0bbb991 (squash, pinned to ad82259), 18 Nov 2026 ~22:05Z. #466 closed by the PR body.

## Verified

- Diff df587f7..ad82259: `tests/unit/test_extraction_text.py` only (+21).
- S1 re-checked here by hand on ad82259: `_title` mutants 13 and 14 each fail all three cases of `test_punctuation_before_closing_quotes_or_brackets_keeps_the_lines_joined` (English quotes, German guillemets, bracket); mutants 3 and 4 each fail `test_a_two_letter_line_can_be_a_title_line`. Clean: 78 passed.
- Final-round evidence (REV-03): code unchanged since df587f7, so mutation run 44401678397 (4 real survivors, now killed; the rest equivalent or a boundary) and nightly property run 44401683375 (green) stand. CI on ad82259: `CI passed` green in 44403909890 and 44404014751; `tests (ubuntu/macos/windows-latest)` success in both, no re-run.
- MRG-03: no file of the PR changed on main 1797ceb..215405c (includes #558 c51e846 and #562 215405c); mergeable clean. Main was not red at merge time.
- No closing keyword in commit messages; squash message set explicitly.
