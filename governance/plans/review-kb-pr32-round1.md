# Review: dubidu22/sci2audio-design PR #32, round 1

KB decision-log rows D-210 to D-226 (sci2audio #72, the command line). Head 485d171, base a6b26a2 (main). Reviewed 13 Nov 2026.

## Checked and fine

- Seventeen rows, D-226 down to D-210, newest first, directly above D-166 (the top row on main). Numbers match plan `plans/issue72-cli-plan.md` §3 questions 1 to 17 in order, and each Record cell names its question number.
- Every row is **Decided (Claude)** with "Colin informed in the project chat at 2026-11-13T02:26:49Z", which is the created_at of the coordinator's decision post.
- Content matches the plan's recommendations. The deviations the PR body names (D-219 waits on an `Event`; D-221 sizes as printed, `_mb` rounds above 10 MB; D-224 test file `test_cli_end_to_end.py`) match the code on sci2audio PR #108 head 3bd338a.
- D-212: the exit-code table (0, 1, 2, 3, 4, 5, 6, 7, 8, 130) matches plan Q3 and `Exit` / `EXIT_CODES_HELP` in `cli.py`. The `sci2audio: <message>` line, no traceback and "this is a bug" exit 1 match `run()`.
- D-223 names `sci2audio.app.UnreadableFileError(JobError)`, raised by `app.job.read_document` for `ExtractionError` and `OSError`. It is exported from `sci2audio.app` in the code.
- D-222 order (voice files checked first, then the voice id, both before the file is read) matches `run_convert_command`.
- D-224 describes the nightly test as coded (killed after three chunks, resumed, refused without `--overwrite`, nothing spoken with it) and the CI step in `ci.yml`.
- D-210: no command prints the help on stderr and exits 2, as in `run()`.
- D-225: `errors="replace"` reconfigure, as in `main`.
- PR body: the code PR is referenced as "Code PR, see: <link>". No "closes", "fixes" or "resolves" anywhere in the body, the commit message or the diff.

## Must fix

1. **D-217 breaks the table.** The cell text `` `--format both|m4b|mp3` `` has two unescaped pipes. GitHub's table parser splits cells on `|` even inside a code span, so the row gets ten cells instead of eight: the Decision cell ends at `both`, and the Status and Record columns are shifted. Escape them as `` `--format both\|m4b\|mp3` ``, as rows D-143, D-114 and D-103 already do.

## Should fix

2. **D-226: say where the lock lives in the code.** The row says it was "fixed in sci2audio PR #99 itself". Name the place so it is referenceable without opening the PR: `app/chunks.py` `clean_work_folder`, merged in 3ef8ac5 (PR #99). For example: "implemented in sci2audio PR #99 (merged as 3ef8ac5) in `app/chunks.py`; #72 adds a command-line test."

## Not checked

- That sci2audio Issue #104 exists and that Issue #73 has the EPUB checkbox: this review session can't read sci2audio issues through the API.

## Round 2 (13 Nov 2026, 02:53 UTC)

Commit 797274a fixes both items: (1) D-217 now reads `both\|m4b\|mp3`; all 17 rows have 8 cells (6 columns) when escaped pipes are ignored. (2) D-226 names `clean_work_folder` in `src/sci2audio/app/chunks.py`, PR #99, merged as 3ef8ac5. Nothing else changed. Squash-merged as 87e5aa8.
