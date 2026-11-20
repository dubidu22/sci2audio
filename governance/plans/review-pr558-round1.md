# Review PR #558 (#529 + #535), round 1

- PR: dubidu22/sci2audio#558 "layout: contents pages with page numbers at the left edge, page labels from running heads (#529, #535)"
- Head reviewed: c27ce9d (c27ce9d642799336e2e47096dfe6e723bee1deeb), parent 1797ceb; main is f919d81 (CLAUDE.md and docs/readalong-format.md only since, no overlap, no update needed under MRG-03).
- Reviewer: B3 review thread, Opus high, 18 Nov 2026.
- **Verdict: changes requested, tests only (1 should-fix). The code and every golden move are accepted.**

## Verified

- CI on c27ce9d: `CI passed` green (runs 44393877637, 44393999500); `tests (ubuntu-latest)`, `tests (macos-latest)`, `tests (windows-latest)` success in run 44393999500 (ci:full).
- Golden moves, each against the plan:
  1. `test_layout_corpus.ambr`: only the PrivacyScore `page labels` line moves (`- 2 3 … 13`).
  2. `test_app_corpus.ambr`: all 431 changed lines are `printed_page` inside the PrivacyScore json report section (lines 4057 to 11380); 374 + 57 nested, as the plan says. Every changed value equals its record's `page` (pages 2 to 13); page 1 keeps `''` (29 records). No other field or document moves.
  3. Corpus truth test: the new expectation derives head numbers from the truth's running-head texts only when one offset holds on two or more pages; for every other paper it is `{}`, so their expectation is unchanged.
  4. `test_heads_in_a_small_type_area_are_running_heads`: `("", "2", "3", "4", "5")` with the reason; correct.
- Corpus comparison (REV-07): `run_script_job` on all 13 corpus documents, main f919d81 vs c27ce9d. Only `arxiv2017-maass-privacyscore.report.json` differs, and only in `printed_page` (431 values). Every script and Markdown report is byte-identical.
- Nightly property run on c27ce9d (nightly.yml dispatch, property only): run 44398253796, `property-based tests, many examples` success.
- Mutation (mutation.yml dispatch, run 44398248044, 2 runners, mutants `furniture.x_head_labels*`, `x__left_entries*`, `x__contents*`, `build.xǁ_Layoutǁlabel*`, tests `test_layout_contents_labels.py test_layout.py test_layout_corpus.py`; baseline run passed): 140 killed, 17 survived. `head_labels` and `_Layout.label`: all killed. Survivors read one by one (`mutmut show`, local generation on c27ce9d):
  - `_contents` 8, 11, 18: equivalent (empty `lines` has no rows; `size` is never below 2 pt). 13, 34, 35 touch old lines (reach scale, `\W` strip of "Table of Contents") that `test_layout_headings.py` covers; it was outside the selected tests.
  - `_left_entries` 4, 5, 6, 16: equivalent (start values overwritten at the first entry; `at` unused for a one-piece row; page 0 aside).
  - `_left_entries` 30, 37, 60, 65: `<=`/`>` boundary flips at exactly `edge`/`reach`/`numbers`; accepted as boundaries.
  - `_left_entries` **21, 32, 40: real gaps, see S1.**

## Findings

**S1 (should fix, tests only). Three behaviours of `_left_entries` that the plan states have no test.**
- (a) Mutant 32 (`int(number) >= last` → `>`) survives: **two entries on the same page** (two short pieces sharing a page, common in a journal issue's contents) are never tested. Add an entry pair with the same page number; both must be `contents`.
- (b) Mutant 21 (`len(row) > 1` → `>= 1`) survives: the plan says "a row whose number and text are one piece is not taken", but no test puts **a lone number row right after the title**. With the mutant it becomes an entry at indent 0. Add: title, then a row holding only "3", then text: the lone number and what follows stay text.
- (c) Mutant 40 (the indent follows the latest entry instead of the first) survives, and every test sets numbers and indents to exact equal x. Add a page with the jitter measured on Kehren: page numbers right-aligned ("9" and "17" start at different x), entry text indents between 87.4 and 89.1 pt, continuation rows at varying x within reach, and entries whose indent creeps by about 1.5 pt each so that the fourth is more than `contents_reach` from the first (it must end the contents if the rule is "within reach of the first entry's text", as the docstring says).
Each new test must fail on its mutant (state which in the answer).

## Notes (no action)

- N1. `head_labels` with `repeat_pages = 2`: heads such as "Chapter 1" on page 5 and "Chapter 2" on page 6 would give labels "1" and "2". It needs one-page chapters with bare numbered heads; not seen in the corpus. No issue filed.
- N2. A document whose footer prints article page numbers and whose heads print journal page numbers would mix the two numberings across pages. Not seen; no action.

## Next

One test-only fix commit; answers in `plans/answer-pr558-round1.md` (fixed, with the mutant each test kills). Final round (round 2): Linux CI and the three-system run on the fix head (I add `ci:full` if the author has not run it), then merge pinned to that head.
