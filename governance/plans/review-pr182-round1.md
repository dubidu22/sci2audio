# Review of PR #182, round 1

PR: dubidu22/sci2audio #182, "testing: fix the flaky keyboard, upload and launch tests and the lost early Ctrl-C (#138, #166, #157, #147, #161)"
Head reviewed: 3b5b3c7 (base 3a55407). Reviewed 13 Nov 2026, 18:36 to 18:55 UTC.
Classification: non-critical (no layer contract, core dataclass, KB or golden file). One app change, `web/launch.py` (D-392).

## Verdict

**Approve. No must-fix, no should-fix.** Every stated cause is real and every fix removes the cause instead of retrying or sleeping. No quarantine marker remains.

## Cause and fix, one by one

1. **#138, first Tab stop on the document page.** Real cause. After `reloadAt("step-check")` the URL ends in `#step-check`; `page.goto()` to the same URL with a fragment is a same-document fragment navigation in Chromium, so focus starts at the anchor. Fix loads the URL without the fragment, which is always a full load. Removes the cause.
2. **#166, 1 px default focus ring.** Real cause. `settled()` only waited for `#document[data-events]` to vanish, which is already true while the reloaded page is still parsing, before `app.css` applies. Fix waits for the load event and for a computed style that only `app.css` sets (`.skip` is `position: absolute`). Both are condition waits on the current document, not timeouts.
3. **File-chooser race (new, no issue).** Real cause, confirmed in the installed Playwright (1.65.1): `ChannelOwner.on()` turns on the `fileChooser` subscription with `fire_and_forget(updateSubscription(...))` when the first listener is added, so the Space sent inside `expect_file_chooser` can reach the browser first. Fix keeps a listener from the start of the test, so interception is on long before (and stays on, since the count never drops to zero). It is the only test that opens a chooser by key (`grep expect_file_chooser tests/`).
4. **#157, Windows mtime.** Real cause. The old test derived the stale time from the file's own mtime and called `clear_stale_uploads(older_than=0)` on a file written "now", so a file-system time a tick after `time.time()` broke both. Fix sets both times from `time.time()` with a minute to spare and a 30 s limit. The app's one-hour rule is unchanged. The test also now checks the fresh file is really removed.
5. **#147, nothing listens after stop.** Real cause. Under `-n auto` the freed port can be taken by another worker's server, and a connect to a free ephemeral port can self-connect. `still_served()` treats refused, self-connected, or an answer other than 200 to this server's unique token as stopped, and a socket that accepts but never answers (a child that inherited the listener, the case this test exists for) as still served. The test also asserts the server answered before the stop and exited with 0.
6. **#161, Ctrl-C lost right after the line (D-392, app code).** Real cause, checked against uvicorn 0.54.0: `Server.serve()` installs `handle_exit` in `capture_signals()` before `_serve()` calls `startup()`, and `startup()` sets `started = True` at its end. The old code printed the line before `server.run()`. `_Server.startup()` calls back only when `started` is true; a lifespan failure exits from inside `super().startup()` (`sys.exit(STARTUP_FAILURE)`), so nothing claims it is running.

## `sci2audio ui` behaviour (checked by hand)

Ran the real `sci2audio ui` with `BROWSER="echo OPENED %s"` and sent SIGINT the moment "running at" appeared:

```
sci2audio is running at http://127.0.0.1:<port>/start?token=…
Keep this window open while you use sci2audio; press Ctrl-C to stop it.
OPENED http://127.0.0.1:<port>/start?token=…
sci2audio has stopped.
exit 0
```

Same text, same order, browser opened with the same start link; only the moment changes.

## New tests fail on the old code

With `web/launch.py` from main and the PR's tests: `test_ctrl_c_as_soon_as_the_link_shows_stops_the_server` fails ("the link shows before uvicorn takes Ctrl-C: default_int_handler") and `test_serve_prints_the_link…` fails (`before_start == [(2, 1)]`). Both pass on the PR.

## Runs (Linux, 4 CPUs, Chromium headless shell 1243)

- `ruff check`, `ruff format --check`, `lint-imports` (3 kept), `deptry src`: clean.
- `pytest -m quarantined --collect-only -q`: no tests collected.
- Fast suite `-n auto`: 2787 passed, 1 skipped (Windows-only junction test).
- Browser suite: 45 passed.
- Under load (3 busy-loop CPU hogs, all three loops running at once):
  - `tests/browser/test_keyboard.py`: **30 of 30** runs green (60 test runs).
  - `tests/unit/test_web_launch.py -n 4`: **40 of 40** runs green (11 tests each).
  - `test_a_new_server_removes_uploads_a_killed_one_left_behind`: **60 of 60** green.

## CI on 3b5b3c7

All green, including `tests (windows-latest)`: 2785 passed, 3 skipped (POSIX-signal launch test, folder link, symbolic links). The #157 test ran and passed on Windows, and the new Ctrl-C test ran and passed on Windows too. ZAP baseline green.

## Observations, no action needed

- A Ctrl-C pressed after uvicorn's handler is in place but before startup finishes still shows the "running" line and opens the browser, then stops at once. Not a regression (before, the browser opened even earlier), and the user pressed Ctrl-C before being told it runs.
- A Ctrl-C before `capture_signals()` (while the event loop module is imported) can still be dropped; the server then starts and prints the line normally, so the user sees it running and can press Ctrl-C again. #161 is about a Ctrl-C after the line, which is now always honoured.
- `still_served()` does not catch `ConnectionResetError`; if one ever came, the test would error loudly rather than pass wrongly.

## Merge

Main moved to 5d8fd2f (#169, extraction only, no overlap with this PR's five files). Branch updated with a merge commit; merge after CI is green on the new head.
