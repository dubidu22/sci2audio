# PR #366 round 1: answer (D-628)

New head: 4108d81 (was 766d56a). One commit; no other changes.

## B1: fixed

- `src/sci2audio/extraction/isolate.py`:
  - New `_sigint_held()` holds SIGINT back in the starting thread (`signal.pthread_sigmask(SIG_BLOCK, {SIGINT})`) around `child.start()`. Spawn's exec inherits the mask.
  - `_child` sets `signal.signal(SIGINT, SIG_IGN)` first, then unblocks SIGINT, so a SIGINT held back since the start is dropped. Only the parent's cancel ends the child.
  - Windows has no signal mask, so there the child ignores SIGINT from the first line of `_child` on.
- Tests, all three failing on 766d56a:
  - `tests/unit/test_extraction_pdf_progress.py::test_a_sigint_to_the_child_leaves_the_cancel_to_the_parent[while-starting]` sends real SIGINTs every 10 ms from before the child exists until the cancel, and expects `Stopped("cancelled", "page 1 of 1")`. On 766d56a the child ended while starting. Without the mask (SIG_IGN only) it still fails.
  - `[on-a-page]` sends SIGINTs only during the page step. On 766d56a this raised `KeyboardInterrupt` in the parent.
  - `tests/unit/test_cli_convert.py::test_ctrl_c_on_a_terminal_reaches_the_reader_too_and_still_reads_as_cancelled` sends real SIGINTs to the child from its start, then one KeyboardInterrupt to the program. `convert` exits 130 with "the job was cancelled while the file was read; run the same command again to continue", with no "cannot be read" and no "damaged".
  - All three are POSIX only (skipped on Windows).
- The helper `sigint_children` lives in `tests/unit/reader_targets.py`, which imports only the standard library and `isolate`.

## S1: fixed

`test_with_a_cancel_to_watch_a_step_is_stopped_at_its_own_time_limit` wraps `isolate._wait` and takes the time when it returns. That is the decision point: the kill has been sent, but the child has not been joined or closed. The bound stays `1.0 <= took < 1.5`, measured from the page step's arrival.

## Checks at 4108d81

ruff check and format, lint-imports (3 kept), deptry clean. Fast suite: 5301 passed, 1 skipped, 2 xfailed. Browser: 57 passed. The new tests ran 3 times in a row without a failure.
