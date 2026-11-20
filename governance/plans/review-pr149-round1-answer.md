# PR #149, answer to review round 1

New head: **4fa2072** (ef57ab5 holds the fixes, then main a0bb69f is merged in; no force-push).

## Fixed

- **M1 (fixed).** New test `test_a_continued_table_header_under_a_real_head_is_not_a_running_head`. A body-size head "Tests in Print" stands at y 40 on 6 of 6 pages. "Model Accuracy F1" stands at y 62 on 2 of them, with 1.2 em of white above and below. The head is a running head on all 6 pages and the header stays text. The mutant that pools across heights (`covered` without the height condition) now fails this test.
- **M2 (fixed).** New test `test_a_table_header_in_two_cells_on_two_pages_is_not_a_running_head`. "Model" and "Accuracy F1" are separate cells on one row, at the top of 2 of 6 pages, and both stay text. The mutant that counts lines instead of pages (`covered` as a list) now fails this test.
- **S1 (fixed in code).** `_body_heads` now keeps only lines from `small` to `head_size` times the body (`settings.small * size <= line_size(line) <= settings.head_size * size`). The comment says that a smaller line has its own rule and lends no pages to the pooled count. New test `test_a_smaller_head_does_not_lend_its_pages_to_a_body_size_line`: a small "Preprint" on 6 of 6 pages and a body-size "Model Accuracy F1" on the same row on 2 of them. "Preprint" is a running head on all 6 pages and the header stays text. This test failed before the fix.
- **N1 (fixed).** The module docstring's list of residual cases now names a head for a section printed on one page only, which is read aloud. It also names D-328 and #156 for lines set smaller than the body.
- **N2 (answered).** You are right: there are 185 lines. My listing file had 193 lines, but 7 of them were per-paper header lines and 1 was a uv warning. The PR body now says 185.
- **N3 (fixed).** `repeat_pages` now reads "an edge line on this many pages is a running head (body size: below)".

## F1

The coordinator decided it as **D-328**: smaller lines keep the shape rule in v1.0. I filed the follow-up as **Issue #156** (v1.1, lane:layout), with your two made-up cases. KB PR #44 has a new D-328 row above D-327, Colin informed 2026-11-13 13:45:04 UTC, with plain links. Its title now says D-322 to D-328. Main has not moved for the KB, so no merge was needed there.

## Checks on 4fa2072

- Fast suite: 2199 passed, 19 subtests. Run with `--snapshot-update`, 54 snapshots passed and nothing was rewritten.
- Nightly Hypothesis profile on `tests/unit/test_layout*.py`: 332 passed, 7 snapshots passed.
- ruff, ruff format, lint-imports (3 contracts kept) and deptry are clean.
- Mutants: the height mutant and the lines-not-pages mutant each make one of the new tests fail. The band guard in the pooled count is still the only mutant that survives, as the PR says.
