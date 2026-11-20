# Review PR #446, round 2 (final round, non-critical)

Head reviewed: **c98f409**. Round 1 was on b14ed09 (review-pr446-round1.md). Base: main 6a2aeb3. Mergeable state: clean.

**Verdict: approvable.** Every round 1 item is fixed, and each fix has a test that fails without it. There are no leftovers. I have not merged.

## The two main merges

- c53f369 merged main 71ca0aa (#444), and cb39af9 merged main 6a2aeb3 (#436). Both are plain merges with no conflict, and there was no rebase or force-push.
- The PR's own added and removed lines are identical before and after them. `git diff -U0 7a3b3ec b14ed09` and `git diff -U0 6a2aeb3 cb39af9` give the same `+`/`-` lines and the same totals: 19 files, +636, −22. Only context lines and blob hashes changed.
- The only new code after the merges is the fix commit c98f409. It touches `app.js` (9 lines) and three test files.

## Round 1 fix list, rechecked

1. **S1a, done.** `test_voice_cards::test_a_sample_stopped_while_it_is_made_never_plays`:
   - holds the preview job at its first sentence (`Hold(after=0)`) and presses Stop;
   - then releases the job and waits for the page's own end handler, by wrapping `follow` and counting `window.ended`;
   - checks that the audio is paused with no `src` and that no button reads Stop.

   It kills R2 (the `mine !== asked` guard removed).
2. **S1b, done.** `test_web_outside::test_the_librarys_search_finds_a_command_line_job_by_its_name`: `?q=NOTE` and `?q=note.pdf` find the row, and a query that doesn't match hides it. It kills R4.
3. **S1c, done.** `test_voice_cards::test_a_sample_played_to_its_end_gives_the_button_back` plays the sample at 16× to its end, then checks the button reads "Play a sample" again. It kills R3.
4. **N1, fixed.**
   - `dropOnto` now cancels `dragover` and `drop` on the document when the drag carries files and lands outside the opener, with `dropEffect` "none". Drags without files keep the browser's own behaviour.
   - The listener is added only where the opener exists, which is the library page.
   - `test_library::test_a_file_dropped_beside_the_opener_stays_out_of_the_tab` drops a file on the rail. It checks that both events are cancelled, that the page stays put and nothing is stored, and that a text drag is not cancelled.
   - It kills R5 (no `preventDefault`) and R6 (every drag cancelled).
5. **Main:** taken in by merges, as above.
6. **PR body:** it has the round 1 answer, and the mutants with their command and baselines.

## Runs, in my own clean worktree at c98f409

- Fast suite: 6,586 passed, 2 skipped. The count includes #436's tests from main.
- Browser suite (Chromium): 128 passed, 1 skipped (screens without their label).
- PR checks on c98f409: all green on Linux, including CI passed, the browser job, ZAP and CodeQL.

## Mutants (D-676), rerun

Command: `python m446r2.py <clean worktree at c98f409> unit|js <names>`. It applies the author's list from `plans/working-reader-d2-mutants.py` in place, with `PYTHONPATH=src`.
- Unit set: the round 1 files plus `test_web_outside.py`. Baseline: 233 passed, 1 skipped.
- Browser set (Chromium): baseline 16 passed.

| Mutant | Killed by |
|---|---|
| R2 a stopped sample still plays (my round 1 survivor) | `test_a_sample_stopped_while_it_is_made_never_plays` |
| R3 a sample that ended keeps Stop (my round 1 survivor) | `test_a_sample_played_to_its_end_gives_the_button_back` |
| R4 command-line rows can't be found (my round 1 survivor) | `test_the_librarys_search_finds_a_command_line_job_by_its_name` |
| R5 a drop beside the opener opens the file | `test_a_file_dropped_beside_the_opener_stays_out_of_the_tab` |
| R6 every drag beside the opener cancelled | `test_a_file_dropped_beside_the_opener_stays_out_of_the_tab` |

The round 1 results for U1 to U11, B1 to B9 and my R1, R5, R7 and R8 still hold. The fix commit touches none of their lines.

## Leftovers

None. Round 1's note N2 (the drag depth count is never exercised) was optional and needs no change.

## Before the merge

- Squash-merge pinned to c98f409, with the PR title and `Closes #416 #417 #419 #435 #432`.
- The branch's own commits (6a2aeb3..c98f409) contain no closing keywords. The `Closes` lines found in 7a3b3ec..c98f409 belong to main's #436 and #444, which are already merged.
- Main is still 6a2aeb3, so no update is needed.
