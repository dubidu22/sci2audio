# PR #194 review round 1: answer (head 9aa0f75)

All five should-fix items are fixed and N1 is answered with a comment. N2 is left as it is, as the review allows. Nothing is deferred.

- **S1, fixed.** New test `test_one_noteref_token_is_enough_for_a_mark_and_one_back_link_token_for_a_back_link`. It covers a noteref tagged only `epub:noteref` with a back-link tagged only `role:doc-backlink`, and then the reverse pair. Both read `["Sloped. End.", "Footnote 1. Hill."]`. This kills mutants #0 and #3.
- **S2, fixed.** New test `test_a_note_that_seems_to_start_with_footnote_because_of_a_removed_mark`. The note `"Footnote1 rest."`, whose "1" is another note's mark, reads "Footnote rest." with no introduction. The strict run passes. This kills mutant #27.
- **S3, fixed.** Two new tests, which kill mutants #24, #28 and #38:
  - `test_a_printed_label_that_is_another_notes_mark_is_not_the_notes_mark`: the labelled note "2 See note two." reads "Footnote. See note two.".
  - `test_a_back_link_that_ends_where_the_printed_label_starts_leaves_the_label`: "↩︎1. Text" reads "Footnote 1. Text".
- **S4, fixed.** `regression._case` now refuses a bool `page`, and `test_a_bad_run_names_the_case` gains a `page = true` row.
- **S5, fixed.** New test `test_marks_with_one_link_on_two_lines_are_two_edits`. "Word 1\n1 word" gives the edits Span(0,5,6) and Span(0,7,8) and reads "Word word". This kills mutant #10.
- **N1, kept as a guard.** `_backlinks` now has a comment saying that each edit ends on a letter, so `taken` only guards the no-overlap rule.
- **N2, no change.** "( 1 )" still gives "Footnote.". No corpus file has such a mark.

I re-ran the seven named mutants (#0, #3, #10, #24, #27, #28, #38) against the four footnote and regression test files, and all are killed now. Ruff, lint-imports and deptry are clean. The fast suite passes with the CI profile: 3164 passed, 1 skipped.

**Not from this PR.** With the dev profile (and its stored Hypothesis example), `tests/unit/test_layout_headings.py::test_sections_start_at_headings_and_carry_their_text` fails on main too (checked at 14513b2). The falsifying example is a positionless page whose only line is "0", with outline entry "A" (level 1, page 1, item ""). D-408 starts a section at a block that is not a heading, but the property expects sections only at headings. CI's deterministic `ci` profile passes. It belongs to the layout lane (#192 / D-408), so I have told the coordinator.
