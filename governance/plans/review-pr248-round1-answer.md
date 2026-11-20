# PR #248, answer to review round 1

Fixes pushed as f43c550 (on 62eb832). Every finding of round 1 is fixed; nothing is deferred.

- **M1, fixed.** `_raised` now compares a run only with the runs beside it in the same `TextLine`.
  `_runs` is built on a new `_lines` helper, and `_marks` takes each run's line neighbours from it.
  The old list neighbours `number ± 1` could be a run of the next or previous line. As a second
  guard, the two boxes must still share a band of the line (`other.y0 < run.y1`).
  New test: `test_a_label_like_run_at_a_line_end_is_not_raised_by_the_next_lines_run[de, en]` uses
  two lines whose boxes overlap (100–111 and 110–121). Line 1 ends in a "4" in the text's size, and
  a note "4" is on the page. The "4" is kept. This test fails on 62eb832.
- **S1, fixed.** The rise is measured only against a neighbour that is not set small
  (`not _set_small(other, main)`), so a normal run beside a subscript no longer counts as raised.
  New test: `test_a_run_beside_a_subscript_is_not_raised[de, en]` ("die Werte" "4" then the
  subscript "i" at 7 pt, set lower). It fails on 62eb832.
- **S2, fixed.** `_CLOSING` gains U+2018 ‘, U+00AB « and U+00BB ». New German regression case
  `de-footnote-mark-after-guillemets-and-single-quote` covers »Top 1 Million«7, ‚klein‘8 and
  «gross»9: all three marks are left out and the three notes are introduced. It fails on 62eb832.

## Checks after the fixes

- English byte comparison: every corpus file was run through `run_script_job` on main and on f43c550,
  once on automatic and once with "en". With automatic, all 11 English scripts are identical; only
  the German paper and the German Markdown note differ, as before. With "en", all 11 English
  scripts are identical; only the German paper forced to English differs, as before.
- German paper: script hash unchanged from 62eb832 (62209cf37ca4), so 30/30 marks are still found
  and no golden changed.
- ruff, format, lint-imports, deptry clean. Fast suite (`HYPOTHESIS_PROFILE=ci`): 3798 passed,
  3 skipped.

#249 ("Formel 3.2" read "drei.zwei", v1.2) is noted; it is not part of this PR.
