# Review: PR #768, round 1

- PR: #768 (PR 3 of #725, web: download the whole audiobook, Closes #725), lane:web, non-critical.
- Head reviewed: 22a8e2db81f5aa89aaaa492822e27f1cdd69dea8.
- Thread: review-b005. Date: 2026-11-23.
- **Verdict: changes_requested.** 1 must-fix, 3 should-fix, 0 deferred.

## Critical or not

The plan (D-903, section 3) calls PR 3 non-critical, and none of the critical list applies:
- it changes no layer contract, no `sci2audio.core` and no golden file;
- `scripts/zap_scan.py` is the scan's walk, not a workflow;
- the new file writing is PR 2's `build_book`, reviewed critical in #765.

Adding the built file to `record_files` (D-750) widens what a project removal deletes. It is the project's own file, vouched for by the record, through the existing removal path. This review accepts it as non-critical.

## What was checked

1. **The book route** (`POST /documents/{id}/book`, `web/api.py`):
   - 200 with the name of a current build, 202 with a book job, 409 `missing-chapters` with the titles unless `partial_ok`, 409 `busy`, 409 `not-buildable` for a pre-#723 audiobook.
   - The busy check before `board.start` is backed by `BoardBusyError`.
   - `BookIn` is strict: a literal `kind` and a `StrictBool`.
2. **The web audio job writes no M4B** (the D-895 line removed). The nine changed existing tests were read one by one. Each follows from this or from D-903 numbering, and none is weakened:
   - `test_flow` now names the one chapter;
   - `test_subtitles` reads the book's pair beside the built M4B;
   - the pause test in `test_web_audio` pauses in `_Chapters.done` instead of `finish`;
   - the foreign-file test uses the read-along name.
3. **The job page and the box:**
   - The done page shows the file, Save, the folder and the chapters left out of a partial file. `back` goes to Listen.
   - The box names the missing chapters, focuses the list and offers the partial file.
   - A change of kind hides the offer again.
   - The buttons are drawn disabled until the click is attached (#427).
4. **ZAP:** the walk posts `…/book` and waits for the job to end.
5. **Tests:**
   - Locally on the head, ruff and format are clean and lint-imports keeps 3 contracts.
   - `tests/unit/test_web_*.py`: 1063 passed, 5 skipped.
   - Chromium: `test_download_book` plus the six changed browser files, 81 passed.
   - CI on the head is green.

## Mutation probes

Each mutation was applied alone and run against `tests/unit/test_web_book.py` and, for the survivors, `tests/browser/test_download_book.py`.

- **Caught:**
  - the `kind` filter in `whole_book`;
  - its vouch for a current build;
  - the 409 for missing chapters;
  - the busy check;
  - `record_files` for the built file.
- **Survived:** the five listed under Findings, plus two trivial ones (N1).

## Findings

- **B1** (must-fix, `missing-test`, a recurring kind, so REV-05 applies). No test catches a stale whole-book file served as current.
  - In `whole_book` (`web/player.py`), `entry.chapters != held` is what keeps the route from answering 200 with a file built from other chapters. Examples: a partial M4B after the missing chapter was made, or a full one after a chapter was made again.
  - With that condition removed, all unit and browser book tests still pass.
  - A web audio job with more chapters chosen adds them (PR 2), so this case is reachable in PR 3.
  - Fix: a test that builds, then changes the chapters made (adds one, or regenerates one with overwrite), then posts `…/book` again. It must not get the old name with 200; it gets a job, or a new file that holds the new chapter.
  - REV-05 check: the test must fail with the condition removed (VER-02).
- **S1** (should-fix, `missing-test`). `_built`'s vouch is untested.
  - With `_built` returning `folder / name` unvouched, all tests pass.
  - The vouch is what keeps the audiobook route from serving a file of a recorded name that was replaced or edited since.
  - Fix: a test that edits the built file and gets 404 from `…/audiobook/{name}`.
- **S2** (should-fix, `missing-test`). The pre-#723 path of the route is untested.
  - With `if not book.buildable` removed, and separately with the old M4B no longer served (`old = None`), all tests pass.
  - Fix: a test with an audiobook that has no `chapters.json`. Its M4B is served with 200, and `mp3` answers 409 `not-buildable`.
- **S3** (should-fix, `missing-test`). The job's `missing-chapters` failure kind is untested.
  - With the `("missing-chapters", MissingChaptersError)` row removed from `_KINDS`, all tests pass. The failure would then be shown under a generic kind.
  - Fix: a test where a made chapter's chunks are cleaned from the cache before the build, so the route answers 202 and the job fails. Assert that the job's error kind is `missing-chapters` and that its message names "no longer in the working folder".

## Notes

- **N1.** Two trivial survivors: the `BOOK_STEP` throttle in `book_work`, and the line that drops the subtitle pair for an MP3 book. No test is needed for either.
- **N2.** As the author notes for PR 4, the output `m4b` flag is part of the settings key. A project made by the CLI, which writes an M4B, and then extended in the web, which does not, meets `SettingsChangedError`. PR 4's settings-changed dialog is where this should be handled.

## Summary

- Done: the route, the job page, the box, ZAP and the changed tests reviewed; the tests run; twelve mutation probes.
- Not done: none.
- Open: B1, S1, S2 and S3 for round 2. All four are tests only; the code is correct by reading.
