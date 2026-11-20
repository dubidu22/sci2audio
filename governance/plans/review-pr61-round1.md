# Review of sci2audio PR #61 (head bb8bc2f), round 1

Formulas as placeholders (layout step 3, PR D2, D-93, D-94). Verdict: **changes requested**, three must-fixes.

## Verified

- 529 tests pass; ruff, ruff format, lint-imports and deptry are clean; CI is green on bb8bc2f.
- The nightly Hypothesis profile on `tests/unit/test_layout*.py` passes: 289 tests in 97 s.
- **Counts.** 45 of 45 numbered formulas, with labels per page as printed. 6 of 6 unnumbered formulas. FIGURE 17, TABLE 10. Every other block kind's count per paper is unchanged. The chi, hardt, seaborn and pymedphys documents are identical to main.
- **Items and reading order.** I traced every item independently: each is in exactly one block, on main and on this branch. Outside formulas, the order of text lines is identical to main except for the 10 lines nowak p5-l106 to l115 (#34), as the body says.
- **D-94 (a), `math_share` 0.4.** I swept it from 0.0 to 0.6 over the corpus. No false formula appears anywhere at any value of 0.2 or more. At 0.5, nowak's restated Eq. (9) is lost (5 of 6). So 0.4 has a safe margin.
- **D-94 (b), in-place rule.** `Paragraphs._hold` ends the open paragraph when a held formula is on the same page as its last row, and lets it wait when the formula is on a later page. I removed the rule and `test_a_formula_across_both_columns_mid_page_ends_the_paragraph_before_it` failed, so the test covers it. nowak p9 formula (21) is now whole.
- **Contracts.** No core or contract change, and the truth files are unchanged. The diff touches only `layout/` and tests.

## Must-fix

1. **Text is trimmed: two liu lines lose their last letter** (Colin's rule: text exactly as printed).
   - liu p2-l69 "…density operator ˆρ," comes out as "…operator ˆρ".
   - liu p2-l84 "…part ⟨ρˆ⟩ satisfies" comes out as "…satisfie".
   - Both are in the golden file (lines 1055 and 1057 of `test_layout_corpus.ambr`).
   - Cause: `split.part_ends` assumes the next part that starts later is preceded by a separator, so it ends the part at `after - 1`. On main, both lines are followed by a zero-width graphic part (p2-d124 and p2-d126) standing at the very end of the text. When `kept` keeps the line without the formula after it, it cuts off one real character.
   - Fix: take a part's end from the next part that holds text (a graphic holds none). Then:
     - add a unit test for `kept` with a trailing graphic;
     - add a corpus invariant test: for every block, every line part's text equals `block.text[start : start + len(line.text)]`. This would have caught the bug. The body's "substring of the old paragraph" check cannot.
   - Then update the golden file.

2. **Formula (14) on nowak p4 is incomplete.** Its second row, "P n = I + P P∗ = (I − P) −1" (p4-l25), and that row's "n=0" (p4-l24) stay as two PARAGRAPH blocks after FORMULA "14", so they would be read aloud as fragments. The plan names (14) as its two-row case.
   - Cause: p4-l25 ends 7.3 pt from the column's right edge, which is within `fill_slack` (0.7 em × 10.9 = 7.6 pt). It counts as running text, so the chain stops before it, and "n=0" becomes a chain of its own that is too small to be a formula.
   - Fix the rule, not the setting. For example: a line on the row of a display line that starts at least `formula_indent` in is no running text. Add a corpus assertion that FORMULA "14" holds "(I − P)" and that no fragment of it is left as a paragraph.

3. **arsiwalla Eq. (2) is a diagram, and only its middle row became the formula.** FORMULA "2" is "RObj RRel (2)". Six one-word paragraphs are left around it: "AP", "ObjP" (with arrow drawings p13-d3 and d4), "RelP", "ObjM" (with p13-d7 and d8), "RelM" and "AM".
   - The four vertical arrows (d1, d2, d5, d6) reached the formula only through `_flush`'s D-90 rule, because on main they followed p13-l18 in the same block. Detection did not find them: they run from y 350 to 469, outside the formula's box of y 388 to 428.
   - Fix: let a graphic that overlaps a group's box grow the group, and take the display lines inside the grown box; repeat until stable. The arrows then bring in the diagram's top and bottom rows.
   - Correct body point 5 ("the 4 arrows of Eq. (2)"), add a corpus assertion for the whole diagram, and explain the golden change.

## Should-fix (fix, or say why not; anything deferred needs an issue)

4. `MAX_SKIPPED_LINES = 100  # nowak p4 needs 81 until #34` is stale now that #34 is closed. The verbatim test passes with 2. Tighten it (for example to 10) and fix the comment.
5. Two new `paragraphs.py` rules go beyond the plan:
   - a caption right after a held float starts afresh. This now also applies after a held FIGURE, because `self.figure` covers both kinds;
   - the rows of the caption's float don't release the set-aside paragraph.

   Only the nowak corpus tests cover them: I removed each rule in turn, and only the nowak golden, verbatim, caption and formula tests failed. Add a unit test on a made-up page for each rule, and say in the body that the first rule also applies after figures, with no corpus change.
6. **Complexity.**
   - `_chains` finds a line's row-mates with `any(same_row(...) for other in shown)`, which is lines × display lines per column.
   - `_graphics` scans every graphic on the page once per group, which hurts with marker clouds (#60).
   - Corpus time only goes from 0.37 s to 0.43 s, so this is not urgent: group by rows once and index the graphics once per page, or file an issue.

## Notes (no action needed)

- `_flush` adds a graphics-only remainder to `out[-1]`, which can be the new FORMULA placeholder. That is D-90 as specified, and it is how the arrows in point 3 arrived.
- `test_core_properties.py::test_overlapping_edits_are_refused` failed once during my mutation runs and passed three times on a rerun. This is the known flake #47 and is unrelated.

Reply listing exactly what you fixed and why, with the new head sha. Do not merge.
