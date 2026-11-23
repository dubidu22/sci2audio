# impl-725: the whole audiobook on demand (#725, LW-03) and the remaining chapters later (#726, LW-04)

Status: **approved (D-903, 4.1: numbers from the book's place). Coding waits for #724's merge (D-902) and goes to a fresh thread.** (critical: output files, the job's reuse and overwrite rules, file names of chapters, a new golden file; `risk:high` for PR 1 and PR 2, CRIT-01, PLAN-02). One open choice (4.1). No code or tests before approval, and none before #724 has merged (D-902).
Written 2026-11-23 by impl-725 (Opus 5.5 high) on main at 9f622af (after #723's PR B #761), on top of `plans/impl-724-plan.md` as D-902 asks (section 2.4). Batch: `plans/batch-005.md`, slot A.

## 1. What changes

### #725 (LW-03): download the whole audiobook, built on request

- The web job stops writing the M4B (the D-895 line in `web/tasks.py` goes). A job writes the chapter MP3s, their subtitles and the read-along file, as #723 made it.
- The library row and the Listen page offer "Download audiobook": M4B (one file with chapter marks, cover and tags as today, #69) or MP3 (one file with ID3 `CHAP`/`CTOC` chapter marks, same cover and tags).
- The file is built from the chapter audio already made: the chunk WAVs in the project's cache, placed on the same timeline the job used. Nothing is spoken again. So the M4B is the M4B today's job writes for the same chapters, byte for byte in one run.
- Only generated chapters go in. When chapters the person chose are missing, the dialog names them and still offers the ready ones, as a file named partial.
- The built file is kept in the project's audiobook folder and recorded with the chapters it holds (their fingerprints). A second download reuses it. Once chapters are added (LW-04), the record no longer matches and the next download builds it again.
- Building is a cancellable job with progress, like the audio job. A cancel or failure leaves no half file (output's `.partial` then rename, vouched first as in #723).

### #726 (LW-04): generate the remaining chapters later

- Every chapter of the book is listed on the project page and the Listen page with its state: generated, being generated, not generated. A not-generated chapter has "Generate"; the project has "Generate the remaining chapters".
- Adding chapters is an audio job in the same project, whose chapters are the generated ones plus the new ones. The generated chapters are reused as #723's resume reuses them (record, size, SHA-256, fingerprint): never spoken, never encoded again.
- Chapter numbers stop depending on which chapters were chosen (4.1), so a chapter's file name, track tag and fingerprint stay the same when others are added.
- If the voice, speed or text settings differ from the ones the generated chapters were made with, the job is refused before any speech with a clear message, and the person chooses: keep the old settings for the new chapters, or regenerate all. Nothing is mixed silently.
- Chapters play and export in document order, whatever order they were generated in (the job plans them in document order; the read-along file and the built file follow it).
- CLI: `sci2audio convert <file> --chapters …` on a project that has generated chapters adds only the missing ones. With other settings it exits 7 and names the two choices: `--keep-settings` or `--overwrite`.

## 2. Design

### 2.1 Output lane (`src/sci2audio/output/`)

- `chapters.py`:
  - `BookWriter` takes each planned chapter's number and the book's chapter count (`numbers: Sequence[int] | None, count: int | None`; default: 1..n of n, so every caller and every file today stays as it is). Chapters must still come in increasing number order.
  - `write_book_file(job_folder, target, chapters: Sequence[ChapterAudio-like (number, title, spoken)], book, settings, kind: BookKind, *, ffmpeg, vouch, replace: bool) -> Path`: one file of the whole book (or of the chapters given), from the chunk files, on the same timeline `BookWriter` plans. `BookKind.M4B` uses today's `_m4b_args` and `_ffmetadata` unchanged (so it is today's M4B). `BookKind.MP3` adds `_book_mp3_args`: libmp3lame at `settings.mp3_bitrate`, `-id3v2_version 3`, `-map_chapters 1` from the same ffmetadata (ffmpeg's MP3 muxer writes `CHAP` and `CTOC` frames from it), the book's tags and cover as the chapter MP3s carry them. Same `.partial`, vouch and rename as every other file. With subtitles on, the M4B build also writes the book's `.srt`/`.vtt` pair, as `finish` does.
  - `finish` uses `write_book_file` for its M4B, so both stay one path.
- `write.py`: `audiobook_targets` takes the numbers and the count too (default as today); `book_file_name(book_title, kind, partial: bool)`: `<book>.m4b`, `<book>.mp3`, `<book> (partial).m4b`, `<book> (partial).mp3`, retried like the other names (#493). The `<book>.mp3` name cannot meet a chapter file (`<book> - 01 …mp3`).
- `model.py`: `BookKind` (StrEnum m4b, mp3). `__init__.py` exports.

### 2.2 App lane (`src/sci2audio/app/`) and CLI

- `audio.py`:
  - Numbers (4.1): `_BookPlan.number(index)` is the chapter's place among the **book's** chapters that have something to say (document order), and the count is their total; `prepare_script` already runs the text steps on the whole document (`app/script.py:83`), so `script.py` gains `speakable(result) -> tuple[int, ...]`, which cuts the utterances of the chapters not chosen without speaking them.
  - Custom order (#119, chosen chapters in another order than printed): numbers stay as today (among the chosen, in the chosen order), and the record says so (`"order": "chosen"`). Adding chapters to such a project is refused with the message to regenerate all; that keeps #119's files as they are.
  - The settings key (#723's `settings_key`) leaves out the chapter choice, so adding chapters is the same settings. The record also keeps the settings themselves (`settings_data`, voice id and version, output settings), not only their hash, so "keep the old settings" can rebuild them.
  - Adding chapters: when the record is complete and has the same key, the job plans the union of the recorded chapters and the chosen ones, in document order; recorded chapters are reused as a resume reuses them; only the new ones are spoken. A finished audiobook is still refused without `overwrite` when nothing new is chosen (D-163; `test_running_again_reuses_every_sentence` stays).
  - Other settings than the record's: `SettingsChangedError(OutputExistsError)` with the old and new settings named, before any speech; `keep_settings=True` runs the new chapters with the record's settings; `overwrite=True` regenerates all, as today.
  - Each committed chapter also writes `spoken/<index>.json` (its chunks: file, duration, span, pause, text, join) in the working folder, its SHA-256 in the chapter's record entry, vouched before the chapter's files are put in place. The build (below) needs it, and it spares the build a new text run, whose fingerprint would change with every app update.
- `playable.py`: record version 2: `order`, `settings_data`, each chapter's `spoken` hash, and `built: [{name, bytes, sha256, kind, chapters: [fingerprints]}]`. Version 1 records still read (they hold no built files and no settings data: adding chapters to them asks for `overwrite` or `--keep-settings` is refused with that message). `chapter_states(work, out_folder, chapters) -> list[ChapterState]` (generated, not generated; "being generated" is the web's from the running job's `playable` and current chapter).
- `book.py` (new): `build_book(work, out_folder, kind, *, progress, cancel, ffmpeg) -> BuiltBook`. Under the working folder's lock: reads the record and each playable chapter's `spoken` file, checks every chunk file is in the cache, reuses a recorded built file whose chapters and hash still match, otherwise writes it with output's `write_book_file` (vouched in the record first, as #723 does). Progress from ffmpeg's `-progress` time over the book's length; cancel stops ffmpeg (`_CancellableFfmpeg`). A chapter whose chunks were cleaned out of the cache (`clean_work_folder`) is reported as not available, never spoken again. A replaced built file is only ever one the record vouches for (size and SHA-256); any other file of that name is refused (D-163).
- `runner.py`: `run_book(...)` under `_one_job`, as `run_audio`. `__init__.py` exports.
- `cli.py`: `--keep-settings`; the exit-7 message names both choices when the settings differ; `--chapters` on a project with generated chapters adds the missing ones (the job decides; the CLI only passes `keep_settings`). Nothing else in the CLI's output changes.

### 2.3 Web lane (`src/sci2audio/web/`)

- `tasks.py`: the D-895 line goes (`output_settings=OutputSettings()`); `book_work(...)` for the build job; `audio_work` takes `keep_settings`; the built file joins `record_files` (D-750) so removing the project removes it.
- `jobs.py`: `JobKind.BOOK` (cancellable).
- `api.py`, `models.py`: `POST /documents/{id}/book` `{kind, partial_ok}`: 200 with the file's name when a current build exists, 202 with a book job otherwise, 409 `missing-chapters` with their titles unless `partial_ok`; the file is downloaded through the existing `/documents/{id}/audiobook/{name}` (with `Content-Disposition: attachment` when `?download=1`). `GET /documents/{id}/chapters` gains each chapter's state. `POST /jobs` gains `keep_settings`; a settings change answers 409 `settings-changed` with the old and new settings, for the dialog.
- `state.py`: wires `book_work`. `pages.py`, `library.py`: the row's and the Listen page's download data, the project page's chapter states.
- Templates: `index.html` (row action), `listen.html` (download button and dialog; chapter list states), `document.html` (chapter states, "Generate", "Generate the remaining chapters", the settings-changed dialog), `job.html` (book job progress, cancel). `static/app.js`, `static/player.js`, `static/app.css`, `strings/en.toml`, `strings/de.toml`.

### 2.4 On top of #724 (D-902)

What #724's plan adds, and how this plan builds on it. Every PR here starts from main after #724's merge and is rebased on what #724 actually merged; a difference from its plan that touches the points below is reported before coding.

- **Chapter states.** #724's `PlayerView.planned` lists the *chosen* chapters as ready, generating or missing. PR 4 widens it to *every* chapter of the book that has something to say (`app.script.speakable`, PR 2), with the state "not generated" for chapters never chosen, and adds the "Generate" buttons and "Generate the remaining chapters" on that list (Listen page) and on the project page. It reuses #724's `_listen_chapter.html` fragment and `player.js` `ready` handling unchanged: a chapter added later arrives through the same job events as in #724.
- **The book's stamp (#153).** #724's `book_stamp` hashes the settings key and `planned`. Adding a chapter changes `planned`, so the stamp would change and the listening position and markers would be forgotten. PR 4 drops `planned` from the stamp, so it is the settings key only (with PR 2, that key no longer holds the chapter choice). A kept position still has to fit the current read-along file (`Bounds.fits`); a chapter added *before* the position moves its book time, so PR 4 maps a kept position by its chapter and the time inside it (tested). Overwrite (regenerate all) gives a new key, so a new stamp, as for another book today.
- **The growing view while chapters are added.** #723 removes `audio.json` before the first new chapter is committed, and #724's growing view takes over while `chapters.json` says `complete: false`. Adding chapters to a finished project therefore shows the growing view with the generated chapters playable at once, and the finished view again at the end. No new code; PR 4 tests it.
- **The record.** #724 reads `chapters.json` through `app.playable.read_record`. PR 2's record version 2 is read by the same function (version 1 still reads), so #724's code needs no change; PR 2 runs #724's tests unchanged.
- **`audiobook.json`.** #724 writes it at job start with `made`. PR 3 adds nothing to it: the built file is recorded in `chapters.json` (`built`) and in the removal record (`record_files`, D-750).
- **`document.json` early.** #724 writes it before the first chapter. The build (PR 2's `book.py`) does not need it: it reads `spoken/<index>.json` and the chunk cache.
- **`web/tasks.py`.** #724 changes the position removal and the start-of-job record; PR 3 removes the D-895 line and adds `book_work`; PR 4 passes `keep_settings`. Different functions of the same file, after #724's merge.

## 3. How the PRs split (lanes, LANE-02)

| PR | Lanes | Files | Closes | Critical |
|---|---|---|---|---|
| **1** `output: the whole book as one M4B or MP3, and chapter numbers from the book (#725, #726)` | lane:output | `output/{chapters,write,model,__init__}.py`; `tests/unit/test_output_book.py` (new), `tests/unit/test_output_chapters.py` (numbers); one new snapshot | none (part of both) | yes |
| **2** `app: build the audiobook on request and add chapters later (#725, #726)` | lane:app, lane:cli | `app/{audio,playable,book (new),script,runner,__init__}.py`, `cli.py`; tests `tests/unit/test_app_book.py`, `test_app_book_faults.py`, `test_app_add_chapters.py`, `test_cli_add_chapters.py` (new), snapshot updates in `test_app_audio_chapters.ambr` and `test_cli_convert.ambr` (4.1); `docs/baseline.md` row | none | yes |
| **3** `web: download the whole audiobook from the library (#725)` | lane:web | `web/{tasks,jobs,api,models,state,pages,library}.py`, `templates/{index,listen,job}.html`, `static/{app.js,app.css}`, `strings/{en,de}.toml`; tests `tests/unit/test_web_book.py`, `tests/browser/test_download_book.py` (new), `test_web_audio.py`, `tests/browser/test_flow.py`, `tests/browser/test_listen.py` (the M4B the web no longer writes), `tests/browser/test_axe.py` | #725 | no |
| **4** `web: generate the remaining chapters later (#726)` | lane:web | `web/{tasks,api,models,pages,player,library}.py`, `templates/{document,listen,_listen_chapter}.html`, `static/{app.js,player.js,app.css}`, `strings/{en,de}.toml`; tests `tests/unit/test_web_add_chapters.py`, `tests/browser/test_add_chapters.py` (new), `tests/unit/test_web_listen_growing.py` (the stamp without `planned`, 2.4), `tests/browser/test_axe.py` | #726 | no |

- Order: 1, then 2 (imports 1), then 3, then 4. One PR per lane per issue; 3 and 4 stay apart because each can be reviewed and merged on its own and each closes one issue (D-75).
- **Overlap with #724:** settled by D-902: #724 goes first and no PR here starts before it has merged. #724 touches `app/audio.py` (early `document.json`), which PR 2 also changes, and every web file PR 3 and PR 4 touch except `jobs.py`, `models.py`, `state.py`, `index.html`, `document.html` and `job.html`.

## 4. Choices

### 4.1 The one open choice: how chapters are numbered

Today a chapter's number (file name `<book> - 03 Title.mp3`, track tag `3/12`) counts among the chapters chosen for the job. Adding a chapter later would change the number of every later chapter, so its file name and track tag, so it could not be reused as #726 requires.

- **Recommended: number among the book's chapters that have something to say, in document order.** A file never changes once made (people copy them to a phone), and reuse is the #723 resume unchanged. Cost: the track tag's count and, rarely, a number change against today when not every chapter is chosen. The default choice leaves out the reference list (Q6), so most default runs change in the count of the last tag field (`n/12` becomes `n/13`), and the file names change only for a chosen subset with gaps. That changes golden files (`test_cli_convert.ambr`, `test_app_audio_chapters.ambr`), explained in PR 2. A full-book choice stays byte-identical.
- Alternative: keep today's numbers and, when chapters are added, rename and retag the later chapters' MP3s with a stream copy (no speech, no new encoding). No golden change today, but files the person already has change names and bytes, and the reuse check needs a second kind of "same chapter".

### 4.2 Decided in this plan (clearly better than the alternatives)

- **Built from the chunk cache, not from the chapter MP3s.** It is the only way the M4B equals today's job output (the AC's golden comparison) and avoids a second lossy encoding. The cache is the project's own and is kept; after a manual clean the chapter is named as not available.
- **A chapter's chunks are kept as `spoken/<index>.json`**, not found again by a new text run: after an app update the text run's fingerprint differs, and the download would fail for every older project.
- **The built file lives in the project's audiobook folder**, not in the working folder: the person finds it next to the MP3s, and removing the project removes it (D-750).
- **Custom order (#119) projects are not extended**: their numbers are their order; mixing in document numbers would break it. The person can regenerate them.
- **The book's subtitles come with the built M4B** (as today's M4B brings them), not with the MP3 build.

## 5. Tests (TST-01; node IDs repeated in each PR body)

### PR 1 (output)
Characterisation first, green on main: `tests/unit/test_output_book.py::test_finish_writes_the_m4b_it_wrote_before_the_book_file_split`.
- `tests/unit/test_output_book.py::test_the_book_m4b_is_byte_identical_to_the_one_finish_writes`
- `tests/unit/test_output_book.py::test_the_book_mp3_has_a_chapter_mark_at_each_chapter_start` (ffprobe chapters equal the M4B's within one MP3 frame)
- `tests/unit/test_output_book.py::test_the_book_files_carry_the_tags_and_cover_of_the_chapter_files`
- `tests/unit/test_output_book.py::test_the_chapter_marks_and_tags_of_the_book_files` (syrupy: ffprobe chapters, durations, tags of both kinds; times rounded to the millisecond, the new golden file)
- `tests/unit/test_output_book.py::test_a_failing_book_build_leaves_no_partial`
- `tests/unit/test_output_book.py::test_a_partial_book_is_named_partial`
- `tests/unit/test_output_chapters.py::test_given_numbers_name_and_tag_the_chapters`
- `tests/unit/test_output_chapters.py::test_numbers_left_out_keep_every_file_as_before`
- `tests/unit/test_output_chapters.py::test_a_chapter_added_between_two_others_leaves_their_files_unchanged` (Hypothesis: any set of numbers, any order of adding)

### PR 2 (app, CLI)
Characterisation first: the existing `test_cli_convert.py::test_convert_writes_the_same_files_as_before_chapters_became_playable_early` and `test_app_audio_chapters.py` snapshots, green on main before the change; their changes under 4.1 are explained in the PR.
- `tests/unit/test_app_book.py::test_the_built_m4b_equals_the_m4b_of_a_job_for_the_same_chapters`
- `tests/unit/test_app_book.py::test_a_second_build_reuses_the_file`
- `tests/unit/test_app_book.py::test_the_file_is_built_again_after_chapters_are_added`
- `tests/unit/test_app_book.py::test_only_generated_chapters_go_in_and_the_missing_are_named`
- `tests/unit/test_app_book.py::test_nothing_is_spoken_to_build_the_book`
- `tests/unit/test_app_book.py::test_a_chapter_whose_cache_was_cleaned_is_named_not_available`
- `tests/unit/test_app_book.py::test_a_file_of_that_name_not_from_this_project_is_refused`
- `tests/unit/test_app_book.py::test_the_build_reports_progress_and_stops_on_cancel`
- `tests/unit/test_app_book_faults.py::test_a_build_killed_midway_leaves_no_half_file_and_builds_again` (subprocess SIGKILL)
- `tests/unit/test_app_book_faults.py::test_a_full_disk_while_building_leaves_no_half_file`
- `tests/unit/test_app_book_faults.py::test_a_chunk_removed_during_the_build_fails_with_a_message`
- `tests/unit/test_app_book_faults.py::test_a_build_runs_with_the_network_blocked`
- `tests/unit/test_app_add_chapters.py::test_adding_a_chapter_speaks_only_it`
- `tests/unit/test_app_add_chapters.py::test_generated_chapter_files_stay_byte_identical_when_others_are_added`
- `tests/unit/test_app_add_chapters.py::test_chapters_play_in_document_order_whatever_order_they_were_made`
- `tests/unit/test_app_add_chapters.py::test_other_settings_are_refused_before_any_speech_and_name_the_choice`
- `tests/unit/test_app_add_chapters.py::test_keep_settings_makes_the_new_chapters_with_the_old_settings`
- `tests/unit/test_app_add_chapters.py::test_overwrite_regenerates_every_chapter`
- `tests/unit/test_app_add_chapters.py::test_a_finished_audiobook_with_nothing_new_is_still_refused`
- `tests/unit/test_app_add_chapters.py::test_a_custom_order_project_is_not_extended`
- `tests/unit/test_app_add_chapters.py::test_a_version_1_record_reads_and_asks_for_a_choice`
- `tests/unit/test_app_add_chapters.py::test_a_job_killed_while_adding_a_chapter_resumes_and_keeps_the_others` (subprocess SIGKILL, then resume)
- `tests/unit/test_cli_add_chapters.py::test_convert_with_more_chapters_adds_only_the_missing`
- `tests/unit/test_cli_add_chapters.py::test_convert_with_other_settings_exits_7_and_names_keep_settings`
- `tests/unit/test_cli_add_chapters.py::test_convert_with_keep_settings_adds_with_the_old_settings`
- Benchmark: `tests/unit/test_app_book_speed.py::test_time_to_build_the_whole_book` (`@pytest.mark.benchmark`), row in `docs/baseline.md`.

### PR 3 (web, #725)
- `tests/unit/test_web_book.py::test_a_book_job_builds_the_file_and_the_download_serves_it`
- `tests/unit/test_web_book.py::test_a_current_build_is_served_without_a_job`
- `tests/unit/test_web_book.py::test_missing_chapters_answer_409_unless_partial_is_asked`
- `tests/unit/test_web_book.py::test_a_book_job_can_be_cancelled`
- `tests/unit/test_web_book.py::test_the_audio_job_writes_no_m4b`
- `tests/unit/test_web_book.py::test_removing_the_project_removes_the_built_file`
- `tests/browser/test_download_book.py::test_download_the_audiobook_from_the_library_row`
- `tests/browser/test_download_book.py::test_download_from_the_listen_page_with_missing_chapters_names_them`
- `tests/browser/test_download_book.py::test_the_build_shows_progress_and_cancels`
- `tests/browser/test_axe.py` gains the dialog.
- Schemathesis (`test_web_schemathesis.py`) covers the new endpoint through the schema, unchanged.
- Changed, with reason (the web no longer writes the M4B in the job): `test_web_audio.py` (around lines 74, 86), `tests/browser/test_flow.py:162`, `tests/browser/test_listen.py:535` now download the built file instead.

### PR 4 (web, #726)
- `tests/unit/test_web_add_chapters.py::test_the_chapters_list_their_states`
- `tests/unit/test_web_add_chapters.py::test_generate_one_chapter_starts_a_job_in_the_same_project`
- `tests/unit/test_web_add_chapters.py::test_generate_the_remaining_chapters_chooses_every_missing_one`
- `tests/unit/test_web_add_chapters.py::test_changed_settings_answer_409_with_both_settings`
- `tests/unit/test_web_add_chapters.py::test_keep_settings_starts_the_job_with_the_old_settings`
- `tests/unit/test_web_add_chapters.py::test_the_stamp_stays_when_a_chapter_is_added`
- `tests/unit/test_web_add_chapters.py::test_a_position_after_an_added_chapter_keeps_its_place_in_its_chapter`
- `tests/unit/test_web_add_chapters.py::test_adding_to_a_finished_project_shows_the_growing_view_until_done`
- `tests/browser/test_add_chapters.py::test_generate_a_chapter_from_the_project_page_and_listen_while_it_is_made`
- `tests/browser/test_add_chapters.py::test_the_settings_changed_dialog_offers_both_choices` (keyboard only)
- `tests/browser/test_axe.py` gains the project page with chapter states and the dialog.

Runs: the fast checks before each PR, `uv run pytest -m browser` for 3 and 4, `ci:full` before review on 1 and 2 (critical, D-698), mutation on the final round of 1 and 2 (`output/chapters.py`; `app/book.py`, `app/playable.py`, the add path of `app/audio.py`; INV-09), corpus comparison on a local merge of main (INV-07): full-book CLI output byte-identical; default-choice output differs only as 4.1 says.

## 6. Licence, risk, size

- No new dependency, file, model or text. The MP3 chapter frames come from the bundled ffmpeg; PR 1's first test proves it on all three systems (`ci:full`). If it cannot, I report a question before going on.
- Risks: (1) numbering change (4.1), golden diff explained; (2) a replaced built file not ours: refused unless the record vouches for it; (3) a v1 record from #723: read and handled, tested.
- Size: PR 1 about 200 lines of code, 300 of tests; PR 2 about 450 and 700; PR 3 about 350 and 350; PR 4 about 300 and 300.

## 7. Out of scope

- The live chapter list and "Start listening" during a job: #724 (PR 4 adds the "not generated" state and the Generate buttons on top of it).
- A CLI command to build the whole-book file on request: not asked; the CLI still writes the M4B in the job. A new Issue if wanted.
- Subtitles inside the book MP3: no player reads them; not asked.

## Handoff (THR-07)

- Goal: plan #725 (LW-03) and #726 (LW-04) and get it approved.
- Done: this plan, from main 9f622af (`web/tasks.py`, `app/audio.py`, `app/playable.py`, `app/script.py`, `output/chapters.py`, `output/write.py`, `output/names.py`, web routes, `cli.py`).
- Next: the coordinator decides 4.1 and approves; after #724 merges (D-902), rebase this plan's 2.4 on what merged, then PR 1. Per THR-07 the coding may go to a fresh thread started from this handoff, since the wait for #724 is likely longer than an hour.

## Handoff (THR-07), 2026-11-23, after approval

- Goal: #725 (LW-03) and #726 (LW-04) in four PRs (section 3), plan approved as written with 4.1 = number chapters by their place among the book's speakable chapters (D-903).
- Done: plan only (this file, on main 9f622af and `impl-724-plan.md`). No branch, no code, no tests, no Issues opened.
- Next (fresh implementation thread, Opus 5.5 high): wait until #724 has merged (D-902). Then read #724's merged diff against section 2.4 and report any difference that touches it before coding. Then PR 1 (output, `risk:high`, characterisation test first: `test_finish_writes_the_m4b_it_wrote_before_the_book_file_split`), `ci:full` before review; PR 2 after PR 1 merges; PR 3 and PR 4 after PR 2.

Tried and ruled out, with evidence:
- Numbering among the chosen chapters (today): adding a chapter renames and retags every later chapter's MP3, so #726's "finished chapter files are reused" fails. Rename and retag by stream copy was the alternative; D-903 chose the book's numbering.
- Building the book from the chapter MP3s: a second lossy encoding, and the M4B would not equal today's job output (#725 AC golden comparison). Built from the chunk cache instead.
- Finding a chapter's chunks again with a new text run: `chapter_fingerprint` holds `__version__`, so after any app update every older project's download would fail. `spoken/<index>.json` per chapter instead.
- `settings_key` today holds `settings_data(settings)`, which includes `chapters` (`app/job.py:164`): adding chapters would read as changed settings. PR 2 leaves the chapter choice out of the key.
- Text steps run on the whole document (`app/script.py:83`), so a chapter's script doesn't depend on the chapter choice. A later chapter's chunks match the cache.
- Unchecked: whether the bundled ffmpeg writes ID3 `CHAP`/`CTOC` frames for the book MP3 on all three systems. PR 1's first test and `ci:full` settle it; if it cannot, report a question.
