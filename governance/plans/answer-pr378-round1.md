# Answer to review PR #378, round 1

New head: 5d8e520. It merges main 514dc2f (#373) and adds #376, the listen jobs' position save, and the round 1 fixes. The fixes are in commit 5d8e520; #376 is 1898378; the merge is 0cd6ad6.

## Fixed

- **S1.**
  - `OutsideJob.id` is now `cli-<file id>`; `DocumentStore`'s id pattern never matches it. `ServerState.listening` resolves a `cli-` key only to an outside job and any other key only to the store.
  - `Listening` carries both the key (`id`, used in addresses and the page's data) and the file id (`document`, used for every record check). The listen page, the audiobook route and the position route use them that way.
  - Tests (`test_web_outside.py::test_a_file_also_opened_in_the_interface_keeps_the_two_apart`, with the same PDF uploaded to the web store):
    - the `cli-` link plays the command line's audiobook and serves its files;
    - the web document's own listen page says "no audiobook" and serves nothing;
    - `/documents/<file id>/listen` does not reach the outside job (also in `test_the_listen_page_shows_a_command_line_job`).
  - The store-first mutant fails that test.
- **S2.**
  - `test_the_web_record_of_a_folder_is_not_tried`: a valid `audiobook.json` in the job's working folder names the folder holding the files, and the named folder is empty. M2 (`(recorded_folder(job.work, job.document), job.folder)`) fails it.
  - `test_the_settings_output_folder_is_not_tried`: the server's settings file names that folder. M3 (`(job.folder, saved.output_folder)`) fails it.
  - Both check that the listen page has no `player-data` and that every file gives 404.
- **N1.** `test_cli_listen.py::test_a_missing_document_record_is_refused`: with `document.json` removed, `listen` exits 1 with "can't be read" and does not start the server. M5 fails it.
- **N2.**
  - New `app.file_id(source)`: SHA-256 in 1 MB blocks, first 16 hex digits, cached per file version (identity, time and size). `default_work_folder` uses it, so `listen` reads the file once with the default work folder and never holds it in memory.
  - Test: the id follows a file replaced under the same name, time and size.
- **N3.** The CHANGELOG and the PR body now describe the code: every chapter in the list has the buttons, drawn `hidden` and shown once `app.js` has bound them, and only the title in each button's name is visually hidden. The behaviour is unchanged.

## Added with main merged in

- **#376.**
  - The report JSON gets a `publisher` flag per chapter. The golden `test_app_corpus.ambr` gains `'publisher': False` on each chapter of the three PDF papers (29 lines, nothing else).
  - `ChapterOut.publisher` defaults to false for a report written before the flag existed (tested).
  - The hint "publisher's page, not read by default" (de: "Verlagsseite, standardmäßig nicht vorgelesen") appears in the chapter list.
  - `browser/test_publisher_pages.py` on the Time Machine: Imprint, Colophon and Uncopyright show the hint, stay unticked and can be ticked; the title page, I, Epilogue and Endnotes don't show it; axe passes in light and dark.
  - `test_app_job` checks the flags in the report JSON.
- **#153 for listen jobs.**
  - The position POST resolves the job through `listening` (the `cli-` key) and writes `position.json` into the job's own working folder, with the token, origin and stamp (409) checks unchanged. Nothing is written into the output folder or the web's work root.
  - Test: `test_an_outside_job_keeps_its_position_in_its_own_working_folder` (204, a resume offer on the next run, 409 with another stamp, 404 for an unknown key).

## Checks on 5d8e520

- ruff, format, lint-imports (3 kept) and deptry: clean.
- Fast suite: 5628 passed, 1 skipped.
- Browser suite: 69 passed, 1 skipped (#365).
