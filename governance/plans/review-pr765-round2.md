# Review: PR #765, round 2

- PR: #765 (PR 2 of #725/#726, app + CLI), critical.
- Head reviewed: adeba2857d88fecd3708233efe60d27f61862e83 (one fix commit on round 1's 9e160c0).
- Thread: review-b005. Date: 2026-11-23.
- **Verdict: approved.** 0 must-fix, 0 should-fix, 1 deferred (Issue #767).

## Round 1 findings

- **B1** (version-1 record of another book): fixed.
  - `_same_book` now decides whose record it is before anything else. A version-2 record is compared by title and authors; a version-1 record by its files' names (`<book> - `, `<book>.readalong.json`, `<book>.m4b`). `_adding` gets the record only when it is this book's.
  - This review reproduced it again with a real version-1 record written by main's code (origin/main in a separate worktree). Main writes book A, then the PR's code runs `other.md` into the same work and output folders. It now writes `other - 01 Delta.mp3` and leaves `book - 01 Alpha.mp3` byte-identical, as main does.
  - The same book with a version-1 record still asks for a choice ("earlier version ... choose to replace them") before any speech.
  - Mutations: with the version-1 branch of `_same_book` returning False, `test_a_version_1_record_reads_and_asks_for_a_choice` fails. Returning True, `test_another_books_version_1_record_neither_refuses_nor_lends_its_settings[plain]` fails. With the version-2 comparison returning True, the 9e160c0 test fails.
- **S1** (`keep_settings` took another book's settings): fixed.
  - The settings are kept only when `same`, which is decided after the document is read. The document is read again when the kept language differs, since `read_document` depends on settings only through the language (`LayoutSettings(language=...)`).
  - Reproduced: book A at speed 1.2, then `other.md` with `keep_settings`, is now made at speed 1.0. A version-1 record of another book with `keep_settings` no longer raises.
  - Mutation: with `keep_settings and same` changed to `keep_settings and record is not None`, the `[keep-settings]` case fails.
- **S2** (`_pair_current` untested): fixed. With the clause removed, `test_a_book_whose_subtitles_were_removed_is_built_again` fails. The edited-subtitle test checks that an edited `.srt` is refused as not this project's.

## New finding

- **D1** (deferred to Issue #767, `missing-test`). The language re-read added for S1 is untested.
  - With `if settings.language != given.language: document = read(settings)` removed, all 19 tests of `test_app_add_chapters.py` and `test_cli_add_chapters.py` pass.
  - It only matters when the kept language differs from the given one. The code is correct by reading.
  - Recorded in `ledger/deferred/pr765-1.yaml` (planned, #767), with acceptance criteria.

## Checks

- Locally on adeba28: ruff and format are clean, lint-imports keeps 3 contracts, and the app and CLI tests pass (721 passed, 2 skipped).
- ci:full run 45216903017 on adeba28: tests on ubuntu, macOS and Windows, both Chromium shards, lint, licences, security and `CI passed` are all green.
- The run's overall conclusion is red only because of the report-only `browser (Linux, webkit, 2/2)` job. Its one failure is `test_markers.py::test_the_undo_ends_after_sixty_seconds_and_with_the_next_marker[webkit]` (attribute 'false' expected). That job fails no other test.
- This review found no earlier WebKit failure of that test: not in the round 1 run 45213028392, and not in the last three nightly runs. It is not one of #764's two WebKit flakes. One failure without a code cause does not meet D-374, so there is no quarantine. If it fails again, quarantine it the same day with an Issue.

## Notes

- **N1.** The version-1 name test is a prefix test, so it can match too much. A book titled `Intro` reads a version-1 record of a book titled `Intro - Part 2` as its own, because `Intro - Part 2 - 01 X.mp3` starts with `Intro - `. The result is the "earlier version" request for a choice, never a silent overwrite. This is acceptable for a one-time migration case.
- **N2.** Round 1's N1 (a second book replaces the first book's record in a shared working folder) is unchanged and the same as on main.

## Summary

- Done: B1, S1 and S2 verified fixed, with tests that fail on the mutation. D1 deferred to #767.
- Not done: none.

## Merge

Squash-merged by review-b005 on the coordinator go D-908, pinned to adeba28, as ebd6e40. Main CI run 45221066638 on ebd6e40: tests on ubuntu, macos and windows and CI passed all success.
