# Review of PR #162, round 1: EPUB files in the jobs and the cover in the audiobook (#73, part 3)

Reviewed head 4c02ea2 (base 586094f), 13 Nov 2026. Plan: plans/issue73-epub-plan.md (q10, D-313; D-316 note).

## Verdict

Changes requested: two must-fixes (M1, M2). Everything else is clean.

## Must fix

**M1. A damaged cover image fails the whole audio job, after all the speech.**
D-313 says "failure means no cover, never a failed job". `Cover` (and output's `_check_cover`)
only check the first bytes, so a declared cover with the right signature but damaged data
passes `write_cover`, and ffmpeg then refuses it when it writes the first MP3:

```
JobError: could not write the audiobook: ffmpeg failed (exit code 234):
[mp3] dimensions not set ... Could not write header (incorrect codec parameters ?)
```

Reproduced with the PR's own helpers (`run(small_epub(tmp_path, data), tmp_path)` from
`test_app_cover.py`, fake voice, real ffmpeg) for three covers:

| cover bytes | result |
|---|---|
| `FF D8 FF` + 400 junk bytes | JobError (ffmpeg 234) |
| PNG signature + 400 junk bytes | JobError (ffmpeg 234) |
| the corpus cover cut to its first 2,000 bytes | JobError (ffmpeg 234) |
| the corpus cover cut to 80 % | works, cover embedded |

A truncated or damaged cover in a real EPUB is plausible, and the failure comes after the
whole book was spoken (hours on a CPU); the rerun would fail the same way.

Suggested fix (the author may choose another): check the written cover with the job's ffmpeg
before any speech, e.g. `ffmpeg -v error -i <cover> -frames:v 1 -f null -`, and on a non-zero
exit (or any error) remove the file and go on without a cover. I checked that this decode test
gives exit 69 for the three failing covers above and 0 for the 80 % cut and the intact cover,
the same split as the real MP3 embed. Tests: the three failing covers above give an
audiobook without a cover and a finished job (the 80 % cut may stay as is); the check runs
before speech (for example, a broken cover with a voice that records calls shows the cover
dropped before the first chunk), and works with the fake `ffmpeg` the tests pass in.

**M2. The new nightly EPUB test fails on its first run with the real voice.**
`tests/integration/test_cli_end_to_end.py -m slow` run here with the Kokoro voice from
`prepare_models.py`: the PDF test passes (181 s); the EPUB test fails at
`assert spoke == total > 0` with `assert 24 == 25`. The CLI prints "Spoke 24 of 25 sentences,
reused 1 from the last run" on a fresh work folder: the cut book's script has "A figure is
skipped." twice (title page, imprint), and the job reuses a sentence spoken earlier in the
same run (`Speech.reused`). The job is right; the assertion is wrong. Fix: assert
`spoke + reused == total`, `spoke > 0`, pin `reused == 1` for the repeated notice, and run the
test once with the real voice. Everything before that line holds (outline, two pictures,
cover asserts pass; `work/cover.jpg` equals the corpus cover; the M4B carries a 1400x2100
mjpeg attached picture).

## Checked and fine

- Whole diff (13 files). `EXTRACTORS` and `COVERS` are the single source for the job, CLI,
  speed script and web (`supported_suffixes`, `stored_name`, `accept`, `file_hint`).
- Upload: `.epub` goes through the same path as `.pdf`: the name is cut to its last part,
  cleaned, suffix lower-cased and checked before any byte is copied; size limit in
  `BodyLimit` and again while copying; stored under the content hash. No magic-byte check at
  upload for either type, by design: the extractor refuses a non-EPUB with a clear message
  (`test_a_damaged_epub_fails_with_a_message_naming_the_file`).
- Cover path: built only from the fixed name `cover` and `Cover.suffix` (".jpg"/".png" from
  the checked signature); nothing from the EPUB's own file names reaches a path. Written
  atomically inside the work-folder lock; old covers removed first; a directory named
  `cover.jpg` or an unremovable old cover gives no cover or the new one, never a stale one.
- Cover errors other than M1: no cover, raising cover function, full disk (half-written
  partial removed), unknown type: all give an audiobook without a cover. The
  `test_app_audio_faults.py` change counts only chunk `.wav` replaces, so the test still
  checks the same full-disk point; not weakened.
- German strings: no new interface keys; `file_hint` takes `{types}` in both tables
  ("sci2audio liest Dateien vom Typ EPUB, PDF"). App error details stay English as D-291
  decides; browser test `test_german.py` pin updated.
- Layer check: 3 contracts kept; cli/web do not import `sci2audio.testing`; deptry clean.
- Fast suite (`HYPOTHESIS_PROFILE=ci`): 2407 passed, 19 subtests, 55 snapshots, 74 s.
- Browser suite: 29 passed (Chromium).
- CI on head 4c02ea2: tests on ubuntu, macOS and Windows, browser, lint and layers,
  licences, security, CodeQL all green.
- Nightly CLI test with the real Kokoro voice: PDF test passes; EPUB test fails (M2).
- Nightly Hypothesis profile: see below.
