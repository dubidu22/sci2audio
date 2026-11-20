# Review: sci2audio-design PR #30, round 1 (D-154 to D-166, #71 audio job)

Reviewed 13 Nov 2026 at head d26bb76 against main 421c270. Verdict: **pass, no changes needed**.

## Checked

- **Rows**: D-154 to D-166 each map to plan `plans/issue71-audio-job-plan.md` §9 items 1 to 13 in order, and each row's Record cell names its §9 item. All thirteen are "**Decided (Claude)**", coordinator 13 Nov 01:46 UTC under D-80, "Colin informed in the project chat at 2026-11-13T01:46:19Z", which equals the decision post's created_at (cmsg_…XDVuiqwfTPcBmDqcPE39N5). Every point of that post is covered by a row.
- **Format**: each row has six cells (pipes inside backticks and escaped pipes not counted); date 2026-11-13; each gives question, alternatives not chosen and reason, as the earlier rows do.
- **Order and placement**: the rows sit directly above D-153, the D column is strictly descending from D-166 with no gap or duplicate; the rest of the file is unchanged except the two status cells below.
- **Cross-references**: D-115 status gains "**refined by D-157**" and D-138 gains "**extended by D-161**", appended after the existing text, nothing else in those rows changed.
- **Code as built (sci2audio PR #99 head e3bb443)**:
  - D-166: `VoiceSource(engine, version, make, voices, default_voice, release=_dispose)` in `app/voice.py`; `kokoro_voice(models_dir)`; `run_audio_job` and `JobRunner.run_audio` take `voice=` and no `models_dir`. The deviation from the plan is recorded correctly.
  - D-164: `app.default_models_folder()` = `user_data_path("sci2audio")/models`, `app.default_work_folder(source)` = `user_cache_path("sci2audio")/jobs/<sha256[:16]>`, both exported. Matches.
  - D-155: `chunk_key` hashes format, engine, engine_version, voice, speed, text (no span); `chunks/<key[:2]>/<key>.wav`; version string `kokoro-82m@{KOKORO_REVISION[:12]};kokoro …;misaki …` gives `kokoro-82m@f3ff3571791e`. Matches.
  - D-156, D-158: `is_finished` (16-bit mono, last frame readable), `remove_partials`, `clean_work_folder` removes only `chunks/` (records stay). Matches.
  - D-157: `Utterance.continues` set by the cutter; `Pause.NONE` for it, `Pause.SENTENCE` otherwise in the same block. Matches.
  - D-159: `Phase` gains LOADING_VOICE, SPEAKING, ENCODING; `ESTIMATE_MIN_CHARACTERS = 500`; first call not measured. Matches.
  - D-160: `_check_cancel` before work and per utterance; `_CancellableFfmpeg` checks between fed blocks; `JobCancelledError`. Matches.
  - D-161: `app/lock.py`, `fcntl.flock` / `msvcrt.locking` on `job.lock`. Matches. (Note only: commit e3bb443 retries a busy lock for up to 3 s on Windows, because Windows may free a killed process's lock late. The row's statements stay true; this is an implementation detail like others the rows leave out, so not a finding.)
  - D-162: `FAILURES_IN_A_ROW = 5`; skipped pause carries over (`assemble`); "the voice is not set up" on `ModelNotFoundError`; "could not speak any of the chosen chapters" when nothing was spoken. Matches.
  - D-163: `_check_targets` uses output's `audiobook_files` and raises `OutputExistsError` before `_speak`. Matches.
  - D-165: `audio.json` fields (format, version, sci2audio, source, settings, engine, engine_version, voice, speed, duration, chapters with selected/chunks/seconds, chunk counts, skipped items with chapter/block/span/page/printed page/text/error, characters_per_second, cache_bytes, files) and `document.json`, written after encoding. Matches.
- **PR body**: references the code PR as "is in sci2audio PR #99: <link>"; no "closes", "fixes" or "resolves" anywhere. Attribution lines present.

## Findings

None.
