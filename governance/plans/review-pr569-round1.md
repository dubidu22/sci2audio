# Review PR #569, round 1 (removal with warning, closes #470)

Reviewer: app-lane batch review thread. Head reviewed: **ef6d520** (main 8622f85 merged in). Critical (deletes user files).
Verdict: **changes required**: 4 required items (R1 to R4). R1 is a real deletion through a link, narrow but in the one path this PR exists to make safe. One fix commit for all four.

## What I checked

- Whole diff (18 files), against plan §4 R1 to R9 and §5 S1 to S14, and the D-733 rule (the destructive button alone in the box).
- CI on ef6d520: ubuntu, macOS, Windows fast suites green (no test of `test_web_remove_audiobook.py` skipped on Windows); Chromium browser shards and ZAP green; Firefox and WebKit 1/2 green, WebKit 2/2 still running (reported only).
- Local baseline: the 6 affected test files pass (175 passed, 1 skipped).
- **Mutants:** 30 of mine (the author's script is not shared, so these are independent of the PR body's K1 to K19), run against test_web_remove_audiobook, test_web_remove, test_web_projects, test_web_outside, test_web_markers_survive, test_web_project. **28 killed**, each by the S test aimed at it: hash, file link, folder link, guards (each protected folder separately: output, saved, Documents, config, models, data root, old root; and "above" one), drive root, bare name, `..`, shared, both re-checks before unlink, rmdir only, clutter size and link, unreadable kept, step inside the lock, `keep_audiobook` required and honoured, delete error not swallowed, box default, earlier-audiobook line.
  Two survive, both **equivalent**: r15 (`real.parent != folder_real` in `_file_refused`): once the name is bare and the file is a regular file (not a link), its real parent is always the folder's real path. r23 (home not in the protected list): home holds Documents and the data folder, which are protected, so "is or holds a protected folder" refuses home anyway.
- Probes: R1 below.

## Required (exact list)

**R1: `_remove_if_empty` follows a project folder swapped for a link after the plan.** `carry_out` checks each file again before `unlink`, but then lists and deletes the folder's "clutter" through the unchecked path. Probe (the S10 folder test, with the link pointing at a folder of the person's that holds only a `.DS_Store`): the removal answers 200 and **the person's `.DS_Store` is deleted** through the link. Fix: right before listing a folder's entries, check it again as the files are checked: not a link or junction (`lstat`), and its real path equal to the planned one (keep `folder_real` per planned folder). Otherwise leave it and add it to `kept` as `changed`. Test: that probe; the person's `.DS_Store` keeps its bytes, and the folder appears in `kept`.

**R2: S9 asks for real faults; the PR only patches `os.unlink`.** Plan S9: "run as a non-root user … and on Windows CI (locked files)". Add both and keep the patched tests.
- (a) Windows only: an audiobook file held open by the test → 500 `remove-failed` naming it, the document still listed, every file of the project folder still there. Close it, press again → 200, folder gone.
- (b) Linux and macOS, skipped when running as root: the project audiobook folder made read-only (`0o555`) → 500 naming the first file. Restore the mode, press again → 200.

**R3: the message after the press does not say where files stayed** (plan R8: "{k} files stayed in {folder}: …"). `remove.kept_some` has no folder, and folder-level `kept` entries (`outside`, `link`, `unreadable` for a whole folder) are counted as "files". Fix: the message names the folder (the first kept path's folder; when there are several folders, it names the first and the count covers all). Folder-level entries get their own sentence or are left out of the file count (your choice, stated in the PR body). Test it in the browser test that counts the files that stay (en), with the de string checked in a unit test.

**R4: a `project.json` that can't be read gives a false line in the box.** `_removal` then has no own folders, so `audiobook.json`'s folder (the project's own folder) is shown as "Your earlier audiobook in {folder} stays: sci2audio made it before each document had its own folder". That is untrue, and plan A4 says the box must say why nothing is deleted. Fix: when `project.json` exists but reads as no record, the box says the audiobook files stay because sci2audio's record of them can't be read, naming the record's path (new key in en and de, Sie form, „…" quotes). The pre-#469 line is shown only when there is no `project.json` at all. Test: a broken `project.json` → that line, no earlier-audiobook line, nothing deleted on the press.

## Notes (no action)

- N1: the re-check before `unlink` leaves a one-call window (plan R4), as accepted in the plan.
- N2: the web never knows where the opened original lives, so plan S4's "folder holding a kept original" has nothing to guard here.
- N3: the `shared` cross-check skips projects being removed at the same moment; a file listed by two records exists only in a crafted record.
- N4: the PR body's K19 claims a kill by the bare-name test. That mutant (my r15) is equivalent, as above. Mark it so in the table.

## Next round

One fix commit for R1 to R4, then Linux CI green. ci:full again is needed for R2a (final round: three systems). Then I re-run the 30 mutants plus R1's guard.

## Added after the report (D-768)

**R5: CHANGELOG.md Unreleased lines.** Every lane PR with a user-visible change now adds a CHANGELOG Unreleased line (D-768). In the same fix commit, add two lines under `## [Unreleased]`, in the file's existing style: one for #552 (each document's audiobook goes into its own folder under Documents/sci2audio, recorded in `project.json`), and one for #470 (removing a document from the library deletes its audiobook files after a warning; the "Keep the audiobook files" box keeps them; earlier flat audiobooks are never deleted).
