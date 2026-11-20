# Review of PR #200, round 2 (head dfe302f, main a37c18e merged in as 1a53da4)

## Round 1 findings

- **S1 fixed.** `test_layout.py::test_in_page_order_moves_a_block_back_past_every_later_page_block` tests `_in_page_order` directly (identity on blocks in page order; a block moving back past three later-page blocks; two blocks of one page keeping their order; a block without items staying where it is read). `test_layout_formulas.py::test_two_figures_waiting_for_a_cut_paragraph_follow_their_page_in_order` covers two waiting figures through `build_document`. The author reports the multi-step case is unreachable through `build_document` today (matches my own probes in round 1).
- **S2 fixed.** main a37c18e merged in (1a53da4, no conflicts); PR body updated.
- **N1** kept, now reached by the direct test.

## Re-checked on dfe302f

- Mutations of `_in_page_order`: all 7 killed (M0 to M5 by tests; M6 "stable sort" is killed too, by the partless block in the direct test). M4 (`while` to `if`) is now killed.
- Fast suite with `--snapshot-update` (`ci` profile): 3112 passed, 1 skipped; no snapshot rewritten.
- Golden diff against main: still the one nowak hunk ("65" 187 to 186).
- Nightly layout property (`tests/unit/test_layout*.py -k "not corpus"`): 256 passed, 0 failed (this run did not hit #199).
- No `src` change since round 1, so the 7 spoken scripts stay byte-identical to main (checked in round 1).
- CI on dfe302f: all checks green.

## Verdict

Approved. Squash-merge pinned to dfe302f.

## Merged

main moved to 4bc809b (#194) after approval; main merged into the branch via update-branch (head 1275f51). Spoken scripts re-checked on 1275f51 against 4bc809b: all 7 byte-identical. CI green on 1275f51. Squash-merged pinned to 1275f51 as b09f18f at 2026-11-13T21:32Z.
