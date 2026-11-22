# Layout B-L3: #679, a centred heading atop a short column is read in the next column (plan)

Thread layout-b-l3 (implementation, Opus 5.5 high), batch 004 slot B, 22 Nov 2026. Base: main 880b170. Numbers below come from a read-only probe (scratch script that swaps `order._column`; no product code).

**Critical: no.** No golden file, layer contract, core type or CI file changes. The probe finds every block (kind, label, text, parts) and every page's column count identical on all 8 corpus papers. If the PR's run moves a golden line after all, it becomes `risk:high` and goes back to the dispatcher before review (CRIT-01).

## 1. Cause (measured, not the issue's guess)

The issue guessed the two centred top lines become a running head. They do not: no line is furniture. The reading order is wrong:

- `c0r1..c0r6, c0r0, c1r0, ...`: column 0's heading is read after column 0, at the head of column 1, and `paragraphs` joins it to `c1r0`'s paragraph.
- `order.gutters` lets a strip be crossed by `gutter_crossings` (10 %) of the band's items, here 5 of 50. Column 0 holds only 7 lines. So the strip opens where coverage drops to 5, at x 105.3, the end of its two short last lines (`c0r3`, `c0r6`). The first gutter is (105.3, 227.3), not the white (211.3, 227.3).
- `order._column` puts an element right of a gutter when `x0 >= start`. `c0r0` starts at 105.3, inside the strip, so it goes to column 1.
- The tie at 105.3 is Hypothesis's luck; any line of a short column that starts right of its short lines' ends (a centred heading, an indented line) meets the same fate.

## 2. Rule

`order._column`: an element that does not cross a gutter (`_spans`) stands right of it when it reaches past the gutter's end (`x1 > end`). This is the split `gutters.splits` already checked before it accepted the gutter: its left column is the items with `x1 <= end`, its right one those with `x0 >= end`. The reading now uses the same partition the gutter was found with.

- Unchanged for every element that starts left of a strip (its `x1 <= end`) or right of it.
- Changed only for an element lying wholly inside a strip (`start <= x0` and `x1 <= end`): now left, before right. Corpus: 3 such elements (waskom tick labels "15", "0", "5" inside a figure); no block and no column count moves.
- The docstring of `_column` says why (the split `splits` checked).

Alternatives rejected:
- `x0 > start` (strict): fixes only the tie; a heading starting at 110 fails the same way.
- Trimming the strip to its white in `gutters`: moves the gutter edges that `sides` and `_Layout._edges` give to paragraphs on every column page, so far more corpus risk for the same fix.
- Narrowing the property's generator: the page is not ambiguous; it is a plain three-column page.

## 3. Tests (first, failing on main)

1. `tests/unit/test_layout.py::test_any_clean_column_page_reads_column_by_column`: the issue's page as an explicit `@example` (lines in the issue's order, expected texts, 3 columns).
2. `tests/unit/test_layout.py::test_a_centred_heading_atop_a_short_column_is_read_in_its_column`: a smaller hand-made page (a short left column whose heading starts right of its short lines' ends, a long right column): the heading is read first, as a block of its own, not in the right column's paragraph.

Both fail on main 880b170 (checked with the probe on the issue's page). Then the fast checks (with the three real-espeak tests deselected locally, #663), and the `nightly` Hypothesis profile on `tests/unit/test_layout.py` before review.

## Tests promised in the plan

- tests/unit/test_layout.py::test_any_clean_column_page_reads_column_by_column
- tests/unit/test_layout.py::test_a_centred_heading_atop_a_short_column_is_read_in_its_column

## 4. Size

About 5 lines in `src/sci2audio/layout/order.py`, about 70 lines of tests in `tests/unit/test_layout.py`. One PR, `lane:layout`, `risk:low`: `layout: a centred heading atop a short column is read in its own column (#679)`. Feature ID IN-01 (from the issue).
