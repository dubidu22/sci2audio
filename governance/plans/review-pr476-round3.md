# Review PR #476, round 3 (sentence-boundary batch PR 2, #454)

Head reviewed: 1789d4f, one fix commit on 8c22c49. Round 2: plans/review-pr476-round2.md.

**Verdict: approvable, and merged.**

## The fix commit
- It changes `tests/unit/test_layout_paragraphs.py` only: +58 lines. The source diff against 8c22c49 is empty.
- It adds the four tests from round 2's S1:
  - `test_rows_ending_at_two_edges_are_no_flush_right_block`;
  - `test_rows_with_two_middles_are_no_centred_block`;
  - `test_one_italic_word_leaves_a_centred_row_upright`;
  - `test_a_short_line_goes_on_with_e_g_and_i_e` (Hypothesis `sampled_from` over "e.g." and "i.e.").

## Checks on 1789d4f
- **Mutants** (`/home/user/probe/m476/run.py 0 6 20 24 25`, same test paths as round 2):
  - baseline: 568 passed;
  - mutant 6 (italic = any italic run) is killed by `test_one_italic_word_leaves_a_centred_row_upright`;
  - mutant 20 (lettered mark without `\s`) is killed by `test_a_short_line_goes_on_with_e_g_and_i_e`;
  - mutant 24 (two right edges count as flush right) is killed by `test_rows_ending_at_two_edges_are_no_flush_right_block`;
  - mutant 25 (two middles count as centred) is killed by `test_rows_with_two_middles_are_no_centred_block`.
- **Overall:** 25 of the 32 mutants are now killed. The other 7 are equivalent or notes, with the reasons in round 2's table.
- **CI on 1789d4f:** all green with `ci:full` on. That includes `tests (macos-latest)`, `tests (windows-latest)` and `tests (ubuntu-latest)`, plus browser, lint and layers, licences, security, CodeQL and `CI passed`.
- **Unchanged since round 2:** the corpus blocks, fast suite, sentence gate and nightly seeds. The source has not changed since round 2, where all of them were green on 8c22c49.

## Merge
- Main was 1c45cab, the branch's merge base, so the diff against main is the one reviewed and the three-system run is on the merged head itself.
- On the coordinator's standing go, it was squash-merged at about 21:15Z on 16 Nov, pinned to 1789d4f. The new main is **2e2ae77**.
- #454 is closed (completed).
- #454's second criterion (the Kehren motto itself) cannot be checked in the repo, because the PDF has a personal-use licence. Colin can confirm with `uv run sci2audio script "GSW 16.11.26 Kehren - BNE.pdf"`.

## Notes carried forward
- **Accepted risk of the plan.** An unindented lower-case paragraph start with no extra white, after a line that ends without a stop, still joins.
- **Code lines.** Code lines set as body text without a caption join into one block. Neither reading is good, and such code usually sits in floats.
