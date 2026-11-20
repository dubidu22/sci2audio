# Review PR #421, round 2 (final, non-critical)

Head reviewed: **f9df0e9**. It is 52adfd9 plus the N1 test b3e3f2d, with #420's branch merged in twice, the last time at 4235d74. Round 1: review-pr421-round1.md.

**Verdict: approvable.** Nothing is left for this PR. I have not merged. #421 merges only after #420: once #420 is squash-merged, merge main into this branch (a merge, never a force-push), retarget it to main, and wait for green checks on that head before the go.

## Round 1 fix list, rechecked

1. **N1, done.** `test_the_download_button_names_what_is_still_missing` installs the English pack and leaves the German one missing. It then checks that the button names the German size and not the total. The round 1 mutant (`size=missing` → `size=total` in `voice.html`) now fails that test. Before, it passed.
2. **Merge of the fixed #420, done.** Both merges are plain merges. `privacy.work` keeps both changes in English and German:
   - from #420: the three records (opened.json, about.json, position.json);
   - from this PR: "The library and each document's page…".

   #420's privacy test point 7 passes on this head.

## Runs on f9df0e9, in a clean worktree

- Web unit tests: 275 passed, 2 skipped. The files were test_web_pages, test_web_remove, test_web_languages, test_web_design, test_web_library and test_web_outside.
- The full browser suite (Chromium): 95 passed, 2 skipped (the #365 quarantine; screens without their label).
- PR checks: all green, including CI passed.

## Merge

Squash with the PR title and `Closes #390`. The branch commit messages name no fixes/closes/resolves (checked).
