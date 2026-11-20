# Review of PR #162, round 2

Reviewed head 0f78c43 (two commits on 4c02ea2), 13 Nov 2026. Author's answer:
plans/review-pr162-round1-answer.md.

## Verdict

Approved. Both round-1 must-fixes are fixed; nothing new to fix in this PR.

## Round-1 findings

- **M1 fixed.** `usable_cover(cover, exe)` decodes the cover's first frame with the job's
  ffmpeg (`-protocol_whitelist file,pipe`) right after ffmpeg is found and before any speech;
  on FfmpegError or OSError the file is removed and the job goes on without a cover. The
  three covers from round 1 each give a finished job with no cover in the M4B or the MP3s
  and no file left; the fake voice shows the cover gone before the first chunk. An intact
  cover is kept; a missing ffmpeg program gives no cover. Checked by running the tests.
- **M2 fixed.** The nightly test asserts `spoke + reused == total`, `spoke > 0`,
  `reused == 1`. Ran here with the real Kokoro voice: passes.

## New in round 2 (deferred, not blocking)

- A small cover image with huge pixel dimensions is costly: a 1.99 MB 16-bit RGBA PNG of
  16000x16000 makes every ffmpeg run that opens it use about 2 GB and 3 to 6 s (opening it
  alone costs the same, so this is not new with the decode check). The job does not fail:
  if memory runs out during the check the cover is dropped before any speech. Filed for
  v1.1 as #165 (cap the pixel size from the PNG/JPEG header).

## Checks on 0f78c43

- Fast suite (`ci` profile): 2411 passed, 19 subtests.
- `tests/unit/test_app_cover.py` (12) and the nightly EPUB CLI test with the real voice:
  13 passed in 65 s.
- Nightly Hypothesis profile on the fast suite: 2407 passed (run on 4c02ea2; the round-2
  delta adds `usable_cover` and tests only, no property-tested code).
- ruff, format, lint-imports (3 kept) clean.
- CI: tests on ubuntu, macOS, Windows, lint and layers, security, licences green. The browser
  job failed once in `test_keyboard.py::test_the_main_flow_by_keyboard` (the skip link on
  the document page showed a 1 px auto outline instead of the 2 px focus ring); the PR does
  not touch web code, the same test passed on 4c02ea2 in CI and locally. The one re-run passed,
  and every check on 0f78c43 is green (CodeQL included). Filed as #166 (v1.0, testing), next to #138.
