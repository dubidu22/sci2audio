# Light batch audit: app lane, v1.1 player wins (PR #373 514dc2f, PR #378 c841f3d)

Diff read as a whole: 342a8f5..c841f3d (47 files, +2414/-112). Scope: cross-PR inconsistencies and contract touches only (D-627 rule 6). Paused 17:35Z on Colin's stop, resumed 19:01Z on his "resume normally until v1.1".

**Verdict: the batch is sound. 0 missed bugs (B0 S0). One test gap (T1) on a safety mechanism, for an issue. All contract touches were reviewed as critical in #378. The lane thread's output quality held.**

## Cross-PR checks that hold

- **#153 position x #119 order.** The position's `chapter` is a read-along index everywhere: player.js `loaded`, `fits`, and `_resume` via `view.chapters`, which has exactly one entry per read-along chapter in `build_view`. A new order writes a new read-along file, so the new stamp drops the old position.
- **#153 position x #154 listen.**
  - The POST goes to `data.document`, which is the `cli-` key for a listen job (`view.data(found.id)`).
  - `save_position` resolves through `listening()` and keeps the 409 and 422 checks. It writes only into `Listening.work`.
  - The record's `document` is the file id for both kinds of job.
- **#153 stamp cache x #154 `file_id` cache.** Both use the same key (path, st_ino, mtime_ns, size), and both live in this process only.
- **#190 x #376.** `Chapter.publisher` is read the same way by the report JSON, the report Markdown, the CLI `script` list, `ChapterOut` (default false for old reports) and the document page hint.
- **#119 records.** `job.json`, `audio.json`, the API's `_settings_data` and `_merged`, `app.js` `controls()` and the page's `_chapter_order` all keep the given order together. `selected()` returns the default in printed order. The settings file still leaves the chapters out.
- **#119 x #190.** `default_selection` leaves out both the reference list and the publisher's pages. `--chapters all` (`_all_chapters`) still takes every chapter. The Move buttons are drawn for every chapter, ticked or not, and hidden until bound (#350 pattern).
- **Strings.** en and de have the same key set. Every new key is in both: speed, resume, outside, back_home, move_up/down, js.moved and check.publisher.
- **Listen page for an outside job.** Both back links go to the start page and never to `/documents/cli-…`. The resume offer and the speed control work the same for both kinds of job.

## Contract touches (all reviewed as critical in #378)

- **Golden files.**
  - `test_cli_golden.ambr`: the `--chapters` help line and the `listen` command.
  - `test_app_corpus.ambr`: 29 new `'publisher': False` lines. The key is additive, and the report format stays v1.
- **`JobSettings.chapters`** changed from a frozenset to a tuple. It is an app dataclass, not one in `sci2audio.core`, and the change amends D-133.
- **Nothing else changed:** no file under `src/sci2audio/core`, and no regression case, corpus truth, pyproject or import contract.
- **Safety mechanisms:**
  - D-295 served folders: an outside job uses only its named folder.
  - The position stamp and the 409 answer.
  - The `cli-` key separation.

  They are applied the same way in api.py, pages.py and state.py.

## Finding

**T1 (test gap, safety mechanism; not a bug). In the default setup, a listen job's working folder is the web document's folder for the same file, and no test covers that.**

- `default_work_root()` is `<cache>/sci2audio/jobs` (web/config.py:31), and `default_work_folder(FILE)` is `<cache>/sci2audio/jobs/<file id>` (app/config.py:58). This folder sharing is older than the batch (D-198).
- So with the default folders, a file opened in the interface and also run through `convert` and `listen` has one working folder for both. They share `audio.json`, `document.json`, the web's `audiobook.json` and `position.json`.
- `tests/unit/test_web_outside.py::outside_job` puts the CLI work folder (`tmp/cli`) and the server's work root (`tmp/server`) in separate trees.
  - `test_an_outside_job_keeps_its_position_in_its_own_working_folder` asserts `not (config.work_root / job.document).exists()`. That is true only in the test.
  - `test_a_file_also_opened_in_the_interface_keeps_the_two_apart` uploads the same bytes, but into a different folder from the CLI's.
- Why it is still safe, by reading the code:
  - Both pages serve only an audiobook that agrees with the one `audio.json` (`locate`).
  - A shared `position.json` is offered only for a read-along file with the same hash, so the timeline is the same.
  - A web audio job removes the record for both.
  - `cli-` routing keeps the two routes apart.
  - The web's Remove of that document deletes the shared folder (unchanged since before the batch). A running `listen` page then shows its "no audiobook" problem, which is safe.
- Fix (tests only, `tests/unit/test_web_outside.py`). Add one TestClient test where the outside job's `work` is `config.work_root / <file id>` and the same file is uploaded through the web. It must assert:
  - (a) GET `/documents/cli-<id>/listen` serves only from the named folder, with a valid web `audiobook.json` in the shared folder pointing elsewhere;
  - (b) a position saved through the `cli-` key is offered on the web page only when the web page locates the same read-along file, and is refused (409) for another stamp;
  - (c) a web audio job's `remove_position` also clears the offer on the `cli-` page.
- Also correct the docstring and test name "its own working folder" to say that it is the file's cache folder, shared with the interface.
- Suggested home: an issue, v1.2, lane:app, tests only (coordinator decides; it does not block v1.1).

## Lane quality

Two PRs, five issues plus #376. Review findings were caught inside rounds 1 and 2 (#373: S1 N1 W1 W2; #378: S1 S2 N1 N2 N3, round 2 N1 → #380). The batch audit found no missed bug, only one test gap on the shared folder. Output quality held, the same result as the textprep batch audit (D-645).
