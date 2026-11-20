# Review PR #712, round 2, the last (batch B-I4, #695, #706)

Thread: review-infra-b-i2 (Opus 5.5). Head reviewed: d562db0 (one fix commit on c0d934e). Date: 2026-11-20.
**Critical: no** (unchanged: comments, docstrings, tests and the scaffold copy only; no core, `.github`, regression, corpus or snapshot file). Plan `plans/infra-b-i4-plan.md`, section "PR 2", approved as D-860. Answer: `plans/answer-pr712-round1.md`.

**Verdict: approved** (0 must-fix, 0 should-fix, 1 note).

## Verified

- Scope of `git diff c0d934e..d562db0`: 37 files, +146/−88. They are 35 `.py`, `static/app.js` and `templates/privacy.html`; no TOML, golden, regression, corpus, snapshot, core or `.github` file. The 35 `.py` files cover the clean-up and the test.
- Comments and docstrings only, by the same check as round 1:
  - For the 34 modified `.py` files other than the test, the AST with docstrings blanked is identical before and after.
  - The three `app.js` lines are `//` comments, and the `privacy.html` line is a `{# #}` Jinja comment.
- S1 is fixed:
  - `REVIEW_TAG` gains alternatives for every form I listed. Each has a comment naming its form, and the finding letters are limited to `B F M N R S T`, so an issue's own `Q2` or `D5` stays.
  - `joined()` merges consecutive `#` or `//` comments into one text at the first line's number, and the tag's line is still exact.
  - The 14 new forms and the 4 new plain phrases are parametrized, and the split-over-lines case is pinned for Python and JS.
  - With d562db0's test on c0d934e's sources, `test_no_comment_or_docstring_carries_a_review_tag` reports 77 hits. On d562db0 it passes.
  - A broad rescan of every comment and docstring the test reads, for "review" and "round N", leaves only the plain uses: "for a review (#386)", "review the changed file", "outside review (D-703c)" and "a reviewer can check" (3 files).
  - The rewrites keep the issue numbers, and the section rules in `test_web_figures.py` now say what each section holds.
- Labels and ownership: the labels are unchanged (`lane:infra`, `lane:cli`, `lane:extraction`, `lane:layout`, `lane:textprep`, `lane:web`, `risk:low`). `templates/privacy.html` is `lane:web`, which is already set. `pr_checks.py`, run locally on `git diff b00002d..d562db0`, passes with these labels: title, lane label and ownership ok, nothing critical. Its unowned-tests warning is the usual one for `tests/`.
- Local run in a fresh `/tmp/review-712` at d562db0:
  - ruff check: clean. ruff format --check: 389 files formatted.
  - lint-imports: 3 kept. deptry src: no issues.
  - Fast suite with `-k "not espeak" -n auto`: 8713 passed, 6 skipped, 6 xfailed, and 77 snapshots passed.
  - Browser tests (Chromium, `-n 4`): 198 passed, 5 skipped.
- Not verified here: the Linux CI on d562db0, which the coordinator checks.

## Findings

### Notes
- N1: the author's answer reports two unnamed failures in a first local fast-suite run, and none on a full rerun of the same tree. My run on d562db0 was clean. Unnamed failures cannot be followed up under D-374. If it happens again, the run should be kept with `-rf`, so the test is named and gets an Issue on its second failure.

Verdict: approved. Merge on the coordinator's go after `main` (c82b2d6, with #713) is merged in. That merge touches only `promised_tests.py` and its test, and this PR changes neither, so a clean merge needs a check of the merge commit and Linux CI only (not critical).
