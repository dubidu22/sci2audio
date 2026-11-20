# Review PR #478, round 2, final (sentence-boundary batch PR 3, #465 #406 #141 #268)

Head reviewed: 4d57b9f, one fix commit on 82dd2fe. Main is 2e2ae77, which is the merge base, so the branch is up to date. Round 1: plans/review-pr478-round1.md.

**Verdict: approvable, and merged as 7d866bf.**

## Round 1 findings
- **S1, fixed.** `_letter_of` now tests only the last character of the word before: `unicodedata.category(before[1][-1]) == "Sm"`. "Let x= N." and "Let 2x≤ N." are cut, and both are rows of `test_sentence_ends_found_by_the_sentence_test_set`.
- **N1, fixed.** The U.S., Lorenz FP and Lorenz FN whys now name the mechanism.
- **N2a, fixed.** ("It ended. 2019. Then more.", three sentences) pins the one-to-three-digit limit.
- **N2b, fixed differently and better.** The author found that `not previous["dot"]` mattered the wrong way round: "Siehe Kap. 2. Kap. 3 folgt." read "Siehe Kapitel zweites Kapitel 3 folgt.", because the ordinal step sees the printed "Kap." with its dot.
  - The condition is dropped.
  - `test_german_ranges_and_dotted_numbers_read_the_same_on_a_second_run` pins it with rows "Satz 2. Satz 3" and "Siehe Kap. 2. Kap. 3 folgt." (read "Siehe Kapitel 2. Kapitel 3 folgt.").
- **Follow-up, filed.** #479 "German 'Abs. 2. Abs. 3' stays one utterance" (open, v1.2.x abbreviations, lane:textprep) is named in the PR body.

## Final-round checks on 4d57b9f
- **Corpus utterances** of all 13 files are byte-identical to 82dd2fe. So round 1's line-by-line account of every change against main (chi, nowak, arsiwalla, sample-plain, Maaß) still holds, and the goldens are unchanged.
- **Fast suite** (`HYPOTHESIS_PROFILE=ci`, `-n 4`): 6748 passed, 2 skipped.
- **Mutation** (`/home/user/probe/m478/run.py`): the 19 round 1 mutants, with mutants 8, 10, 17 and 18 rewritten for the new code. The test files are round 1's plus `test_textprep_numbers_statistics_de.py`. The baseline passes (1777 passed).
  - **19 of 20 are killed**, including the round 1 forms of S1 (mutant 10) and N2b (mutant 18).
  - Mutant 6 (four digits) is now killed by the new "2019." row.
  - The one survivor, mutant 3 (`<=` for the removed-stretch gap), is equivalent: adjacent pieces give an empty stretch, which `_ENDED` cannot match.
- **Nightly seeds and fuzz** (`HYPOTHESIS_PROFILE=nightly`, `--hypothesis-seed` 2024 and 123456). They ran on `test_textprep_utterances.py`, `test_textprep_units_abbreviations.py`, `test_textprep_numbers_statistics_de.py`, `test_textprep_units_per_and_german_readings.py`, `test_textprep_numbers.py` and `test_app_script.py`, which covers the fuzz of the cutter and the second-run idempotency properties. Result: 1110 passed each.
- **Three systems.** I re-added `ci:full`, and the run on 4d57b9f started at 22:09Z. It is green: `tests (macos-latest)`, `tests (windows-latest)`, `tests (ubuntu-latest)`, browser, lint and layers, licences, security and `CI passed`. The author's earlier run on this head was green too.

## Merge
- **Pinned and squash-merged** on the coordinator's standing go (Colin's autonomy messages), at about 22:25Z on 16 Nov, pinned to 4d57b9f. The new main is **7d866bf**.
- **Closed:** #465, #406, #141 and #268 (all completed).
- **Open follow-ups:** #466 (layout-join entries), #455 (Lorenz entries, PR 4), #477 (limits kept on purpose, milestone Later) and #479 (Abs.).
