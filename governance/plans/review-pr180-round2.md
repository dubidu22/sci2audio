# Review of PR #180 (issue #48, ruled headings), round 2

Reviewed head 510e30b (author's fixes on top of my merge of main, bc6909b). 13 Nov 2026.

## Round 1 findings

- **M1, fixed and verified.** `_ruled` now measures all four conditions against the block's last row: the union of its text lines whose vertical middle lies inside the last line's box. My split-cell reproductions (full-width table x 70 to 526 and narrow table x 170 to 370, rule overhanging by 6 pt) are now paragraphs; my other cases are unchanged (header written as one line: paragraph; title framed by rules: no heading; underlined link: no heading; footnote rule at the foot of a column: goes to the footnote). The single-line uncaptioned header over a rule that overhangs it by at least 1 em is still a heading: that is the residual risk now named in the PR body. Two new unit tests cover the fix and the two-line heading case. The surviving "row upper bound dropped" mutant is explained correctly: no line read before the last one stands below it in a block, so the bound only documents the intent. Accepted.
- **S1, fixed.** Issue #181 "layout: a narrow rule under an indented line joins the block before it" exists, open, lane:layout, milestone v1.1, linked in the PR body.
- **S2, fixed.** The Risk paragraph names the residual case.

## Re-checked on 510e30b

- Fast suite: 2799 passed, 1 skipped (Windows only); snapshot tests pass without update, so the golden files are the ones I regenerated and checked in round 1.
- ruff check, ruff format --check, lint-imports (3 kept, 0 broken), deptry: clean.
- Spoken script, all seven papers: identical to round 1; against main only chi and hardt differ, by the one new chapter line each.

## Verdict

No open findings. Ready to merge once the required checks are green on 510e30b.
