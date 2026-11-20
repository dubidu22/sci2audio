# Review PR #489, round 1 (web lane v1.3 PR A: #461, #462, #471, #472)

Head reviewed: 39e11d3, one commit on main 4bb8f81. Non-critical (Opus medium, at most two rounds). Plan: plans/web-lane-v13-pr-a-plan.md (D-723, section 3 per D-724). Linux CI is green on 39e11d3 (`CI passed`, `tests (ubuntu-latest)`, `browser (Linux, Chromium)`, lint and layers, licences, security, CodeQL, ZAP).

**Verdict: not approvable yet.** Three should-fixes, one nit. #471, #472 and the Settings and search parts of #462 are right as they stand.

## What I checked

### #471 (D-720, D-724) and D-727
- Tokens: light `--now` = reading yellow 30 % on paper, dark 18 %; `--on-now: var(--ink)`; `--now-bar` light `#9A7400` (D-727), dark `var(--hl-read)`. The two dark blocks are identical.
- My measurement with the test's own `mark_contrasts` on the served CSS:

  | | bar on paper | bar on desk | bar on fill | text on fill |
  |---|---|---|---|---|
  | light | 4.31 | 3.74 | 4.02 | 16.55 |
  | dark | 11.85 | 13.35 | 7.45 | 8.63 |

  The unit test asserts bar ≥ 3:1 against paper, desk (`--desk`, which Focus stands on: `html { background: var(--desk) }`, `.focus-view` has none of its own) and fill, and text ≥ 4.5:1, in both themes. With D-716's `#B08400` the desk check fails (2.97), so the test pins D-727. `--desk-2` is a hover colour only, so not measuring it is right.
- `test_one_mark_for_the_sheet_and_focus` pins that only `.s.now`, `#focus-now` and `.now-bar` use the three tokens, and that `.s.done` and `--held` are gone. No other reader of `done`/`--held` in `web/` (grep).
- The bar is a border (kept in forced colours, `Highlight`), no transition or animation, `aria-hidden`, hidden when nothing is marked and on the view not shown; placed from the line boxes on mark change, Focus change, ResizeObserver on `#text` and the stage, window resize and `fonts.ready`. Browser tests check it spans the lines within 1 px, follows the mark, follows a 1440 → 700 resize, survives forced colours, and that Focus fill, text and bar equal the sheet's in light and dark.
- Focus type 24/1.6, 60ch, neighbours 18 px (20/16 under 760 px); the test caps `.cur` at 1.25 × the sheet at 1440 and 700 px. Colin's long German sentence fits 1512 × 900 without scroll in light and dark (browser test). Screenshot `pr-a-shots/listen-en-light.png` shows the pale fill with the bar in the left padding.
- No hover tint and no tint on heard text: tested.

### #472
- Template line, both strings and `PlayerView.left_out` gone; no other reader. Tests updated, the page text test asserts the line is absent.

### #462 Settings and search
- `settings.keys_save` in en/de, docstring names the keys cookie.
- `app.js` folds spaces then cuts at 200, the same order as `pages.py:398`; `maxlength="200"` on the input; the browser test sets 248 characters by script and gets the server's rows.

### #461
- P calls `set(open, true)`; the toggle, the close button and Esc still focus the toggle; the wide-window test fails on main and passes here.
- Space or an arrow while the person has put the focus on the toggle itself presses the toggle: that is how every control behaves (`player.js` `CONTROLS`) and is not a finding.

### Tests run here
- Browser (`test_focus.py`, `test_listen.py`, `test_player.py`, `test_library.py`, Chromium headless shell 1243): 58 passed.
- Unit (`test_web_listen.py`, `test_web_player.py`, `test_web_pages.py`): 88 passed.

## Findings

### S1. Page furniture is counted though the sheet never shows furniture, and nothing says so (#462)
- `FurnitureStep` proposes one whole-block REMOVE per furniture block. `_shown` counts it through the "block cut whole" branch (`player.py:689`), but `build_view` never shows a furniture block at all (`player.py:596`, `continue`), so the "Not read" reason in the docstring does not apply.
- Probe: blocks heading / furniture "Journal of Things 12" / paragraph, made with this version: shown blocks `[0, 2]`, `page-furniture` count 1.
- Ruling: keep counting them. The sheet is the text without its furniture, as it is heard, and a 0 would say nothing was taken out. But it must be a stated rule, not a side effect of `_whole`.
- Exact fix:
  1. In `_shown`, before the `notices` check: `if document.blocks[block].kind is BlockKind.FURNITURE: return edit.kind is EditKind.REMOVE` with the comment `# never shown: the sheet is the text without it, as heard`.
  2. Name the rule in the `_changes` and `_shown` docstrings and in the PR body's list of what counts.
  3. A unit test in `tests/unit/test_web_listen.py` with my probe's document: the furniture block is not among the shown blocks and `page-furniture` counts 1.

### S2. In the narrow window, P then P then Space reopens the panel instead of playing (#461)
- Below 1280 px, P opens the overlay and focuses the selected tab; P again closes it and, since the focus was inside, `set` focuses the toggle (`player.js` `if (!open && (!keep || inside)) toggle.focus()`). Space on the toggle then opens the overlay again and the voice does not play.
- Probe (Chromium, 1024 × 768, nobody focused, P, P, Space): `aria-expanded` is `true` and the audio is paused. This is the exact repro of #461, moved to the narrow window, and the review lesson "a shortcut closing a panel must not let Space reopen it".
- Exact fix in `contextPanel()`:
  1. Keep `let before = null;`. When `set(true, true)` opens the panel and the focus is not inside the panel, store `before = document.activeElement`.
  2. When `set(false, true)` closes it and the focus is inside the panel: if `before` is connected, not `document.body` and not inside the panel, `before.focus()`; otherwise `document.activeElement.blur()` (the focus goes back to the page, where it was). Then `before = null`.
  3. Every close by the toggle, the close button or Esc keeps today's `toggle.focus()` and sets `before = null`.
  4. In the wide window, focus inside the panel with no `before` (the panel was open from the start) still goes to the toggle, as today.
- Tests (`tests/browser/test_focus.py`), each failing on 39e11d3:
  1. Rewrite `test_p_over_the_page_gives_the_focus_back_to_the_toggle` as `test_p_over_the_page_gives_the_focus_back_where_it_was`: 1024 × 768, nobody focused, P (the Chapters tab is focused), P: the panel is closed and the toggle is not focused; Space plays and the panel stays closed; → moves to the next sentence.
  2. Same width: focus `#next-sentence`, P, P: `#next-sentence` is focused again.
  3. The button and Esc paths still focus the toggle (keep the existing checks).

### S3. The notice and move branches of the new count rule are untested (#462)
- Mutants of `_shown`, run against `test_web_listen.py`, `test_web_player.py` and `test_web_pages.py`:

  | mutant | result |
  |---|---|
  | M1 notice branch returns True (edits inside the notice text count) | survives |
  | M2 notice branch removed | survives |
  | M3 MOVE returns True (a move the audio did not make counts) | survives |
  | M4 MOVE returns False (a heard note read at its mark does not count) | survives |
  | M5 whole-block branch removed | killed |
  | M6 every edit counts as drawn | killed |
  | M7 `_shown` not called | killed |

- Exact fix: two unit tests in `tests/unit/test_web_listen.py`:
  1. A placeholder (table) read as its notice whose printed text also gets an accepted edit from a test step (an `_Edits`-style step matching the placeholder's text): `tables-and-figures` counts 1 and the test step's category counts 0. Must fail under M1 and M2.
  2. A footnote moved to its mark: with a read-along that reads it at the mark (`_heard_moves` finds it), `footnotes` counts 1; with a read-along that reads it where printed (an audiobook made before #213), it counts 0. Must fail under M3 and M4.
- I will re-run M1 to M4 on the fix commit.

### N1. The plan's corpus check was dropped without a word
- Plan 2.1 promised a check that the counts match what the page draws on the fast-fixture corpus papers; the PR has none and the body does not say why. Either add it or say in the PR body why it was left out (for example: the hand-made cases now cover every branch). No code needed for the nit itself.

## Not findings
- The knowledge base's design notes on the mark (D-706, D-711, D-716) are now amended by D-724 and D-727; that is a decision-log row for the KB thread, not this PR.

## Process
- One fix commit for S1, S2, S3 and N1 (N1 may be a PR body edit only). Branch frozen otherwise.
- Linux CI green on the fix commit, then round 2.
