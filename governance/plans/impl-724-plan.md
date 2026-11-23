# impl-724 plan: start listening when the first chapter is ready (#724, LW-02)

Thread impl-724 (implementation, Opus 5.5 high), batch 005 slot B item 3. Written 2026-11-23
on main 9f622af (#723 merged: #754 f1a9c1f, #761 9f622af). Status: **approved as D-902** (choice A,
critical, `risk:high`, #724 before #725/#726; a kill fault test added).

## 0. What #723 left and what is missing for the web

#723 gives, per job: each chapter's MP3 (and subtitles) in the project's audiobook folder as
soon as it is spoken; the read-along file rewritten after each chapter (the chapters so far,
in job order, on one timeline whose earlier part never moves); `chapters.json` in the working
folder (`planned`, the playable `chapters` with their files, size and SHA-256; `settings`
key); `AudioProgress.ready` / `.playable` on the job's events.

The Listen page cannot use any of it yet:

1. `player_for` needs `audio.json` and `document.json`. The audio job removes both at its
   start (`app/audio.py::_remove_old_records`, D-119) and writes them only at the very end.
   Without `document.json` there is no text to read along.
2. `locate` / `_agrees` demand that the read-along file agrees with `audio.json` (duration,
   chunk count, MP3 list); mid-run there is no `audio.json`.
3. The listening position (#153) is stamped with the read-along file's hash, which changes
   after every chapter, and `web/tasks.py` removes the position when the job ends.
4. `audiobook.json` (where the audiobook is) is written only at the end; mid-run the folder is
   found through `project.json` (written before the job writes anything, D-749), so that is
   fine.
5. The job card (`_making.html`) offers "Listen" only once the job is done.

## 1. The open choice: the laid-out document mid-run (needs lane:app)

The web cannot get the laid-out document without the app: the pre-analysis does not store it,
and laying it out again in the web could differ from what the voice reads (wrong highlights).

- **A (recommended): one small app change.** `run_audio_job` writes `document.json` as soon as
  the chapter record of this run exists (after `_check_targets`, before the first chapter is
  spoken), instead of only at the end. `audio.json` stays end-only: it still alone vouches for
  a finished audiobook (D-119 unchanged for it). A failed rerun now leaves this run's
  `document.json` beside the whole chapters it kept, which is what the growing view needs to
  play them. About 15 lines in `app/audio.py`, one new test, one existing test adjusted (see 5).
  The PR then carries `lane:web` and `lane:app`.
- B: web-only. The web lays the document out again from the source with the job's settings.
  Refused: duplicate work, and a document that differs from the spoken one gives wrong
  highlights (the player only checks that spans lie inside blocks).
- C: split into an app PR first, then the web PR. More review rounds for 15 lines; only worth
  it if the coordinator wants the app change reviewed as critical on its own.

Criticality (CRIT-01): I judge the PR **not critical**. No layer contract, no core dataclass,
no golden file (the records snapshot `test_app_audio_job.py::test_the_records_snapshot` is byte
unchanged: same content, written earlier), no user file deleted or overwritten (`document.json`
is in sci2audio's working folder), no network. It touches the job runner that #723 called
critical, so the coordinator may rule otherwise; then `risk:high`, `ci:full` before review,
up to four rounds.

## 2. Design (web)

### 2.1 The growing view (`web/player.py`)

- `GrowingRecord`: read from `app.playable.read_record(work)` (web may import app): the
  record must say `complete: false`, name at least one playable chapter, and name the
  read-along file among its `book` files. Read strictly like the other records; anything
  else means "no growing audiobook".
- `locate_growing(work, document_id, folders)`: the first candidate folder (same list as
  today, `candidate_folders`) where the read-along file matches its record entry (size and
  SHA-256, `RecordedFile.matches`), its chapters' MP3s are exactly the playable chapters'
  MP3s in order, and every playable chapter's files are there (`playable_chapters`). Same file
  checks as `locate` (`in_folder`: bare names, no link out of the folder).
- `player_for` tries the finished audiobook first (unchanged); only when `audio.json` is
  missing **and** a growing record exists does it build the growing view. The edit marks use
  the job's switched-off categories and plugin ids, which the web knows: `web/tasks.py`
  writes them into `audiobook.json` at job **start** (optional key `made`: `voice`,
  `switched_off`, `plugins`; version stays 1, older readers ignore it, a broken `made` reads
  as no growing view). The finished view keeps reading `audio.json`, unchanged.
- `PlayerView` gains `planned` (every chosen chapter: index, title, state `ready` /
  `generating` / `missing`) and `growing: bool`. Titles of chapters not yet ready come from
  `find_chapters(document)` on the early `document.json`. States: ready = playable; while an
  audio job of this document runs, the others are `generating`; otherwise `missing`
  ("not generated": the job was paused, cancelled or failed).
- `chapter_slice(view, n)`: one chapter's blocks, chunks (global chunk indices), sentences,
  its start and offset on the timeline, for the page to append (2.3).
- Files: `audiobook_file` serves, in growing mode, only the files the growing record names
  for playable chapters plus the read-along file, after `locate_growing`.

### 2.2 One stamp for a book that grows (#153)

`book_stamp(work, document_id, readalong_path)`: when `chapters.json` exists and names this
read-along file, the stamp is the first 16 hex digits of SHA-256 over (`settings` key,
`planned`); else the read-along file's hash as today (every audiobook made before #723). So
the stamp stays the same while the book grows and after it is finished, and a position kept
mid-run still fits at the end (`Bounds.fits` / `continues` still check it against the current
read-along file). Used by the Listen page, `save_position` and the markers API (`api.py`),
and the library shelf (`library.heard`). `web/tasks.py` then removes the position at the end
of a job only when its stamp differs from the book's stamp (a different book), not
unconditionally.

### 2.3 The pages

- **Job card** (`_making.html`, `pages.making_card`, `app.js`): while running, once
  `playable` is non-empty, a "Start listening" link to `/documents/{id}/listen` (drawn by the
  server if already playable when the page is drawn; shown by `app.js` on the first `ready`
  event). Each `ready` event says "Chapter N is ready: <title>" in the existing
  `#job-status` live region.
- **Listen page** (`listen.html`, new `_listen_chapter.html` macro shared with the fragment):
  - the chapter list shows every planned chapter with its state; ready ones are links that
    play, the others are plain text with "being generated" or "not generated";
  - the page's data block names the running job's events URL; `player.js` follows that
    stream (`EventSource`, same origin) and on each `ready` fetches
    `GET /documents/{id}/listen/chapters/{n}` (new HTML fragment route in `pages.py`, its
    data in a JSON block inside it): the chapter's text with its chunk elements, appended in
    order; `data.chapters`, `data.chunks`, `data.sentences`, the duration and the dock's
    ticks grow in place. If the fragment's first chunk index is not the page's chunk count
    (the book changed under it), the page reloads instead of guessing;
  - on `done` / `failed` / `cancelled` / `paused` the remaining chapters turn "not
    generated" (or all ready on done); a later visit shows the finished view;
  - announcements: "Chapter N is ready" in a polite live region (once per chapter, not per
    chunk).
- **Continuing at a chapter's end** (`player.js`, the `ended` handler, mp3 mode): next chapter
  ready → plays it, as today; not ready → the player pauses and shows (and announces) "The
  next chapter is still being generated"; when its `ready` arrives the player loads and plays
  it on its own, unless the person paused or moved meanwhile.
- **Markers** (#474): placed against the chunks so far; the fragment carries the markers it
  places, so a marker in a chapter that just arrived gets its sentence. A marker in a chapter
  not ready keeps the existing "not in the audiobook" state until then.
- Read-along, speed, keyboard and the position save work unchanged on the growing view; the
  position save uses the stamp of 2.2.

### 2.4 Out of scope (they are #725 / #726)

Download of the whole book (#725). Chapters that were never chosen, "Generate" buttons,
settings changed between runs (#726). My chapter list shows chosen chapters only; #726 adds
the unchosen ones with their state and buttons on top of it.

## 3. Files I will touch

App (lane:app; only with choice A):
- `src/sci2audio/app/audio.py`: write `document.json` early (1).

Web (lane:web):
- `src/sci2audio/web/player.py`: growing record and view, `book_stamp`, `chapter_slice`,
  growing-aware `audiobook_file`, `made` in `audiobook.json`.
- `src/sci2audio/web/pages.py`: listen page growing branch and running-job lookup; fragment
  route; job card "Start listening".
- `src/sci2audio/web/api.py`: position and markers use `book_stamp`.
- `src/sci2audio/web/tasks.py`: write `audiobook.json` (folder + `made`) at job start; remove
  the position only for a different book.
- `src/sci2audio/web/library.py`: `heard` with `book_stamp` and the growing view (Listen tab
  and shelf during the run).
- `src/sci2audio/web/templates/listen.html`, `src/sci2audio/web/templates/_listen_chapter.html`
  (new), `src/sci2audio/web/templates/_making.html`.
- `src/sci2audio/web/static/player.js`, `src/sci2audio/web/static/app.js`,
  `src/sci2audio/web/static/app.css`.
- `src/sci2audio/web/strings/en.toml`, `src/sci2audio/web/strings/de.toml`.

Tests:
- `tests/unit/test_app_audio_chapters.py` (lane:app), `tests/unit/test_app_audio_faults.py`
  (one existing test adjusted, 5).
- `tests/unit/test_web_listen_growing.py` (new), `tests/unit/test_web_audio.py`,
  `tests/unit/test_web_player.py`.
- `tests/browser/test_listen_growing.py` (new), `tests/browser/conftest.py` (a fake voice
  that waits at a gate between chapters, if the existing `FakeVoice` cannot).

Not touched: `core`, `output`, `.github/**`, `pyproject.toml`, `uv.lock`, snapshots, corpus,
regression cases. No new dependency. Nightly already runs every browser test in Chromium,
Firefox and WebKit (D-259), so no workflow change.

**Overlap for LANE-02:** #725/#726 (lane:app, lane:web) will very likely touch
`web/pages.py`, `web/player.py`, `web/api.py`, `listen.html`, `player.js`, the strings files,
and (#726) `app/audio.py`. The chapter list and its states are shared ground with #726 AC 1.
I recommend #724 first, then #726 builds its "Generate" buttons on the states from 2.1, and
#725 after or beside #726 only if its files are disjoint.

## 4. Tests promised (pytest node IDs)

App:
- `tests/unit/test_app_audio_chapters.py::test_the_laid_out_document_is_written_before_the_first_chapter_is_playable`
  (named "..._is_spoken" before coding: the document is written where the old records are
  removed, just before the first chapter's files are put in place, so an old `audio.json`
  never stands beside a new `document.json`; see 7)
- `tests/unit/test_app_audio_chapters.py::test_audio_json_is_still_written_only_at_the_end`
- `tests/unit/test_app_audio_faults.py::test_a_kill_after_the_document_is_written_resumes_without_overwrite`
  (D-902 ruling 2)

Web, unit (TestClient where a route is involved):
- `tests/unit/test_web_listen_growing.py::test_the_listen_page_plays_the_first_chapter_while_the_job_runs`
- `tests/unit/test_web_listen_growing.py::test_the_chapter_list_shows_every_planned_chapter_with_its_state`
- `tests/unit/test_web_listen_growing.py::test_chapters_not_ready_read_not_generated_once_the_job_stopped`
- `tests/unit/test_web_listen_growing.py::test_the_chapter_fragment_continues_the_chunk_numbers`
- `tests/unit/test_web_listen_growing.py::test_a_chapter_not_ready_has_no_fragment`
- `tests/unit/test_web_listen_growing.py::test_only_the_recorded_files_of_ready_chapters_are_served`
- `tests/unit/test_web_listen_growing.py::test_a_readalong_file_the_record_does_not_vouch_for_shows_no_growing_view`
- `tests/unit/test_web_listen_growing.py::test_a_broken_or_foreign_chapter_record_shows_no_growing_view`
- `tests/unit/test_web_listen_growing.py::test_the_finished_audiobook_wins_over_a_growing_record`
- `tests/unit/test_web_listen_growing.py::test_the_stamp_stays_while_the_book_grows_and_when_it_is_done`
- `tests/unit/test_web_listen_growing.py::test_a_position_kept_mid_run_is_offered_after_the_job_is_done`
- `tests/unit/test_web_listen_growing.py::test_an_audiobook_without_a_chapter_record_keeps_the_readalong_stamp`
- `tests/unit/test_web_listen_growing.py::test_markers_in_a_chapter_that_just_arrived_get_their_sentence`
- `tests/unit/test_web_audio.py::test_the_job_card_offers_start_listening_once_a_chapter_is_playable`
- `tests/unit/test_web_audio.py::test_the_running_card_hides_start_listening_before_a_chapter_is_playable`
- `tests/unit/test_web_audio.py::test_the_web_record_names_the_folder_and_settings_at_job_start`
- `tests/unit/test_web_audio.py::test_a_job_for_another_book_still_forgets_the_position`

Browser (Chromium on every PR, all three nightly; each with `check_axe`; the existing fence
fails any request outside the test server):
- `tests/browser/test_listen_growing.py::test_start_listening_appears_and_opens_the_first_chapter`
- `tests/browser/test_listen_growing.py::test_a_chapter_that_becomes_ready_appears_without_a_reload`
- `tests/browser/test_listen_growing.py::test_the_player_waits_for_the_next_chapter_and_goes_on_by_itself`
- `tests/browser/test_listen_growing.py::test_chapter_ready_is_announced_and_reachable_by_keyboard`
- `tests/browser/test_listen_growing.py::test_the_position_and_read_along_work_while_the_book_grows`
- `tests/browser/test_listen_growing.py::test_the_growing_listen_page_has_no_axe_problems`

## 5. Existing tests that change, and why

- `tests/unit/test_app_audio_faults.py::test_a_rerun_that_fails_while_encoding_leaves_no_old_record`
  (only with choice A): it asserts the old `audio.json` and `document.json` are gone. After A,
  `audio.json` is still gone; `document.json` is now **this** rerun's (byte-equal to the
  document of a clean run), not the old one. The test keeps checking that no old record
  outlives the rerun; it checks the new document instead of its absence.
- `web/tasks.py` no longer removes the position unconditionally: any existing test that
  expects the position gone after a rerun with the same settings and chapters is adjusted
  to the new rule (same book, same stamp); a test with another book keeps expecting it gone.

## 6. Size and order

About 700 to 900 lines of code and templates, 700 to 900 of tests. Order: the app test and
change (A) first, then the growing view with its unit tests, the stamp, the routes, then the
pages and the browser tests. One PR: `web: start listening while the rest is generated (#724)`,
labels `lane:web` (+ `lane:app` with A), `risk:low` unless ruled critical.

## 7. While coding

- `document.json` is written in `_Chapters._writer`, right after the old records are removed
  and before the first chapter's files are put in place (after the first chapter is spoken).
  Written before the first chapter is spoken, a kill while speaking it would leave the old
  `audio.json` (still vouching for the finished book, D-119) beside a new `document.json`.
  The kill test of D-902 runs at exactly that point.
- The web writes `made` into `audiobook.json` at the first playable chapter, not at job start:
  the voice follows the document's language (D-469), known only from the laid-out document.
- The book key stamps a finished book only while its chapter record vouches for the very
  read-along file (size and SHA-256); a read-along file changed by hand keeps the old rule
  (its hash), as `test_web_outside` and `test_web_markers_survive` expect.

## Handoff (THR-07)

- Goal: #724 LW-02, plan above.
- Done: plan approved (D-902); code and tests on `claude/project-thread-vxzknj`.
- Next: PR, Linux CI, `ci:full`, then review.
