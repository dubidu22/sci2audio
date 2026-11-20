# Light audit: layout batch B13 (#156, #238, #354, #322), 19 Nov 2026

Auditor: the B13 review thread. Merged diff read: bf25945 (#620), fac140c (#645), fb48c1c (#647), against the plan `plans/layout-batch-b13-plan.md` (D-793). Scope: inconsistencies across the PRs and contract touches only.

## Result: 0 blocking, 0 new issues

| # | Check | Finding |
|---|---|---|
| A1 | Files and lanes | All src changes are in `layout/` (furniture, captions, build, order, settings, graphics, paragraphs). Tests changed: layout tests, plus two textprep corpus test files in #647, which are renumbering only (planned D-756 cross-lane touch, after B9 per LANE-02). Docs: CHANGELOG (3 lines), `docs/baseline.md` (1 row, #645). No core, contract, KB, CI or packaging file |
| A2 | Shared files across the three PRs | `order.py`: #620 adds `uncounted` to `reading_order`, and #645 replaces `figures`' body with `touching`. These are separate functions, merged without a conflict. `build.py`: #620 changes `columns_per_page` and `_Layout.read`, and #647 passes `bars` to `rows_of`, also separate. `settings.py`: #620 adds comments only; #647 adds `fraction_inside` (0.1 em), the batch's only new threshold, which is in `LayoutSettings`, as the AC asks. No setting is listed anywhere else (grep) |
| A3 | Callers | `rows_of` has one caller (build.py:204, passes `bars`); `figures` has one (build.py:169); `touching` is called only by `figures`; `columns_per_page` is used only by the corpus truth test, and since #620 it builds the whole document, so it now runs #645's and #647's code too |
| A4 | Goldens | Only #647 moves goldens: liu layout at two sites (p2, p4; 133 → 129 blocks) and the liu rows of the citations golden (pure renumbering, checked as a multiset). #620 empties `NOT_YET_COLUMNS` (AC of #238). #645 moves none |
| A5 | Plan narrowings, each named in its PR | #156: the coverage and short-document rules apply to the top band, while the bottom keeps the shape rule plus the label guard. #238: captioned figures only. #322: the page-break remainder is filed as #648 (v2). #354: limits unchanged, #355 is on v2 (D-795) |
| A6 | CHANGELOG | Three "Fixed" lines (#322, #354, #156), with #238 deliberately absent (no user-visible effect). Two CHANGELOG conflicts during the batch were resolved by keeping both lines; no line was lost |
| A7 | Defects found in review | One, in #645 round 1: the banded sweep's cost grew with a drawing's height, and one path from −1e9 to 1e9 pt ran out of memory. It was fixed by an exact segment-tree sweep before merge. Post-merge defects so far: 0 |
| A8 | Issues filed by the batch's reviews | #649 (test for a loose mark joining a running head in `graphics._place`, v1.2.x); #648 came from the author (v2) |

## Notes for the ledger (thread length)

The batch had 3 PRs with 2 rounds each, one review thread and no compression. Round 1 of #620 and #647 found only test gaps, which mutation found and a reading did not. Round 1 of #645 found the only code defect, from a probe with extreme coordinates. That suggests a review thread of this length suits a layout batch of 3 PRs, and that any sweep or bucketing code should get the extreme-coordinate probe as a standard check.
