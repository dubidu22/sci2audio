# PR #671 review, round 2 (head 6a759bb)

Reviewer: B-L1 layout review thread (review-layout-b-l1), Opus. 20 Nov 2026. Answer: plans/answer-pr671-round1.md.
Critical: **yes** (unchanged from round 1).
Verdict: **approved** (0 must-fix, 0 should-fix open; 1 note). Before merge, CRIT-02 needs a three-system run on the final head (see "Merge").

## Round 1 findings

- **M1, fixed.** In `extraction/pdf.py`, the new `_letter` refuses any `_COMBINING` character and accepts NFD letter plus combining marks, so a letter that already took an accent can take a second one. `_only_accents` widens the rule to lines made only of spacing accents. Such a line is placed only when every accent in it finds a letter; letters are changed only after that check, so a partial match changes nothing. My round 1 probe ("Nguyen", circumflex and acute in both stored orders) now gives placed {1, 2} and "Nguyến" / "Nguyé̂n", and no accent is lost. The new `test_two_accents_stacked_on_one_letter_both_go_onto_it` covers both orders. The Hypothesis property now draws a second accent now and then and counts every drawn accent (spacing or combining); the author reports it failed on 933cdf4. Widening the rule from "one accent" to "accents only" follows from "no character is lost", and no golden changes, so I accept it.
- **S1, fixed.** `tests/unit/test_layout_corpus.py::test_accents_and_lines_under_braces_read_as_printed` asserts the Chi, Hardt and Liu texts directly, with no lone or trailing acute or caron line. It does not go through the snapshots.
- **N1** accepted. **N2** done (`paragraphs.py:233`).

## Checked

- **Golden diff.** 6a759bb touches no snapshot (`git diff 933cdf4 6a759bb --stat`: pdf.py, paragraphs.py and two test files). The golden diff against main is therefore the one verified line by line in round 1.
- **Layers and lint.** extraction still imports only `unicodedata` here. ruff, ruff format, lint-imports (3 kept) and deptry are green.
- **Linux CI on 6a759bb.** `tests (ubuntu-latest)`, both Chromium browser shards, lint and layers, licences, security and `governance pr checks` passed; `CI passed` is green. macOS and Windows did not run (no `ci:full`, D-698).
- **Local fast suite** (temporary worktree at 6a759bb, macOS, `-k "not espeak"`, the #670 test deselected): 8370 passed, 1 failed. The failure is `test_layout.py::test_any_clean_column_page_reads_column_by_column`, an example found by the local `dev` Hypothesis profile. It fails the same way with main's `paragraphs.py`, so this PR did not cause it. I opened #679 with the full example (lane:layout, v2). All touched test files pass on their own (488 passed).

## Notes

- **N3.** When the acute is stored before the circumflex, the result is "é" plus a combining circumflex (stored order), not the canonical stack. That is faithful to the stored order and harmless for the #65 step. No action.

## Merge

- CRIT-02 / D-580: the three-system `ci:full` run was on 933cdf4. The final head 6a759bb needs its own green `tests (macos-latest)` and `tests (windows-latest)` before the merge go. GitHub reports the PR as mergeable (CLEAN) with main after #677.

## Handoff (THR-07)

- Goal: PR #671 merged.
- Done: round 2 at 6a759bb, approved; #679 opened for the unrelated property example.
- Next: `ci:full` on 6a759bb (author), then squash-merge on the coordinator's go, pinned to 6a759bb.
