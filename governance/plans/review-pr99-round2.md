# Review of sci2audio PR #99 (issue #71, the audio job), round 2

Reviewed head `fcb3071` (one commit on `e3bb443`, no force-push; base `395e4c9`, main unchanged). Author's answer: https://github.com/dubidu22/sci2audio/pull/99#issuecomment-6842105391

## Items

- **M1 fixed.** `_encode` notes the targets that exist before `write_audiobook`; on any `BaseException` it removes targets that did not exist and whose identity (device, inode, size, mtime_ns, kept by the rename) matches a file ffmpeg finished in this run, then maps the error. Own probes: cancel at ffmpeg call 2, 4 and 5 (the M4B) each leave an empty output folder and no `audio.json`, and a rerun **without** `overwrite` succeeds reusing 41 chunks. With `overwrite`, a cancel at call 3 leaves the replaced files and no read-along (output's D-119 rule), as the docstring says. The author's tests cover disk full at MP3 1, MP3 3 and the M4B, cancel, Ctrl-C and a foreign file.
- **M2 (D-226) fixed.** `clean_work_folder` holds `work_folder_lock`; probe: `JobBusyError` while the lock is held in this process, cleans afterwards, a missing folder gives 0 and is not created. Author's tests cover another process and a running runner.
- **S1 fixed.** `_remove_old_records` removes `audio.json` and `document.json` as encoding starts; tested.
- **S2 deferred** to #106 (open, acceptance criteria, milestone left to the coordinator).
- **N1 fixed** by a rate check before encoding with a "clean the working folder" message; reasoning for not checking in `is_finished` is sound.

Observation, no change needed: `_encode` re-raises a `JobError` as `raise error from error` (its own cause). Python's traceback printing guards against that cycle; `traceback.format_exception` on the cancelled error worked in the probe.

## Checks on fcb3071

- `ruff check`, `ruff format --check`, `lint-imports` (contracts kept), `deptry src`: clean.
- Fast suite: **1204 passed**, 39 snapshots passed.
- Nightly Hypothesis profile on the three property-test files: **81 passed**.
- Slow `tests/integration/test_audio_job.py` with the real Kokoro voice: **passed** (179 s).
- CI on fcb3071: all green (Linux, macOS, Windows tests, lint and layers, licences, security, CodeQL, "CI passed").

## Verdict

Passes. No change to core, voices, output or the layer contract. D-154 to D-166 unchanged in substance; the `models_dir` in `kokoro_voice(models_dir)` is already recorded in the merged D-166 row. One new decision, D-226 (clean_work_folder under the lock), is implemented here.
