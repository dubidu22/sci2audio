# Plan: Issue #71, the audio job (app layer; closes #10)

Status: **waiting for the coordinator's approval** (critical: writes and may overwrite user files, risk:high; a small refinement of textprep's `Utterance` from D-115; a golden file; KB entries). Written 13 Nov 2026 on `main` at 660d21f (after #90). Thread "Build the audio job". Feature IDs: WI-02 (resume), WI-04 (measured time estimate), VA-04 (offline after setup).

Sources read: Issues #71 and #10; `CLAUDE.md`, `.claude/rules/tests.md`, `.claude/rules/licences.md`, `.github/lanes.yml`; `plans/v1-remaining-plan.md` (wave 3, §3 app, Q4, Q6, Q8, Q9, Q12), `plans/issue70-script-job-plan.md`, `plans/issue69-output-plan.md`, `plans/issue18-kokoro-plan.md`; KB D-98, D-100, D-102, D-104, D-115 to D-119, D-121, D-122, D-129 to D-141, playbook 3.2; code on `main`: `app` (job, script, chapters, files, settings, config), `textprep.utterances`, `output` (model, timeline, write, wav, names), `voices` (engine, kokoro_engine, wav, runtime, download), `sci2audio.testing`, `tests/unit/voice_fakes.py`, the nightly workflow.

Measured today on the corpus (default chapter choice, built-in steps of `main`): pymedphys 41 utterances / 5,800 characters, seaborn 88 / 11,200, hardt 255 / 20,700, arsiwalla 481 / 60,300 (the largest). Liu has 455 utterances but only 375 different texts. At the #18 container speed (44 characters/s on CPU) pymedphys takes about 2.2 minutes to speak, arsiwalla about 23 minutes. The front chapter of the ACL papers holds only 3 utterances (about 200 characters).

## 1. What the job does

`file → script preparation (as #70, in memory) → voice per utterance into the job folder (skipping cached chunks) → output (MP3 per chapter, M4B, read-along) → records`, never stopping to ask (D-61 (3)).

1. **Checks before any work**: file type (`EXTRACTORS`), folders, and **the audiobook's target files** (computed with `output.names`, the same names `write_audiobook` uses): without `overwrite`, existing targets stop the job now, not after an hour of speech. The work folder is locked (section 6).
2. **Script**: extraction, layout and `prepare_script(document, settings, steps, max_chars)`, exactly as the script job, so the same file and settings give the same utterances (D-137).
3. **Plan**: the `Spoken` list and output `Chapter`s from the chosen chapters' utterances (section 3), and one cache key per spoken utterance (section 2). Chapters with nothing to say get no audio and are listed. Nothing to say at all: `JobError` before the voice loads.
4. **Voice**: only if some key has no finished chunk, the voice engine is made (lazily: a fully cached rerun never loads the model) after `voices.prepare_environment(models_dir)`; each missing chunk is spoken with `voices.speak_to_wav` into `work/chunks/…` (written atomically by voices). Progress after each chunk (section 4).
5. **Output**: `output.write_audiobook(work, out_folder, chapters, spoken, BookInfo, output_settings, ffmpeg=<cancellable wrapper>, overwrite=overwrite)`.
6. **Records** in the work folder, written last: `audio.json` and `document.json` (section 5).

## 2. Chunks, cache and resume (WI-02)

- **Key** = SHA-256 of a canonical JSON of `{"format": 1, "engine": "kokoro", "engine_version": …, "voice": …, "speed": …, "text": …}`, the four parts the issue names. `engine_version` = the Kokoro model revision pinned in `voices.download` (`f3ff357…`) plus the installed `kokoro` and `misaki` versions (`importlib.metadata`, no torch import), e.g. `kokoro-82m@f3ff3571;kokoro 0.9.4;misaki 0.9.4`. The sample rate follows from the engine version. The span is **not** in the key, so the same text twice in a job ("Table 2 is skipped.", repeated lines in Liu) is spoken once and both `Spoken` entries point at one file.
- **File**: `work/chunks/<key[:2]>/<key>.wav` (`AudioChunk.file` = that relative path, forward slashes, as core requires).
- **Finished** = the file exists and is a 16-bit mono PCM WAV at the voice's rate whose size matches its header (checked with output's `inspect` plus a size check). `voices.write_wav` writes `<name>.part` and renames, so a kill leaves at most a `.part`, which the next run deletes. A damaged file (e.g. after a power cut) is spoken again.
- **Resume = rerun with the same work folder**: every finished chunk is reused, so a chapter whose chunks all exist needs no speech ("skips finished chapters"). A changed switch or chapter choice reuses every chunk whose text did not change.
- **Encoding is always redone for all chapters** at the end (ffmpeg needs seconds per hour of audio, speech needs minutes per page), so `output` stays unchanged.
- Chunks stay in the work folder after success (a rerun after changing a switch only speaks what changed). `clean_work_folder(work)` removes them; the command line (#72) and the interface (#77) offer it, and `audio.json` states their size (about 173 MB per hour of audio).

## 3. Pauses and chapters (D-116, Q8)

The app gives each chunk one `Pause` kind; output turns kinds into seconds and always opens a chapter with the chapter pause.

| Chunk | Kind |
|---|---|
| first chunk of a chapter | anything (output puts the chapter pause) |
| after a chunk of a `heading` block | HEADING |
| first chunk of another block | PARAGRAPH |
| next sentence in the same block | SENTENCE |
| continues a sentence cut by the length fallback (Q4) | NONE |
| after a `pause` utterance | `Pause.strongest(PAUSE_EDIT, kind above)` |

**Telling a clause cut from a sentence end needs one fact the cutter knows and the `Utterance` doesn't carry.** Recommended: add `Utterance.continues: bool = False` to `textprep.utterances` (True when this utterance continues a sentence the length limit cut), set by `cut_utterances`; default keeps every caller working. This refines D-115 (lane textprep: one field and about 5 lines in `_fitted`/`cut_utterances`, plus tests). Alternative: guess from the previous utterance's last character (`.?!`), which misreads "e.g." cuts and replacements ending in a full stop.

Output chapters: one per chosen chapter with at least one spoken utterance, `title` = the app's chapter title as printed (D-130), `first` = index of its first `Spoken`. Book: `BookInfo(title=document_title(document), authors=metadata.authors, language=document.language)`; cover comes with #73.

## 4. Progress, time estimate and cancel (WI-04)

- `progress: Callable[[AudioProgress], None]`, called as each phase starts (reading, layout, text steps, **loading voice**, **speaking**, **encoding**, done: `Phase` gains three members) and after each chunk: `AudioProgress(phase, chapter, chapters, chapter_title, chunks_done, chunks_total, reused, characters_done, characters_total, characters_per_second, seconds_left)`.
- **Measured speed** = characters spoken / wall time spent speaking (synthesis plus WAV write), counting only chunks spoken in this run; model load and the first utterance (warm-up) are not counted.
- **Estimate**: `seconds_left` is None ("measuring") until the first chapter with speech is finished **and** at least 500 characters are measured (the ACL front chapters have about 200, too few to measure); after that, remaining characters still to speak / measured speed, updated after every chunk with all speech measured so far. Never a fixed rate. Encoding time is not in the estimate (seconds; the encoding phase is shown as its own step).
- **Cancel**: a `threading.Event` passed in, checked before each utterance (one call is at most a few seconds) and between the blocks fed to ffmpeg (a thin `Ffmpeg` wrapper passed through `write_audiobook(ffmpeg=…)`, so output's partial-file cleanup removes the half file). Raises `JobCancelledError(JobError)`; finished chunks stay for a rerun. Ctrl-C (KeyboardInterrupt) takes the same path.

## 5. Files

- **Output folder** (`settings.output_folder`, else the source's folder): exactly what `write_audiobook` writes: `<Book>.m4b`, `<Book> - NN <Chapter>.mp3`, `<Book>.readalong.json` (D-102, D-119). The audio job does **not** write the script or the report (the script job's files); the command line `convert` (#72) and the interface run the script job first when they want them, so the two jobs never fight over overwriting.
- **Work folder** (passed in): `chunks/`, `job.lock`, and, written last, `audio.json` = `{"format": "sci2audio-audio", "version": 1, sci2audio version, source name/format/sha256, settings (as `settings_data`), engine, engine_version, voice, speed, chapters (index, title, chosen, chunks, seconds), chunks spoken / reused, skipped utterances, measured characters per second, size of chunks/, files written}` and `document.json` (the laid-out `Document` through `core.export.to_data`, so the read-along player (#78) can show the block text the read-along spans point at without the source file).
- **Default folders** in `app.config` for the cli and server (the job itself always gets folders passed in): models `platformdirs.user_data_path("sci2audio")/models` (D-122 left this to the app; data, not cache, so OS cleaners don't delete 355 MB of voice files), work `platformdirs.user_cache_path("sci2audio")/jobs/<first 16 hex of the source's sha256>`.

## 6. Running jobs

- `JobRunner.run_audio(source, settings, work, *, voice, models_dir, output_settings=OutputSettings(), overwrite=False, progress=None, cancel=None, steps=BUILT_IN_STEPS, max_chars=DEFAULT_MAX_CHARS) -> AudioJob` under the runner's existing lock (one job at a time, D-138), plus `run_audio_job(...)` without a runner, like the script job.
- **Voice** argument: `VoiceSource(engine, engine_version, make)` where `make()` returns a contract `Engine`; `kokoro_voice(models_dir)` builds the Kokoro one. Tests pass the fake Kokoro adapter from `voice_fakes.py`. The voice id comes from `settings.voice` ("" = `DEFAULT_VOICE`), checked against `engine.listVoices()` before any speech; speed from `settings.speed`.
- **Across processes** (cli and server on one work folder, or a second window): an OS lock on `work/job.lock` (`fcntl.flock` / `msvcrt.locking`, stdlib, about 30 lines), held for the run and released by the OS if the process dies, so a killed job never leaves a stale lock. Busy → `JobBusyError`. Alternative: a lock file with a pid (stale after a kill, needs pid checks per OS) or the `filelock` package (a new dependency for 30 lines).
- **Voice failures**: if one utterance fails (`EngineError` from synthesize), it is **left out, listed in `audio.json` and the result with its chapter, page and text**, and the job goes on (D-61 (3), D-140); after **5 failures in a row** the voice is taken as broken and the job stops with `JobError` (finished chunks kept). Missing voice files (`ModelNotFoundError`) stop the job before any speech with "run the voice setup". Alternative: stop on the first failure (one odd sentence would block the whole book; a rerun would fail the same way).
- **Errors** follow D-140: `JobError` with an actionable message and nothing half-written: disk full while writing a chunk or an audiobook file, the output folder removed during the run, ffmpeg failing, a chunk file removed during encoding (output's `ChunkAudioError`).

## 7. Modules (lane app, plus one small textprep change)

| Module | Holds | Size |
|---|---|---|
| `app/audio.py` | `run_audio_job`, `AudioJob`, `AudioProgress`, `JobCancelledError`, planning (`plan_audio`: utterances → `Spoken`, chapters, keys), the speaking loop, estimate | ~350 |
| `app/chunks.py` | `chunk_key`, `chunk_path`, `is_finished`, `clean_work_folder`, `.part` clean-up | ~90 |
| `app/voice.py` | `VoiceSource`, `kokoro_voice`, `engine_version()` | ~60 |
| `app/lock.py` | `work_folder_lock(work)` context manager | ~40 |
| `app/job.py`, `app/config.py`, `app/__init__.py` | `Phase` members, `JobRunner.run_audio`, default folders, exports | ~60 |
| `textprep/utterances.py` | `Utterance.continues` | ~10 |

No change to core, voices, output or the layer contract.

## 8. Tests

- `test_app_audio_plan.py`: pause kinds per row of section 3 (heading, paragraph, sentence, clause cut, pause edit combined with a paragraph start); chapters without speech left out; chapter `first` indices; duplicate texts share a file. **Hypothesis** (random documents from `core_strategies`, random selections and pause pieces): every spoken utterance gives exactly one `Spoken` in order, chapter starts strictly increase from 0, `check_chapters` passes, spans equal the utterances' spans.
- `test_app_chunks.py`: the key changes with each of text, voice, speed and engine version and not with the span; finished-file check (missing, `.part` only, wrong rate, truncated, stereo); `clean_work_folder` removes only `chunks/`. Hypothesis: key is deterministic and the path is a valid `AudioChunk.file`.
- `test_textprep_utterances.py` (added cases): `continues` is set exactly on fallback cuts; Hypothesis: joining a sentence's pieces at `continues` gives the uncut sentence.
- `test_app_audio_job.py` (fake Kokoro adapter, real ffmpeg on a tiny generated PDF, a few seconds of audio as D-118 allows): files written; overwrite refused **before** the voice is made; rerun reuses every chunk and never makes the engine; changed speed or voice speaks again; progress phases in order, counters monotonic, `seconds_left` None until the first chapter and 500 characters, then decreasing (clock injected); cancel before, during speaking and during encoding (no output file, chunks kept, rerun finishes); unknown voice → JobError; one failing utterance skipped and listed; 5 in a row → JobError; `JobBusyError` from the runner and from a second process holding the lock; nothing to say → JobError without loading the voice.
- `test_app_audio_faults.py` (#10, tests.md): **killed mid-run** (a subprocess runs the job with the fake voice and is killed with SIGKILL / `TerminateProcess` after N chunks) → the rerun speaks exactly the remaining keys and the result equals an uninterrupted run; **no network** (the whole job under `sci2audio.testing.no_network`, fake voice; the slow test does it with the real one, VA-04); **disk full** (ENOSPC injected into the chunk write and into output's write) → `JobError`, no `.part`/`.partial` left, finished chunks kept; **output folder removed during the run** and **a chunk removed before encoding** → clear `JobError`, no half file; stale `.part` from a kill cleared.
- Golden file (syrupy): `audio.json` and the read-along JSON of the tiny job with the fake voice (deterministic durations).
- `tests/integration/test_audio_job.py` (`slow`, nightly, 3 systems): **pymedphys to M4B and MP3s with the real Kokoro voice, network blocked**: chapter marks match the chosen chapters, durations equal the read-along, the AI label is present; then a rerun reuses every chunk and does not load the model.
- `benchmark`: the real voice on pymedphys: characters per second and the job's own overhead (planning, keys, encoding) separately; row in `docs/baseline.md`.

Before the PR: the full CLAUDE.md check list, plus the nightly Hypothesis profile on the new property tests, plus the slow and benchmark tests here (models fetched with `tests/integration/prepare_models.py`).

Rough size: about 650 lines of code, 1,000 lines of tests. No new dependency (platformdirs is already in).

## 9. Decisions (numbered, for the KB; my recommendation first)

1. **What the audio job writes**: the audiobook files only (M4B, MP3s, read-along) plus its records in the work folder; it prepares the script in memory like the script job but does not write the script or report. Alternative: also write them (then a `script` run followed by `convert` would need `overwrite` for files the person may have edited).
2. **Chunk cache key**: SHA-256 of text, voice, speed and engine version (model revision plus kokoro and misaki versions), without the span; files `chunks/<2>/<key>.wav`; the same text in one job is spoken once.
3. **Resume granularity**: per chunk; a chunk is finished when its WAV is complete and valid; all chapters are encoded again at the end (no per-chapter output cache, output unchanged). Alternative: keep finished chapter MP3s (an output change to save seconds).
4. **`Utterance.continues`** in textprep (refines D-115) so a clause cut gets no pause (D-116); pause kinds as in section 3.
5. **Chunks kept after success**; `clean_work_folder` for cli/web; size recorded. Alternative: delete on success (a switch change would speak the whole book again).
6. **Progress events and the estimate**: `AudioProgress` after every chunk; speed measured on this run's own speech without load and warm-up; first estimate after the first chapter with speech and at least 500 characters, then a running estimate; encoding not estimated.
7. **Cancel** by a `threading.Event`, checked between utterances and while feeding ffmpeg; `JobCancelledError`; chunks kept.
8. **One job per work folder across processes** with an OS file lock (`job.lock`, stdlib), on top of the runner lock (D-138).
9. **Voice failures**: one failing utterance is left out and listed; 5 in a row stop the job; missing voice files stop it before speech.
10. **Overwrite check of the audiobook targets before any speech** (output checks again when writing, D-119).
11. **Default folders** (for cli/web only): models in `user_data_path("sci2audio")/models`, work folders in `user_cache_path("sci2audio")/jobs/<sha256[:16]>`.
12. **Records**: `audio.json` (`sci2audio-audio` v1) and `document.json` (core export) in the work folder, written last; the script job's `job.json` stays as it is.
13. **The voice is passed in as a `VoiceSource`** (engine name, version, lazy factory), so a fully cached rerun never loads the model and the server can keep one engine loaded later.

## 10. Out of scope

- Command line `convert` and `voices` (#72), server endpoints and the interface (#76, #77), the player using `document.json` (#78), cover images (#73).
- Remembering the measured speed between jobs for an estimate before the first chapter: not in WI-04; an issue if #77 wants it.
- Parallel synthesis or GPU tuning (#11).
- #91 (cutter splits inside "(2022)[p. 8]"): not blocking.
