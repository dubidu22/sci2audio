# Review: PR #762, round 2

- PR: #762 (`output: the whole book as one M4B or MP3, and chapter numbers from the book`, #725, #726), critical.
- Head reviewed: 16b6e7ae64ecd37bc39234dd7422c4587536c84a (fix commits 3041d5d and 16b6e7a on round 1's bc5b481).
- Thread: review-b005. Date: 2026-11-23.
- **Verdict: approved.** 0 must-fix, 0 should-fix, 0 deferred.

## Round 1 finding

- **B1** (must-fix, `vacuous-test`, REV-05): fixed at the root, with a check.
  - `quiet_edged_job` moved into `tests/unit/output_helpers.py`. The book byte test (`test_the_book_m4b_is_byte_identical_to_the_one_finish_writes`, both parameters) now runs on edge-silent chunks with a cover.
  - New guard `assert_joins_trim(job)` fails when no `ChunkAudio.kept` is shorter than its frames. Both join byte-equality tests call it: the book test and `test_chapter_by_chapter_with_clause_joins_writes_the_same_bytes`.
  - Mutation, checked by this review: with `_trim_joins` replaced by plain `_inspect_all` in `write_book_file` (`output/chapters.py`), both parameters of the book byte test fail (2 failed, 10 passed). In round 1, all 12 tests passed with the same mutation.
  - VER-02, checked by this review with a throwaway probe: `assert_joins_trim(make_job(...))` raises `AssertionError: no join trims anything`, the known-wrong case, and `quiet_edged_job` passes it.
- 16b6e7a only removes review tags from that helper's docstring: a one-line diff, which leaves `(#480)`.

## Checks

- Locally on 16b6e7a:
  - ruff check, ruff format --check and lint-imports are clean (3 contracts kept).
  - Fast suite: 9038 passed, 8 skipped, 6 xfailed.
- CI on 16b6e7a:
  - ci:full run 45202299756 is green: tests on ubuntu, macos and windows, both Chromium browser shards, lint and layers, licences, security, web paths, and CI passed.
  - `governance pr checks` is red until this round is recorded, then it is rerun.
- D-374: the macOS textprep plugin-isolation failure seen at 3041d5d failed once and did not recur on 16b6e7a. One failure without a code cause does not meet D-374, so there is no quarantine. If it fails again on any run, quarantine it the same day with an Issue.

## Notes carried

- N2 from round 1 stands for PR 2: always pass both `numbers` and `count` to `chapter_numbers`.

## Summary

- Done: B1 fixed with a guard that fails on the vacuous case; the byte test now catches a missing join trim in `write_book_file`.
- Not done: none.

## Merge

Squash-merged by review-b005 on the coordinator go D-906, pinned to 16b6e7a, as 51dd21d. Main CI run 45211348862 on 51dd21d: tests on ubuntu, macos and windows and CI passed all success.
