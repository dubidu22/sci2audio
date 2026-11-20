# Review PR #583, round 1 (retried names #493, CRIT-02; linked earlier folder test #544)

Reviewer: app-lane review thread (B7). Head reviewed: **83e6c5f** (base main 5a605e5). Critical (risk:high, CRIT-02: names of files written into the person's folders).
Verdict: **changes required**: 3 small items (R1 to R3). The CRIT-02 guarantee holds, and I checked it by mutants and probes. One fix commit plus a merge of main.

## What I checked

- The whole diff (13 files), against plan B7 PR 2, the CRIT-02 guarantee as the plan states it, #493's criteria and #544's criterion.
- CI on 83e6c5f:
  - The Linux run is green, and ci:full is green on ubuntu, macOS and Windows.
  - Chromium shards, ZAP and CodeQL are green, and every reported-only Firefox and WebKit leg is green.
  - **Mergeable: dirty.** Main moved (0a72357, #572) and `CHANGELOG.md` conflicts. See R1.
- Local baseline on the 8 affected test files: 228 passed, 2 skipped.
- **CRIT-02, step by step:**
  - (a) Without `overwrite`, the check before speech (`audio.py` `_check_targets` → `audiobook_files` → `audiobook_targets`) and `write_audiobook`'s own check both see the retried names. A person's file under a retried name is refused before speech, and again at the write.
  - (b) The refusal lists the same names the writer uses, because both call `audiobook_targets` on the same folder. In the web, the folder already exists before the job (`audiobook_folder`), so the check before speech probes there. Into a folder that doesn't exist yet, nothing can be there, so no name is needed.
  - (c) The probe uses `O_CREAT | O_EXCL` and unlinks only what it made. A probe file that is already there counts as accepted. On a refusing volume, the real write of that name then fails, so nothing is replaced.
  - Script files: I probed a person's `notes.script.txt` under a retried stem without `overwrite`. The result is `OutputExistsError` naming it, the file is kept byte for byte, and nothing is beside it.
- **D-768:** the CHANGELOG Unreleased / Fixed line is there. It is accurate, including "never replaced without your choice to replace the audiobook".
- **Mutants:** 18 hand mutants (17 in the script plus a valid redo of q10). 15 are killed, each by the test aimed at it:
  - never refused; any error counts as a refusal; every name probed; probe not removed; no `O_EXCL`; `older` keeps everything; book not retried; chapter not retried;
  - the check before speech uses unretried names (killed by `test_the_check_before_speech_names_the_retried_file`);
  - `_encode` without its `mkdir`; script stem not retried; `_write` not renaming in a new folder; `_placed` not retried; `_placed` without its fallback;
  - #544 `_through_folders` check of the earlier place removed. This is my #532 n12, now killed.
- The survivors:
  - q9: the base probed on the M4B and only when `m4b` is on. It is near-equivalent (same characters, different suffix), so no action.
  - **q17**: `_placed` retries on *any* `OSError`. See R2.
- **Hypothesis, nightly profile:** `test_a_retried_name_holds_only_old_characters_and_is_clean` passes with seeds 1, 2 and 3.

## Required (exact list)

**R1: merge main.** `CHANGELOG.md` conflicts with main 0a72357 (both added lines). Under MRG-03 a conflict means a branch update. Merge main (never rebase) and keep every line of both sides. #577 also adds a CHANGELOG line, so whichever of the two lands second merges main again.

**R2: a refusal that is not EILSEQ is not retried (mutant q17 survives).** `_placed` is meant to retry only on EILSEQ (plan, and its docstring). Add a test: `os.replace` raising `ENOSPC` on the first try makes exactly one attempt and answers the disk-full store error as before, and nothing is left in `source/` or the work root.

**R3: name the follow-up issue.** The PR body's "Out of scope" says "follow-up issue to file". The issue exists as #584, so link #584 there.

## Notes (no action)

- N1: a name with characters from Unicode 4.0 to 9.0 is probed even though every APFS knows them. That costs one hidden create and unlink per name, and only for such names. Accepted.
- N2: the probe file `.<name>.partial` has the same name output writes under. A concurrent writer of the very same file would be refused by the work-folder lock first. Accepted.
- N3: if a volume's verdict changed between a refusal and the "Replace" run (the folder moved to another disk), the names would be computed afresh, and the check before speech names them again only without `overwrite`. This is contrived; the refusal-then-replace flow is unchanged from D-163.

## Next round

The merge of main plus one fix commit for R2 and R3. Then Linux CI green and `ci:full` again (final round: three systems). I will then re-run q17, the 15 killed mutants and the nightly seeds, then merge pinned. #577 is reviewed separately, and whichever lands second merges main.
