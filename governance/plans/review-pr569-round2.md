# Review PR #569, round 2 (removal with warning, closes #470; critical)

Reviewed head: **d2f3acd**. It is a6a75c7 (the R1 to R5 fix) plus d2f3acd (a browser test only: the box opens by the keys before tabbing, which WebKit needs. No product code changed, and it does not weaken the test).
Verdict: **one more round (round 3), test-only.** All five round-1 items are fixed and the product code is right. But one guard on the delete path has no test, and my probe shows that if this guard regresses, a person's file is deleted. The fix commit adds tests and no product code.

## Round-1 items

| Item | Result |
|---|---|
| R1 folder swapped for a link | Fixed. `_folder_moved` checks lstat, junction, not-a-folder and the real path before `_remove_if_empty`, and keeps the folder as `changed`. My round-1 probe is now `test_s10_a_folder_swapped_after_the_check_keeps_the_person_s_clutter`, which kills s1 and s4. |
| R2 real faults | Fixed. Windows: a held-open file gives 500 naming the first file; it ran on windows-latest (not in the skip list). Read-only folder: a 0o555 folder; it ran on ubuntu-latest and macos-latest (not skipped, since the runners are not root). Locally I am root, so it skips here as designed. |
| R3 message names the folder | Fixed. `Kept.folder` and `whole` are added, and whole folders are sorted first so the limit cuts files only. Whole folders get their own sentence (en and de). The box leaves out a recorded folder that is now a link. The browser test checks the exact en message, and a unit test checks the de strings. |
| R4 unreadable record | Fixed. The `remove.record_unread` line names the path, the pre-#469 line is suppressed, and nothing is deleted. Test added. |
| R5 CHANGELOG (D-768) | Two lines under Unreleased / Changed, for #552 and #470. They are accurate to the code. |

## Checks this round

- **CI on d2f3acd:** Linux run and ci:full both green on ubuntu, macOS and Windows. Browser Chromium 1/2 and 2/2, ZAP and CodeQL are green. The reported-only Firefox and WebKit legs (1/2 and 2/2) are green too. The PR is mergeable (clean), and the author removed `ci:full`.
- **Main since review:** main is at 675d1c6. The only file both main and the PR changed since the merge base 8622f85 is `CHANGELOG.md`, in a different section (main's change is in Fixed). `git merge-tree` merges cleanly, and only `release.yml` reads that file. Ruling under MRG-03: a CHANGELOG-only overlap that merges cleanly needs no branch update, since no code or test can differ.
- **Mutation, from a clean baseline:** 179 passed, 3 skipped on the 6 affected unit files. The browser `test_remove.py` passes 8 of 8 in Chromium.
  - My 30 round-1 mutants: 28 killed (r25 by line, since its pattern now occurs twice). r15 and r23 survive and are equivalent, as in round 1.
  - 16 new mutants for the round-1 fixes. 11 are killed: s1, s4, s5, s5b, s7, s10 and t1 by unit tests, and s6, j1, j2 and j3 by the browser test.
  - s3 (link or junction test dropped from `_folder_moved`) is equivalent. A link lstats as not-a-folder, and a junction resolves to another real path, which the real-path check catches.
  - Four survivors need tests: **s2**, s8, s9 and j4. See below.

## Required (exact list, tests only, one commit)

**R1: no test covers the real-path check in `_folder_moved` (mutant s2).** It guards the case where a folder *above* the project folder is swapped after the plan. For example, the output folder is renamed and replaced by a link to a folder of the person's that holds `<name>/.DS_Store`. Then `<output>/<name>` lstats as a plain folder, and only its real path shows the change.

My probe confirms this. With the check, the person's `.DS_Store` keeps its bytes. Without it, the `.DS_Store` is **deleted**, and the files are kept only by the per-file parent check.

Add that probe as a test: swap the output folder in the patched `plan`, as the S10 test swaps the book folder. Assert:
- the person's `.DS_Store` keeps its bytes;
- the moved book folder keeps every file;
- `kept` holds the folder as `changed`, and each recorded file as `changed` too (the per-file parent check).

Skip it when no links can be made, like the S10 tests.

**R2: three message details have no test.**
- (a) **s8:** a record entry that is not a bare name (`"sub/book.mp3"`) answers with `folder` equal to its project folder, not to its own path. Assert the `folder` field in the existing S5 test.
- (b) **s9:** a file that changes after the plan (the existing S10 swap test with a file-level change, or the R10 re-check test) answers with `folder` equal to the project folder. Assert the `folder` field there.
- (c) **j4:** when more files stay than the answer lists (`kept_more > 0`), the message counts them all, as in "57 files stayed in …". Either assert the text in a browser test with more than `KEPT_LIMIT` files that stay, or extend `test_files_that_stay_are_counted_after_the_removal`. The unit test `test_a_whole_folder_that_stayed_is_listed_before_the_limit_cuts_files` already checks the answer's count; this item is about the script that turns it into the message.

## Notes (no action)

- N1 to N4 of round 1 stand.
- N5: when every listed kept entry is a whole folder and files are left only in `kept_more` (more than 49 folders), the message names the last folder's path as where the files stayed. This only happens with a crafted record. Accepted.
- N6: the author's K19 and K21 equivalence claims match my r15 and s3.

## Next round

The branch stays frozen except for one test-only fix commit for R1 and R2. Then Linux CI green, and `ci:full` again, because round 3 is the final round and needs three systems. I will then re-run s2, s8, s9 and j4, plus R1's probe, and merge on the green head under MRG-03.
