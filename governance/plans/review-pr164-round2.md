# Review of PR #164, round 2 (Issue #58)

Head reviewed: 8ad3609 (fix 1b39dac + merge of main 2079d12), 13 Nov 2026. Then brought up to
date with main 47c86fb (#144) by a merge commit through GitHub's update-branch (no force-push).

**Verdict: approved; merge once CI is green on the updated head.**

- M1 fixed: `find_graphics` builds the read index once per document and passes it to `_hosts`.
  liu repeated to 600 pages: `build_document` 17.2 s on main 47c86fb, 17.4 s on the PR (round 1:
  36.9 s). `blocks` is the same list as `state.blocks` (never reassigned), so the index is the
  one round 1 built per page.
- S1 fixed: `test_a_logo_on_every_page_inside_a_line_box_stays_a_running_head`; removing the
  "join" check in `_hosts` now fails 1 test.
- S2 fixed: `test_a_mark_in_two_lines_of_one_size_stands_in_the_one_read_first`; reversing the
  tie key now fails 1 test.
- N1 kept, N2 no change, as asked.
- Re-checked against main 47c86fb: exactly the same five graphics move (nowak p1-d7/p1-d8, liu
  p1-d97, biggs p1-d5/p1-d6), every block's kind, label and text unchanged, line order unchanged,
  text at offset holds; `sci2audio script --chapters all --ignore-settings` on the 7 papers: 21 of
  21 files byte-identical to main.
- Fast suite 2423 passed (19 subtests); nightly Hypothesis profile on the layout and
  core-properties tests 378 passed.
- Nit, no change asked: `find_graphics` reuses the name `read` (first a set of caption blocks,
  then the index).
