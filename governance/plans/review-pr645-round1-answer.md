# PR #645, round 1: what the fix commit does

Fix commit **bf8dd65**. `ci:full` set for the final round.

## M1: fixed by replacing the bands

Clamping the band range would bound one huge drawing, but not two other cases that would still break it:
- Two spots 3 pt apart down the page (`Box(100,100,110,110)` and `Box(100,113,110,115)`, alternating). Each new box looked box by box through the other spot's boxes in their shared band and found none touching, so the work was quadratic: 41× for 8× the drawings. That family is now in the growth test, and it fails on e743448.
- Far-apart tiny drawings would widen any clamp window computed from the boxes.

So `touching` is now a sweep over a segment tree of the page's distinct tops (`y0`):
- Each drawing's span is `[y0, y1 + reach]`. Two open drawings touch exactly when their spans meet, and the test uses the reference's own float sums (`a.y0 <= b.y1 + reach and b.y0 <= a.y1 + reach`). Across, a drawing stays open while `x1 + reach >= x0` of the new one, which is again the reference's sum. So the groups equal all pairs to the last bit, also at ±3.4e38 and at half-float-step reaches. The old `y0 - reach` form could differ there.
- Spans that meet hold the lower of their two tops (`max(y0)`), and that top is a leaf. So the new drawing joins the open groups whose top lies in its span (the canonical cover nodes, table `starts`) and those whose span holds its top (its leaf-to-root path, table `spans`).
- **What bounds the work:** about 2 log₂ n nodes per drawing, read and written, whatever its height in points. A node keeps one entry per group, holding the farthest right its drawings there reach. Entries no longer reaching the sweep are dropped when read, so no deletion pass is needed.

Measured on a 4-core container:

| Case | Result |
|---|---|
| ±1e30, 1 and 1,000 tall drawings among 1,500 to 2,500 ordinary ones | 0.02 s, same groups as all pairs |
| Families at 100,000 drawings, grouping alone | 0.2 to 1.0 s |
| Two spots at 8,000 drawings | 0.03 s (bands: 1.4 s) |
| 100,000 random overlapping boxes up to 30 pt | 4.9 s (bands: 0.9 s): the price of the log factor |
| Peak memory for those random boxes | 85 MB (bands: 10 MB) |
| Benchmark page of 100,000 drawings | 2.7 s |
| The 5 × 100,000 file | layout 18.5 s |

## Tests

- (a) `test_the_groups_are_those_of_comparing_every_pair_at_any_size`: Hypothesis, coordinates and sizes up to ±3.4e38 mixed with the grid ones. `@example`s: a drawing from −1e30 to 1e30, and `reach` half a float step at 2⁵⁵. The first property test also gains an `@example` of a group filed twice at one height, the second time reaching less far. It kills the mutant that keeps the last reach instead of the farthest.
- (b) `test_drawings_from_far_above_to_far_below_the_page_cost_no_more_than_small_ones`: 1 and 1,000 drawings from −1e30 to 1e30 among ordinary ones, 2,500 in all. They give the same groups as `all_pairs`, within 4× the time of 2,500 ordinary drawings (`assert_near`). On e743448 these tests do not finish.
- The growth test gains the "two spots" family.

Hand mutants on the new `touching` (`tests/unit/test_layout_figure_speed.py`): 8 of 8 killed. They cover open `>=` → `>`, `bisect_right` → `bisect_left`, no `reach` down the page, no span lookup, no top lookup, last reach instead of the farthest, no `reach` across, and a path that stops below the root. Two equivalents found on the way were removed from the code: a re-filed group (a new box is always its own root when filed) and `root()` on keys that are already roots.

Fast suite on bf8dd65: 8039 passed. ruff, lint-imports and deptry are clean. The PR body now says what bounds the work and why the groups stay exact.
