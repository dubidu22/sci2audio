# Review: PR #765, round 1

- PR: #765 (PR 2 of #725/#726, app + CLI: build the audiobook on request and add chapters later), critical (golden files, reuse and overwrite rules, file writing in the output folder).
- Head reviewed: 9e160c09ba794d82d3d499bc6c780ae643c7758d.
- Thread: review-b005. Date: 2026-11-23.
- **Verdict: changes_requested.** 1 must-fix, 2 should-fix, 0 deferred.

## What was checked

1. **Version-1 `chapters.json` (coordinator's extra check, CRIT-01).** I used a real v1 record, written by main's code (51dd21d) in a separate worktree, not the test's synthesized one. Its keys match the test fixture: `book, chapters, complete, format, pending, planned, settings, version`, and chapters `files, fingerprint, index, number, title`. Read by the PR's code:
   - The same book with another chapter choice is refused before any speech, with "made by an earlier version ... choose to replace them". The record is not rewritten and the files are untouched.
   - With `overwrite`, the job runs and the record becomes version 2.
   - `build_book` on a v1 record raises a JobError asking for the chapters to be made again.
   - Nothing silently rejects or overwrites a v1 record of the **same** book. A v1 record of **another** book is wrongly refused; see B1.
2. **The 9e160c0 fix (coordinator's extra check).** With the `book` check removed, `test_another_book_in_the_same_working_folder_is_not_added_to` fails, so the test does catch the v2 case. The fix is incomplete for v1 records; see B1.
3. **Golden diffs (D-903 4.1).** The three snapshot diffs are exactly the ones the PR body explains:
   - `three - 02` became `03`, and tracks `1/2, 2/2` became `1/3, 3/3`;
   - `chapters.json` is version 2 with `made`, `order`, `built` and a masked `spoken` hash;
   - `--keep-settings` appears in `--help`.
   No other snapshot changed, so a full-book run is byte-identical.
4. **Mutation probes on the new rules.** Each of these, applied one at a time, fails a named test:
   - the 9e160c0 book check;
   - the foreign-file refusal in `build_book`;
   - reuse of a built file;
   - `entry.chapters == held`;
   - the `partial_ok` refusal;
   - the cleaned-cache check;
   - `SettingsChangedError`;
   - the D-163 refusal;
   - the custom-order refusal.

   One survives; see S2.
5. **Tests and CI.**
   - Locally, every `tests/unit/test_app_*.py` and `test_cli_*.py` test passes: 716 passed, 2 skipped.
   - The ci:full run 45213028392 is green on ubuntu, macOS and Windows, and on both Chromium shards.
   - All 26 promised tests and the six extra ones exist.

## Findings

- **B1** (must-fix, `incomplete-fix`). A version-1 record of **another book** in the same working folder refuses the job. On main the job goes ahead.
  - Reproduced: main writes book A with chapter 0 into `work/` and `out/`. The PR's code then runs `other.md` into the same `work/` and `out/`, and raises `OutputExistsError: the chapters made so far were made by an earlier version of sci2audio ... choose to replace them`. Main's code ran the same second step and wrote `other - 01 Delta.mp3`.
  - Cause: in `_adding` (`app/audio.py`), the `record.made is None` refusal comes before the 9e160c0 check `record.made.get("book") != made["book"]`. So a v1 record is refused before the code asks whose record it is.
  - The message is also wrong for that case, because nothing of this book was made. A user following it with `--overwrite` loses book A's record.
  - Only a shared `--work-folder` reaches this (the default work folder is per project), but this is exactly the case 9e160c0 set out to fix.
  - Fix: decide "another book" before the v1 refusal. A v1 record has no `made`, but its chapter files carry the book's name (`<book> - NN <title>.mp3`). For example, a v1 record none of whose files are among this job's targets adds nothing.
  - Add a test that writes a v1 record and then runs another book into the same working folder. This has to be the v1-record variant of the 9e160c0 test, because the v2 test passes with B1 present.
- **S1** (should-fix, `correctness`). `keep_settings` takes another book's settings.
  - `_kept` runs before the document is read, so it rebuilds the settings from whatever record the working folder holds. Reproduced: book A at speed 1.2, then `other.md` with `keep_settings=True` into the same working folder, is made at speed 1.2, silently.
  - The same order means a v1 record of another book plus `keep_settings` raises the "earlier version" error.
  - "Keep the settings the chapters were made with" should only apply to this book's chapters. Fix: check the book (as in B1) before taking the kept settings, or apply `_kept` after `book_info`. Add a test.
- **S2** (should-fix, `missing-test`). `_pair_current` in `app/book.py` is untested.
  - With the `and _pair_current(...)` clause removed from the reuse condition, all 11 tests of `test_app_book.py` still pass.
  - That clause is what rebuilds a book M4B whose `.srt` or `.vtt` was removed or changed. Without it, the M4B would be reused without its subtitles.
  - Add a test: build an M4B with subtitles, delete or edit one subtitle file, and build again. It must not be reused, and both subtitle files must be back.

## Notes

- **N1.** A second book run into a shared working folder replaces the first book's record, so the first book's files are no longer this project's. This is the same as on main, and only reachable with `--work-folder`. It needs no change in this PR.
- **N2.** `convert --with-script --keep-settings` writes the script with the settings given, as the PR body says. If that stays, an Issue is enough.

## Summary

- Done: both extra checks, the golden diffs, ten mutation probes, the tests and the three-system run.
- Not done: none.
- Open: B1, S1, S2 for round 2.
