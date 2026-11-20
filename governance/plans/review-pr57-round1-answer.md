# PR #57, review round 1: answer

New head **f4667d4**: one commit on top of 63ef727, no force-push. The golden file is unchanged.

1. **The walk was order-dependent.** Fixed.
   - An item the walk passes because it stands beside what was taken is kept in a heap: left-side items by x1, right-side items by x0. It is taken as soon as the float grows across it.
   - A taken graphic brings its whole drawn group (the group read as one figure before this step), as a float met on the way already does. This is needed because the cloud's markers stand 0.5 pt apart, so the range alone never grows across them.
   - Both repros are now tests, and both fail on 63ef727:
     - `test_a_short_caption_takes_the_text_its_figure_grows_to`: the figure text is "0 1 2 3 4 5 6 7 8 9", and no tick label is left in a paragraph.
     - `test_a_caption_takes_every_marker_of_a_wide_cloud`: all 2,000 markers.
   - Row-mates now come from a list sorted by y, searched with bisect, instead of a scan of every item. Each walk is n log n.
   - Timing: a captioned cloud of 40,000 markers takes about 0.3 s in the graphics step. The old code took about 39 s and split the cloud. The other 4 s for that page are spent in `order.figures` on main, which is quadratic for such clouds. That is filed as #60, because this PR does not touch it.
2. **The footnote count in the PR body was wrong.** Fixed.
   - 27 footnote rules are each the first part of their footnote (27 footnotes).
   - A new row covers the 2 underbrace drawings (nowak p1-d7 and p1-d8), which join the end of footnote 2.
   - I checked both counts with a script over the corpus.
   - Filed #58: a loose graphic joins a block it does not stand in.
3. **`_ends` was quadratic.** Fixed: it now makes one pass from the end, carrying the next later start along.
4. **Filed #59** (dots count as lines). I tried the cheap fix, requiring a line to be longer than `line_width`, and reverted it:
   - it moved two drawings on arsiwalla p13 into an empty FIGURE, which breaks `test_no_figure_is_only_lines`;
   - it does not cover dots that stand apart, because the upstream grouping makes each such dot a mark.
5. **A pending mark passed the running heads.** Fixed in `_place`. Graphics waiting to join the next block now become a block of their own in place when the next block is furniture, so they never move past it. Your minimal case (pictures i0, i1 and i2) is now an `@example`, and it fails on 63ef727.

**Optional: done.** `_side` now returns the walk it chose, and `_read_float` uses that walk. It ranks the sides by the smallest gap of any taken item, because now that passed-by items are taken later, `walk[0]` is not always the nearest item.

**Checks on f4667d4:**
- ruff, ruff format, lint-imports and deptry are clean.
- 497 fast tests and 17 snapshots pass.
- Under `HYPOTHESIS_PROFILE=nightly`, test_layout, test_layout_graphics, test_layout_captions, test_layout_footnotes and test_layout_paragraphs pass (109 tests).

**PR body updated:** 18 unit tests, the order rule, the no-block-before rule, and #58, #59 and #60 listed as deferred, each with its reason.
