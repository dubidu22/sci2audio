# Review of sci2audio PR #99 (issue #71, the audio job), round 1

Reviewed head `e3bb443` on base `395e4c9` (main has not moved since). Plan `plans/issue71-audio-job-plan.md`, decisions D-154 to D-166 (KB merged in sci2audio-design #30, a6b26a2).

## What I ran

- `ruff check`, `ruff format --check`, `lint-imports` (2 contracts kept), `deptry src`: clean.
- Fast suite `pytest -m "not slow and not benchmark"`: **1197 passed**, 39 snapshots passed.
- Nightly Hypothesis profile on `test_app_audio_plan.py`, `test_app_chunks.py`, `test_textprep_utterances.py`: **80 passed**.
- Slow tests with the real Kokoro voice (models fetched with `tests/integration/prepare_models.py`): **5 passed** in 179 s (`tests/integration -m slow`, network blocked in the tests; this includes the new pymedphys-to-M4B test with the cached rerun, and the speech-recognition round trip, which ran here because the whisper model was fetched too).
- Probes (throwaway tests, not committed): a chunk cut to half its size in the cache is spoken again on the rerun (1 chunk, correct); a cancel set while the **second** ffmpeg call starts (see M1).
- CI on `e3bb443`: green on Linux, macOS and Windows.

## Must fix

**M1. A cancel or a failure part-way through encoding leaves a half audiobook set, and the rerun is then refused.** Output commits each file on its own (D-119), so when the job is cancelled, or the disk fills, after the first MP3 is renamed into place, that MP3 stays in the output folder with no M4B and no read-along file. The next run without `overwrite` then stops at the pre-check (D-163): "these files exist already: … - 01 ….mp3; choose to replace them". Probe on pymedphys: cancel at the second ffmpeg call left `[… - 01 ….mp3]` and the rerun raised `OutputExistsError`. The tests miss it because `test_cancel_while_encoding_leaves_no_audiobook_file` cancels at the start of the encoding phase (before any file), and `test_a_full_disk_while_encoding_leaves_no_half_file` reruns with `overwrite=True` ("completed files of the failed run stay"). This breaks the plan's "nothing half-written" (D-140) and D-160 ("cancel ... chunks kept, rerun finishes"), and it is the same "half set" the script job had in PR #90 round 1, which `app.files.write_texts` now handles by removing the targets it already renamed.
Fix: around `write_audiobook`, note which of the audiobook's target files (`audiobook_files` with the assembled chapters' titles) exist just before encoding; on any exception (BaseException, so Ctrl-C too), remove the targets that did not exist then and exist now, then re-raise. With `overwrite=True` the files it replaced cannot be restored; say so in the docstring. Tests: cancel at the second and at the last ffmpeg call, disk full at MP3 3 and at the M4B, each then `outputs == []` and a rerun **without** `overwrite` that succeeds and reuses all 41 chunks; change the existing full-disk test's rerun to no `overwrite`.

**M2 (added 02:27 UTC, coordinator decision D-226). `clean_work_folder` does not take the work-folder lock.** It removes `chunks/` while a job (from the command line or the server, #72/#76) may be speaking into it or encoding from it, so a clean during a run deletes chunks under the job (a `ChunkAudioError` at encoding at best). Decision D-226: `clean_work_folder` holds `work_folder_lock(work)` while it removes the cache and raises `JobBusyError` when a job holds the lock. Test: with the lock held by another process (and by a runner in this process), `clean_work_folder` raises `JobBusyError` and `chunks/` is untouched; without a holder it cleans as before.

## Should fix

**S1. An old `audio.json` outlives a failed rerun.** Output removes the old read-along file before encoding because "the read-along file vouches for the audio: an old one must not outlive a failed rerun". `audio.json` (and `document.json`) from an earlier success stay when a later rerun with `overwrite` fails or is cancelled during encoding, so the record names files that were replaced or removed. #76/#77 will list jobs from it. Fix: remove `audio.json` before encoding (it is written again last), and a test that a rerun failing during encoding leaves no `audio.json`.

**S2. A job killed outright during encoding** (no Python clean-up runs) still leaves the MP3s it finished, and the rerun is refused without `overwrite`. M1 cannot cover a kill. Fine to defer: open an issue (for example, write a small "encoding" marker in the work folder listing the targets that did not exist before, so the next run may replace exactly those), and link it in your reply.

## Nits

**N1.** If cached chunks ever have different sample rates, output raises `ChunkAudioError` ("chunks must share one sample rate") and the app says "run the job again to speak it anew", but a rerun reuses the same chunks (`is_finished` does not check the rate, unlike the plan's "at the voice's rate"), so the same error comes back each time. Very unlikely, since the rate follows from the engine version in the key. Either check the rate against the first chunk spoken or cached in this run, or make the message for that case say to clean the working folder. Your choice; say which.

## Checked and fine

- **Chunk key** (D-155): SHA-256 of a canonical JSON of format, engine, engine version, voice, speed (as float), text; no span; voice "" resolved to the default before the key, so both share the cache. Engine version = model revision plus installed kokoro and misaki.
- **Finished check** (D-156): missing, `.part` only, stereo, 32-bit, cut short after the rename, junk and a folder all fail it; probe: a halved WAV is spoken again and replaced (`os.replace`). `.part` files are removed under the lock before planning.
- **Kill and resume**: subprocess killed with `Popen.kill` while hanging; rerun speaks exactly the rest, clears a planted `.part`, byte-identical MP3s and the same read-along. Output removes its own stale `.partial` files at start.
- **OS lock** (D-161): `flock` per open file description (also refuses a second runner in the same process), `msvcrt.locking` on byte 0 with a 3 s retry on Windows only for the killed-process case; released in `finally`; tested across processes and after a kill.
- **Cancel** (D-160): before each utterance and between every block fed to ffmpeg (MP3s and the M4B both use the feed); ffmpeg's `run` iterates the feed in the calling thread, so the `JobCancelledError` propagates, ffmpeg is killed and output removes the partial file. (Only the whole-set issue above remains.)
- **Utterance.continues** (D-157, refines D-115): set on every piece after the first of a cut sentence, never on a new sentence or block; default False; the Hypothesis property (pieces joined at `continues` give the uncut sentences, starts match) holds under the nightly profile. No core change.
- **Five failures** (D-162): duplicates of a failed text are not retried or counted twice; counter reset on a success; 5 in a row stop with chunks kept; all failing with fewer than 5 gives "could not speak any".
- **Overwrite check before the voice loads** (D-163): `_check_targets` and the ffmpeg lookup run before `_speak`; tested with `voice.made == 0`.
- **Estimate** (D-159): warm-up call and model load excluded; None until the first spoken chapter is done and 500 characters measured; tested event by event with an injected clock.
- **Layers**: no change to core, voices, output or the import contract (diff stat; `lint-imports` clean). `JobRunner` moved to `app/runner.py`, same public name.
- **Plan deviation, `models_dir` in `kokoro_voice(models_dir)`**: sound. Only the voice uses it, `create_kokoro_engine` already calls `prepare_environment(models_dir)` before loading, and a fully cached rerun needs neither. It does not change D-164 (default folders) or D-166 in substance (the voice is still passed in and made lazily), and the merged KB row D-166 already records it ("the models folder lives in the source, not in the job's arguments").
