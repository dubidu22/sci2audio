# Review PR #631, round 1: the app window (#215 part 1, critical)

Reviewer: installers release review thread (Opus high), 19 Nov 2026. Reviewed head ec17b3a, base b6355cc. Main is now 805da4e (#630, #609); the PR overlaps it only in CHANGELOG.md and THIRD_PARTY_LICENSES.md and merges cleanly (`git merge-tree`).

Verdict: **changes requested**: 4 findings (F1–F4), 1 test list (T1, 6 items), 1 nit to fix (N1). One fix commit.

## What holds

- The PyPI install is unchanged: wheel built from ec17b3a has `Requires-Dist: pywebview<7,>=6.2.1; extra == 'window'` only; default deps identical (uv.lock diff only adds packages). New for everyone: the gui-script `sci2audio-app`, which without the extra opens the browser mode. Accepted.
- Licence rows checked against the lock (pywebview BSD-3-Clause, bottle/proxy-tools MIT, pythonnet/clr-loader MIT, cffi MIT-0, pycparser BSD-3-Clause, PyObjC MIT, QtPy MIT); the licences job now syncs `--extra window`.
- SmartScreen switch: Microsoft documents `msSmartScreenProtection` as a WebView2 flag, and `--disable-features` values are merged across switches ("a merge ... is not attempted, except for disabled and enabled features"), so pywebview's own `--disable-features=ElasticOverscroll` does not cancel it. Caveat: the environment variable is ignored by elevated processes (note N3).
- Quit (`POST /quit`) runs behind LocalOnly and the cookie/token checks, 404 outside browser mode; the voice download is a board job, so idle stop never cuts a download; `board.current` is RUNNING-only.
- Browser leg webkit 1/2 red on `test_markers.py::test_two_quick_presses_set_and_remove_in_order[webkit]`: pre-existing, reported only, not this PR.

## Findings

**F1 (blocker, macOS): closing during an audiobook deadlocks the app.** pywebview 6.2.1 runs `closing` handlers synchronously (`Event(self, True)` in window.py:163) inside `BrowserView.should_close`, which AppKit calls on the main thread (`windowShouldClose_`, `applicationShouldTerminate_`, cocoa.py:66–93, 1310). `AppWindow.closing` then calls `window.create_confirmation_dialog`, whose cocoa implementation (cocoa.py:1437–1454) posts `_confirm` with `AppHelper.callAfter` to that same main thread and blocks on `semaphore.acquire()`. The main run loop never runs `_confirm`: the window hangs. The fake pywebview cannot show this.
Fix: use pywebview's own close confirmation, which both backends show safely on the GUI thread: `closing()` sets `self.window.confirm_close = self.server.running and not self._checked.is_set()` and returns True; the dialog strings go into the window's localization (`global.quitConfirmation` = `app.close_making`, `global.quit` and `global.cancel` from two new strings `app.close_quit` / `app.close_cancel`, en and de; drop `app.close_title` if unused). Never call `create_confirmation_dialog` from a closing handler. Tests: the fake window gets a `confirm_close` attribute and a `localization` dict, and its `create_confirmation_dialog` fails the test when called from inside `closing`; check `confirm_close` is False with no job / a preview / after the self test, True while an audiobook is made, and the three strings.

**F2: the close question is not in the interface language (plan §3) and misses German on Windows.** `system_language()` reads `locale.getlocale()`; on Windows that gives names like `German_Germany`, which do not start with `de`, and a macOS app started from Finder has no `LANG`, so German users get English. The plan says "English or German by the interface language".
Fix: `ServerState` keeps the language of the last page the server rendered (set in `pages._page`); `closing()` fills the localization strings (F1) from it each time, falling back to `system_language()`; `system_language` passes the name through `locale.normalize` first (`German_Germany` → `de_DE...`). Tests: a page fetched with the German language → German strings in the window's localization at closing; `system_language(lambda: ("German_Germany", "1252")) == "de"`.

**F3: reading in the browser mode stops sci2audio after 15 minutes.** `Watch` stops when no request came for 15 min and no job runs. Only playback saves the position; the Working Reader, the library and a paused player send nothing, so a Linux tester reading a paper for 15 minutes finds the server gone and the next click shows the browser's connection error (new port on restart, the tab cannot recover).
Fix: when launched as "browser" (a flag on the page, e.g. `data-launched-as` on `<body>`), app.js sends one small authorised request (any existing cheap GET, or a new `GET /api/v1/alive` 204) every 60 s while `document.visibilityState === "visible"`; nothing in terminal or window mode. A hidden or closed tab still lets the idle stop happen. Tests: unit, the flag only in browser mode; browser test with `page.clock`, a visible browser-mode page makes the request after 60 s and `state.seen` moves, a terminal-mode page makes none.

**F4: a failed start is invisible and partly unlogged (plan §3 "a native dialog naming the log file").** `run_browser()` → `run()` → `bind()`/uvicorn errors propagate out of `main` to a devnull stderr: nothing in app.log, nothing on screen. `run_window` logs a failed server start but shows nothing.
Fix: `main` wraps both paths, logs the exception with `log.exception` and returns 1; when the app cannot start at all it shows a native message naming `app_log_file()`: Windows `ctypes.windll.user32.MessageBoxW`, macOS `osascript -e 'display alert ...'` (subprocess, no network); Linux logs only (say so in the docstring). Strings en/de by `system_language()`. Tests: `run` raising OSError → the log holds the reason, exit 1, the stand-in message function called with the log path; no message on a normal stop.

**T1: six hand mutants survive** (script `plans/b631-review/mut.py <worktree>`; baseline 69 passed on test_web_window.py, test_web_launch.py, test_web_pages.py; 13 of 19 killed). Add a test for each:
1. `serve()` starts a `Watch` for every launch (`if True:`): add a test that a "terminal" serve (and the window's `Background`) never stops on idle: `IDLE_STOP` and `WATCH_EVERY` patched small, the server still answers after several idle periods, then stops on `should_exit`.
2. idle boundary `>=` → `> idle + 1`: check `seen + idle - 0.001` → False and `seen + idle` → True.
3. `main` without `engine_settings(os.environ)`: a test that `main` on win32 (platform faked, fake webview) has `WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS` containing `--disable-features=msSmartScreenProtection` before the window is created.
4. `Background.stop` without `_wind_down`: closing the window while an audiobook is made ends that job as cancelled and sets `stopping` (check the job's state after `run_window` returns).
5. `Background.stop` without `should_exit` (suite passed after 87 s instead of 13 s): assert `stop()` returns within `SHUTDOWN_WAIT + 2` s and the server thread has ended.
6. quit page `making` counting a preview: a running voice preview shows no `#quit-making` warning.

**N1: privacy text says "the link sci2audio shows in the terminal"** (`privacy.interface_key`) on the app's privacy page, where there is no terminal. Fix: a variant for launched_as window/browser ("The address the app opens carries a key that is new for each start..."), en and de, and the rail/privacy test checks it.

## Notes, no action

- N2: uv.lock `revision = 5` → `3`: written by an older uv; CI's `--locked` accepts it and the next lock by a newer uv sets it back. No action.
- N3: WebView2 ignores `WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS` in elevated processes (Microsoft's flags page), so SmartScreen would be on if someone runs the app as administrator. The per-user installer never elevates. Filed as #644 (v2): also set `IsReputationCheckingRequired = false` through pywebview's native object.
