# PR #180, answer to review round 1

Head after the fixes: 510e30b (on top of your merge bc6909b; no force-push).

## Fixed

- **M1 (fixed).** `_Headings._ruled` now measures the rule against the block's **last row**, not its last line part: the union of the block's text lines whose vertical middle lies inside the last line's box. All four conditions (vertical place, start, end, 1 em reach) use that row. Why: a table header split into cells is one row of words, and D-385 asks the rule to be longer than its words. Docstrings of the module and of `_ruled` say so. Two new unit tests in `tests/unit/test_layout_headings.py`:
  - `test_a_header_row_split_into_cells_over_a_table_rule_is_not_a_heading`: your reproduction (cells "Model", "Accuracy", "F1", bold, a booktabs rule overhanging the row by 6 pt, no caption), for a full-width table (x 70 to 526) and a narrower one (x 170 to 370). It failed before the fix (block became a HEADING) and passes now.
  - `test_a_rule_under_the_last_of_two_lines_is_measured_against_that_line_only`: a two-line heading whose short last line has a rule 1 em longer than it but shorter than the first line is still a heading, so the row is the last line's height only.
  Corpus goldens: unchanged (the layout and app snapshot tests pass without `--snapshot-update`). Mutants re-run: all earlier 11 still fail a test; new ones "last line instead of last row", "every line of the block" and "row's lower bound dropped" fail a test. "Row's upper bound dropped" survives: no line read before the last one stands below it in a block's reading order, so that bound only documents "at the last line's height".
- **S1 (fixed).** Filed [#181](https://github.com/dubidu22/sci2audio/issues/181) "layout: a narrow rule under an indented line joins the block before it" (lane:layout, milestone v1.1), with the made-up reproduction (indent 15 pt, rule x 70 to 165 joins the paragraph above; to 326 it joins the line). Linked under Out of scope in the PR body.
- **S2 (fixed).** The PR body's Risk paragraph now names the residual case: an uncaptioned table whose whole header row is one short bold block over a rule overhanging that row by at least 1 em at one end, after the first numbered heading.

## Also changed in the PR body

The change list describes the last row, the test list names the two new tests (12 in all), the fast-suite count is 2799 passed, 1 skipped (after main merged in), and the mutation list adds the round 1 mutants.

## Checks

ruff check, ruff format --check, lint-imports, deptry: clean. Fast suite: 2799 passed, 1 skipped.
