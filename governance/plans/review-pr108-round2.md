# Review of sci2audio PR #108, round 2

Reviewed head `4c21d92` (the answer to round 1: https://github.com/dubidu22/sci2audio/pull/108#issuecomment-6842491377).

## Round 1 items

- S1 fixed: `test_a_second_ctrl_c_stops_at_once` added. **But it is timing-dependent and failed on CI** (see R2-1).
- S2 fixed: `_settings` no longer reads the file; `--chapters all` is resolved after both voice checks in `convert` (and before the work folder in `script`). `test_an_unknown_voice_with_every_chapter_is_refused_before_reading` covers it, and my probe now shows zero reads. The double read is deferred to #112 (open).
- S3 fixed: without `--overwrite`, `--with-script` pre-checks `script_files(...)`, then the audio job runs first. Both orders are tested with the folder's mtimes unchanged; my probe shows the folder unchanged and exit 7.
- N1 done (`Command.epilog`), N2 done ("the file to read", two snapshot lines, explained), N3 done (plan and question on stderr through `_ask`; `_ask` raises EOFError at end of input, so the existing refusal path holds).

Local on `4c21d92`: ruff, format, lint-imports (2 kept), fast suite with the ci profile 1303 passed, `test_cli_properties.py` with the nightly profile passed, and every property test file (56 tests, `-k "propert or hypothesis"`) passed with the nightly profile in 185 s.

## New

**R2-1 (must fix): `test_a_second_ctrl_c_stops_at_once` is racy; `tests (ubuntu-latest)` is red on `4c21d92`.** The CI log shows exit 130 within the time limit, but stderr lacks the "stopping after the current sentence" line: the main thread had not handled the first `_thread.interrupt_main()` when the second came 0.5 s later, so the two were seen as one KeyboardInterrupt. (`interrupt_main` only sets the pending-signal flag; the main thread sees it when its 0.1 s `Event.wait` returns and the runner is loaded by `-n auto`.) The code is right; the test must not depend on the scheduler. Fix: after the first `interrupt_main()`, wait (with a timeout of a few seconds) until the env's stderr holds the "stopping after the current sentence" line (for example by polling `cli.env.err.getvalue()`), then press the second time. Keep every assertion. Re-running the job is not a fix.

**R2-2 (nit, optional): Ctrl-C before the `try` in `_audio_in_thread`.** `threading.Thread(...).start()` sits before the `try: _wait(...)`. A Ctrl-C landing inside `start()` skips the cancel event and is treated as a second Ctrl-C. In a real process the result is the same as a second Ctrl-C (exit 130, the daemon thread ends with the process, the cache is safe), so this is cosmetic; moving `start()` inside the `try` would make the first Ctrl-C always polite.

**Filed by the reviewer, not blocking: #115.** With the audio job now first, a `convert --with-script` stopped or failed in the script phase leaves the audiobook in place, and the same command again stops with exit 7 instead of continuing (D-218); `--overwrite` finishes it without speaking again.

No decision of D-210 to D-226 changes in substance.

## Verdict

Request changes: R2-1. R2-2 is the author's call; the reply names it.
