# Review PR #444, round 2 (final round, non-critical)

Head reviewed: **34fb5e7**, one fix commit on 11a628d (round 1: review-pr444-round1.md). Base main 7a3b3ec, mergeable state clean.

**Verdict: approvable.**
- Every round 1 item is answered, and each fix has a test that fails without it.
- My S1 was wrong: the author is right, and their new test covers the real path.
- The S2 fix brings one small regression: a click on text inside the open overlay closes it. Under the two-round limit it is filed as **#447** (v1.3), to go into D3, which works on the same code.
- I have not merged.

## S1, settled against the code: no guard is needed

- `document.json` in a document's work folder is written in one place only: `app/audio.py::_write_records`. It writes `document.json` beside `audio.json`, with `write_texts` and `overwrite=True`, from the `document` the audio job spoke.
- `_remove_old_records` deletes both at the start of an audio rerun.
- No analysis or script job writes it, and nothing else in `src/` names it. Searched for `DOCUMENT`, `"document.json"` and `to_data(` across `src/`.
- `player.load_document` reads only that file. So the run behind the marks always uses the document, and with it the language, the audiobook was made from.
- **What my probe did:** it called `build_view` directly with a document I built by hand, then swapped its `language` with `dataclasses.replace`. That skips `document.json` entirely, so the scenario it showed cannot happen through the app.
- **The author's test** is `test_the_marks_stay_in_the_audiobooks_language_after_a_new_analysis`, and it follows the real path:
  - a German PDF, with its audiobook made with `language="en"`;
  - a new analysis job through the API with the automatic setting, after which the report says `de`;
  - `audio.json` and `document.json` are byte for byte the same as before;
  - the Listen text, its marks and the Changes panel are unchanged, and there is no version note.

  That is the #212 path I described. **Accepted.**

## Round 1 fix list, rechecked

1. **S1:** answered with the test above.
2. **S2, done.**
   - Below 1280 px the open panel closes on `focusout` when the focus goes outside it, and the focus stays where it went.
   - `test_below_1280_px_the_focus_never_goes_under_the_panel` tabs out at 1024 px and checks with `elementFromPoint` that the focused element is not covered. J11 (the panel stays open) is killed.
   - **New leftover, #447:**
     - The handler also closes the panel when `relatedTarget` is `null`. Probe at 1024 px, Chromium: open the panel, then click the text "Not in this audiobook: References" inside it, and the panel closes.
     - On Safari, a click on a chapter button inside the open panel may close it and lose the click, because buttons don't take the focus on click on macOS. I have not checked that; it is an expectation.
     - Fix: return early when `!event.relatedTarget`. That is one line plus a test, and it fits D3, which reworks this page next.
3. **S3, done.** The `test_subtitles.py` part of 08d5965 matches it word for word: the import and the `settled(page)` line with its comment.
4. **S4, done.**
   - `test_a_jump_ahead_while_playing_leaves_no_tint` kills J9, and my R1.
   - `test_a_timeline_move_saves_the_position_and_reaches_the_end` kills J10, and my R6.
5. **N1, fixed.**
   - The timeline is `step="any"`. The arrows move 5 s, Page Up and Page Down 30 s, and Home and End go to the two ends; keys with Alt, Ctrl or Meta are left to the browser.
   - `moveTo` writes the clamped time into the slider.
   - J12 (End stops at a 5 s step) is killed.
6. **N2, fixed.** A cut carries visually hidden "(not read)" (en) and "(nicht gelesen)" (de). M14 is killed, and the existing page test now expects the hidden text.
7. **PR body:** it has the round 1 answer, and the new mutants with their commands and baselines.

## Runs, in my own clean worktree at 34fb5e7

- Fast suite: 6,335 passed, 2 skipped.
- Browser suite (Chromium): 118 passed, 1 skipped (screens without their label).
- PR checks on 34fb5e7: all green on Linux. As agreed in the workflow, non-critical PRs get no ci:full.

## Mutants (D-676), rerun

Command: `python m444.py <clean worktree at 34fb5e7> unit|js <names>`. It applies the author's list from `plans/working-reader-d1-mutants.py` plus mine, in place, with `PYTHONPATH=src`.
- Unit baseline: 89 passed, 1 deselected.
- JS baseline (Chromium, `test_listen.py`, `test_player.py`, `test_player_position.py`): 28 passed.

| Mutant | Result |
|---|---|
| M14 cut not told to screen readers | killed (`test_web_player::test_the_listen_page_after_an_audio_job`) |
| J9 tint without adjacency | killed |
| J10 timeline move not saved | killed |
| J11 panel stays open when the focus leaves | killed |
| J12 End stops at a 5 s step | killed |
| R1 (mine, round 1 survivor) | killed |
| R6 (mine, round 1 survivor) | killed |

The round 1 results for the other 20 author mutants and my other 10 still hold. The fix commit touches none of their lines.

## Leftovers

- **#447** (v1.3, lane:web): a click inside the open overlay can close it. D3 should take it.
- Round 1 notes with no change asked: the announcement uses `textContent`; R3, R9 and R10 are small gaps.

## Before the merge

- Squash-merge pinned to 34fb5e7, with the PR title, `Closes #392` and `Closes #393`. Do not close #314: the body says "Part of #314" (D-704 Q3).
- The branch commit messages contain no closing keywords (checked).
- If main has moved by then, for example after #446, update the branch with a merge, check that the PR diff is unchanged, and wait for green checks first.
