# Review PR #484, round 3 (sentence-boundary batch PR 5, #463 + #464)

Head reviewed: 33108b7. It is the round 2 fix commit 64adb70 on 99b3f48, plus a merge of main 6525212 (#486, the Windows quarantine). Earlier rounds: plans/review-pr484-round1.md and plans/review-pr484-round2.md.

**Verdict: approvable, and merged.**

## The fix commit and the merge
- **S1 of round 2, fixed.** `_run_tags` is byte-for-byte `fix484-r2.diff`: each tagged run is cut at line breaks, empty pieces are skipped, and a piece that starts before the previous range's end is skipped. Three new tests are in `test_testing_rebuilt_from_script.py`:
  - (a) `test_a_tagged_run_across_a_line_break_keeps_its_tag_on_each_line`;
  - (b) `test_a_tagged_run_ending_in_a_line_break_gives_no_empty_range`;
  - (c) `test_a_line_not_where_its_part_says_gives_no_tag`.

  I put the round 3 tests on 99b3f48's source: (a) and (b) fail there. (c) pins the other-text guard, which 99b3f48 already had.
- **The merge of main** adds only the 3-line quarantine marker of #486. Apart from that, the diff against the reviewed 99b3f48 changes only `_run_tags` and its tests (D-725).

## Final-round checks on 33108b7
- **Nightly seeds** (`HYPOTHESIS_PROFILE=nightly`, `--hypothesis-seed` 2024 and 123456, `-n 4`, on the 20 textprep property files plus `test_textprep_conformance.py` and `test_testing_rebuilt_from_script.py`): 2866 passed each. The runner property test that failed in round 2 passes.
- **Mutation** (`/home/user/probe/m484/run.py`, baseline 1325 passed): every rebuild and harness mutant is killed:
  - no tags kept;
  - the other-text guard off;
  - empty pieces kept;
  - the overlap guard off;
  - no split at line breaks;
  - the exclusion put back.

  With round 2's results, 18 mutants were run in all: 15 are killed and 3 are equivalent (5, 6 and 9, argued in rounds 1 and 2).
- **`hole.py`** (Neighbour step): 8 problems, so it is caught.
- **Corpus utterances:** byte-identical to main.
- **Three systems** on 33108b7: `tests (macos-latest)`, `tests (windows-latest)` and `tests (ubuntu-latest)` are green, as are browser, lint and layers, licences, security, CodeQL and `CI passed`. This is the base-move run that counts as round 3's (D-725).
- **The coordinator's rulings:**
  1. No exclusion remains.
  2. The #464 departure is approved and recorded, with URL-only and citation-only tests in en and de.
  3. The D-718 coverage (kind × on/off × en/de/fr) is in round 2's table.

## Merge
- **Main had not moved:** it was 6525212, which is in the branch.
- **Squash-merged**, pinned to 33108b7. The new main is **4bb8f81**.
- **The merged tree is identical** to the reviewed head's tree.
- **Closed:** #463 and #464.
- **Main's own three-system run on 4bb8f81** is watched, and its result is added below.
- **Main 4bb8f81 three-system run:** `tests (macos-latest)`, `tests (windows-latest)` and `tests (ubuntu-latest)` are green.
