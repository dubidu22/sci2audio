# Review PR #532, round 1 (per-project data folders and migration, #469 part a)

Reviewer: app-lane batch review thread. Head reviewed: **75dca31** (base 2979dce). Critical (moves user data): reviewed as a safety mechanism.
Verdict: **changes required**: 11 required items (R1 to R11), 2 of them blocking defects (R1, R2), the rest test gaps where a guard's mutant survives or a plan item is missing. Branch stays frozen except for **one fix commit** covering R1 to R11.

## What I checked

- Read: plan (D-747 to D-752, D-754), CLAUDE.md, rules 1.4.4, review lessons, the whole diff (16 files).
- CI on 75dca31: Linux, macOS, Windows fast suites green; browser, ZAP, CodeQL green. The Windows job ran the symlink tests and the junction test (none of `test_app_projects.py` is in its 12 skips).
- Local: the PR's tests pass (Python 3.12.3).
- **Exhaustive cut points** (my probe, not in the PR): for each of the 4 cases the uncut run's file operations were counted (merge 28, merge-across 71) and the move was cut at every k from 0 to that count, then run again. Every case passed, also with two stronger checks: the new folder's own files are unchanged, and fast/across end with the digest equal to the original. So M5/M6/M8/M9/M10 hold in code; R6 is about the test.
- **Mutants** (19, run against test_app_projects, test_web_projects, test_cli_project_folders, test_web_remove, test_app_chunks):

| # | Mutant | Result |
|---|---|---|
| a | `_kind`: `lstat()` → `stat()` | killed (`test_a_link_in_place_of_an_old_folder_is_never_followed`) |
| b | `_kind`: `S_ISLNK(mode) or` removed | survives, **equivalent** (see N1) |
| c | `_real_folder` → `is_dir()` | killed (same test) |
| w | `project_folder`: legacy check → `is_dir()` | killed (same test) |
| d | `_same`: hash compare → `True` after the size check | **survives** (R3) |
| e | `_place`: `if _lexists(target)` → `if False` | killed |
| f | `_copy_checked`: digest check removed | killed |
| g | busy probe removed | killed |
| h | `_prune` → `shutil.rmtree` | killed |
| i | `_discard(staging)` → `shutil.rmtree(staging, ignore_errors=True)` | survives, equivalent (rmtree unlinks links, never follows them; the PR body says it is killed: R9) |
| k | `_remove_copied`: `_same` re-check removed | **survives** (R4) |
| m | `migrate_all`: id filter removed | killed |
| o | old root `rmdir` → `rmtree` | killed |
| q | `DocumentStore._folder`: `not _is_link(old)` removed | **survives** (R5a) |
| r | `_inside_root`: parent check removed | survives, equivalent (the resolve check below it refuses the same folders) |
| v | `_make_folders`: link/file refusal removed | **survives** (R5b) |
| x | `_copy_folder` copies what a link points to | **survives** (R5c) |
| y | preview move: `is_symlink` check removed | survives (R10) |
| z | `_migrate`: "target is not a folder" check removed | the suite **hangs** (no return in 600 s): the R1 loop |

## Required (exact list)

**R1 (blocking): `_merge_file` can loop forever, and the server never starts.** `_lexists` answers True when `lstat` fails with anything but "not found", and `_same` then answers False, so every numbered name looks taken and the `while True` never ends. Reproduced: a regular file named `from-earlier-version` in the new project folder → `migrate_one` does not return (killed after 5 s); `migrate_all` runs in `ServerState.__post_init__`, so the server hangs before serving, on every start. The same happens when `lstat` is refused (EACCES) and with mutant z. Fix: a candidate whose `lstat` fails with an error other than FileNotFoundError ends the attempt with OSError (the file stays in the old folder and is listed in `left`); and the numbering stops with OSError after a fixed bound. Test: `from-earlier-version` as a regular file in the new folder, one old file that differs → the call returns (test under a pytest-timeout of a few seconds), the old file is unchanged in the old folder and in `outcome.left`, the new folder unchanged.

**R2 (blocking): the job lock is released for the whole copy and merge, not just around the rename (M5).** `_migrate` probes `job.lock` and releases it at once; the copy across file systems (minutes for a large speech cache) and the file-by-file merge then run with the old folder unlocked. Probe: during the copy a `work_folder_lock(old)` succeeds (an older-version job, or a command-line run that gave up after the 10 s migration wait and fell back to the old folder, M2/M7), writes `audio.json`; the move ends COPIED with the stale `audio.json` in the project folder, and the next start puts the newest record into `from-earlier-version/`. No byte is lost, but the project uses the stale record and the person's newest one is hidden. Fix: hold the old folder's lock for the whole move: during the copy, the commit, the removal of the originals and the merge; release it only right before the single folder rename on Windows (plan M5), keep it across that rename on Linux and macOS (a folder with an open file can be renamed there); never copy or read `job.lock` while it is held (Windows refuses reading a locked byte); remove it in `_prune` after releasing. Tests: a lock attempt on the old folder raises JobBusyError (a) during the copy across file systems, (b) during a merge, (c) on Linux and macOS during the fast rename (patch `_rename` to try the lock first); and the probe's case ends with no `from-earlier-version/` entry.

**R3: the SHA-256 part of `_same` has no test** (mutant d survives; the PR body's mutant "`_same` returns True" also skips the size check, so it is killed by size alone). Test: merge where an old file and the new folder's file have the same size and different bytes (and the same mtime, set with `os.utime`) → the new file unchanged, the old bytes in `from-earlier-version/`. Same for `_remove_copied`'s re-check (covered by R4's test with a same-size change).

**R4: the re-check before removing originals after a copy has no test** (mutant k deletes every old file after the commit and survives). Test: across file systems, an old file rewritten after its copy was made (same size, other bytes; patch `_copy_checked` as a writer that ignores the lock) → that old file is not deleted; after the next run its bytes are in the project folder or `from-earlier-version/`, none lost.

**R5: three link guards have no test.**
- (a) mutant q: test that an old folder `<legacy>/<id>` that is a symbolic link to a folder holding `source/` is not listed and not opened through the link: `store.all()` and `store.get(id)` do not return it, and uploading the same bytes writes into the project root, nothing into the link's target.
- (b) mutant v, and the reads through a link: when a folder inside the new project folder is a link (e.g. `chunks` → an outside folder), the merge neither writes, compares nor removes through it. Today `_lexists`/`_same` look through such a link, so an old file is deleted because an identical file sits in the link's target. Fix: a place in the new folder (or in `from-earlier-version/`) is used or compared only when every folder between the project folder and it is a real folder; otherwise the old file stays (in `left`) or goes to `from-earlier-version/`. Test: `chunks` in the new folder a link to an outside folder holding one file identical to an old chunk and none of the others → the outside folder unchanged (no file added or removed), every old chunk's bytes still in the old folder or `from-earlier-version/`.
- (c) mutant x: across file systems (M6 path) an old folder holding a link to an outside file and a link to an outside folder → nothing of either target is copied, both links in `outcome.left`, targets unchanged.

**R6: MT2 does not reach every cut point.** The Hypothesis test samples 60 of 4 × 61 combinations, and its count stops at 60 while merge-across needs 71 operations, so cut points 61 to 71 inside M8 across file systems are never tried. Make it exhaustive: per case, count an uncut run's operations, then cut at every k from 0 to that count (about 5 s locally for all four). Also assert, as plan MT2 says: the new folder's own files from before the move are unchanged after the re-run, and the fast and across cases end with a digest equal to the original (no `from-earlier-version/`).

**R7: MT10 on Windows is missing.** The plan asks for a Windows CI test with a file of the old folder held open; the PR only patches `_rename`. Add a Windows-only test (keep the patched one): a file in the old folder open in the test, `migrate_one` → SKIPPED, the folder intact and still used (`project_folder` gives the old folder), and after closing it the next call moves it.

**R8: M1's terminal line is missing** and not named as dropped. Print one line before moving when at least one old project folder is found ("Moving N projects to their new folders…"), and one line when the old root is a link and is therefore not moved (today that case returns silently). Test with caplog or capsys.

**R9: PR body mutant table**: replace the `_same` row with mutant d (and its killing test from R3), mark the `shutil.rmtree(staging)` row equivalent (it is: rmtree never follows links), and add rows for R4, R5a/b/c, R1 and R2's guards.

**R10: voice preview move** (`web/state.py move_old_folders`) checks `is_symlink` but not a Windows junction (mutant y has no test). Use `projects._real_folder` (or a shared public helper) for `old_preview`, and add a POSIX test with a linked `preview` folder (not moved, target unchanged).

**R11: a staging copy left when the commit rename fails is never removed.** If the project folder appears during a long copy, `_rename(staging, target)` fails, the outcome is SKIPPED, and from then on the merge path runs, which never discards `projects/.moving-<id>/` (possibly gigabytes). Fix: the merge path discards a leftover `.moving-<id>` too (same `_discard`). Test: patch the commit rename to create the target first and fail → after the next run no `.moving-<id>` and every old file in the project folder.

## Notes (no action)

- **N1, the coordinator's question on `_kind`:** the `S_ISLNK` check is equivalent on every system (an `lstat` of a symbolic link is neither folder nor regular file); the real guard is `lstat` instead of `stat` (mutants a, c, w), and `test_a_link_in_place_…` kills it on Linux and also ran on Windows CI. The junction check is covered by the Windows junction test, which ran on windows-latest. **No extra POSIX symlink test for `_kind`**; the missing link tests are R5.
- N2: `_place` fallback checks `_lexists(target)` and then renames, which replaces on Linux and macOS if a file appears in between (one call wide; Python has no no-replace rename). Accepted.
- N3: while an old folder is skipped, the command line (`project_folder`: new folder if it exists) and the server (`_folder`: new folder only if it has `source/`) can pick different folders when a command-line run made a new folder without `source/`. Lasts until the next start moves it. Accepted.
- N4: verified fine: Documents and the output folder are never read or written (M11); `audiobook.json` moves byte for byte (M12); `--work-folder` test (MT13); D-164 equality test on the new root (H8); `web/api.py` and `web/pages.py` unchanged; privacy text en/de matches the code (D-293); M8 into `source/` with another file name leaves two sources, the newest wins as in the `in_use` case.

## Next round

One fix commit for R1 to R11, Linux CI green, then `ci:full` (three systems) since R2 and R7 are system-specific. Final round then: mutation (my mutants a to z re-run plus the new ones), exhaustive cut points, three-system run on the head.
