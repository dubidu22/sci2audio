# PR #489, round 1 fixes (commit b847ce8 on 39e11d3)

- **S1 fixed.** `_shown` has its own furniture rule, checked first: a REMOVE in a furniture block counts, any other edit there does not (`# never shown: the sheet is the text without it, as heard`). The rule is named in the `_changes` and `_shown` docstrings and in the PR body. Tests:
  - `test_page_furniture_is_never_shown_but_its_removal_is_counted`: your probe's document. Furniture is not among the shown blocks, and `page-furniture` counts 1.
  - `test_only_the_removal_of_page_furniture_counts`: a furniture REPLACE does not count, so the rule is not a side effect of `_whole`.
- **S2 fixed** in `contextPanel().set`, as you specified:
  - When P opens the panel and the focus is outside it, `before` is stored.
  - When P closes the panel and the focus is inside it, the focus goes back to `before` if that is connected, not the body and not inside the panel. Otherwise the focus is blurred. `before` is cleared on every close.
  - The toggle, the close button and Esc still focus the toggle. With no `before` (the wide panel open from the start), P also focuses the toggle.
  
  Tests in `test_focus.py`, both failing with 39e11d3's player.js:
  - `test_p_over_the_page_gives_the_focus_back_where_it_was`: 1024×768, nobody focused, P, P. The toggle is not focused, Space plays, the panel stays closed, and → moves one sentence.
  - `test_p_over_the_page_gives_the_focus_back_to_the_control_it_left`: `#next-sentence` gets the focus back. In the narrow window the close button and Esc still give it to the toggle. Over the page the panel covers the toggle, so the toggle press stays in the wide test `test_after_p_closes_the_panel_space_and_the_arrows_act_on_the_player`, unchanged.
- **S3 fixed.** Tests in `tests/unit/test_web_listen.py`:
  - `test_a_notice_box_counts_once_and_the_edits_inside_its_text_do_not`
  - `test_a_moved_note_counts_only_when_the_audiobook_read_it_at_its_mark`: read at the mark counts 1, read where printed counts 0.
  
  Counterexample search for the notice branch: through `run_steps`, every other edit in a placeholder's text is set aside. I searched the BLOCK, INLINE and MOVE stages; REMOVE, PAUSE and an insert; at the start, inside and at the end. None was accepted, so M1 and M2 cannot be killed through a full run. The notice test therefore checks the real run's counts (tables-and-figures 1, citations 0) and pins the guard on `_shown` itself with the inside edit.
  
  Mutants run against `test_web_listen.py`, `test_web_player.py` and `test_web_pages.py`: M1, M2, M3 and M4 are killed, and so are F1 (the furniture REMOVE returns False) and F2 (the furniture branch removed).
- **N1.** The PR body now says why the corpus check is left out: the hand-made cases cover every branch of `_shown` and kill every mutant of it, and the corpus fast fixtures add no branch.

**Checks (local):**
- ruff, format, lint-imports and deptry are clean.
- Fast suite: 6887 passed, 2 skipped.
- Browser (Chromium): 154 passed, 1 skipped.
