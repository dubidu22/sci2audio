# Review PR #378, round 1 (v1.1 player wins, PR B: #119 chapter order, #154 `sci2audio listen`)

Head reviewed: ed60ec6 (branched from main 342a8f5). Plan: plans/v11-player-wins-plan.md (D-642, PR B). Critical (CLI help golden, served folders = D-295 safety mechanism), lane:app. #376 is still to come after #373 merges.

**Verdict: not approvable yet. No blocker, two should-fixes (S1, S2), three nits (N1–N3).** Heavy checks (ci:full, nightly Hypothesis seeds) are kept for the round expected to be final, which is the one that also carries #376.

## What I checked

- **Lint and layers:** ruff check, ruff format, lint-imports (3 contracts kept), deptry: clean.
- **Fast suite:** 5544 passed, 1 skipped (matches the author's claim).
- **Browser suite (Chromium):** 59 passed, 1 skipped (the quarantined #365 test).
- **Golden change:** only `tests/unit/__snapshots__/test_cli_golden.ambr`: the `--chapters` help of `script` and `convert`, the `listen` row in the top-level help, and one new `listen --help` snapshot appended as the last parametrize case. No report, script, job.json or audio.json golden changes. Claim verified.
- **Commit messages:** no closing keywords. The PR body closes #119 and #154.
- **#119 on the Time Machine (corpus EPUB):**
  - `script --chapters 5,3,17,2` writes "Read in the chosen order, not as printed: 5. III, 3. I, 17. Colophon, 2. Imprint." and the script starts with chapter III.
  - `convert --chapters 5,3,2` (FakeVoice, real ffmpeg): the read-along file lists III, I, Imprint with MP3s `01 III`, `02 I`, `03 Imprint`.
  - The listen page for that job finds all 340 chunks on the page, and the chunk start times are increasing.
  - Printed order adds no line, so the existing goldens stay.
- **#119 code:** `JobSettings.chapters` keeps order and drops repeats, and a set is sorted. `selected` keeps order. `prepare_script` puts the chosen chapters first, then the others in printed order. `job.json`, `audio.json` and the API keep the order (`list`, not `sorted`). The page keeps the order from the report's settings. The browser test covers keyboard, focus, the status line and axe in light and dark, and checks that the listen page plays Methods first.
- **#154 serving scope (mutation probes on `ServerState.listening` and `check_outside`, run against test_web_outside, test_cli_listen, test_web_player):**
  - M1 outside job given the web's D-295 list (recorded, saved, default): killed.
  - M2 recorded folder (`audiobook.json` in the outside work folder) tried before the named folder: **survives**.
  - M3 the settings file's (saved) output folder as a fallback: **survives**.
  - M4 the default output folder as a fallback: killed.
  - M5 `check_outside` without the document-record check: **survives**.
  - M6 no "other version" message: killed.
- **Path traversal:** `..%2F…`, `%2E%2E`, `audio.json`, `document.json`, a stray `other.mp3`, a link out of the folder and a renamed file all give 404 (the PR's tests). Every name goes through `record.names` and `in_folder`, unchanged from main.
- **Read-only:** DELETE of the document, DELETE of its chunks and POST of a job give 404 for an outside id; the document page gives 404.
- **Binding:** `listen` goes through `web.run` → `bind()`, the same 127.0.0.1-only path as `ui`.

## Deviations from the plan (accepted; for the KB)

- `listen` opens the start page, which lists the job under "Audiobooks from the command line", instead of opening `/documents/<id>/listen` directly. The token exchange goes through `/start`, so this is simpler and loses nothing.
- Refusal exit codes follow the existing `Exit` codes: no audiobook or missing files → 3, other version or broken record → 1. The plan said 2 for all of them.

## Fix list

### Should-fix

**S1. When the web interface already holds the same file, `listen` opens the web's audiobook instead of the one it was asked for.**

Both kinds of document use the same id, the first 16 hex digits of the file's SHA-256 (D-198). `ServerState.listening` looks in the web store first. A person who once opened `paper.pdf` in the interface, then ran `convert` and `listen` on it, clicks the start page's "Audiobooks from the command line" link and gets the web document's listen page. That page shows "no audiobook" when the web never made one, or plays the web's audiobook, which may have other chapters, voice or speed. Meanwhile `listen` printed that the job was checked and ready.

Reproduced on ed60ec6: the `outside_job` fixture, then `upload(client, <same PDF bytes>)`, then GET `/documents/<id>/listen` gives no `player-data`.

Fix: give a command-line job a route key that can never equal a web document id. For example, `OutsideJob.id` returns `cli-<document>`, which `DocumentStore`'s `ID` pattern never matches. Then:
- `listening()` resolves that key to the outside job;
- the audio record is still checked against `OutsideJob.document` (the hash);
- the start page link, the listen page and the audiobook route use the key.

Tests (TestClient):
- with the same file also in the web store, the outside link plays the outside job's audiobook from its named folder;
- the web document's own listen page still uses its own D-295 folders;
- `/documents/<16-hex id>/listen` does not reach the outside job.

**S2. The serving scope has no test for two of the folders it must never use (M2 and M3 survive).**

`test_only_the_named_folder_is_tried` moves the files into the web's default output folder only. If an outside job also tried the recorded folder from `audiobook.json`, or the settings file's output folder, every test still passes. This is the #345 rule: each part of a safety mechanism needs a test that fails without it.

Add two TestClient tests. In each, the named folder is an empty folder and the real files sit elsewhere:
- (a) a valid web record `<work>/audiobook.json` (`format` "sci2audio-web-audiobook", `version` 1, the document id, `folder` = the folder holding the files);
- (b) the server's settings file names that folder as `output_folder`.

Both must show no `player-data` on the listen page and give 404 on the audiobook route. Each test must fail on its mutant: M2 for (a) is `(recorded_folder(job.work, job.id), job.folder)`, and M3 for (b) is `(job.folder, saved.output_folder)`.

### Nits

**N1. `check_outside`'s document-record check is untested (M5 survives).** Add a `test_cli_listen` case: `document.json` removed from the working folder → a non-zero exit with "can't be read", and no server start (`started == []`).

**N2. `listen` reads the whole FILE into memory and hashes it twice** (`source.read_bytes()`, plus `env.work_folder` when `--work-folder` is not given). Hash it once, streamed in 1 MB blocks as `default_work_folder` does, and reuse that digest.

**N3. The PR body and the CHANGELOG describe the Move buttons wrongly.** They say the buttons are "visually hidden" and shown "only for chosen chapters". In the code, every chapter gets visible buttons, which are drawn `hidden` and shown once `app.js` has bound them; only the chapter title in the button's name is visually hidden. Correct both texts to match the code. Keep the behaviour.

## To check in round 2 (with #376 and main merged in)

- #376: the `publisher` flag in the report JSON (explain the golden diff), `ChapterOut`, the hint in en and de, and a browser test on the Time Machine with axe light and dark.
- #153 for outside jobs: `position.json` is then written into the command line's working folder. Check that the POST resolves the job through the same key as S1, keeps the token, origin and stamp (409) checks, and writes nothing into the output folder.
- Heavy checks on that round if it is expected to be final: the `ci:full` label (three systems) on the head, and the nightly Hypothesis profile on `test_app_script`, `test_app_settings` and `test_app_chapters`.
