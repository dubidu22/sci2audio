# Review of PR #620, round 2 (final): approved

Reviewer: B13 review thread, 19 Nov 2026. Reviewed head **4e24dea** (fix commit for round 1; answer `plans/review-pr620-round1-answer.md`).

## Fix list check

| Item | Result |
|---|---|
| T1 | `test_a_small_header_apart_from_its_rows_on_three_of_ten_pages_is_text` kills hand m04 and mutmut `_small_heads_64` |
| T2 | Hypothesis `_pages_near` vs `_repeated` property test kills hand m13–m15 and mutmut `_pages_near_16/18/24/26/36` |
| T3 | drift tests kill mutmut `_small_heads_6` and hand m16, m17, m24 |
| T4 | kills mutmut `_small_heads_41` |
| T5 | kills hand m02 and mutmut `_small_heads_15` |
| T6 | both counting rules kept; `test_a_captioned_figure_s_labels_count_neither_for_the_share_nor_for_the_fill` kills m20 and m21 each alone |
| T7 (a) | captioned-table test kills m22 |
| T7 (b) | stated and checked: `graphics._groups` takes only items with `line is None`; `build._block` builds FIGURE blocks from graphics; `build_tagged` runs only for content without positions. m23 equivalent. Code comment and test docstring now say only that |
| T7 (c) | `caption_reach` test kills mutmut `columns_per_page_5/7` |
| N1 | CHANGELOG reworded as suggested |

Code behaviour unchanged by the fix commit (src diff: one comment in `columns_per_page`).

## Final-round evidence on 4e24dea

- CI: `CI passed`, `tests (ubuntu-latest)`, `tests (macos-latest)`, `tests (windows-latest)` success (ci:full), browser Chromium 1/2 and 2/2, lint and layers, licences, security, CodeQL.
- Hand mutants (`plans/b13-review/mut.py`, PYTHONDONTWRITEBYTECODE=1 and the layout `__pycache__` cleared before and after each mutant, following the author's note; the unmutated set passes, 476 tests): **23 of 25 killed**; m01 and m23 survive, both equivalent (round 1 report; T7 (b)). Round 1's m20/m21 survivors may have been helped by stale bytecode, since those mutants keep the file length; either way they are killed now.
- mutmut (mutation.yml run 44481551672, same globs and tests as round 1): 252 killed, 2 timeout, 16 survived. The 16 are exactly the ones round 1 listed as equivalent (`_small_heads_11/28/30/69/72/73/94/97/98`, `columns_per_page_35/38/39`, `_pages_near_12`) or pre-existing (`reading_order_3/45/68`).
- Nightly property tests (nightly.yml, property only) run 44481554762: success.
- Corpus: the fix commit changes no source behaviour, so round 1's comparison holds: furniture and blocks identical on all 8 papers, PrivacyScore p3 columns 3 → 1.

## Base move

Main moved from b6355cc to 805da4e (#630 tests, #609 extraction: EPUB, Markdown, markup parser; no PDF or layout file). CHANGELOG.md conflicted (both added "Fixed" lines). The reviewer merged main into the branch (merge commit 144056c, both lists kept, no rebase). Diff-unchanged check: `git diff b6355cc 4e24dea` and `git diff 805da4e 144056c` are identical outside CHANGELOG.md (index lines aside), and the CHANGELOG diff is the same single #156 line. Merge after `CI passed` on 144056c and the three-system CI on main 805da4e are green.

## Verdict

Approved. No issues to file from this PR.
