# Review PR #552, round 1 (project audiobook folder + project.json, closes #469)

Reviewer: app-lane batch review thread. Head reviewed: **2ffdd3f** (base 1cf1f65 + merges). Critical.
Verdict: **changes required**: 4 required items (R1 to R4), none of them data loss today; R1 and R2 matter because PR 3's removal reads this record. One fix commit for all four.

## What I checked

- Whole diff (14 files). CI on 2ffdd3f: ubuntu, macOS, Windows, browser, ZAP all green.
- Local baseline: the 6 affected test files pass (156 passed, 1 skipped).
- **Mutants:** 20 run against test_web_project, test_web_audio, test_web_player, test_web_remove, test_web_joined, test_web_markers_survive. 19 killed (the PR's 10 guards plus format, version as bool, SHA-256 shape, absolute path, NUL, negative size, the player's own-folder candidates, the `record_files` call in the task, the cut of numbered names). p20 (`PurePosixPath` → `Path` for the stem) survives on Linux. That's expected, because it only differs on Windows, where the `C:paper.pdf` / `dir\paper.pdf` tests cover it (the first ci:full run caught that exact bug).
- Probes: see R1 and R2.
- Plan §7: `web/api.py` not touched (the audio route needed no change: the folder is claimed inside the job). Plan A2 holds: `mkdir` without `exist_ok`, numbered names, never taking over an existing folder or file.

## Required (exact list)

**R1: the record's `name` is trusted as a folder name.** `read_project` checks only that `name` is a string, and `_numbered(name, 1)` returns it unchanged, so `audiobook_folder` makes `output / name`. Probe with a `project.json` written by `write_project`: name `"../escape"` makes `<output>/../escape` (outside the output folder), an absolute name makes that absolute folder, and `"a/b"` fails the job. Fix: a record whose `name` is not already a clean folder name (empty, a separator, `..`, `.`, a drive, anything `clean`/`cut` would change, over 60 characters or 80 bytes) reads as no record. Also, `audiobook_folder` refuses a made folder whose parent is not `output`. Test: those four names plus `"."`; nothing is made outside `output`, and the job fails naming the record or gets a fresh record (your choice, stated in the PR body).

**R2: a recorded folder that is made again is recorded twice.** Probe: make the folder, record a file, remove the file and the folder, then call `audiobook_folder` again. The record now lists `<output>/paper` twice. `record_files` then updates both entries, and PR 3's warning ("one line per recorded folder") and its `shared` cross-check would count it twice. Fix: when the made folder's path is already recorded, that entry is replaced (its files list reset), never appended. Test: after a remake, `project.folders()` lists the path once.

**R3: the old-reader and old-file tests of plan A7 (D-730) are missing.**
- Old reader: with `project.json` removed after a job, the listen page still finds the audiobook through `audiobook.json` alone, which is what a version before this PR reads. Your new test covers the opposite case (only `project.json`).
- Old file: a project in the pre-#469 layout (audiobook files flat in the output folder, `audiobook.json` naming the output folder, no `project.json`) still listens. Its next audiobook goes into `<output>/<name>/`, and every flat file keeps its bytes. The `elsewhere` test in test_web_player used to cover the first half, but it now records `book_folder(elsewhere)`, so the flat layout is no longer tested anywhere.

**R4: texts that are no longer true.**
- The PR body (plan H2) names each changed assertion. The one that changed meaning is in test_web_audio around `test_cancelling_while_speaking_keeps_the_chunks`: `not output.exists() or list(output.iterdir()) == []` became "no file under output", because a cancelled first run now leaves an empty project folder. Name it with that reason.
- `web/player.py`'s module docstring ("the folder is only ever one of three") and the `audiobook` route docstring in `web/api.py` ("only from the recorded, the saved or the default output folder") must name the project's own folders too. The api.py docstring is the only change allowed in that file.

## Notes (no action)

- N1: `record_files` keeps an earlier entry while its file exists, without checking that the file still matches. Plan A5 said "while it still matches". This is safe, because PR 3 deletes only on a size and SHA-256 match, so a stale entry just keeps the file as `changed`. Accepted.
- N2: if the person deletes the project folder and makes a folder of the same name themselves, it is used as the recorded folder (`_real_folder` and the path match). Nothing is deleted or replaced without "Replace these files" and PR 3's hash match. Accepted.
- N3: a first audio run that fails or is cancelled leaves an empty recorded project folder in the output folder (plan A2: claimed before the job). The next run uses it. Accepted.
- N4: output folder spelled differently (case on macOS, a link to it) makes a `(2)` folder instead of reusing the first one. Accepted, rare.

## Next round

One fix commit for R1 to R4, then Linux CI green. Round 2 then needs `ci:full` again (final round, three systems), and I re-run the 20 mutants plus R1's and R2's guards.
