# Review PR #204, round 2

Reviewed head 92e5408. It is round 1's head afe9eb9 plus main 486e18b (PR #201) merged in as bbd2fcf, plus one test commit.

## Round 1 items

- **S1, fixed.** `test_a_picture_too_tall_for_a_mark_still_ends_the_row` uses a 30 pt line with a 26 pt picture between the pieces and asserts "A Big\nTitle". I re-ran the mutant that drops `inline_mark` from the deferral in `rows_of`: it is now killed by this test.
- **S2, fixed.** `test_a_mark_in_a_pages_last_printed_line_stands_just_after_it` covers a bar in the page's last printed line. I re-ran the mutant that drops the final flush: it is now killed by this test.
- **N1, fixed.** The PR body now says only p1-d5 and p1-d6 have a host line. The other 20 icons stand at the block's end, as on main.

## Re-checks on 92e5408

- **Since afe9eb9:** the only changes are the two tests and #201's merge (test_layout_headings.py). No code, golden or snapshot change.
- **Layout golden vs main 486e18b:** the diff touches only liu and biggs, with the same hunks as in round 1.
- **Lint:** ruff, format and lint-imports are clean.
- **Fast suite** (ci profile): 3174 passed, 1 skipped.
- **Nightly layout properties:** 262 passed.

## Verdict

Clean. I merge it (squash) once CI on 92e5408 is green.
