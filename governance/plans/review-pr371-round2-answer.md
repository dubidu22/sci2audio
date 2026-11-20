# PR #371 review round 2 answer

## Review round 2 (D-641), head 81ba6a3

Fixed exactly these:
- **S1.** The round 1 check `text[end : end + 1] in "(["` was true at a block's end, because the empty string is in every string. It is now `in ("(", "[")`. So "Text (see https://example.org)" and "Text [see https://example.org]" give the script piece `ScriptPiece("Text", Span(0, 0, 4))` again, as on main. The new test `test_a_link_bracket_that_ends_its_block_takes_the_space_before_it` checks the script pieces themselves and fails on 0f43871.
- **N1.** These rows were added to `test_textprep_links_in_brackets.py`:
  - "Text (see https://example.org/a)b)(more) here." reads "Text (more) here.";
  - "Lee (see https://x.org/a(b)(Smith, 2019)." reads "Lee.";
  - "(e.g. (Smith, 2019); Jones, 2020) is cited." reads "Jones is cited.".

  Each of the three mutants from the review now fails a test: `_closed_before` without the glued-bracket check, without the depth count, and `_listed_inner_names` allowing text before the inner bracket.
- **N2.** A "/" with white space on both sides now goes with the link, as "and" does, so "It holds (see https://example.org / Lee, 2019) here." reads "It holds here." (en and de). A "/" glued to the address or to the next word stays as before, because it belongs to them. Rows were added to `links-a-join-word-after-a-link-at-a-bracket-start`, `de-links-in-brackets-read-the-same-on-a-second-run` and the unit file.
- **N3.** The S1 rows, the block-end row, the slash row and the N1 rows are in the table above. The CHANGELOG line names the slash and the kept space.

Checks at 81ba6a3:
- The fast suite passes: 5507 passed, 1 skipped.
- The 13 corpus documents are identical to main 82d9e0d.
- Nightly seeds 7, 555 and 8080 pass on the links, links-in-brackets and citations tests.
- Token fuzz seeds 1 to 4 give 15, 17, 18 and 12 second-run differences, against 16, 18, 19 and 13 on main. No input differs on the branch that does not also differ on main.
- The new tests fail on 0f43871 (S1, N2). The N1 mutants and two more (the block-end check reverted, the slash taken out) each fail a test.

