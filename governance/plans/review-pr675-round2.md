# PR #675 review, round 2 (head 51b6735)

Reviewer: B-W1 web/app review thread, Opus. 20 Nov 2026. Plan: plans/web-b-w1-plan.md (D-837, D-838). Author's answer: plans/answer-pr675-round1.md.
Critical: **yes** (unchanged from round 1).
Verdict: **approved** (0 must-fix, 0 should-fix, 2 notes). Merge still needs the coordinator's go and, as a critical PR, a green three-system run on the final head (CRIT-02, D-580).

## Round 1 findings

- **M1 fixed.** `app/updates.py` `set_enabled(False)` sets `_off` before saving and `_read()` reports off while `_off` holds; `_due()` also refuses when the file says off while an unsaved result says on. "On" on a failed save does not take effect. My round-1 probe (on, unsaved result, off on a full disk) now reads `enabled False` and makes no further request. Tests: `test_turning_it_off_on_a_full_disk_still_stops_it_for_this_run`, `test_off_in_memory_wins_over_a_file_that_still_says_on`, `test_web_updates.py::test_turning_it_off_on_a_full_disk_answers_507_and_is_off_for_the_run`. `app.js` now shows the server's state after a failed PUT.
- **M2 fixed, as the plan says.** `web/state.py` builds `UpdateCheck(..., available=not config.outside)`; only `sci2audio listen` fills `outside` (`web/config.py:93`), so `ui` and the app window are unaffected. `available` false blocks `_due()` and `newer_version()`, and Settings hides the switch. `cli.py` untouched (LANE-02). Test `test_sci2audio_listen_never_runs_the_check`: the real fetch under `offline`, file on and never checked, every page and a PUT on → no attempt, `checked_at` still empty.
- **S1 fixed.** `network_uses()` in `tests/unit/test_web_languages.py:635` walks the AST: all `Import`/`ImportFrom` (incl. `from urllib import request`, imports in functions), literal `import_module`/`__import__`, and calls `create_connection`, `getaddrinfo`, `open_connection`, `start_server`, `urlopen`; deny list widened (ssl, ftplib, smtplib, xmlrpc, socketserver, http.server, websockets …). Applied to all of `src/sci2audio` with the same 4-file allow-list; 10 positive and 3 negative self-tests.
- **S2 fixed.** `test_a_failed_check_writes_one_line_to_the_app_log`: after `window.open_log`, one WARNING line, without the answer's body; the logger state is restored.
- **S3 fixed.** `test_web_player.py:830` asserts both headers on the audiobook MP3's 206 answer.
- **S4 fixed.** #678 (v1.4, lane:docs, risk:low), linked in the PR body.
- **N1 declined with reason** (governance pr checks refuse two `(#N)` in a title; `Closes #172` is in the body): accepted. **N2, N3 declined** (bounded by the cap; no plan requirement): accepted. **N4 fixed** with a test.

## CLAUDE.md line (D-838)

The new hard-rule line in `CLAUDE.md:11` is word for word plan §4's proposed text, including the unchanged second sentence. The owner's approval is D-838 ("Yes, add the line", 20 Nov 2026). INV-03 untouched.

## Checks

- **Diff of the fix commit**: 11 files, all within the PR's lanes plus `CLAUDE.md` (now in scope, D-838); no unrelated change, no narrating comment.
- **Local run** (temporary worktree at 51b6735, macOS): ruff, ruff format, lint-imports (3 kept), deptry green; `pytest -m "not slow and not benchmark and not browser" -k "not espeak" --deselect …test_a_child_that_ends_without_a_result_is_named`: 8461 passed, 6 skipped, 6 xfailed, 0 failed; `pytest -m browser` (Chromium): 196 passed, 5 skipped.
- **CI on 51b6735 (Linux, pull_request)**: `CI passed` green; `tests (ubuntu-latest)`, both Chromium shards, lint and layers, licences, security, ZAP baseline, CodeQL, governance pr checks all pass; Firefox shards pass. The three-system jobs did not run on this head (no `ci:full`).

## Notes

- **N5.** `browser (Linux, webkit, 2/2, reported only)` failed on 51b6735: `tests/browser/test_remove.py::test_the_removal_reflows_at_320_pixels[webkit-en]`, `Locator.click` timeout. Same shard passed at c691608; the fix commit touches only the Settings switch, `app.js`'s update handler and server state, nothing on the remove page, and the Chromium and Firefox runs of that test pass. Not required and judged unrelated; if it fails again without a code cause, D-374 (quarantine with an issue the same day) applies.
- **N6.** Before merge: merge `main` into the branch if behind (no rebase), then the `ci:full` run on that final head and check `tests (macos-latest)` and `tests (windows-latest)` (D-580, MRG-01).

## Handoff (THR-07)

- Goal: PR #675 (B-W1) to merge.
- Done: round 2 at 51b6735, approved.
- Next: on the coordinator's go, the three-system run on the final head, `ledger_tool.py gate 675`, squash-merge pinned to that head.
