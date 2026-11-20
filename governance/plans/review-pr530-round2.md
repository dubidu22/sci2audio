# Review of PR #530, round 2 (final)

PR: https://github.com/dubidu22/sci2audio/pull/530. Reviewed head: a42b511 (fix commit on 91d0b79). Answer: plans/answer-pr530-round1.md.
Criticality: non-critical (lane:layout). Opus medium depth.

## Verdict: APPROVED, 0 findings

| Round 1 item | Check |
|---|---|
| F1 small footer tight under the notes | Fixed (`_Page._own` trims trailing stack rows that are alone on their row and repeat word for word at their height, D-323). My probes: 7 pt footer at y 747 and 748 is a running head on all 4 pages, no note holds it; the round 1 probe with notes above the band (footer at y 720, 8 pt under) gives running heads and clean notes, as on main. New test fails on 91d0b79. |
| F2 small page number tight under the notes | Fixed (same trim, page-number shape). Probe: labels 55 to 58, notes end with their text. New test fails on 91d0b79. |
| Fixture change (`journal_page` note text per page) | Accepted: identical rows at one height on every page are a footer by D-323; the guarded case (note numbers at one height on several pages, notes in the bottom band) is unchanged and the assertions check every page by name. Not a weakening. |
| T1, T2, T3 | Tests added; the author re-ran each mutant by hand and each fails a test. Read the tests: each builds the case the mutant breaks. |
| T4 | Check removed with the reason in the docstring; agrees with my reading (found headings all come through `_short`). |
| N1 | Filed #535. N2 no action. |
| Corpus | Own run: all 8 corpus papers, every block, section and page label identical to main 96de4a3. No golden, snapshot or regression case in the diff. |
| Kehren (PR B extraction, measuring only) | Identical to round 1 output: 14 heads, labels 1 to 5, I/II/III. |
| CI on a42b511 | Linux CI green (tests ubuntu, browser Chromium, lint and layers, licences, security, CodeQL, CI passed). |
| Commit messages | No closing keywords. |

Residual risk noted, no action: a note's last continuation row that is alone, a bare Roman-numeral-shaped word ("mix") or repeated at the same height on two pages is given back to the furniture rules. Negligible.

## Merge

Main moved 2 commits (CLAUDE.md, web joined-sentences files); no overlap with this PR's files. Merge main into the branch (update-branch, merge commit), confirm the PR diff is unchanged, wait for CI, squash-merge pinned to the new head.

Merged: 158f1ae (squash, pinned 2fcebdf = a42b511 + main merge, PR diff unchanged, Linux CI green).
