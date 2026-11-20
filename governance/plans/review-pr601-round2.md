# PR #601 review, round 2 (head 309f516)

Verdict: **approved.** Merge waits only for a merge of main (CHANGELOG conflict).

- R1-1 fixed (test only): `test_a_fresh_readalong_file_rewritten_in_place_is_read_again` now asks for the stamp before the in-place rewrite and checks the new bytes' stamp after it; the round-1 mutant fails it. No src change since 7a87a97.
- CI on 309f516: every required check and `CI passed` green. Reported-only legs: WebKit 2/2 failed once in `make_audiobook` (test_player highlight_follows, test_markers undo_ends, wait_for_url after the Make click on a settled page, which has no `data-events`, so the #299 line does not run there); WebKit 1/2 failed once in test_listen timeline-by-keyboard (seek timing). Both green on one re-run; neither test is touched by the diff and both legs were green on 7a87a97 with the same src. Read as the #437 WebKit instability; no repeat, no fix asked.
- Mergeability: GitHub reports the PR dirty. main moved to b32612d (#513, #515, #514, #600, #598, #593); merging it conflicts only in CHANGELOG.md (Unreleased Fixed lines from #593/#598). main's document.html change (#598, the picture-pages callout) does not touch `#make` or `data-events`.

## Asked of the author (MRG-03: update on conflict)
1. `git merge origin/main` (no rebase), resolve CHANGELOG.md by keeping every line from both sides, push the merge commit only.
2. Tell the reviewer the new head once Linux CI is green. The reviewer checks the PR diff against main is unchanged apart from the conflict resolution, then squash-merges pinned to that head.
