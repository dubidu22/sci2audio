# Review of PR #200, round 1 (head 599297f, base 14513b2)

PR: layout: blocks stay in page order after a paragraph is cut (#196). Critical (corpus golden). Plan: plans/issue196-page-order-plan.md (D-434, D-435).

## What I checked myself

- **CI** on 599297f: all checks green (tests on Linux, macOS, Windows; lint and layers; licences; browser; security; CodeQL).
- **Goldens regenerated** on the PR head (`pytest <every snapshot test file> -m "not browser" --snapshot-update`): nothing rewritten, 60 snapshots pass. The committed golden diff against main is exactly one hunk in `test_layout_corpus.ambr` (nowak): "65" (p9-l62, furniture/page-number) moves from 187 to 186, after formula (24) and before p10's "Definition 14" paragraph. `test_layout_tagged_corpus.ambr` and every other snapshot unchanged.
- **Spoken scripts**: `sci2audio script FILE --chapters all --ignore-settings` on all 7 corpus papers, main (worktree via PYTHONPATH) against the PR: all 7 `.script.txt` byte-identical. Of the `.report.json` files 6 are identical; nowak's differs only in three `"block"` indices (186 and 187 swapped), as expected from the move.
- **Fast suite** (`HYPOTHESIS_PROFILE=ci`, `-m "not slow and not benchmark and not browser"`): 3110 passed, 1 skipped.
- **Nightly layout property** (`HYPOTHESIS_PROFILE=nightly pytest tests/unit/test_layout*.py -k "not corpus"`): 253 passed, 1 failed: `test_sections_start_at_headings_and_carry_their_text`, which is #195 (fixed by PR #198, merged to main 21:08Z as a37c18e, not yet on this branch). `test_layout_never_fails_and_keeps_every_line` also passed under nightly with seeds 1 to 4.
- **Mutations of `_in_page_order`** (layout unit, formulas, corpus and tagged corpus tests, `ci` profile):

| Mutation | Result |
|---|---|
| M0 pass removed | killed (`test_layout_never_fails_and_keeps_every_line` @example) |
| M1 `>` to `>=` (a block goes before same-page blocks, so in-order blocks move) | killed (3 layout tests, goldens) |
| M2 page taken from the block's last part | killed (`test_a_sidebar_in_small_letters_beside_the_text_is_furniture`) |
| M3 a moved block goes to the start of its page instead of after the nearest earlier block | killed (new formulas test) |
| **M4 `while` to `if`: a block moves back at most one place** | **survived**, also under the nightly profile with seeds 1 to 6 |
| M5 a block without parts takes page 1 instead of the page before it | survived (branch unreachable: no layout step makes a block without parts) |
| M6 replace with a stable sort by first page | survived (equivalent) |

So "blocks already in page order don't move" is held by M1 and the unchanged goldens. The gap is M4.

I also built made-up pages trying to make a waiting figure step back past two later-page blocks (p2 piece holding a mid-page formula, two formulas, a list, a formula at each page foot over three pages). In each, `paragraphs` already ends the paragraph at the p2 formula on main, so the figure only ever has to move one place. Every nowak-like case so far needs one step; the multi-step part of the rule is untested.

## Findings

### Must-fix

None.

### Should-fix

- **S1. The multi-step move is untested (M4 survives).** Add a test where a block has to move back past two or more blocks from a later page, and one where two waiting blocks from the same page keep their order when they move. If you can reach such a case through `build_document` on made-up pages, use that; if you find it unreachable through the pipeline today, say so in the PR and test `_in_page_order` directly with hand-made blocks (that is also where the plan's "already in page order stays as it is" identity case fits cheaply). Either way M4 must be killed.
- **S2. Merge main into the branch.** PR #198 (#195) merged at 21:08Z (a37c18e). The branch is behind and main's ruleset needs it up to date; after the merge, rerun the nightly layout property and update the PR body's nightly line (the #195 failure should be gone).

### Nits (no action needed)

- N1. The `if block.parts else last` branch is unreachable from today's steps (M5 survives). Keeping it as a guard is fine; dropping it is fine too.

## Verdict

Request changes for S1 and S2. Code and golden change are otherwise right: the move is the one D-435 accepts, nothing else moves, and the scripts are unchanged.
