# Review of sci2audio PR #61 (head 749ab0f), round 2

Verdict: **changes requested.** Round 1's findings 1 to 5 are fixed and verified, and 6 is deferred as #62. But the new `_grown` step adds one must-fix.

## Round 1 fixes, verified

1. **Trimmed text.** Over the whole corpus, every line part's text now stands unchanged at its offset in every block: 0 mismatches, against 2 at bb8bc2f. `part_ends` skips graphic parts, and the corpus invariant test and `test_layout_split.py` are in place.
2. **Formula (14).** It now holds p4-l16 to l25, and no fragment of it is left as a paragraph.
3. **arsiwalla Eq. (2).** It is the whole diagram, with all 8 arrows. My leftover scan (PARAGRAPH blocks of up to 3 lines that are at least half math) now lists only inline maths and list-item limits. Those are out of scope.
4. `MAX_SKIPPED_LINES` is now 10. Done.
5. The unit tests for the `paragraphs.py` rules are added, and the PR body is updated. Done.
6. #62 is open. Accepted as deferred.

**Checks**
- 547 fast tests pass; ruff, ruff format, lint-imports and deptry are clean.
- 45 of 45 numbered and 6 of 6 unnumbered formulas; FIGURE 17, TABLE 10.
- Every item is in exactly one block.
- Outside formulas, the order of text lines matches main except for the 10 lines of #34. chi, hardt, seaborn and pymedphys are unchanged.

## Must-fix

7. **`_grown` lets a frame pull plain text into a formula, where it is no longer read aloud (D-55).**
   - The repro uses the helpers of `tests/unit/test_layout_formulas.py`:
     - `paragraph(100, 3)`;
     - `math("a = b + c", 250, 160, 330)` with `number("(1)", 160)`;
     - three full lines of running text at y 180, 194 and 208 from `LEFT`;
     - a centred quotation, `line("To be, or not to be,", 220, 230, 330)` and `line("that is the question.", 225, 244, 325)`;
     - running text at y 262, 276 and 290;
     - `paragraph(340, 3)`;
     - a framed box of four thin rules around y 150 to 310 (top, bottom, left and right, just outside `LEFT` and `RIGHT`).
   - Without the frame, the result is `[("1", "a = b + c (1)")]`, and on bb8bc2f also with the frame.
   - On 749ab0f with the frame, it is `[("1", "a = b + c (1)\nTo be, or not to be,\nthat is the question.")]`.
   - Cause: the top rule reaches the formula's chain and grows the area to the column's width. The side rules then reach the grown area and grow it to the whole box. The quotation's chain is inside the box, so it joins, and `_split` hands its rows to the nearest number. On its own, the quotation's chain is rejected by `_unnumbered`. Joined this way, it skips that test.
   - Framed boxes (definitions, theorems, prompts) are common in ML papers, so this is a likely failure outside the corpus, and the worse kind (the plan, choice 5: a false formula silences text).
   - Fix suggestion: a chain joined only through growth must itself be maths (`math_letters` ≥ `math_share`, or set smaller than body). Also consider ignoring graphics as wide as the column, which are rules and frames rather than connectors. arsiwalla's joined rows are all CMMI, so Eq. (2) should still be whole. Add the repro above as a test, and confirm that the corpus golden file is unchanged from 749ab0f.

## Notes

- One fast-suite run failed a single test while the nightly run was going at the same time. The rerun passed 547 of 547. This is most likely the known flake #47.

Reply with exactly what you fixed and why, and the new head sha. Do not merge.
