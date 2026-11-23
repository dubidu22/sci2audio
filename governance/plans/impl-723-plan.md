# impl-723: each chapter becomes playable as soon as it is spoken (#723, LW-01)

Status: **waiting for coordinator approval** (critical: job runner, output files, golden files; `risk:high`, CRIT-01, PLAN-02). No code or tests before approval.
Written 2026-11-23 by impl-723 (Opus 5.5 high) on main at 0994f97. Batch: `plans/batch-005.md`, slot A.

## 1. What changes

Today `run_audio_job` speaks every chunk of every chosen chapter, then `write_audiobook` encodes all chapter MP3s, the M4B, subtitles and the read-along file at the end. After this work:

1. The job speaks chapter 1, encodes chapter 1's MP3 (and its subtitles, when chosen) into the output folder, rewrites the book's read-along file to list the chapters done so far, records them, tells the progress listener, and only then speaks chapter 2. Document order throughout.
2. Each committed chapter is recorded in a new working-folder record, `chapters.json`, with its file names, sizes, SHA-256 hashes and a fingerprint of everything that went into the bytes. A rerun or resume reuses a chapter whose fingerprint and hashes still match: nothing is spoken or encoded again.
3. By default the job writes no M4B (the app's default `OutputSettings` becomes chapters only). The CLI passes its settings explicitly, as it does today, so `sci2audio convert` still writes the M4B at the end, and its files stay byte-identical.
4. A killed or cancelled job leaves whole chapters only. This replaces today's "all or nothing" rule for the new files of a failed encoding (`_encode`, D-119/D-160). For book-level files (M4B, book subtitles) all-or-nothing stays.

How I read "project folder": the chapter MP3s go where the audiobook goes today, the output folder (in the web, the project's own audiobook folder, D-749). The record goes into the working folder (the project data folder) beside `audio.json`. The read-along data is the book's read-along file next to the MP3s, rewritten after each chapter.

## 2. Design

### 2.1 Output lane (`src/sci2audio/output/`)

`write_audiobook` is split into parts that can run one at a time. It stays, as the composition of those parts, so its callers and output's own tests keep working unchanged.

- `write.py`:
  - `write_chapter(job_folder, targets, chapter_index, chapters, spoken, book, settings, *, ffmpeg, overwrite, on_complete) -> ChapterWritten`: writes chapter `chapter_index`'s MP3 and its subtitle pair. It plans the timeline over **all chapters given so far** (pure, cheap) and feeds only that chapter's chunks. This works because a chapter's samples depend only on its own chunks: the timeline places chapters one after another in whole samples, and a chapter starts with the chapter pause and joins nothing (`_trim_joins`).
  - `write_readalong(targets, chapters, spoken, ..., on_complete)`: the book's read-along file for the chapters written so far, format v1 unchanged. Its times lie on the book's timeline, the same timeline the M4B would have. A prefix of the book in document order never moves an earlier chapter's times.
  - `write_book(...)`: the M4B and the book's subtitle pair, from the chunks (unchanged ffmpeg arguments).
  - `on_complete(target, size, sha256)` is called for every file once its `.partial` is finished and **before** it is renamed into place. The app records the file there. So a file is in place only once the record vouches for it, and a kill between the two steps leaves either an unrecorded partial (removed on the rerun) or a recorded whole file. That is the atomicity the acceptance criterion asks for.
  - `chapter_fingerprint(chapter, spoken slice, number, count, book, settings) -> str`: SHA-256 over the inputs that decide the chapter's bytes: chunk file names, durations, pauses, joins, the chunk texts (for subtitles), title, number and count (the track tag), book title, authors, language, the cover file's SHA-256, every `OutputSettings` field, and `sci2audio.__version__`. It lives in output because output knows what goes into its files.
  - `audiobook_targets` is unchanged and is computed once, up front, for all planned chapters, so every name (including names retried after a refusal, #493) is the one the CLI writes today.
- `readalong.py`: the module docstring and `docs/readalong-format.md` change from "written last: when it exists, the run is complete" to "lists exactly the chapters whose files are complete". The format and version do not change.
- `__init__.py`: exports the new functions and `ChapterWritten`.

### 2.2 App lane (`src/sci2audio/app/`)

- `audio.py`:
  - `_speak` and `_encode` merge into a loop over the planned chapters. For each chapter it speaks the chunks (same cache, cancel and failure rules as today), then calls `output.write_chapter`, then `output.write_readalong`, then updates `chapters.json`, then sends the progress event. A chapter whose every utterance failed gets no file. It is listed as skipped, as today.
  - Numbering: a chapter's number and count come from the plan (chapters with something to say). Today they come from the chapters that ended up with audio. The two differ only when every sentence of a chapter fails, which leaves a gap in the numbers instead of renumbering later files that are already playable. This is the one possible output difference, and it needs a voice that fails whole chapters. The corpus and the golden files do not have one.
  - Old records: `audio.json` and `document.json` are removed just before the first chapter is committed, not at the end (they vouch for a finished audiobook, D-119). They are written at the end as today. So the library and the player see the audiobook as finished only when it is, and the web's behaviour before #724 does not change.
  - At the end: the M4B and the book subtitles when the settings ask for them (CLI), the final read-along file (naming the M4B when there is one, so the CLI's file is byte-identical), `audio.json` and `document.json` (format unchanged), then `chapters.json` with `"complete": true`.
  - `AudioProgress` gains `ready: int | None` (the chapter index that just became playable, on the event sent right after its record is written) and `playable: tuple[int, ...]` (every playable chapter so far, on every event after the first). There is no new `Phase`, so the web card and the CLI line read as today. The web's job record keeps the last progress event, so a page opened later sees `playable`.
  - The default `output_settings` becomes the module constant `JOB_OUTPUT = OutputSettings(m4b=False)`.
- `chapters.py` (app) gains the record helpers, or a new module `app/playable.py` if `chapters.py` gets too long:
  - `chapters.json`: `{"format": "sci2audio-chapters", "version": 1, "complete": false, "planned": [indices], "chapters": [{"index", "title", "number", "fingerprint", "seconds", "chunks", "files": [{"name", "bytes", "sha256"}]}], "book": [{"name", "bytes", "sha256"}]}`. It holds bare names only: like the other records, no folders, since folders are machine-specific. It is written atomically (`write_texts`) and read strictly: missing, too large, a link, another format or version, or broken all read as no record.
  - `playable_chapters(work, out_folder) -> tuple[PlayableChapter, ...]`: the recorded chapters whose files are still there with the recorded size. It is for #724 and for a CLI run started later. It is public in `sci2audio.app`.
- Reuse and the overwrite check (D-163), decided before any speech:
  - A target vouched for by a record with `"complete": false`, the same fingerprint, and the same size and SHA-256 is **reused**: not spoken, not encoded, not refused.
  - Any other existing target is refused without `overwrite`, as today. That includes every file of a **finished** audiobook (`"complete": true`), so `sci2audio convert` run twice is still refused (exit 7, `test_running_again_reuses_every_sentence` unchanged). It also covers a chapter whose settings changed since, which LW-04 (#726) will turn into a choice for the person.
  - With `overwrite`, a matching vouched chapter is still reused (same bytes) and everything else is replaced.
- `runner.py`: passes the new defaults through. No new behaviour.

### 2.3 What stays as it is

- The CLI (`cli.py`): no change. It passes `OutputSettings(mp3=..., m4b=...)` explicitly, so it keeps the M4B, and its progress line is unchanged.
- `audio.json` format v1 and the read-along format v1.
- The web player: it already plays MP3s when there are any (`player.py` mode "mp3"). With `m4b: null` in the record it works unchanged.

## 3. How the PRs split by lane (`.github/lanes.yml`)

lanes.yml lets a PR change files of its own lane only, and output and app are different lanes, so this is two PRs, merged in order.

| PR | Lane label | Files | Closes |
|---|---|---|---|
| **A** `output: a chapter's files can be written on their own, as the job speaks (#723)` | lane:output, risk:high | `src/sci2audio/output/{write,readalong,__init__}.py`; tests `tests/unit/test_output_chapters.py` (new); `docs/readalong-format.md` (docs, any lane) | none ("Part of #723") |
| **B** `app: each chapter becomes playable as soon as it is spoken (#723)` | lane:app (+ lane:web, see 4.1), risk:high | `src/sci2audio/app/{audio,chapters or playable,runner,__init__}.py`; `src/sci2audio/web/tasks.py` (one line, see 4.1); tests under `tests/unit/test_app_*`, `tests/unit/test_cli_convert.py`; one new snapshot; `docs/baseline.md` row | #723 |

- B starts after A has merged (B imports A's API). B's branch is cut from main after A's merge.
- A is a pure addition plus one composition change: `write_audiobook`'s output is byte-identical, which A's tests prove.
- Lane note for the coordinator: per `implementation.yaml`, lane:output belongs to the extraction/voices execution lane, the same one as #744 (lane:voices, slot B). The files are disjoint (`output/` vs `voices/`, and no shared tests or golden files), so LANE-02 lets both run. I am naming it because the extract says one implementation thread per execution lane.
- After B merges, slot A continues with #725 and #726 (a new thread per D-626/THR-02).

## 4. Choices

### 4.1 The one open choice: the web's M4B until #725

When the app default flips, the web job (which passes no `output_settings`) stops writing the M4B at once. The web's existing tests pin that M4B (`test_web_audio.py` lines 74 and 86, `tests/browser/test_flow.py:162`, `test_listen.py:535`), and the web's way to get a single file, the M4B link in the job's files, would disappear until #725 adds the on-demand download.

- **Recommended: B keeps the web as it is.** One line in `web/tasks.py` passes `OutputSettings()` explicitly, so the web still writes the M4B at the end (chapters are playable earlier anyway). #725 removes that line when it adds the download. Web tests stay untouched, and B touches one web file (lane:web). #724 runs after #723 anyway, so nothing collides.
- Alternative: let the web drop the M4B now. B would then change the web unit and browser tests, and the web would offer no single-file audiobook on main until #725 merges.

### 4.2 Decided in this plan (clearly better than the alternatives)

- **The read-along is rewritten after each chapter, not written per chapter.** One file in format v1 means the player and #724 read what they read today. Per-chapter read-along files would add a format variant and extra files to the CLI's output, which the issue says must not change.
- **A separate `chapters.json`, not a growing `audio.json`.** `audio.json` means "finished audiobook" to the library (`has_audio`) and the player. Changing that meaning belongs to #724, not here.
- **The file is vouched before the rename (hash of the partial).** Recording after the rename leaves a window where a kill gives an unrecorded whole file that the next run refuses (D-163). Recording before the rename with a fingerprint only would let another program's file at that name pass as ours.
- **Encoding runs in the job's thread, between chapters.** Encoding is at least 50 times faster than real time (baseline.md), so a background encoder would only add locking to save seconds.

## 5. Tests (TST-01: characterisation first)

All are fast tests unless marked. The node IDs below are the list the PR bodies repeat under "## Tests promised in the plan".

### PR A (output)

First, the characterisation tests, written and green on main before any change:
- `tests/unit/test_output_chapters.py::test_write_audiobook_output_is_pinned_before_the_split`: for the fixtures `output_helpers` makes, the SHA-256 of every file and the read-along JSON are compared in-run against a reference. Cross-platform ffmpeg bytes are compared within one run only, never against a stored hash.

Then:
- `tests/unit/test_output_chapters.py::test_chapter_by_chapter_writes_the_same_bytes_as_write_audiobook`
- `tests/unit/test_output_chapters.py::test_a_read_along_for_the_first_chapters_lists_only_them_on_the_book_timeline`
- `tests/unit/test_output_chapters.py::test_every_file_is_vouched_for_before_it_is_put_in_place`
- `tests/unit/test_output_chapters.py::test_a_failing_chapter_leaves_no_partial_and_keeps_the_chapters_before_it`
- `tests/unit/test_output_chapters.py::test_write_book_writes_the_m4b_and_its_subtitles_as_write_audiobook_does`
- `tests/unit/test_output_chapters.py::test_the_fingerprint_changes_with_each_input_that_changes_the_bytes` (parametrized: chunk, pause, join, text, title, number, count, book tag, cover, each setting)
- `tests/unit/test_output_chapters.py::test_the_fingerprint_is_the_same_for_the_same_input`
- `tests/unit/test_output_chapters.py::test_chapter_times_on_their_own_add_up_to_the_book_timeline` (Hypothesis: any split into chapters, any pauses and lengths)
- Every existing `tests/unit/test_output_*.py` test stays green unchanged, including the `test_output_faults.py::test_readalong_file_golden` snapshot.

### PR B (app)

First, the characterisation tests, written and green on main before any change:
- `tests/unit/test_cli_convert.py::test_convert_writes_the_same_files_as_before_chapters_became_playable_early`: the CLI's file names, its read-along JSON, its ffmetadata chapter marks and its `audio.json` (version stripped) as a syrupy snapshot recorded on main. It is a **new golden file**, made before the change and unchanged by it.
- `tests/unit/test_app_audio_job.py::test_the_records_snapshot` stays byte-unchanged: the test passes `OutputSettings()` explicitly (the CLI's settings). This is the one edit to it, because the default changes underneath it.

New:
- `tests/unit/test_app_audio_chapters.py::test_each_chapter_is_playable_before_the_next_is_spoken`
- `tests/unit/test_app_audio_chapters.py::test_a_ready_event_names_each_chapter_in_document_order`
- `tests/unit/test_app_audio_chapters.py::test_the_record_lists_the_playable_chapters_while_the_job_runs`
- `tests/unit/test_app_audio_chapters.py::test_the_job_writes_no_m4b_by_default`
- `tests/unit/test_app_audio_chapters.py::test_a_resume_reuses_finished_chapter_files_without_speaking_or_encoding_them`
- `tests/unit/test_app_audio_chapters.py::test_a_resume_after_the_settings_changed_is_refused_without_overwrite`
- `tests/unit/test_app_audio_chapters.py::test_a_chapter_file_changed_since_is_not_reused`
- `tests/unit/test_app_audio_chapters.py::test_a_finished_audiobook_is_still_refused_without_overwrite`
- `tests/unit/test_app_audio_chapters.py::test_a_chapter_whose_every_sentence_failed_gets_no_file_and_keeps_the_numbers`
- `tests/unit/test_app_audio_chapters.py::test_a_broken_or_foreign_record_reads_as_none`
- `tests/unit/test_app_audio_chapters.py::test_the_records_snapshot_of_a_chapters_only_job` (new snapshot: `audio.json`, the read-along file, `chapters.json`)
- Fault injection (`tests/unit/test_app_audio_faults.py`):
  - `::test_a_job_killed_mid_chapter_leaves_whole_chapters_and_resumes` (subprocess SIGKILL while chapter 2 is spoken; resume: chapter 1 neither spoken nor encoded; the end result byte-equal to an uninterrupted run)
  - `::test_a_job_killed_while_a_chapter_is_encoded_resumes_and_leaves_no_partial` (ffmpeg hangs on chapter 2)
  - `::test_a_full_disk_while_a_chapter_is_encoded_keeps_the_chapters_before_it`
  - `::test_the_output_folder_removed_after_a_chapter_fails_with_a_message`
  - `::test_a_kill_between_vouching_and_renaming_resumes_cleanly`
- Benchmark: `tests/unit/test_app_first_chapter_speed.py::test_time_to_the_first_playable_chapter` (`@pytest.mark.benchmark`). A 10-chapter book with a fake voice that takes a fixed time per chunk. The first chapter must be playable within 20 % of the whole job's time (today it is 100 %), and the seconds are printed. Row in `docs/baseline.md` (nightly; seconds and share of the job).
- No network: the existing `test_a_whole_job_runs_with_the_network_blocked` covers the new path, unchanged.

Existing tests whose assertion changes, with the reason (TST-02: the rule they pin changes, none is weakened). The PR body explains each:
- `test_app_audio_faults.py::test_cancel_part_way_through_encoding_leaves_no_file_and_the_rerun_needs_no_overwrite`, `::test_ctrl_c_while_encoding_leaves_no_file`, `::test_a_full_disk_while_encoding_leaves_no_file_and_the_rerun_needs_no_overwrite`, `::test_a_failed_encoding_never_removes_a_file_that_came_from_elsewhere`, `::test_a_rerun_that_fails_while_encoding_leaves_no_old_record`. Each now asserts "whole chapters only, recorded, no partial, the rerun needs no overwrite and reuses them" instead of "no file". The other file stays untouched as before. Each test keeps its name's promise where it still holds, and is renamed where "no file" is no longer true.
- App tests that check the M4B under the default settings (`test_app_audio_job.py` around lines 94 to 115 and 578, `test_app_audio_faults.py` network test) pass `OutputSettings()` explicitly.
- No web test changes under the recommended 4.1.

Runs: the fast checks from CLAUDE.md before each PR, `uv run pytest -m browser` for B (the web's job path), and `ci:full` before review on both PRs (critical, D-698). The mutation run on the final round: `output/write.py` for A, `app/audio.py` and the record module for B (INV-09: command, paths and a clean baseline named in the PR). The corpus comparison on a local merge of main (INV-07): the CLI's output files are byte-identical.

## 6. Licence, risk, size

- No new dependency, file, model or text (licence gate: nothing to add).
- Risks: (1) a timeline or trim difference between chapter-by-chapter and whole-book encoding. A's byte-equality tests guard it. (2) The reuse check vouching for a file that is not ours. Size and SHA-256 must match, and a fingerprint mismatch never reuses. (3) The changed all-or-nothing rule. The fault tests pin the new rule.
- Size: A is about 250 lines of code and 350 of tests. B is about 400 lines of code and 600 of tests.

## 7. Out of scope (follow-ups, no code here)

- The web UI for "Start listening" and chapter states: #724.
- The on-demand M4B/MP3 download, and removing the web's explicit M4B: #725.
- Adding chapters to a finished project, and the choice when settings changed: #726. The fingerprint and the `"complete"` flag are made so #726 can decide per chapter.
- The CLI printing each chapter as it becomes ready: not asked. It would change the CLI's progress output, so it waits for a separate Issue if wanted.

## Handoff (THR-07)

- Goal: plan #723 (LW-01) and get it approved.
- Done: this plan, from main 0994f97 (app/audio.py, output/write.py, timeline, readalong, web tasks/player, tests named above).
- Next: the coordinator approves the plan (and 4.1). Then PR A, then PR B after A merges.

## Handoff (THR-07, THR-02), 2026-11-23

- Goal: #723 (LW-01), each chapter playable as soon as it is spoken; PR A #754 merged (f1a9c1f), PR B #761 closes the issue.
- Done: PR B #761 open at 492eb06 (branch claude/project-thread-wrlvkm); Linux CI and the ci:full three-system run 45163940997 green; ci:full removed; ledger prs/pr-761.yaml updated. Fast suite and browser tests (Chromium) green locally apart from torch-only voice tests (torch cannot be downloaded in the cloud container).
- Next: review of #761 in review-b005; fix rounds by a fresh implementation thread started from this handoff (impl-723 has handled two PRs, THR-02). Final round: mutation run on `app/audio.py` and `app/playable.py` (INV-09) and the corpus byte comparison of the CLI's output (INV-07).

Tried and ruled out, with evidence:
- More existing tests changed than the five the plan named: every one is listed with its reason in #761's body ("Existing tests that changed, and why"); the rule they pin changed (a stopped job keeps whole chapters), none checks less (`whole_chapters()` asserts no partial, record ownership by size and SHA-256, read-along listing exactly the MP3s).
- `governance pr checks` red on #761 is the D-882 gate (no approving review round for the head yet), as on #754 before review; no comment posted.
- First Windows run failed only in two snapshot tests: `write_text` wrote CRLF, so the source SHA-256 in `audio.json` differed; fixed with `newline="\n"` in 492eb06 (run 45161450149 failed, 45163940997 green).
- A resumed run's kept read-along file sat in both `book` and `pending`; `ChapterRecord.with_book_file` now drops it from `pending` (caught by the kill-between-vouch-and-rename tests).
- Benchmark: share 14 to 16 % at 0.1 s per chunk (0.05 s gave up to 18 %, too near the 20 % limit), row in docs/baseline.md.
