## Review of PR #85, round 1 (output stage, #69)

**Verdict: changes needed before merge.** One must-fix (file names too long for the file system), three should-fix items, four small ones. The design follows the approved plan and D-116 to D-120; the contract points all hold.

### What I ran (head bcc1045, merged locally with current main df76ad6)
- `ruff check`, `ruff format --check`, `lint-imports`, `deptry src`: clean.
- Fast suite, `HYPOTHESIS_PROFILE=ci`: 609 passed, 18 snapshots passed.
- `HYPOTHESIS_PROFILE=nightly` on `test_output_parts.py`: 35 passed.
- `test_output_long.py -m "slow or benchmark"`: 2 passed (2-hour no-drift book and the benchmark).
- Own checks, below.

### Must fix
1. **File names can exceed the file system's 255-byte limit.** `names.clean` caps at 120 *characters*, but ext4 and APFS limit a name to 255 *bytes* (UTF-8), and NTFS to 255 UTF-16 units. The longest name output makes is `.<base>.readalong.json.partial` (24 bytes on top of the base). Reproduced: a title of 130 × "Ü" (cleaned base 120 chars, 240 bytes) and a title of 60 × "量子" (360 bytes) both stop with `OSError [Errno 36] File name too long` after the output folder was created. A title in Greek or with many maths symbols gets there sooner than an ASCII one. Fix: cap the base (and the chapter file name) by UTF-8 bytes, cut on a character boundary, leaving room for the longest suffix; make the Hypothesis property check bytes of every derived name, partial names included (≤ 255), not only characters.

### Should fix
2. **ffmpeg keeps running if the wait is interrupted.** In `Ffmpeg.run`, an exception during `process.wait()` after the feed is done (Ctrl-C, or a later cancel) skips `process.kill()`. ffmpeg keeps writing to the partial file that `_atomic` is removing; on Windows the open file can't be deleted, so a partial is left. Kill and wait in that path too, and add a fault test (e.g. a fake process whose `wait` raises `KeyboardInterrupt`).
3. **`overwrite=True` deletes the old read-along before ffmpeg is found.** `json_file.unlink()` runs before `find_ffmpeg()`. With ffmpeg missing, a complete job folder loses its completeness mark although nothing was rewritten. Find ffmpeg (and finish every other up-front check) before deleting anything; add the case to `test_missing_ffmpeg_gives_a_clear_message` or a new test.
4. **The read-along round trip is not a property test.** The plan listed it under Hypothesis; the PR has one fixed example (`test_readalong_round_trip`). Add `from_json(to_json(build(timeline, spoken, ...)))` over generated timelines and spans, including `None` for `m4b` and `mp3`.

### Small (fix, or defer with an issue)
5. **No-overwrite has a race.** `os.replace` silently replaces a file that appears between the existence check and the rename, even with `overwrite=False`. Without overwrite, rename in a way that refuses an existing target (POSIX: `os.link` then remove the partial; Windows: `os.rename`, which already refuses).
6. **AI label lost the version.** The approved plan says `"... made with sci2audio <version>."`; the PR writes no version. Add it, or say in the fix list why not.
7. **Core docstring is now wrong.** `core/audio.py` says output uses `AudioChunk.duration` for read-along timing; D-117 says timing comes from the WAV frame counts. Update the docstring (a text change only, no data change), or file an issue.
8. **The golden file doesn't pin key order.** The snapshot stores parsed JSON, but `docs/readalong-format.md` promises the keys in a fixed order. Add one assertion on the key order of the raw text.

### Checked and fine
- **The old read-along is deleted first on `overwrite=True`** (beyond the plan): agrees with D-119. It only deletes the target name, only when overwrite is set (without overwrite an existing file raises first), and `test_a_failed_rerun_leaves_no_old_readalong_file` covers it. Only the ordering in item 3 needs changing.
- **`%` in file names** (beyond the plan): checked with the bundled 9.0.2, using cover files named `cover%03d.jpg`, `img%d.png` (PNG) and `c%%.jpg` and the output folder `out%03d`. Every one is read literally and the cover is attached in the M4B and the MP3. The outputs use explicit `-f mp3` / `-f ipod`, so the image2 pattern muxer never comes into play.
- **The `.claude/rules/tests.md` sentence** matches D-118 (decision C).
- **"Bundled programs" in THIRD_PARTY_LICENSES.md**, checked against the binaries:
  - Linux x86_64 `-buildconf`: `--enable-gpl --enable-version3 --disable-libfdk-aac --enable-libmp3lame`.
  - macOS arm64 9.0 configuration string: `--enable-gpl`, no `version3`, no `nonfree`, libmp3lame.
  - Windows 32-bit 4.2.2: `--enable-gpl --enable-version3`, no `nonfree`, libmp3lame.
  - No ffprobe in either wheel I downloaded. The wrapper's METADATA says `License: BSD-2-Clause`.
  - All of this matches the table and D-120.
- **Contract:** output owns read-along JSON v1, documented and refusing unknown versions. Atomic `.partial` files, with stale ones cleared. No overwrite by default. Timing from frame counts, checked again per chunk while streaming. Pause defaults 2.0 / 1.0 / 0.6 / 0.5 / 0.3 s, with none at a clause cut and the chapter pause at every chapter start (D-116). Every `-i` carries `-protocol_whitelist file,pipe`, and a test proves an `http://` input is refused. Layers: output imports only core.
- **Note, no change:** under D-119 the completed files of a failed run stay in place, so a rerun *without* overwrite refuses them. #71 must pass `overwrite=True` on a rerun into its own folder; that is already in #71's scope.

Please answer with an item-by-item list (fixed / deferred with issue link / declined with reason). The branch is behind main; I will update it before merging.
