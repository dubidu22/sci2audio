# Light batch audit: app batch, per-project folders (18 Nov 2026)

Scope: the merged diffs of #532 (1cf1f65), #552 (8622f85) and #569 (5a605e5), read together on main 5a605e5. I looked for cross-PR inconsistencies, contract touches, and anything on the user-file delete path. Plan: plans/per-project-folders-plan.md (D-747 to D-754). Auditor: the app-lane review thread.

Result: **no defect found, and no new issue needed.** One note on a pre-existing check window (A2), which is the same class the plan accepted.

## Files touched by the batch

- #532: `app/projects.py` (the move), `app/lock.py` (`FolderLock`), `app/config.py` (`projects` in user data, `jobs` in the cache as `legacy_root`), `web/documents.py` (`project_folder` reads the old folder until it is moved), `web/state.py`, `web/config.py`, `cli.py`, README.
- #552: `web/project.py` (`project.json`, `audiobook_folder`, `record_files`), `web/tasks.py` (the audio job claims the folder and records the files), `web/player.py` (own folders as candidates), and an `web/api.py` docstring.
- #569: `web/removal.py` (plan and carry out), `web/api.py` (`keep_audiobook` required, `RemovedOut`), `web/documents.py` (audiobook step inside the work-folder lock), `web/state.py` (`protected_folders`), `pages.py`, `_remove.html`, `app.js`, strings, `scripts/zap_scan.py`, CHANGELOG.

## Cross-PR consistency

- **The record moves with its folder (#532 × #552).** `project.json` lives in the work folder, so the move carries it, and the removal reads it from `document.folder`, wherever that is now. A folder that has not moved yet, because its lock was busy at start-up, is read where it is. `from-earlier-version/` can hold only an earlier `audiobook.json`, never a `project.json`, because versions before #552 wrote none. Whatever is in it goes with the work folder, which is app data.
- **One lock for all three.** The move (#532 `FolderLock`), the audio job (`run_audio`, `app/audio.py`) and the removal (#569 `_remove_locked`, audiobook step first) all take `<work>/job.lock`.
  - `audiobook_folder` (mkdir plus the record write) and `record_files` run in the job function just outside `run_audio`'s lock.
  - Within the server, the removal's busy check (`_job_on`) covers that span. A command-line run never touches `project.json`.
  - The worst race (a removal and a job's first start at the same instant) leaves an empty project folder or a stale record. It never deletes a file, because the removal deletes only on a recorded size and SHA-256 match.
- **The record's checks match what the removal trusts (#552 × #569).**
  - `read_project` refuses a name that is not already clean (#552 R1), so a recorded folder is always made directly in an output folder.
  - The removal checks each folder again anyway: absolute, no `..`, no link, not protected or above a protected folder, not a drive root.
  - File names in the record and in the removal go through the same `player.bare_name`.
  - The `{folder, files[{name, bytes, sha256}]}` that `record_files` writes is exactly what `plan()` compares.
  - A record that is there but can't be read deletes nothing, and the box says so (#569 R4).
- **Old layouts (D-751).** A pre-#469 audiobook (flat, named by `audiobook.json` only) is never in `project.json`, so it is never deleted, and the box says it stays. The protected folders include the old cache root (`legacy_root`), the current and saved output folders, Documents, home, and the app's own folders.
- **Strings.** en and de have the same key set. Every new `remove.*` key is used by the template, `pages.py` or `app.js`.
- **The user-facing texts agree with each other.**
  - The privacy page's `output` and `remove` lines (from #552 and #569), the CHANGELOG lines and the box all say the same thing: only unchanged files that sci2audio wrote into the document's own folder are deleted, the box keeps them all, and earlier flat audiobooks stay.
  - README says only that files stay on the computer and that the privacy page names the folders, which is still true.

## User-file delete path (everything that deletes in the batch)

- `web/removal.py`: the only deletion in the person's folders. It was reviewed in three rounds, with 46 mutants (43 killed, 3 equivalent) and probes for a link folder, an ancestor swap and the clutter step.
- `web/documents.py` `_remove_folder` (the work folder, app data, from #120): the store refuses a work folder that is a link or junction, or whose real parent is not the root (`_inside_root`). Inside the folder, `_remove_tree` removes a link itself and never follows it.
- `app/projects.py` (#532): deletes only old app-data copies after a verified copy, and only through checked folders (#532 R1 to R5). #544 tracks the one test gap left (no data at risk).
- `app/audio.py` replacing files in the audiobook folder: unchanged by the batch apart from the folder it writes to. It still needs "Replace these files" (D-733).

## Contract touches

- No layer contract, core dataclass, plugin or text-step interface is changed. `lint-imports` passes on main. The `core/content.py` change between 8622f85 and 5a605e5 belongs to B1 (#562, #575), not to this batch.
- HTTP API: `DELETE /api/v1/documents/{id}` now needs `keep_audiobook` (422 without it), and `RemovedOut` gains `deleted_files`, `deleted_bytes`, `audiobook_folder`, `kept[{path, reason, folder}]` and `kept_more`. The only callers are `app.js` and `scripts/zap_scan.py`, and both were updated in #569. Schemathesis runs against the new schema.
- The on-disk format is new: `project.json` (`sci2audio-web-project`, version 1). It is read strictly and covered by #552's tests. `audiobook.json` is unchanged, so a version before #552 still finds the audiobook (the #552 A7 tests).

## Notes (no action)

- A1: the batch's link checks have three helpers, `removal._is_junction`, `documents._is_link` and `pages._linked`. They agree on links and junctions. `pages._linked` reads an OSError as "not a link", which affects only the count the box shows; the removal checks again with lstat.
- A2: the store checks the work folder (`_inside_root`) before it takes the lock, and does not check it again before `_remove_folder` lists it. If the work folder were swapped for a link inside that window, its target's contents would go. This is the same one-call window class the plan accepted for files (#569 N1). It sits in sci2audio's own data folder, not the person's, and it predates the batch (#120). It is accepted, so I filed no issue.

## Out of scope, and issues

- #544 (a linked `from-earlier-version` test) is open, filed in #532 round 2.
- Nothing else in the batch is left without an issue.
