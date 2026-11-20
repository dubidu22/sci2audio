# PR #162 round 1: what was fixed

The new head is **0f78c43**. It has two commits on top of 4c02ea2. Main had nothing new to merge, and there was no force-push. Both must-fix items are fixed, and nothing is deferred.

## M1: a damaged cover failed the job after all the speech

`app/audio.py` has a new function, `usable_cover(cover, exe)`. It decodes the written cover's first frame with the job's ffmpeg program:

`-protocol_whitelist file,pipe -i <cover> -frames:v 1 -f null -`

This is your suggested check, plus output's local-only protocol list. If ffmpeg fails or the program cannot be started (`FfmpegError` or `OSError`), the function removes the file and the job goes on without a cover.

- **When it runs:** in `run_audio_job`, right after the ffmpeg program is found and before the first cancel check and any speech.
- **Which ffmpeg runs it:** a plain `Ffmpeg(run.exe)`, not the job's counting wrapper. That way it adds no "finished file" identity, and it does not shift the run counts of the fault tests' `FailingFfmpeg`.
- **Cost:** one short ffmpeg run per job.
- The module docstring now says the cover is decoded once before any speech.

Tests in `tests/unit/test_app_cover.py`:

- `test_a_damaged_cover_is_dropped_before_any_speech`, for your three covers:
  - `FF D8 FF` followed by junk;
  - a PNG signature followed by junk;
  - the corpus cover cut to 2,000 bytes.

  Each gives a finished job with no cover in the M4B or any MP3, and no cover file left behind. The fake voice records the working folder's cover files before every chunk, and the first record is already empty, so the check ran before the first chunk. Without the fix, all three fail with ffmpeg's exit code 234: "No JPEG data found", "chunk too big" and "dimensions not set".
- `test_a_cover_ffmpeg_can_decode_is_kept` covers three cases:
  - the intact corpus cover is kept;
  - `None` stays `None`;
  - an ffmpeg program that does not exist gives `None` and removes the file.

## M2: the nightly EPUB assertion

The cut book's script holds "A figure is skipped." twice, and the job speaks it once and reuses it (D-155). The test now asserts three things:
- `spoke + reused == total`;
- `spoke > 0`;
- `reused == 1`, with a comment naming the repeated notice.

I ran it once here with the real Kokoro voice, after `prepare_models.py` fetched the voice files: `SCI2AUDIO_TEST_MODELS=… uv run pytest -m slow tests/integration/test_cli_end_to_end.py -k epub` gave **1 passed in 79.6 s**.

## Checks on the fix

- `ruff check`, `ruff format --check` and `deptry src` are clean.
- `lint-imports`: 3 contracts kept.
- Fast suite: 2411 passed, 19 subtests.
- These ran on the M1 commit. The second commit changes only the nightly test file, which ruff checked again.
