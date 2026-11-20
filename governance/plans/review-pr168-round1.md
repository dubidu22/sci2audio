# Review of PR #168 (#120 remove a document), round 1

Reviewed head `8add896` (base main `47c86fb`), 13 Nov 2026. risk:high, reviewed as critical.

## What I ran

- `ruff check`, `ruff format --check`, `lint-imports` (3 kept), `deptry src`: clean.
- Fast suite locally (Python 3.12.3, root): 2471 passed.
- Browser suite (Chromium): 45 passed.
- `HYPOTHESIS_PROFILE=nightly pytest tests/unit/test_web_*.py`: 304 passed.
- Reflow claim: with the three new `app.css` lines removed, both `test_the_removal_reflows_at_320_pixels` cases fail (page 1057 px wide, the "Remove … now" button). Confirmed: the test guards the CSS.
- **CI on the PR head is red** on all three systems (details in M2).

## Must fix

**M1. A job start that passed the document check before the removal began leaves the document's script on disk after a 200.**
`start_job` calls `_document()` (store.get), then `load_settings`, builds the work, then `board.start`. A removal that runs between the `get` and `board.start` sees no current job (`busy()` returns None) and proceeds; the script job then starts, reads the source (still there, it goes last) and writes `script/` and `job.json` after the removal deleted them. The removal answers 200, the document is no longer listed, and the full listening script and report of the "private by mistake" document stay invisible in the work root. Probe (pauses `start_job` inside `load_settings`, holds the removal at `source`):

```
job start: 202
job end: done
removal: 200
left: ['job.json', 'script', 'script/note.report.json', 'script/note.report.md', 'script/note.script.txt']
listed: []
```

Probe file: `plans/review-pr168-probe-race.py` (drop into `tests/unit/`). D-356 says "during removal the id is gone ... starting a job answers 404", which holds only for a start that begins after the removal marked the id. Fix needs the check and the board start to be atomic against the removal mark, e.g. a store method that, under `_changes`, checks the id is not being removed and still exists and then calls `board.start` (so either the start lands first and `busy()` sees the running job → 409, or the mark lands first → 404). Add this probe as a regression test (both orders).

**M2. CI is red on Linux, macOS and Windows (3 tests).**
- Linux and macOS (CPython 3.12.16 in CI; reproduced locally with 3.13 as a non-root user): `test_a_file_that_cant_be_removed_keeps_the_document_listed` fails because the message names `chunks/c1`, not the wav. Newer `shutil.rmtree` (the stack-based rewrite, in 3.13 and backported to late 3.12 patch releases) catches an error escaping from the handler at the directory step, sets `err.filename` to the directory and calls `onexc` again with the directory's function, so `_retry_writable` runs a nested `rmtree` and the file is tried three times. Local 3.12.3 does not show it, which is why it passed for you. Please don't depend on rmtree's `onexc` internals, which changed between patch releases: walk the tree yourself (`os.scandir`, `follow_symlinks=False`, bottom-up, unlink/rmdir each entry with the read-only retry) so the first path left is known exactly on every Python 3.12+.
- Windows: `test_refused_while_an_audio_job_works_on_the_document` and `test_refused_while_another_process_holds_the_working_folder` fail with PermissionError in the test's `snapshot()` reading `job.lock`, which `msvcrt.locking` holds. Test-only: leave `job.lock` out of the snapshot (or compare its presence, not its bytes).

**M3. A working folder that is a Windows junction is not refused, so its target's contents would be deleted.**
`remove` refuses `folder.is_symlink()`, but on Windows a directory junction is not a symlink; `_remove_folder` then iterates the junction's target and removes everything in it. The PR body says "a working folder that is itself a link is refused", which is not true on one of the three systems. Fix: refuse `folder.is_symlink() or folder.is_junction()`, and add a containment check before any deletion (`folder.resolve(strict=True) == self.root.resolve() / document_id`, i.e. the resolved folder's parent is the resolved work root). Inside the folder, treat a junction like a link (remove the junction itself, never its target) instead of letting rmtree refuse it, which today would make every press fail with 500. Test the containment check on all systems by patching `Path.resolve` or with a symlinked work folder; a real junction test can be Windows-only (`_winapi.CreateJunction`).

## Should fix

**S1. A 200 that leaves files behind.** `folder.rmdir()` errors are suppressed, so any file written into the folder during the removal (M1, or another program) still answers 200. After the lock is released, check the folder is gone, or holds only `job.lock` on Windows; anything else → 500 `remove-failed` naming it. Keeps the API honest about what the person was told was removed.

**S2. The plan's D-360 said the start-page summary puts the file name in a span with the text's language.** Not done. Either do it or say in the reply why not (on the start page the language is unknown before an analysis, which is a fair reason).

## Checked and fine

- Id validation (`ID` regex in `get`), `..`-style and malformed ids 404; nothing outside `<work_root>/<id>/` on POSIX: links inside are unlinked, never followed; folder symlink refused.
- Order: everything, then `source/`, then the lock; a part-way failure keeps the document listed and a second press finishes (fault test).
- Busy: this server's job (script and audio) and another process's lock both 409, folder untouched; a preview or download doesn't block.
- D-194 origin checks unchanged, refusals leave the folder untouched.
- `JobBoard.forget` keeps a running job and other documents' jobs.
- Upload of the same bytes waits for the removal, then a fresh folder; other uploads don't wait.
- UI: `<details>` disclosure, one button, no `confirm()`, `aria-disabled` guard against double press, focus to message/heading, nothing in a URL or storage, German strings, privacy page lines. Browser tests cover keyboard, failure in German, axe light/dark.
