# Review PR #762, round 1

- PR: https://github.com/dubidu22/sci2audio/pull/762 (PR 1 of #725/#726, lane:output; plan `plans/impl-725-plan.md`, approved as D-903 with 4.1 = numbers from the book's place)
- Head: `bc5b481ebf6adf4b6303dd30ef0ebb8200e4f91f`, base `9f622af` (= main)
- Thread: review-b005 (Opus 5.5 high), 2026-11-23
- **Critical: yes** (CRIT-03): output file writing and a new syrupy golden file (`tests/unit/__snapshots__/test_output_book.ambr`). Labels `risk:high, lane:output`.
- **Verdict: changes_requested.** 1 must-fix, 0 should-fix, 0 deferred, 2 notes.

## Verified checks

- `ci:full` run 45178892989 on bc5b481: `tests (ubuntu|macos|windows-latest)`, `lint and layers`, `CI passed` success; `ci:full` removed. The book-MP3 chapter test ran on all three, so the bundled ffmpeg writes the ID3 chapter frames everywhere (plan 6's open point).
- Locally: `test_output_book.py` and `test_output_chapters.py` 76 passed; ruff check and format clean; lint-imports 3 contracts kept. Every node ID of plan 5 (PR 1) exists.
- Lanes: `src/sci2audio/output/**`, `tests/unit/test_output_*`, one new snapshot. No existing snapshot changes.

### The two claims

1. **Existing files are unchanged by default.** With `numbers`/`count` left out, `chapter_numbers` gives 1..n of n, as before. Checked directly with round 1 of #754's scripts on bc5b481: `write_audiobook` on 12 inputs (6 setting sets, with and without clause pauses, cover) and `BookWriter` chapter by chapter on the same inputs give the same SHA-256 as main `0994f97` for all 98 files; `BookWriter` on chunks with silent edges where every clause join trims gives the same 23 files as main. So 4.1 has no golden effect in this PR: the numbering change reaches files only when the app passes numbers (PR 2), whose snapshot diffs D-903 expects there.
2. **The book M4B equals the M4B a job writes.** `finish` and `write_book_file` now share `_write_book` and `_place`, so the ffmpeg arguments and feed are one path. Checked by this review on quiet-edged chunks with every pause `CLAUSE` (also at chapter starts), subtitles on: `write_book_file`'s M4B, `.srt` and `.vtt` equal `finish`'s byte for byte.

## Findings

- **B1** (must-fix, kind `vacuous-test`, seen before in #754 round 1 M1, so REV-05 applies). `test_the_book_m4b_is_byte_identical_to_the_one_finish_writes` cannot catch a join difference: it uses `make_job`'s tone chunks, which have no quiet edges, so nothing is trimmed. With `_trim_joins` removed from `write_book_file` (the one step it does on its own, outside the shared `_write_book`) all 12 tests of `test_output_book.py` still pass. The PR app (PR 2) feeds real voice chunks with clause joins, so the claim it tests is exactly the one left unchecked. Recommended fix at the root, with the check REV-05 asks for: move `quiet_edged_job` from `test_output_chapters.py` into `output_helpers.py`, use it in the book byte test (M4B and subtitles), and give the helper an assertion every byte-equality test calls (for example that at least one `ChunkAudio.kept` is shorter than its frames), so a join-equality test that trims nothing fails instead of passing.
- **N1** (note, ordering). D-902 and D-903 say no code for #725/#726 before #724 merges; #762 was opened while #764 (#724) is still open. The files do not overlap (#764 touches no `output/` file; checked with the PR's file list), so LANE-02 is met and nothing here conflicts; the ordering was the coordinator's to grant.
- **N2** (note). `chapter_numbers` takes `count` as the last number when only `numbers` is given; PR 2 should always pass both, as the plan says, so a partial book's track total is the book's count.

## Handoff (THR-07)

- Goal: critical review round 1 of #762 at bc5b481.
- Done: both claims verified directly (defaults byte-identical to main; book M4B equal to finish's with real trims); one vacuous test, a recurring kind.
- Next: one fix commit for B1 (tests only); round 2 checks that the byte test fails with `_trim_joins` removed from `write_book_file`, and a three-system run on the new head.
