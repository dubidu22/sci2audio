# Per-project folders and removal: #469, #470

Status: **APPROVED as D-752 (18 Nov 13:47Z)**, all Q1 to Q7 as recommended; §8 decisions are D-747 to D-751. Additions (§11): MT2 also injects crash points inside M8; PR 1 keeps `--work-folder` behaviour unchanged, with a test; each PR body lists the mutant for every S test it covers. PR 3 stays uncoded until Colin's answer 1 is relayed.
Author: app-lane thread "Plan per-project folders and removal", 18 Nov 2026. Base: main 96de4a3.
Read: #469, #470 (+ comment on markers.json), CLAUDE.md, KB D-164, D-198, D-199, D-216, D-295, D-353 to D-363, rules 1.4.4 + state, plans/issue120-remove-document-plan.md, plans/general-marker-plan.md, REVIEW LESSONS (memory archive), decisions D-712 to D-745.

Earlier PRs in this batch that built on a model this PR changes: none yet. PR 2 builds on PR 1's folder roots, PR 3 on PR 2's manifest; each PR body repeats this line for its predecessors (D-718).

## 0. Decided by Colin (D-754, 18 Nov 13:52Z, "i approve your recom"); each is still one switch

| # | Assumption | Where it lives in code | What changes if Colin answers otherwise |
|---|---|---|---|
| A1 | On removal the audiobook is **deleted by default**, with a "Keep the audiobook files" tick box | one constant `KEEP_AUDIOBOOK_DEFAULT = False` in `web/pages.py` (the box's initial state). The API has **no default**: `keep_audiobook` is a required parameter | "always": the box is not drawn, the page sends `false`. "only when ticked": the constant becomes `True` (the box reads "Delete the audiobook files too", unticked) |
| A2 | The visible project folder is `Documents/sci2audio/<project>/`; the cache stays outside Documents | `default_output_folder()` (unchanged, D-199) + `audiobook_folder_name()`; data root `default_work_root()` | "one folder": `default_work_root()` points into the output folder; the migration engine of PR 1 moves projects a second time (it is root-agnostic and idempotent) |
| A3 | Milestone v1.2 | issue milestones | none in code |

A1 to A3 are Colin's decisions now (D-754), no longer assumptions. PR 3 (#470) is unblocked and is written after PR 2 and after web PR 4 (#520 #521) has merged.

My reading of A2 (needs the coordinator's ruling, Q1 in §9): the folder a person sees in Documents holds **what they asked for: the audiobook**. Everything sci2audio keeps for its own work (copy of the file, analysis, speech cache, records, position, markers) goes to one folder per project in the app's **data** folder, out of the OS cache (so no clean-up deletes markers or positions) and out of Documents (no iCloud/OneDrive upload of hundreds of MB, no conflict copies of `position.json` or `job.lock`, no "optimised storage" eviction of records, and the records do not move when the person changes the output folder in Settings).

## 1. Folder layout (L)

Per project, keyed by the document id (first 16 hex digits of the SHA-256, D-198):

```
<data>/sci2audio/projects/<id>/        # "project data folder", was <cache>/sci2audio/jobs/<id>/
  project.json        NEW (PR 2): name, audiobook folders and the manifest of files written
  source/<name>       copy of the opened file (D-198)
  script/             analysis: script, report.json, report.md (D-199)
  chunks/             speech cache (D-155)
  cover.jpg|png, job.json, audio.json, document.json, audiobook.json,
  position.json (web + CLI listen, #153/#154), markers.json (#474),
  opened.json, about.json (#389), job.lock
<data>/sci2audio/projects/.incoming/   upload staging (global, same volume as the projects)

<output folder>/<Project name>/        # "project audiobook folder" (PR 2), default ~/Documents/sci2audio/<Project name>/
  <book> - 01 <chapter>.mp3 …, <book>.m4b, subtitles, <book>.readalong.json
```

- **L1** `<data>` = `platformdirs.user_data_path("sci2audio", appauthor=False)`: macOS `~/Library/Application Support/sci2audio`, Linux `~/.local/share/sci2audio`, Windows `%LOCALAPPDATA%\sci2audio` (the models folder, D-164, already lives there). On Windows today's cache root is `%LOCALAPPDATA%\sci2audio\Cache`, so old and new roots are on one volume on all three systems by default.
- **L2** The inner layout of the data folder stays as today (flat records, `source/`, `script/`, `chunks/`). Reason: `AudioChunk.file` (core dataclass) is a path relative to the working folder (`chunks/xx/key.wav`) and `audio.json` stores it; moving `chunks/` out or renaming sub-folders would change a core meaning and every reader, and `--work-folder` / `listen` on old folders would need two readers. A person does not browse this folder; `project.json` names the project inside it.
- **L3** The data folder keeps the id as its name (same bytes find the same folder, D-198; CLI and web use the same folder, D-164/D-216, kept by the existing equality test).
- **L4** Global, not per project (unchanged): settings file, models, voice previews.
- **L5** Speech cache stays inside the data folder (L2). Follow-up issue (filed with PR 1): exclude `chunks/` from Time Machine/backup tools (macOS `tmutil addexclusion` equivalent), since Application Support is backed up and Caches was not.
- **L6** The CLI is unchanged in where audio goes (next to the source or `-o`, D-216); it uses the new data folder for its work (L3). It writes no `project.json` and never takes part in removal.

## 2. Migration of existing projects (M), PR 1

Code: new `app/projects.py` (app layer, because both the CLI and the server call it): `migrate_all(legacy_root, root) -> MigrationReport` and `migrate_one(legacy_root, root, id) -> Outcome`.

- **M1 When.** The server runs `migrate_all` before it answers requests (terminal line "Moving N projects to their new folders…", one per failure). The CLI runs `migrate_one` for its one file in `_work_folder` when no `--work-folder` is given. `--work-folder` is never migrated.
- **M2 Exclusion.** A migration lock `<root>/.migrate.lock` (same `msvcrt`/`fcntl` lock as `app/lock.py`) so two new-version processes never migrate at once; a second process waits up to 10 s, then works on the legacy folder as it is (M7).
- **M3 Candidates.** Only entries of `<cache>/sci2audio/jobs/` whose name matches `ID` and that are real folders. A link or Windows junction is never followed or moved: it is left and reported. `.incoming/`: stale `.part` files (older than an hour, today's rule) removed; the folder removed only if then empty. Legacy `jobs/` and its parent removed only with `rmdir` (never recursive) when empty.
- **M4 Busy.** For each id the old folder's `work_folder_lock` is taken non-blocking; busy (an old-version job runs) means skip, still listed (M7), retried next start.
- **M5 Fast path, target missing:** `os.rename(old, new)` (atomic: before the call the project is old, after it new; no half state). The lock is released just before the rename because Windows cannot rename a folder holding an open file; the migration lock (M2) keeps new-version processes out of that window. Rename refused (Windows file open in another program: `PermissionError`) means skip and retry next start.
- **M6 Copy path, `EXDEV` (XDG folders on two disks):** copy the tree into `<root>/.moving-<id>/` (ours; a leftover from a crash is removed first), fsync, verify every file by size and SHA-256 against the old file, then `os.rename(staging, new)` (atomic commit), then remove the old folder with the D-355 walker (source last). A crash before the commit leaves the old folder intact; after it, M8 applies.
- **M7 Listing during the transition.** `DocumentStore.get(id)` returns the new folder if it has `source/`, else the legacy folder if it has `source/` (read and written in place until a later start moves it). So a skipped or failed migration never hides a document, and `listen` (#154, #381) finds both layouts. Removal of a legacy-folder project works as today on that folder (#120 rules).
- **M8 Target exists** (crash after commit, the person opened the same bytes in the new version first, or an old server still running wrote into the old folder): merge file by file, never overwrite. File missing in new: moved in (rename, or copy+verify). Same size and SHA-256: the old copy is removed. Different: the old copy goes to `new/from-earlier-version/<relative path>` (` (2)` etc. if that name is taken and differs). Then empty old folders go by `rmdir`, `job.lock` last.
- **M9 Never loses, never overwrites:** every step is rename-or-copy-verify-then-remove; `os.replace` is never used on a target that exists; nothing is removed whose copy is not verified.
- **M10 Idempotent and resumable:** running it again is a no-op; any crash point leaves a state that M5/M6/M8 finish. Shown by a crash-point property test (MT2).
- **M11 iCloud / OneDrive.** The migration never reads or writes the output folder or Documents: audiobooks already made stay where they are (flat in the output folder) and are never moved (they may be open in another player). It moves only data-folder content, which is not synced.
- **M12 Old audiobooks.** A migrated project's `audiobook.json` keeps naming the flat folder, so the player finds the old audiobook as today (D-295). Its next audiobook goes to its project audiobook folder (PR 2).

## 3. Project audiobook folder and manifest (A), PR 2

- **A1 Name.** `<output folder>/<Project name>/`, the project name being the opened file's name without suffix (what the library shows), cleaned by `output.names.clean` (strips forbidden, unassigned `Cn` and surrogate `Cs` code points, reserved Windows names, trailing dots/spaces; #491, #493) and cut to **60 characters / 80 UTF-8 bytes** so `<Documents>\sci2audio\<folder>\<file>` stays inside Windows' 260-character limit with today's 120-character file names (tested on Windows CI, S13).
- **A2 Claim.** The folder is created with `mkdir(exist_ok=False)` at the first audio run and recorded in `project.json` before the job starts. If the name exists and is not this project's recorded folder, `<name> (2)`, `(3)`… are tried; `mkdir` itself is the atomic check, so case-insensitive file systems (macOS, Windows) and two servers racing are handled by the OS, not by string comparison. A folder sci2audio did not create is never taken over, so **every recorded folder was made by sci2audio for this project**. Once recorded, the name stays even if the file is opened again under another name.
- **A3 Output folder changed in Settings:** the next run claims `<new output folder>/<name>/`; `project.json` keeps both folders.
- **A4 `project.json`** (web layer, `web/project.py`, format `sci2audio-web-project`, version 1): `{format, version, document, name, audiobooks: [{folder, files: [{name, bytes, sha256}]}]}`. Written atomically (`write_texts`) under the work-folder lock. Read strictly like the other web records: size limit 256 KB, link refused, wrong format/version/document or bad JSON means **no manifest** (removal then deletes no audiobook file and says so; the file is never rewritten, renamed or removed, as `markers.json`).
- **A5 What is recorded.** After a successful audio job the web task hashes every file the job reports as written (`Written.m4b`, `mp3s`, `subtitles`, `readalong`) and replaces those names' entries. Entries of earlier runs in the same folder stay while their file still matches (a re-run with fewer chapters leaves the old extra MP3s, which are still sci2audio's). Decisions use **size + SHA-256 only, never mtime** (mtime+size collide on Windows: review lesson). A crash between the job's end and the manifest write leaves unrecorded files; they are kept on removal and named (R5).
- **A6 Player.** `candidate_folders` = recorded folder (audiobook.json, D-295), then the manifest's folders newest first, then `<saved>/<name>`, `<default>/<name>`, then the flat saved/default folders (old audiobooks). The D-295 path checks are unchanged.
- **A7 Additive format checks (D-730 lesson):** an old reader (main before PR 2) ignores `project.json` (test on a folder written by PR 2's code); PR 2 reading a project without `project.json` (migrated or made before) works and records nothing for old audiobooks.

## 4. Removal with warning (R), PR 3, after Colin's answer 1

- **R1 API.** `DELETE /api/v1/documents/{id}?keep_audiobook=true|false`, the parameter **required** (422 without it, nothing deleted): every removal carries the person's choice explicitly, and a retry after a failure resends the same choice (the page keeps the box's state). Answer `RemovedOut` gains `deleted_files`, `deleted_bytes`, `kept: [{path, reason}]` (at most 50, plus `kept_more`), reasons `changed`, `not-recorded`, `link`, `outside`, `shared`, `unreadable`, `kept-by-choice`; `freed_bytes` and `audiobook_folder` stay (D-358).
- **R2 Order**, all under the store's removing mark (D-356) and the work-folder lock held across both steps (today the lock covers only the data folder): (a) 409 when busy, nothing touched; (b) read `project.json`, build the plan (R3, R4); (c) unless kept: delete the planned audiobook files, then `rmdir` each project audiobook folder if empty (R6); (d) the data folder as D-355, source last. A failure in (c) or (d) answers 500 `remove-failed` naming the first path left, and the project stays listed because its source is still there (D-355 kept).
- **R3 Folder checks** (a recorded folder failing any is skipped whole, reason `outside`): absolute, no NUL, no `..` component; not a link or junction itself (`lstat`, `is_junction`); its real path is not, and does not contain, one of: file-system or drive root, home, Documents, the output root itself, the data root, the legacy root, the config folder, the models folder; its real parent is a real folder. (A link higher up, such as a Documents folder moved to another disk, is allowed; the folder itself must be real.)
- **R4 File checks** (failing one keeps the file with its reason): bare name (`player.bare_name`); `lstat` says a regular file, not a link (`link`); its real parent equals the folder's real path (`outside`); size and SHA-256 equal the manifest (`changed`); readable (`unreadable`, e.g. an iCloud file evicted while offline: never delete what cannot be verified); not listed by another project's manifest (`shared`, cross-check over all projects). Right before `unlink` the parent's real path and the file's `lstat` are checked again (TOCTOU window kept to one call; `unlink` of a swapped-in link removes the link, never its target).
- **R5 Only listed files.** Anything else in a project audiobook folder stays (`not-recorded`), so the folder stays too. Nothing outside the project data folder and the recorded project audiobook folders is ever deleted: **audiobooks made before #469 in the flat output folder are never deleted**; the warning names them as staying (this narrows #470's seeding idea, Q4).
- **R6 Folder removal** is `rmdir` only (never recursive), and only for recorded project folders. Exception for system clutter (Q5): `.DS_Store`, `Thumbs.db`, `desktop.ini` as regular files under 64 KB are removed when they are the last entries, so a folder Finder or Explorer opened can still go.
- **R7 The warning** (`_remove.html` box on the library row and the document page, D-359/D-360 kept, still a disclosure with one destructive button, no `confirm()`):
  1. Goes: "the copy of the file, its analysis, the speech cache, the listening position: {size}" and the marker count read from `markers.json` as the box is drawn ("Your {n} markers and their notes go too", unreadable file: "Your markers file goes too"; D-728 ruling 3 kept).
  2. Audiobook, one line per recorded folder: "{count} audiobook files in {folder}: {size}" (counted by `stat` when drawn; hashes only at removal). Tick box "Keep the audiobook files", initial state from `KEEP_AUDIOBOOK_DEFAULT`, its label names the folder(s).
  3. Stays: the file you opened, wherever it is; files in those folders that sci2audio did not write or that changed since; "Your earlier audiobook in {folder} stays" when `audiobook.json` names a folder that is not a project folder.
  4. The destructive button "Remove {name} now" is last, on its own row after the "Stays" text; there is **no other button in the box** (the safe action is closing the disclosure at its top), so the destructive button never sits beside a safe one (D-733 lesson). D-362 kept: no button while a job runs.
- **R8 After the press** (D-361 kept): status region says "{name} was removed with {n} audiobook files." plus "{k} files stayed in {folder}: they changed since sci2audio wrote them or were not made by it." when any stayed; focus to it. The button is disabled while the request runs; on failure the box (and its tick state) stays as it was.
- **R9 Strings.** `[remove]` new keys and `error.remove-failed` text in `en.toml` and `de.toml` (Sie, „…“, D-292); privacy page `work` and `remove` (D-293: every sentence matches the code), Settings hint for the output folder ("sci2audio makes one folder per project in it", PR 2).

## 5. Safety tests: each fails with its guard removed (S)

Every one is shown failing on a mutant with the guard deleted (listed in the PR body with the mutant), as the deletion review checks of #120 ask.

- **S1** A file the person put in a project audiobook folder (not in the manifest) survives byte for byte; the folder stays.
- **S2** A manifest entry whose file changed survives: (a) other size; (b) **same size, same mtime, other bytes** (proves hash, not mtime+size).
- **S3** A manifest entry that is a symlink (and on Windows CI a junction folder) to a file elsewhere: the target survives, the link is kept as `link`.
- **S4** Manifest folder = output root, home, Documents, data root, legacy root, models, config, `/`, or the folder holding a kept original: no file under it is deleted and it is never removed.
- **S5** File entry with `..`, a separator, an absolute path, NUL, or a drive: refused; folder with a `..` component: refused.
- **S6** Two projects with the same name: folders `X` and `X (2)`; removing one leaves the other's audiobook intact. A crafted file listed by both manifests is kept as `shared`.
- **S7** 409 while a job runs (this server's and another process's lock): nothing deleted, audiobook files included (extends the #120 tests).
- **S8** `keep_audiobook=true` deletes no audiobook file; a request without the parameter answers 422 and deletes nothing.
- **S9** Faults, run as a non-root user (root ignores modes) and on Windows CI (locked files): a file that cannot be deleted gives 500 naming it; the project is still listed; pressing again finishes.
- **S10** TOCTOU: the folder swapped for a link after planning (patched between plan and unlink): nothing outside is touched.
- **S11** `rmdir` never recursive: a folder with `notes.txt` stays; with only `.DS_Store` it goes; a `.DS_Store` that is a link or over 64 KB keeps the folder.
- **S12** Removing a legacy-folder project (not migrated) works as #120 and never touches the flat output folder.
- **S13** Longest names: a 60-character project folder with a 120-character chapter file writes and removes on Windows CI.
- **S14** The page's box: the destructive button has no sibling button; the tick box's state goes into the request (browser test reads the request), and a failed request keeps it.

Migration tests (MT), PR 1:
- **MT1** A library built in the v1.1/v1.3 layout (source, script, chunks, every record, `position.json`, `markers.json`, `job.lock`) opens with every document, position, marker and audiobook intact; tree digest (relative path, size, SHA-256) equal before and after; old root gone.
- **MT2** Crash-point property test (Hypothesis, `ci` profile): an exception injected at the k-th rename/copy/unlink of M5, M6, M8: after the crash every document is listed (legacy or new) and no file is lost; the next start finishes; digest equal (with `from-earlier-version/` allowed only in M8 cases).
- **MT3** Target exists with different files: nothing overwritten, old copies in `from-earlier-version/`. **MT4** identical target: old removed.
- **MT5** Busy old folder (lock held from another process): skipped, listed, migrated next start.
- **MT6** `EXDEV` (patched): copy path; a corrupted copy (byte flipped in staging) is discarded and the old folder stays intact.
- **MT7** A link or junction among the old folders or inside one: never followed, never moved.
- **MT8** Running the migration twice is a no-op (second-run contract).
- **MT9** CLI: `convert`/`script`/`listen` on a file with an old-layout folder migrate that one id; `--work-folder` with an old-layout folder works and is not migrated; the D-164 equality test (`default_work_folder == default_work_root()/id`) moves to the new root.
- **MT10** Windows CI: a file of the old folder held open: rename refused, project listed from the legacy folder.
- **MT11** Two processes start at once: one migrates, the other waits or works on the legacy folder (M2).
- **MT12** Full walk (acceptance of #469): with every platformdirs folder pointed into a temporary home, a web job (open, analyse, audio with the fake voice, listen, save a position, set a marker) writes nothing outside `<data>/projects/<id>/`, `<data>/projects/.incoming/`, `<output>/<name>/`, the settings file and the models folder.

## 6. Test-harness changes (H)

- **H1** `tests/unit/web_helpers.make_config`: new `legacy_root` field (default `tmp/legacy-jobs`, absent). `work_root` keeps its name (now the projects root) to avoid churning ~40 test files.
- **H2** Tests that expect the audiobook flat in `tmp/out` (5 direct paths, about 18 files reading `output_folder`) go through a new helper `audiobook_folder(config, document)` (PR 2). No assertion is weakened; each changed line is listed in the PR body.
- **H3** New fixtures `old_library(tmp, layout="v1.1"|"v1.3")` and `tree_digest(root)` in `tests/unit/project_helpers.py`.
- **H4** Fixture pointing `platformdirs` user data/cache/config/documents at a temporary home (MT12, MT9).
- **H5** `scripts/zap_scan.py`: the DELETE call in `_every_api_route` sends `keep_audiobook` (PR 3); the 500 answer keeps its own description (#171 lesson).
- **H6** `tests/browser/test_remove.py`: the new box (S14); no Linux key chords, no pixel equality, no click-focus assumptions (#497 to #511 lessons).
- **H7** Fault tests that need modes run as non-root via the `setpriv` pattern locally; CI runners are non-root already.
- **H8** The `test_app_chunks` D-164 test changes its expected root (MT9); the change is named in the PR.

## 7. PR split and order (P)

| PR | Issue part | Contents | Files (by lane) | Critical | Depends on |
|---|---|---|---|---|---|
| **PR 1** | #469 a | new data root, migration (M1 to M12), store reads new + legacy, CLI uses it, privacy strings | app: `config.py`, new `projects.py`, `__init__.py`; cli: `cli.py` (`_work_folder`, listen); web: `config.py`, `documents.py` (roots, `get`/`all`, `.incoming`), `state.py` (migration at start, beside `clear_stale_uploads`), `strings/en.toml`, `strings/de.toml` (privacy only) | yes | nothing |
| **PR 2** | #469 b, closes #469 | project audiobook folder + `project.json` manifest (A1 to A7) | web: new `project.py`, `tasks.py` (audio work), `player.py` (`candidate_folders`), `api.py` (only the audio-start route that fills the output folder), strings (Settings hint); output: none (`names.clean` reused) | yes | PR 1 merged |
| **PR 3** | #470, closes #470 | removal with warning (R1 to R9) | web: `documents.py` (`remove`), new `removal.py`, `api.py` (`remove_document` only), `models.py` (`RemovedOut`), `pages.py` (`_removal` only), `templates/_remove.html`, `static/app.js` (remove handler only), strings; `scripts/zap_scan.py` | yes | PR 2 merged and **Colin's answer 1** |

- **Web files and the web lane** (#519 to #521 touch marker data in `web/api.py` and `web/pages.py`): PR 1 does not touch `api.py` or `pages.py`. PR 2 touches one route function in `api.py`. PR 3 touches `remove_document` in `api.py` and `_removal` in `pages.py` only, and starts after the web lane's PR 4 (#520 #521) has merged, merging main first. `strings/*.toml` may conflict textually; resolved by merging main, never by rebasing.
- **Lanes:** the batch spans `app/`, `cli.py` and `web/` (lanes.yml paths). Labels `lane:app`, `risk:high`; the cross-lane files are named here and in each PR body (Q6).
- Each PR: plan items it covers in the body, Linux CI green, then my `ci:full` green, `ci:full` label removed, then review (one review thread for the batch, Opus high). No "fixes #N" in commits; merge main, never rebase; I never merge or force-push; PR bodies start with the attribution lines; one ledger line per PR in `ledger/implementation.md`.
- Rough size: PR 1 about 500 lines of code and 900 of tests; PR 2 about 350 and 600; PR 3 about 500 and 1000.
- Mutation probing, nightly seeds and the three-system run on each PR's final round (critical).

## 8. Decisions (D-747 to D-751)

1. **D-747** Data root moves to the user data folder; inner layout unchanged; id names kept (L1 to L3).
2. **D-748** Migration algorithm M1 to M12 (rename fast path, copy-verify-commit path, merge into `from-earlier-version/`, legacy listing).
3. **D-749** Project audiobook folder naming and claim (A1, A2), 60/80 cap.
4. **D-750** `project.json` manifest format and SHA-256-only decisions (A4, A5).
5. **D-751** Removal: required `keep_audiobook`, order, checks, what stays (R1 to R6); supersedes D-353 and amends D-358, D-359, D-361 once Colin answers question 1.

## 9. Questions for the coordinator (my recommendation first)

- **Q1** A2 reading: the Documents project folder holds the audiobook only; everything else in the data folder (recommended, reasons in §0). Alternative: source copy, analysis and records in the Documents folder too, speech cache outside.
- **Q2** Speech cache stays in the project data folder (L5) because moving it out would change `AudioChunk.file`, a core dataclass meaning; backup exclusion becomes a follow-up issue.
- **Q3** Data folders keep the id as their name (L3).
- **Q4** Audiobooks made before #469 (flat in the output folder) are never deleted, only named as staying (R5). Alternative from #470's text: seed the manifest from `audio.json` and delete them too; I advise against it because it deletes outside any project folder, which the brief forbids.
- **Q5** System clutter files may be removed so an empty project folder can go (R6).
- **Q6** Cross-lane files in one lane:app batch (§7) accepted.
- **Q7** PR 1 can merge on assumption A2 before Colin answers; if he picks "one folder", PR 2 changes the root defaults and the same migration moves projects again, with no data risk.

## 10. Risks

- Windows `MAX_PATH` with the extra folder level (A1, S13).
- iCloud evicted files can't be hashed offline: kept, never deleted (R4).
- A second server of an older version still running during the upgrade writes into the old folder: handled by M8 on the next start.
- Hashing an audiobook after each run costs a few seconds per 100 MB (in the job thread, after the audio is complete).

## 11. Approval additions (D-752)

- Rulings: Q1, Q2, Q3 = D-747; Q4, Q5 = D-751; Q6 = D-752 (name cross-lane files in each PR body); Q7 = D-748 (PR 1 may merge on A2).
- **MT2** also injects crash points inside M8 (the merge into an existing target).
- **MT13** (PR 1): `--work-folder` behaves exactly as before: the named folder is used as given, never migrated, chunks inside it.
- Each PR body lists, for every S test it covers, the mutant (guard removed) that makes it fail.
- PR 2 may be written while PR 1 is in review; PR 3 waits for Colin's answer 1.
