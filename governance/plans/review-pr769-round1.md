# Review: PR #769, round 1

- PR: #769 (PR 4 of #725/#726, web: generate the remaining chapters later, Closes #726), lane:web, non-critical.
- Head reviewed: c23164624a1b889a7b1bb4138788dabb7a918526.
- Thread: review-b005. Date: 2026-11-23.
- **Verdict: changes_requested.** 0 must-fix, 2 should-fix, 0 deferred.

## Critical or not

Non-critical, as the plan says. Nothing on the critical list applies:
- no layer contract, `sci2audio.core` or golden file changes;
- "Make every chapter again" is the existing `overwrite` (D-163);
- the rewritten position file is the app's own record in the working folder.

## What was checked

1. **Settings-changed is a failed job (D-909 item 1).** `classify` maps `SettingsChangedError` to `settings-changed` with `changes`. JobOut carries `changes`. The card offers "Keep the earlier settings" (`restart(false, true)`) and "Make every chapter again" (overwrite). Resume carries `keep_settings` the way it carries `overwrite` (`card.dataset.keepSettings`).
2. **Generate uses `keep_settings` on both pages (D-910 a).**
   - `generateButtons` posts the one chapter, or the missing ones, with `keep_settings: true` into `states.folder.parent`.
   - `audiobook_folder` finds the project's folder whose parent is that output, so no second folder is made.
   - The app adds the chosen chapters to the ones already made (#765).
3. **Positions (D-909 item 2).**
   - A saved position now keeps `index` and `within`. `placed_position` moves it to its chapter's new place.
   - `save_position` maps a page's `index` and `within` to that place.
   - A pre-#726 position, saved with the legacy stamp (`legacy_book_key`, settings and planned chapters), is still read. Before an adding job starts, `_keep_position_by_chapter` rewrites it with its chapter, so the saved place is not lost.
   - Markers are anchored to the text, not to the stamp, so the change of `book_key` leaves them alone.
4. **The three changed tests:**
   - `test_web_jobs` now checks that `state` is null before any audio.
   - `test_player`'s #472 assertion becomes AC1, under D-910 (b).
   - `test_player`'s keyboard Tab order gains the two Generate buttons.

   Each follows from an accepted decision, and none is weakened.
5. **Tests and CI:**
   - Locally, ruff and format are clean and lint-imports keeps 3 contracts.
   - `tests/unit/test_web_*.py`: 1079 passed, 5 skipped.
   - Chromium, running `test_add_chapters`, `test_player`, `test_download_book` and `test_listen`: 36 passed.
   - CI on c231646 is green: tests on ubuntu, both Chromium shards, ZAP, governance, CodeQL, lint and licences. The report-only Firefox and WebKit jobs are green too.

## Mutation probes

Each mutation was applied alone, against `test_web_add_chapters.py` and the web player, listen and audio tests.

- **Caught (a named test fails):**
  - the position move in `placed_position`, and its fallback;
  - the `index`/`within` mapping in `save_position`;
  - the legacy stamp in `_stamps`;
  - `_keep_position_by_chapter`;
  - the `settings-changed` mapping in `classify`;
  - `keep_settings` passed to `run_audio_job`;
  - `book_key` with `planned` put back;
  - `coming` emptied in `chapter_states`.
- **Survived (168 tests passed each time):** the two below.

## Findings

- **S1** (should-fix, `missing-test`). The vouch in `chapter_states` is untested.
  - With `and all(_vouched(...) ...)` removed, a chapter whose files are recorded counts as "generated" even after they were deleted or edited.
  - The page would then show no Generate button for it, while the app (`_adding`, owned files only) would treat it as not made.
  - Fix: a test that deletes or edits a made chapter's MP3 and then gets `not-generated` for it from `GET /documents/{id}/chapters`, with the Generate button on the project page.
- **S2** (should-fix, `missing-test`). `_kept_settings` in `web/tasks.py` is untested.
  - With `made_with = settings` (the form's settings instead of the kept ones), every test passes.
  - `_note_made` writes `Made` (the voice, the categories switched off and the plugins), and the Listen page uses it to draw the growing book while the job runs (#724). So a Generate under a form that differs from the project's settings would show the growing text with the wrong categories.
  - Fix: a test where the saved form settings differ from the project's (another voice, or a category switched off). A Generate job then writes `made` in `audio.json`, while it runs, with the project's settings.

## Notes

- **N1.** `generateButtons` has no in-flight guard, unlike `bookBoxes` (#768). A double click sends a second POST, which gets 409 busy while the first navigates. It is harmless but noisy. Optional.
- **N2.** `_kept_settings` repeats part of `app.audio._kept`, reading the record's settings for language, voice, categories and plugins. If `made`'s layout changes, both have to change together. Optional: share one reader from `app`.

## Summary

- Done: D-909 and D-910 checked against the code, the changed tests read, the tests run, and twelve mutation probes.
- Not done: none.
- Open: S1 and S2 for round 2. Both are tests only; the code is correct by reading.
