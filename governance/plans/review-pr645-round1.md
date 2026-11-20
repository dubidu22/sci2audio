# Review of PR #645, round 1 (#354; layout B13 PR 3, not critical)

Reviewer: B13 review thread, 19 Nov 2026. Pinned head **e743448** (branch with main bf25945 merged in). Verdict: **changes requested: one code defect (M1)**. One fix commit, on this list only.

## What was checked

| Check | Result |
|---|---|
| Plan claim "same groups" | **confirmed** for ordinary coordinates: every block (kind, text, parts, `describes`) and the furniture are identical, main bf25945 vs PR, on all 8 corpus papers (`plans/b13-review/dump.py`). A differential fuzz of `order.figures`, main vs PR, on 6,000 random pages (1–120 boxes, reach 0/0.5/2/3.7/10, coordinates on grids of 0.5/1/2/16 pt or free, boxes up to 1,000 pt tall) found 0 differences in the groups and 0 in the order of figures and their graphics (`plans/b13-review/fuzz645.py`) |
| `graphics._place` | equivalent by reading: joined parts get the same offset (`len(text)` does not change when graphics join) and stay after any parts carried in from `pending`; a furniture block gets its own (empty) `joined` entry |
| Plan claim "100,000 drawings in seconds" | **confirmed**: the `benchmark` test lays out one page of 100,000 drawings in about 2 s here; the fast growth tests pass (6.7 s for the file) |
| CI on e743448 | `tests (ubuntu-latest)`, lint and layers: green (browser shards still running when this was written) |

## Fix list (one commit)

**M1. Layout time and memory now grow with a drawing's height in points, not with the number of drawings.** `touching` files every open box in each band of `8 × reach` (16 pt at the default `figure_reach` 2 pt) that its height crosses, and looks up each new box in every band its height plus reach crosses (`band_range`). The work for one box is therefore proportional to its height divided by 16 pt. Main's code has no such dependence. Extraction does not clip drawing boxes to the page: `pdf._bounds` keeps any finite corners, and `_Frame.shows` keeps every box that overlaps the page. So a single path in a PDF drawn from y = −1e9 to 1e9 (PDFium gives float32 bounds up to about 3.4e38) reaches layout as is.

Measured with `plans/b13-review/huge.py`: `touching` on one tall drawing plus 670 ordinary ones takes 0.03 s at ±1e5 pt, 2.4 s at ±1e7 pt, and at ±1e9 pt it was **killed for lack of memory**, since the band dictionary needs about 1.25e8 entries. At ±1e30 pt it would never finish. One crafted or odd file then hangs or crashes the app, where main lays it out at once.

Fix: make the number of bands a box touches independent of its height in points, while keeping the groups exact. One way is to clamp every box's interval, both when it is filed and when it is looked up, to the band range that ordinary boxes can reach, for example the y-extent of the page or of all boxes' finite edges, widened by `reach`. A box taller than everything else then lives in a bounded number of bands. The choice is yours, but the groups must stay exactly those of all pairs. Tests:
- (a) Widen the Hypothesis strategy of `test_the_groups_are_those_of_comparing_every_pair`, or add a second one, so that it draws some boxes with edges up to ±3.4e38, and keep it equal to `all_pairs`.
- (b) Add a fast test: one page of a few thousand ordinary drawings plus one drawing from −1e30 to 1e30, and another plus 1,000 such drawings. Each goes through `build_document` (or `touching`) within the time `assert_linear` allows for the same page without the tall ones, or a fixed small bound that you state. It must also give the same groups as `all_pairs`.

Say in the PR body what bounds the band range, and why the groups stay exact.

## Final round

Because M1 is a code defect, round 2 is the final round. It needs: `ci:full` on the fix commit (three systems), a nightly property run on the branch, and a mutation run on `sci2audio.layout.order.x_touching*` and `sci2audio.layout.order.x_figures*` (and `sci2audio.layout.graphics.x__place*`) with `tests/unit/test_layout_figure_speed.py tests/unit/test_layout.py tests/unit/test_layout_graphics.py`, which I dispatch.
