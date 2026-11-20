# Review PR #378, round 2 (v1.1 player wins, PR B: #119, #154, #376)

Head reviewed: 5d8e520. It merges main 514dc2f (#373) in 0cd6ad6, adds #376 in 1898378, and the round 1 fixes in 5d8e520. Critical. Answer: plans/answer-pr378-round1.md.

**Verdict: approvable at 5d8e520.** No blocker and no should-fix. One nit (N1) is a test gap, deferred to an issue. Heavy checks are done: three systems green, the nightly Hypothesis profile, and mutation probes.

## Round 1 items, each re-checked

- **S1, fixed.**
  - `OutsideJob.id` is now `cli-<file id>`. `listening()` sends a `cli-` key only to the outside jobs and any other key only to the store. `Listening.document` carries the file id for every record check: the listen page, the audiobook route and the position route.
  - My round 1 reproduction is now the test `test_a_file_also_opened_in_the_interface_keeps_the_two_apart`. With the same PDF in the web store, the `cli-` link plays and serves the command line's audiobook. The web document's own page says "no audiobook" and serves nothing. `/documents/<file id>/listen` gives 404.
  - Mutants: the key equal to the file id (M7) is killed, and an outside fallback behind the store lookup (M8) is killed.
- **S2, fixed.**
  - `test_the_web_record_of_a_folder_is_not_tried` kills M2, the recorded `audiobook.json` folder. It also asserts that the record is valid, so the test is not vacuous.
  - `test_the_settings_output_folder_is_not_tried` kills M3, the saved folder.
  - M1 (the web's whole folder list) and M4 (the default folder) are still killed.
- **N1, fixed.** `test_a_missing_document_record_is_refused` kills M5.
- **N2, fixed.** `app.file_id` hashes in 1 MB blocks and is cached on (path, inode, mtime_ns, size); `default_work_folder` uses it. With the default work folder, `listen` reads the file once and never holds it in memory. The test covers a file replaced under the same name, time and size.
- **N3, fixed.** The PR body and the CHANGELOG now say every chapter has the buttons, drawn `hidden` until bound.

## #376 and the main merge, as new code

- **Report JSON:** a `publisher` flag per chapter. The golden diff is exactly 29 `+ 'publisher': False,` lines in `test_app_corpus.ambr`, on the three PDF papers, and nothing else. The report format stays sci2audio-report v1, because the key is additive (for the KB). `ChapterOut.publisher` defaults to false, so older reports still read.
- **Hint:** shown in en and de, next to the reference-list hint. Removing it from the template fails `browser/test_publisher_pages.py`. That test checks Time Machine chapters 2, 17 and 18 show the hint, stay unticked and can still be ticked, and that the title page, I, Epilogue and Endnotes are ticked without it.
- **Position (#153) for a listen job:** `save_position` resolves through `listening()`, keeps the 409 stamp check, and writes `position.json` only into the job's working folder (the command line's cache folder), never into the output folder or the web's work root. Tested: 204, a resume offer on the next server run, 409 for another stamp, 404 for an unknown id.
- **Merge 0cd6ad6:** #373's position route, stamp check and speed control are intact. `test_web_position` and the browser speed and position tests pass.

## Checks on 5d8e520

- ruff, format, lint-imports (3 kept) and deptry: clean. No dependency change (uv.lock and pyproject unchanged).
- Fast suite: 5628 passed, 1 skipped.
- Browser suite (Chromium): 69 passed, 1 skipped (#365).
- Nightly Hypothesis profile on test_app_script, test_app_settings, test_app_chapters and test_web_chapter_order: 148 passed.
- Mutation probes: M1, M2, M3, M4, M5, M7 and M8 are killed. M9 (no hint) is killed by the browser test.
- CI on 5d8e520: every check run succeeded, including `tests (ubuntu-latest)`, `tests (macos-latest)`, `tests (windows-latest)`, the browser job, ZAP, CodeQL and "CI passed". I added `ci:full`.
- Commit messages carry no closing keywords. The PR body closes #119, #154 and #376.

## Nit, deferred (file an issue, v1.1, lane:app)

**N1. #376's browser test runs axe in light mode only.** The issue asks for light and dark, and the answer file says both. Dark is checked on the document page with hints in `test_chapter_order` (same `.hint` class), so the risk is low. Fix: add `page.emulate_media(color_scheme="dark")` and a second `check_axe` to `test_publisher_pages.py`.

## Merge

- Squash, pinned to `sha=5d8e520`, with an explicit commit message.
- Title: `app, cli, web: choose the chapter order, open a command-line audiobook in the player, name publishers' pages (#119, #154, #376)`.
- Body: Closes #119, #154, #376.
- If main has moved, update the branch by a merge first, then wait for CI.

## For the KB

- `listen` key `cli-<file id>`.
- Outside jobs are served only from the named output folder, never the recorded, saved or default one.
- `listen` opens the start page; exit codes 3 and 1.
- Report v1 gains the additive `publisher` flag.
- A listen job's position lives in its own working folder.

## Correction (15 Nov 19:05 UTC)

N1 was wrong. `check_axe` in `tests/browser/conftest.py:226-232` already runs axe in light mode, then dark mode, then back, so `test_publisher_pages.py` is covered in both. #380 is closed as not planned.
