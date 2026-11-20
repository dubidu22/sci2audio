# Layout batch B-L2: #181, #54, #59, #55, #56 (plan)

Thread layout-b-l1 (implementation, Opus 5.5 high), its third and last PR (THR-02), 20 Nov 2026. Base: main 20f9575. The numbers below come from read-only probes on the 8 corpus papers (scratch scripts that wrap layout functions; no product code).

**Critical: no, as planned.** Each rule below is shaped so that the corpus output stays byte-identical: the probes find no corpus block that changes, and no golden file is expected to change. If the PR's run changes any golden line after all, the PR becomes `risk:high` and comes back to the coordinator before review (CRIT-01). No contract, core or CI change.

## 1. One PR, not two

#181 changes where a loose rule joins (`graphics._hosts` and `_assemble`), and #59, #55 and #56 also change `graphics.py` (`_loose`, `_Walk._row`). #54 changes `build.py` and `headings.py`, and #56 needs `build.py` to pass the column edges into `find_graphics`. The two halves therefore touch the same two files and could not merge on their own without a rebuild of each other. One PR (LANE-01, D-75): `layout: ruled and numbered headings are found, and uncaptioned plots, their labels and rule-less tables keep to themselves (#181) (#54) (#59) (#55) (#56)`.

## 2. Per issue: measured, rule, failing test first

### #181, a narrow rule under an indented line joins the block before it

- **Measured.** The issue's AC as written ("a thin rule under a line joins that line's block, whatever its width") would move many corpus rules:
  - the footnote rules under the last body line (Nowak p4, p10), which #51 puts into the footnote below;
  - Maass's running-head rules (furniture);
  - 19 of Liu's fraction bars.

  The bug is narrower: the rule is *read before* the line it stands under, so D-90 gives it to the block read before. Of the rules read before the line they stand under, the corpus has 7 (all Liu). 6 already end in that line's block through `find_formulas`. The 7th, Liu p4-d1 (x 121–193 under a line x 151–299), covers less than half of that line.
- **Rule.** A group of lines only (a rule) that no line hosts (D-329) and that no footnote below takes (#51) joins a text line's block, read just after that line, when all of these hold:
  - its top overlaps the foot of the line's box or stands at most `heading_rule_gap` below it;
  - it is read before that line;
  - it lies under at least half of that line's width.

  Otherwise D-90 applies, as today.
- **Test first** (`test_layout_headings.py`): the issue's page (`numbered().ruled("Ethics Review Form", indent=15.0, x1=165.0).body()`) gives a level-1 heading whose block holds the rule. The same page with the rule from x 70 to 326 and to 526 is unchanged. A rule under a quarter of an indented line still joins the block before (pins the half-width bound with Liu p4's shape).

### #54, a numbered heading set like a list marker is read as a list item

- **Measured.** Prototype: `find_headings` also takes as candidates the LIST_ITEM blocks whose label is "1." or "1)" style and whose text is one line. They are judged by the existing heading rules, and those not taken stay LIST_ITEM as they were. Corpus: every block's kind, label and text and the section tree are identical on all 8 papers (headings 83, list items 69, before and after).
- **Rule.** As prototyped, in `headings.find_headings` (its candidate filter). The rules that decide a heading are unchanged, so a numbered list item of body text is never a heading. A LIST_ITEM taken as a heading becomes HEADING with the heading label. Lists run before headings, as today (the C2 order), so block indices stay stable.
- **Test first** (`test_layout_headings.py`): "1. Introduction" and "2. Related work", heading-sized (and in a second case bold), with nothing between them, come out as two HEADING blocks labelled "1" and "2". A real numbered list in body text next to them stays LIST_ITEM.

### #59, dots and small markers count as lines, so an uncaptioned scatter plot is not a figure

- **Measured.**
  - Loose groups (no caption) that include a dot (both sides at most `line_width`) and are taller than a mark: only arsiwalla p13, twice (one dot and one 118 pt vertical line each, read in a FORMULA). That is why requiring a line to be long moved them into an empty FIGURE in #57.
  - Loose dot-only groups clustered by `float_gap`, with 3 or more dots and taller than a mark: the JOSS first-page logos, built of small paths (waskom 9 paths, 19.6 × 31.9 pt; biggs 4 paths, 13.1 × 22.0 and 14.9 × 22.0; 9 paths, 19.2 × 31.9), which are read as marks today. A threshold of "bigger than a mark both ways" would clear them by 0.4 pt, too thin.
- **Rule.** `_is_line` is unchanged, so rules, frames, arrows, footnote rules and icons behave as today. New in `_loose`:
  - loose dot-only groups within `float_gap` of each other are judged together;
  - a cluster of at least 3 dots whose box is at least `plot_size` (new setting, 4 em) both across and down is a scatter plot: one FIGURE, its groups merged;
  - anything smaller stays as it is (marks join, D-90).
  The JOSS logos (at most 3.2 em) stay marks, and arsiwalla's groups (one dot each) stay as they are.
- **Test first** (`test_layout_graphics.py`): an uncaptioned scatter plot of 30 small markers in a 15 × 10 em box gives one FIGURE, both with the markers touching each other's groups and with them spread up to `float_gap` apart. A 3 × 3 em logo of 9 small paths still joins the block before. Plus a Hypothesis property: markers at random places in a box of random size give one FIGURE exactly when the box is at least `plot_size` both ways and there are at least 3; never fails, every item in one block.

### #55, text inside a figure no caption names stays in paragraphs

- **Measured.** The corpus has no uncaptioned FIGURE at all, and with #59's rule it still has none. So the rule can't change a corpus block.
- **Rule.** An uncaptioned FIGURE (from `_loose`) takes the text lines that lie wholly inside its box and are set smaller than the body text (`size_change`), as a captioned float takes its lines (`_without`, read row by row). Exception: when a single drawing holds all those lines (a background or a framed box), the text stays where it is. Body-size running text inside a frame or a background therefore stays in paragraphs (`test_a_page_background_or_a_frame_does_not_cut_the_columns` unchanged).
- **Test first** (`test_layout_graphics.py`): an uncaptioned chart (a curve, two axes, 6 tick labels and an axis label in 8 pt inside its box) has its labels in its FIGURE block, read row by row. A background rectangle around a paragraph of 10 pt text leaves the paragraph. A background around 8 pt text (an aside) also leaves it: one drawing holds all of it.

### #56, a rule-less table on a two-column page takes a small line from the other column

- **Measured.** The corpus's 47 small row-mates that walks take (all Liu, the tick labels of figures) stand in the same column as the line that brings them, all 47. None crosses the gutter.
- **Rule.** `_Walk._row` takes a small row-mate only if it stands in the column of the line that brings it (the column edges of the printed rows, which `build` passes into `find_graphics`; a line without edges is judged as today). The exception is when what the walk spans already reaches into the row-mate's column: a table set across both columns keeps its cells.
- **Test first** (`test_layout_graphics.py`): a two-column page with a rule-less table of 8 pt cells in the left column and an 8 pt aside on one of its rows in the right column. The table's block does not take the aside. The same table across both columns under a full-width caption still takes all its cells. The existing rule-less table tests pass unchanged.

## 3. Golden files

None expected to change (`test_layout_corpus.ambr`, `test_extraction_corpus.ambr`, the textprep and app goldens). The corpus truth tests are unchanged. If the PR run shows a changed golden line, see "Critical" above.

## 4. Properties that must still hold

- Layout never fails on any `Content`, and every item is in exactly one block (`test_layout_never_fails_and_keeps_every_line`, `test_layout.py` properties).
- Every line's text stands at its part's offset (`test_each_line_stands_in_its_block_as_found`).
- New: the #59 property above.
- Nightly Hypothesis profile on `test_layout*.py` before review.

## 5. Open choices (recommendations given)

- **Q1, #181 narrower than its AC.** Recommended: the three conditions above (read before the line, under at least half of it, footnote and inline hosts first). The AC's "whatever its width" would move footnote rules, running-head rules and fraction bars in the corpus.
- **Q2, `plot_size` = 4 em**, a new `LayoutSettings` field. The JOSS logos reach 3.2 em, and a plot smaller than 4 em both ways is rare. Alternative: a count threshold. Rejected: the logos have 9 paths, as many as a small plot.
- **Q3, #55 takes only text smaller than the body**, and none when one drawing holds it all. A chart labelled in body-size type keeps its labels in paragraphs, as today. That is the safe side of D-57: framed running text never disappears into a placeholder.
- **Q4, one PR** (section 1).

## 6. Size

About 150 lines in `layout/graphics.py`, `headings.py`, `build.py` and `settings.py`; about 300 lines of tests in `test_layout_headings.py` and `test_layout_graphics.py`. One PR, labels `lane:layout`, `risk:low` (unless a golden changes). The issues name no feature ID beyond the layout lane's.

## 7. Handoff (THR-07)

- Goal: B-L2, the five issues in one PR, this thread's last.
- Done: all five measured on the corpus; #54 prototyped block-identical; the plan.
- Next: on approval, the failing tests per issue, then the rules, fast checks (espeak deselected), PR, ledger entry.
