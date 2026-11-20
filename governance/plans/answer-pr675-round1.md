# PR #675, answer to review round 1 (head c691608 → 51b6735)

Author: B-W1 web/app implementation thread, Opus 5.5. 20 Nov 2026. One fix commit: 51b6735.

## Must fix

- **M1 fixed.** `UpdateCheck.set_enabled(False)` now sets `_off` before it saves, and `_read()` reports off whenever `_off` is set, so off holds for the run even when the save raises. The API still answers 507, and the Settings script then shows the state the server holds. `_due()` also refuses when the file says off while an unsaved result says on. Tests: `test_turning_it_off_on_a_full_disk_still_stops_it_for_this_run` (on → unsaved result → off on a full disk → no request on days 2, 3 and 10, under `no_network()`), `test_off_in_memory_wins_over_a_file_that_still_says_on`, `test_web_updates.py::test_turning_it_off_on_a_full_disk_answers_507_and_is_off_for_the_run`.
- **M2 fixed, as the plan says.** `ServerState` builds `UpdateCheck(..., available=not config.outside)`. A server started by `sci2audio listen` holds outside jobs, so it never fetches, shows no rail notice and no Settings switch. `cli.py` is untouched (LANE-02 with B-P1). Tests: `test_a_check_not_available_here_never_asks` and `test_sci2audio_listen_never_runs_the_check` (the real fetch, under `offline`, file on and never checked → no attempt).

## Should fix

- **S1 fixed.** `network_uses()` in `test_web_languages.py` walks the syntax tree. It flags every `Import` and `ImportFrom` (including `from urllib import request`), `import_module()` and `__import__()` called with a literal, and calls named `create_connection`, `getaddrinfo`, `open_connection`, `start_server` or `urlopen`. The deny list adds ssl, ftplib, smtplib, poplib, imaplib, telnetlib, xmlrpc, socketserver, http.server and the websocket libraries. The allow-list is unchanged (4 files by name). Ten self-tests that it catches each way in, and three that it lets the rest pass.
- **S2 fixed.** `test_a_failed_check_writes_one_line_to_the_app_log`: after `window.open_log()`, a failed check writes exactly one WARNING line, and that line does not carry the answer's body.
- **S3 fixed.** `test_web_player.py::test_the_audiobook_route_serves_only_its_own_files` now asserts both headers on the 206 answer for the audiobook MP3.
- **S4 fixed.** Filed #678 "docs: PRODUCT.md names the opt-in update check" (v1.4, lane:docs, risk:low), linked in the PR body.

## Notes

- **N1, not changed.** `governance pr checks` (PR-01, `TITLE_RE` in `.github/governance/pr_checks.py`) refuses a title with two `(#N)`. The first run failed on exactly that, so the title keeps `(#217)`; #172 is closed by `Closes #172` in the body.
- **N2, not changed.** The read timeout bounds the gap between chunks. The 1 MiB cap bounds the total, nothing waits for the thread, and no second check starts meanwhile.
- **N3, not changed.** Two server processes on the same day can each check once. No plan requirement covers this; an issue can be filed if wanted.
- **N4 fixed.** `put_updates` says `error.strerror or error`. Test: `test_a_save_error_without_a_reason_still_says_something`.

## Also in this commit

The `CLAUDE.md` hard-rule line from plan §4. Colin approved it in this session on 20 Nov 2026 ("Yes, add the line"; D-838).

## Local checks (macOS)

- ruff, ruff format and deptry clean; lint-imports: 3 contracts kept.
- Fast suite: 8464 passed, 6 skipped, 6 xfailed. Deselected: the three espeak tests and `test_a_child_that_ends_without_a_result_is_named` (#677).
- Browser suite (Chromium): 196 passed, 5 skipped.

## Handoff (THR-07)

- Goal: PR #675 to merge.
- Done: round 1 answered in 51b6735.
- Next: review round 2; after approval, merge main (no rebase), then the final ci:full run.
