# Review of PR #582, round 3 (final, critical, web batch B8)

Reviewed head: **bbbf45c** (one test-only commit on 065d22c, no `src/` change; answer `plans/answer-pr582-round2.md`).
Merge head: **ba33026**, which is bbbf45c with main ad6b94f (#585) merged in through update-branch, because main
changed CHANGELOG.md again (MRG-03). The PR's diff against main is unchanged apart from CHANGELOG.md, where only
its own #293 line is added. Reviewer: B8 review thread, 19 Nov 2026 ~02:25Z.

**Verdict: approved, no findings.** I merge pinned to ba33026 once its three-system run is green.

## R2 fixes: verified by mutation at bbbf45c

The same scripts as round 2 were run from a clean worktree (`plans/b8-review/mut582.py`, `mutjs.py`). The baseline
was 85 unit tests passed, and 6 browser tests passed in Chromium.

| fix | mutant | killed by |
|---|---|---|
| R2-1 | `clean_path(ref) != ref` dropped | `test_a_member_named_outside_the_book_is_never_read[../images/fig1.png]` (zipfile keeps both `../` and `/` names; both cases asserted) |
| R2-2 | `S_ISREG` dropped in `read_cached` | `test_a_link_is_not_read_where_the_system_has_no_o_nofollow` |
| R2-3 | `BATCH - 1` → `BATCH` | `test_one_child_renders_at_most_twelve_crops` |
| R2-4 | EPUB TABLE guard dropped | `test_an_epub_table_holding_a_picture_shows_none` (it first asserts the picture is in the table's parts) |
| R2-5 | early hide in `player.js` deleted | `test_an_image_that_failed_before_the_script_ran_is_hidden_too` |

The 21 mutants killed in round 2 are still killed. `not view.code` stays equivalent (CODE is not in `KINDS`). In all,
26 of 27 mutants are killed and 1 is equivalent.

## Final-round CI

- **bbbf45c:** Linux tests; Chromium 1/2 and 2/2; Firefox 1/2 and 2/2; WebKit 1/2 and 2/2; ZAP; CodeQL; licences;
  lint and layers: all success, with no re-runs. `ci:full` three-system run: `tests (ubuntu-latest)`,
  `tests (macos-latest)` and `tests (windows-latest)` success, and `CI passed` success.
- **Nightly seeds:** round 2, seeds 2024 and 4242. Round 3 changed only tests, so nothing needs to run again. The one
  failure is pre-existing, filed as #587.
- **ba33026 (merge head):** the three-system run is required before the merge; its result is in the ledger line.

## Merge

Squash-merge pinned to ba33026, with title
`web: the player shows figures, tables and formulas where their notice is read (#293) (#582)`. Then I poll main's CI
run (MRG-04). #293 and #534 close through the PR body. #541 was already closed as met.
