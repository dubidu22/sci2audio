# Review of sci2audio PR #61 (head 65d0ae1), round 3: approved

- **Must-fix 7, fixed.** The round 2 repro now gives `[("1", "a = b + c (1)")]`. A variant with the quotation above the formula inside the frame, and one with a wider quotation, also stay plain text.
- **Unchanged since 749ab0f.** The corpus output is identical (pickled blocks compared). The snapshot file has no diff.
- **Invariants.**
  - Every line's text stands unchanged at its offset.
  - Every item is in exactly one block.
  - Outside formulas, the order of text lines matches main except for the 10 lines of #34.
- **Counts.** 45 of 45 numbered and 6 of 6 unnumbered formulas, 28 of 28 verbatim sentences, FIGURE 17, TABLE 10.
- **Tests.** 548 fast tests pass; ruff, ruff format, lint-imports and deptry are clean. The nightly Hypothesis run passes 308 of 308 on `tests/unit/test_layout*.py`, and CI is green on 65d0ae1. The branch is up to date with main (84dc299).
- **Note, no action.** The maths-only guard applies to chains that join a group, not to the chain a group starts from. A plain-text chain could still start a group if a connector graphic linked it to a formula. That is unlikely: a display line cannot reach a frame's side rule, because a line ending within `fill_slack` of the edge is not display.
