# Review PR #761, round 1

- PR: https://github.com/dubidu22/sci2audio/pull/761 (PR B of #723, LW-01, closes #723, lane:app (+ one line in web/tasks.py); plan `plans/impl-723-plan.md`, approved as D-895)
- Head: `492eb06ed98f0468ea6d1c18faa018248d012d61`, base `f1a9c1f` (#754); main is at `e3a328e` (#760, governance and CI files only, no overlap)
- Thread: review-b005 (Opus 5.5 high), 2026-11-23
- **Critical: yes** (CRIT-03): two new syrupy golden files (`tests/unit/__snapshots__/test_cli_convert.ambr`, `test_app_audio_chapters.ambr`), the job runner's file writing, and the rule for what a stopped job leaves (safety mechanism, D-119/D-160). Labelled `risk:high`.
- **Verdict: changes_requested.** 1 must-fix, 0 should-fix, 0 deferred, 3 notes.

## Verified checks

- `ci:full` run 45163940997 on 492eb06: `tests (ubuntu|macos|windows-latest)` and `CI passed` success; `ci:full` removed. `governance pr checks` red only on the D-882 `approved` step.
- Locally (Linux, Python 3.12, no torch): the eight test files the PR touches or depends on (`test_app_audio_chapters`, `test_app_audio_faults`, `test_app_audio_job`, `test_app_cover`, `test_cli_convert`, `test_web_audio`, `test_web_prepare`, `test_output_chapters`): 216 passed, 3 snapshots passed. ruff check and format clean; lint-imports 3 contracts kept.
- Plan section 5 (PR B): every promised node ID exists, including the five fault tests and the benchmark (`test_app_first_chapter_speed.py`, row in `docs/baseline.md`).
- CLI characterisation: `test_convert_writes_the_same_files_as_before_chapters_became_playable_early` and its snapshot were added in 0597e04 on top of #754's merge, before any app change; at 0597e04 the test passes (run by this review), and the snapshot file is byte-unchanged from 0597e04 to the head. So `sci2audio convert`'s names, text files, read-along file, record and audio tags and chapter marks are unchanged.
- LF commit 492eb06: changes only two `write_text` calls in the tests (`newline="\n"`); no `.ambr` file changes (`git diff d3c07c3 492eb06 -- '*.ambr'` is empty). It removes the CRLF difference in the source's SHA-256 on Windows, which the snapshot holds.

### Every changed existing test (coordinator's question)

Each change follows from the rule #723 changes (a stopped job keeps its whole, recorded chapters; its own files are no obstacle to a rerun without `overwrite`) or from the new default (`JOB_OUTPUT`, no M4B), and none asserts less than the new rule allows:

- `test_app_audio_faults.py`: the five plan tests (cancel, Ctrl-C, full disk while encoding, a file from elsewhere, a failing rerun) now go through `whole_chapters`, which asserts no partial, every output file owned by the record with size and SHA-256, the read-along listing exactly the MP3s, and the record's chapters matching; the rerun needs no overwrite and speaks nothing twice. `reused == chunks()` became `reused + spoken == chunks()` where the job now stops at the failing chapter before speaking the rest (required: those chunks were never spoken). The killed-mid-run, full-disk-while-speaking, output-folder-removed, chunk-removed and retried-names tests change the same way. `test_a_rerun_that_fails_while_encoding_leaves_no_old_record` now reruns under other output settings, since with the same settings a finished audiobook's chapters are reused under `overwrite` (plan 2.2) and ffmpeg would not fail where the test needs it; its old-record assertions are kept.
- `test_app_audio_job.py`: `run` passes `OutputSettings()` (the plan's one edit); two progress filters skip the new `ready` event, which repeats a chunk event; the cancel-while-encoding test now asserts MP3s present, no M4B, no partial, and the rerun needs no overwrite (which proves the files are the record's); the subtitles test asserts the record owns every file left.
- `test_app_cover.py`, `test_web_audio.py`, `test_web_prepare.py`: pass `OutputSettings()` or hold `_Chapters.finish` instead of the removed `_encode`; the web test asserts the partial set through the read-along's `m4b: null`.

## Findings

- **B1** (must-fix, kind `vouch-window`). A stop between vouching for and renaming a file that replaces one of the job's own files makes the rerun refuse its own file. `_Chapters._vouch` overwrites the record's entry for that name with the new size and SHA-256 before the rename; until the rename, the file on disk is the old one, whose hash the record no longer holds, so `ChapterRecord.owned` leaves it out and `_check_targets` raises `OutputExistsError` without `overwrite`. The read-along file is rewritten after every chapter, so the window opens once per chapter from the second on. Reproduced by this review on 492eb06: three-chapter book (`book_run`), a `BaseException` raised in `write._commit` at the 2nd (and, separately, the 3rd) read-along rename (the same record state as a SIGKILL there, or Ctrl-C), then `book_run` again without overwrite: `OutputExistsError: these files exist already: book.readalong.json; choose to replace them`. `test_a_kill_between_vouching_and_renaming_resumes_cleanly` misses it because it kills only on `02 Beta.mp3`, which has no earlier version. Recommended: keep the previous entry for a name until the new file is in place (for example `owned` accepts the hash in `book`/`chapters` or the one in `pending` for that name, with the new hash going to `pending` and moving to `book` on the next save), and add the read-along case (2nd rename, before and after) to that test's parametrization.
- **N1** (note). The record gains a `pending` list the plan did not name; it is the plan's "vouched before the rename" made concrete for files of a chapter not yet complete, and the plan's own kill test needs it. No change asked.
- **N2** (note). With `overwrite` and unchanged settings, a finished audiobook's chapters are reused, not encoded again (plan 2.2). The web's "Replace" then rewrites only the book files; the bytes are the same, so nothing visible changes.
- **N3** (note, for #724). `playable_chapters` checks size only, by design (cheap for a page); the job checks hashes before reuse.

## Handoff (THR-07)

- Goal: critical review round 1 of #761 at 492eb06.
- Done: CLI byte-identity snapshot verified as pinned before the change; every changed test checked against the rule change; fast tests and lint green locally; B1 reproduced with a short in-process probe (stop at the 2nd or 3rd read-along rename, then resume without overwrite).
- Next: a fresh implementation thread pushes one fix commit for B1 with the extended kill test; round 2 reruns the probe and the extended test against the fix and checks a three-system run on the new head.
