# Web batch B17 plan: #299, #407, #381 (one PR, non-critical)

Base: main 678fe3c. Lane: web. Review: Opus medium, max 2 rounds. Plan source: plans/next-batches-2026-11-19.md (D-776).
Condition C3 kept: no line in web/strings/*.toml; app/report.py and document.html untouched. player.py change is limited to the cache key and the shared helper.

## #299 Make the audiobook while the page still follows the analysis

**Cause.** `documentPage` in `web/static/app.js` wires `#make` (enables it) on every page, also on one drawn while the analysis is the running job (`#document[data-events]`). The Make handler runs `GET settings`, `POST /jobs`, `PUT settings`, then `location.assign('/jobs/<id>')`. When the analysis ends during that chain, `follow(... , () => reloadAt("step-check"))` reloads the page, which cancels the `PUT` and the move. While the analysis still runs, the same click gets 409 busy, and its message is wiped by the reload.

**Change (the issue's second option).** On a page that follows the analysis, `#make` stays disabled (as the page draws it, #350) until the page stops following: the end reloads the page, and the reloaded page (no `data-events`) enables it as now. One line in `documentPage`: wire as before, then `if (box.dataset.events) make.disabled = true;`. The page says why: `#message` already reads "Analysing…" (`document.analysing`), so no new string. Chosen over deferring the reload because it also covers the click during the job (409, message lost) and needs no deferred-reload state; the window is short (report written to job end) or the analysis is running anyway (a start would be refused).

**Test (browser, `tests/browser/test_flow.py` or a new `test_make_race.py`).** Hold the analysis after the report is written: monkeypatch `sci2audio.app.job._write` so the first call waits on a `threading.Event` (the R3-1 probe with an event instead of `sleep`). Open the file, wait until `#summary` is visible and `#document[data-events]` is present (the window). Assert `#make` is disabled (fails on main: it is enabled). Release the gate, click Make (Playwright waits until the reloaded page enables it), change the speed first on the settled page; assert the URL is the job page and `GET /api/v1/settings` has the chosen speed. Lessons kept: no Linux key chords, no pixel equality, wait for `settled()`.

**CHANGELOG (Fixed).** "Make the audiobook" on a document page whose analysis is just ending waits until the page has the finished analysis, so the start always goes to the job page and your choices are remembered (#299).

## #407 Read-along cache key without file identity

**Cause.** `web/player.py::load_readalong` keys `_readalong` on `(st_mtime_ns, st_size)`; a whole-file replacement of the same size within one clock tick is served from the cache.

**Change.** One helper in `web/player.py`: `_version(path) -> tuple[int, int, int] | None` returns `(st_ino, st_mtime_ns, st_size)`, or None when the mtime is within `RACY_NS` (2 s) of now. `load_readalong` reads the file directly on None, else caches by the triple. `audiobook_bounds` uses the same helper (no behaviour change). `audiobook_stamp` also uses it, which adds the racy guard there (a fresh file is hashed each call; same rule as `file_id`). `app/config.py::file_id` keeps its own copy: app cannot import web and app is another lane; noted, no change.

**Tests (`tests/unit/test_web_player.py`).** Replace the read-along file with one of the same size, restore the old `st_mtime_ns` with `os.utime(ns=...)` (mtime set > 2 s in the past so the racy guard does not hide the bug), get the new content; fails on main. Same for a fresh file (mtime now): read twice after an in-place same-size rewrite, new content both times.

**CHANGELOG (Fixed).** The player shows the text of a new audiobook even when its read-along file has the same size and time as the old one (Windows) (#407).

## #381 Shared working folder tests (AC-381.1 to AC-381.4)

`tests/unit/test_web_outside.py`, one new TestClient test (helper variant of `outside_job` with `work = config.work_root / <file id>`, the CLI's records copied there, and the same file uploaded through the web so the web document shares the folder):
- AC-381.1 (a): `/documents/cli-<id>/listen` and the audiobook route serve from the job's named folder while a valid web `audiobook.json` in the shared folder points to another folder holding a copy; with the named folder emptied nothing is served though the web record still points to a valid folder.
- AC-381.2 (b): a position saved through the `cli-` key (204) is offered on the web document's listen page when it locates the same read-along bytes; not offered when its copy's read-along differs in bytes (same data, rewritten); a save with another stamp gets 409.
- AC-381.3 (c): after `remove_position(shared work)` the `cli-` listen page shows no resume offer.
- AC-381.4: rename `test_an_outside_job_keeps_its_position_in_its_own_working_folder` and the `save_position` docstring in `web/api.py` to say the file's cache folder, shared with the interface. No behaviour change, no CHANGELOG line.

## Files
`src/sci2audio/web/static/app.js`, `src/sci2audio/web/player.py`, `src/sci2audio/web/api.py` (docstring), `tests/browser/` (one test), `tests/unit/test_web_player.py`, `tests/unit/test_web_outside.py`, `CHANGELOG.md`. Size: small (~40 lines code/docs, ~200 lines tests).

## Checks
ruff, format, lint-imports, deptry, fast suite; browser tests for the changed page locally (Chromium). Follow-ups, if any, filed with v1.2.x proposed.
