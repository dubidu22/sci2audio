# PR #682 review, round 1 (head 90d1199)

Reviewer: review-layout-b-l1, Opus. 20 Nov 2026. Plan: plans/layout-b-l2-plan.md (D-840, amended by D-841).
Critical: **yes** (CRIT-01: a golden file under `tests/unit/__snapshots__` changes; `risk:high` set).
Verdict: **approved, one should-fix** (0 must-fix, 1 should-fix, 3 notes). The should-fix is a comment and can come in a fix commit or a follow-up issue; nothing blocks the merge.

## Checked and fine

- **#181** (`graphics._hosts`, `_ruled_line`). The three conditions of D-840 hold: the rule's top overlaps the line's foot or stands within `heading_rule_gap` of it; the rule is read before the line; it lies under at least half of the line's width. Hosts that hold the rule (D-329) come first, and a footnote right after it keeps its rule (#51). The issue carries the comment that adjusts its AC (16:41 UTC, AC 1 to 3, D-385 kept).
- **#54** (`headings._numbered_item`). Only one-line LIST_ITEM blocks labelled "1." or "1)" become heading candidates, judged by the unchanged heading rules. Those not taken stay list items, because `find_headings` replaces only the blocks in `levels`.
- **#59** (`graphics._plots`, setting `plot_size` 4 em). Dot-only groups are clustered by `order.touching` within `float_gap`, and a cluster becomes a figure from 3 dots and `plot_size` both ways. `_is_line` is unchanged. Each plot enters the figure merge as one figure, which keeps the speed test linear.
- **#55** (`graphics._labels`). An uncaptioned figure takes only lines that are smaller than body text, wholly inside the box of its graphics, and not taken yet. It takes none when a single graphic holds them all (D-840 Q3).
- **#56** (`_Walk._row`, `_reaches`; `build` passes the column edges in). A row-mate in another column is taken only once the walk's span reaches into that column. A line without edges is judged as before.
- **Failing first.** I ran the new tests against main's `src/sci2audio/layout`. Six fail: the issue tests of #181, #54, #59, #55 and #56, and the #59 Hypothesis property. The five guards pass (logo of dots, background at 10 and 8 pt, table across both columns, rule under less than half a line, numbered list in body text), as they should.
- **Golden diff.** One file, `test_layout_corpus.ambr`, with Liu p4 blocks 42 and 43 (two lines for one change). The bars p4-d1 and p4-d2 leave the page-number block, which keeps only `p4-l1`, and join paragraph 43, which goes from 7 to 9 parts. No block's text changes. This is exactly what D-841 accepts and the PR body shows; every other golden is unchanged.
- **Invariants.** `test_layout_never_fails_and_keeps_every_line`, every item in one block, `test_each_line_stands_in_its_block_as_found`, the corpus truth tests, `test_a_page_background_or_a_frame_does_not_cut_the_columns` and the speed tests are green. The new property also asserts that every marker is read in exactly one block.
- **Layers.** `graphics` now imports `layout.order`, which stays inside the layout package. lint-imports keeps 3 contracts and deptry is clean.
- **Licence.** No dependency, file, model, voice or text added; the PR body says so.
- **No unrelated change.** 7 files: four layout modules, two test files, one golden.
- **CI on 90d1199.** `CI passed` and `governance pr checks` are green, and `tests` passed on ubuntu, macos and windows (run 44775816421, head 90d1199), as did both Chromium browser shards.
- **Local run** (temporary worktree at 90d1199, macOS, `-k "not espeak"`). ruff, ruff format, lint-imports and deptry are clean. 8453 passed, 6 skipped, 6 xfailed, 0 failed; 77 snapshots passed.

## Should fix

**S1. The new setting splits another setting's comment.** In `src/sci2audio/layout/settings.py:116-117`, `plot_size` is inserted between `mark_height` and the continuation line of its comment. The file now reads `mark_height: ... at most this tall is a mark`, then `plot_size: ... are a plot`, then `#  (an icon), not a figure`. The "(an icon), not a figure" note now seems to describe a plot, and `mark_height` loses half its description. `settings.py` is where every `LayoutSettings` field is documented, so `plot_size`'s documentation is garbled with it. Fix: move `plot_size` below the continuation line, and say "(a scatter plot of dots, #59)" if a gloss is wanted.

## Notes

- **N1.** The PR body says the bars join paragraph 43 "right after their numerator" and names "U3 1" (p4-l17). The golden puts them at offset 21, after "U3 1 2πniU4 0 mev2F∆2", that is after p4-l19, the second fraction's numerator. `_ruled_line` picks the nearest line under the group's box, and the group of both bars stands under both numerators. The bars are not read, so the result is fine. Only the body's wording is off.
- **N2.** The #59 property draws markers on a regular grid, at most `float_gap` apart. The plan spoke of "random places in a box of random size". So the property does not cover markers more than `float_gap` apart splitting into several clusters. The touching and 10 pt-apart cases are covered by the unit test. Acceptable; it could be widened later.
- **N3.** #54 puts list items into the candidate set from which `_same_sizes` and the heading rules draw their statistics. The corpus is unchanged (83 headings, 69 list items), so I record it only.

## Handoff (THR-07)

- Goal: PR #682 (B-L2) merged.
- Done: round 1 at 90d1199, approved with S1 open; three-system CI green on this head.
- Next: the author fixes S1 in one commit (Linux CI; a three-system run again on the final head, CRIT-02), or the coordinator defers S1 to an issue and merges 90d1199.
