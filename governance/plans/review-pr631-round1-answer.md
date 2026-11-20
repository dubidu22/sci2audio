# PR #631 round 1: answer (implementation thread)

One fix commit on `web/app-window`; the branch was not updated (main merges cleanly).

## F1 (blocker, macOS): the close question
- `AppWindow.closing` no longer opens a dialog. It sets `window.confirm_close` (True only while an audio job runs and the self test has not taken over) and returns True; pywebview asks with its own question on the GUI thread and keeps the window open on Cancel.
- The question's words go in through `create_window(..., confirm_close=False, localization=close_strings(...))` with the keys `global.quitConfirmation`, `global.quit`, `global.cancel` (`app.close_making`, new `app.close_quit`, new `app.close_cancel`; `app.close_title` removed).
- Test: the fake window's `create_confirmation_dialog` calls `pytest.fail`; `test_closing_asks_only_while_an_audiobook_is_being_made` checks `confirm_close` for no job, a preview, an audio job, and after the self test.

## F2: the language of the close question
- `ServerState.language` is set by every rendered page (`pages._page`); `AppWindow.strings()` uses it, else `system_language()`.
- `localize()` updates the window's own `localization` dict in place on every `loaded` and in `closing` (Cocoa reads the strings before `closing` runs; WinForms after). `loaded` is now always registered.
- `system_language` runs `locale.normalize` first, so `German_Germany` gives de.
- Tests: `test_the_close_question_speaks_the_language_of_the_last_page` (English, then a German page, then German in the same dict object); `German_Germany`, `English_United Kingdom`, `French_France` added to the language cases.

## F3: browser mode stops under a reader
- `base.html` carries `data-keep-alive="/api/v1/jobs"` only when launched as "browser"; `app.js` `keepAlive()` asks that URL every 60 s while the page is visible and Quit has not been pressed (errors ignored).
- Tests: the rail/privacy unit test checks the attribute in browser mode only; `tests/browser/test_app_quit.py` gets two `page.clock` tests: a browser-mode page makes no request in 59 s, one at 60 s, answered 200, and `state.seen` moves; a terminal page makes none in 5 minutes. Both fail with the attribute forced on or off.

## F4: a failure without a terminal
- `main` wraps the start: any exception is logged with `log.exception` (traceback in the log) and ends in `could_not_start`, which logs the reason, shows `app.failed_title` / `app.failed` with the log path, and returns 1. A server that does not start in window mode takes the same path.
- `show_message`: Windows `MessageBoxW`, macOS `osascript display alert` (text quoted), Linux nothing; never raises.
- Tests: `run_browser` raising OSError gives exit 1, the log holds the traceback and reason, the message names the log; a normal stop (browser and window) shows nothing; a server that cannot start shows the message; `show_message` per platform with stubs, quoting, and a failing osascript.

## T1: the six surviving mutants, one test each
1. `test_only_the_app_without_a_window_stops_when_idle[terminal|browser]` and `test_the_app_window_never_stops_when_idle` (Background with idle 0 still answers).
2. `test_the_idle_stop_comes_exactly_after_the_quiet_spell` (`seen + idle - 0.001` False, `seen + idle` True).
3. `test_the_app_switches_smartscreen_off_before_the_window_engine_starts` (win32: the variable holds the flag when `run_window` is called).
4. `test_stopping_the_app_window_cancels_the_job_and_ends_the_event_streams`.
5. `test_stopping_the_app_window_ends_the_server_at_once` (< SHUTDOWN_WAIT + 2 s, thread ended).
6. `test_the_quit_page_does_not_warn_about_a_voice_preview`.

Hand mutants: your `mut.py` list (with "closing never asks" rewritten for the new code) plus 10 new ones for F1–F4 and N1: 28 of 28 killed.

## N1
- `privacy.interface_key_app` (en, de) for window and browser mode; the terminal keeps `privacy.interface_key`. The rail/privacy test checks both languages and that the other text is absent.

## No action
- uv.lock revision; #644 stays v2.

## Checks
ruff, format, lint-imports (3 kept), deptry clean; fast suite 7929 passed, 4 failed = the known Python 3.13-only local failures (3 CLI help snapshots, epub punycode), green in CI on 3.12; browser suite: see the commit's CI.

## Found by the installer smoke test (PR 2 run 44485080787, macOS), fixed in the same commit
- The self test read the page with `evaluate_js`, which pywebview wraps in `eval()`; WKWebView applies the pages' CSP (`script-src 'self'`) and refused it, so the macOS self test hung until the smoke test's timeout. It now uses `run_js` (the engine's own evaluate, no eval; returns the JSON string on Cocoa and WebView2). A read that fails writes a report with the error and closes instead of hanging.
- Tests: the fake window's `evaluate_js` fails the test; `test_a_self_test_that_cannot_read_the_page_reports_why_and_closes`.
- Browser suite: 189 passed, 1 skipped (screenshots label).
