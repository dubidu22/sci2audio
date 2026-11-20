# Review PR #451, round 2 (final round, non-critical)

Head reviewed: **682aad8**. Round 1 was on 0af3d91 (review-pr451-round1.md). Base: main 1adf152. Mergeable state: clean.

**Verdict: approvable.** Every round 1 item is fixed, and each fix has a test that fails without it. D-709 (#452) is in with D-711's contrast, which I measured myself. Leftovers: none that need an issue, only one note. I have not merged.

## The main merge

- 659368d merges main 1adf152 (#453, CLAUDE.md only). It is a plain merge with no conflict, and there was no rebase or force-push.
- The PR's own `+`/`-` lines are identical before and after it: `git diff -U0 12fd90d 0af3d91` and `git diff -U0 1adf152 659368d` give the same lines.
- The only new code is the fix commit 682aad8 (15 files, +541 −210).

## Round 1 fix list, rechecked

1. **S1, done.**
   - Esc is checked after the open-dialog rule and before `typing()`. It leaves Focus from anywhere, the Speed list included, and also with the keys switched off.
   - `test_esc_leaves_focus_from_the_speed_list` kills B28 and B34.
2. **S2, done.**
   - `pressing` also ends on `keydown` (on the window, capture phase), on `contextmenu` and on the window's own `blur`.
   - The `blur` listener is on the window without capture, so it hears only the window losing the focus, not every element blur. That is right.
   - `test_below_1280_px_a_press_that_never_ends_does_not_hold_the_panel_open` covers all three ways of ending the press. It kills B29, B30 and B31, and my round 1 probe now closes the panel.
3. **S3, done.**
   - The setting:
     - a switch "Keyboard shortcuts" / "Tastenkürzel", on by default;
     - stored in the cookie `sci2audio-keys` through `/appearance` (`known_keys` accepts only `on` or `off`);
     - when switched off, `data-keys="off"` on `<html>`.
   - With the keys off:
     - only Esc and the rail item remain;
     - `aria-keyshortcuts` on F and P is gone, and so are the rail's `?` cap and Focus's key hints;
     - the sheet's note and the Settings hint say so in English and German;
     - the privacy text now says "five cookies".
   - Tests: unit tests for the route, the default, the switch and the attribute (U5 to U8), and browser tests in `test_focus` and `test_settings` (B32 to B37).
4. **S4, done.**
   - Tests (a) the cut on the stage, (b) the notice's words only, and (e) + at 2× pass on 0af3d91, because they pin behaviour that was already right. They kill B43, B44 and B41, which were my R1, R2 and R6.
   - Test (c) found a real bug: "Back to the reading" stayed visible in Focus. Entering Focus now also turns following back on and hides the button.
   - `test_focus_and_scrolling_by_hand` covers (c) and (d) and kills B42, B45 and B46, which were my R3, R4 and R5.
5. **N1, done.**
   - F, P and Space ignore `event.repeat`. The test holds each key for four presses, an even count, so a toggle on every repeat would end where it began and fail. It kills B38, B39 and B40.
   - `?` is unchanged, and that is right: once the sheet is open, the open-dialog rule stops the repeats.
6. **D-709 (#452), done.** See below. `Closes #452` is in the body.
7. **Mutant list, done.** B13 and B15 are dropped and their numbers left unused. U5 to U9 and B27 to B47 are new.
8. **Main:** taken in by a merge, as above.
9. **PR body:** it has a "Round 1 of the review" section answering every item.

**The new tests fail on 0af3d91.** I ran the tests of 682aad8 against `src` of 0af3d91 in Chromium. These fail:
- the held key (N1);
- the stage's plain mark;
- scrolling by hand (S4 c, d);
- the reduced-motion mark;
- the keys switched off (S3);
- Esc from the Speed list (S1);
- the plain mark with the heard tint;
- the press that never ends (S2).

The Settings test fails to import (`KEYS_COOKIE`). S4 (a), (b) and (e) pass there, as the author says.

## D-709 (#452) and D-711: the static mark

**Code.** The sweep is gone from `player.js`: `sweep`, `focusSweep`, `sweepSync`, `sweepStop`, `stretch` and their listeners.
- `.read-along .s.now` and `#focus-now` now have `background-color: var(--now)` and `color: var(--on-now)`, with no gradient and no underline.
- `aria-current` and the announcements (#388) are unchanged.
- The reading order for the stage now comes from the chunks themselves.

**Probe, Chromium, 1280 px, paused on the third sentence after reading the first two:**
- `document.getAnimations()` is empty. `text-decoration-line` is `none` on `.now` and on `#focus-now`.
- `.now` is rgb(176, 132, 0) with ink text. The heard sentences keep the 30 % tint.
- Under system dark and under the chosen dark theme (`data-theme="dark"`), `.now` is #F2DC3A with ink text, and the heard tint is 14 %.
- Under reduced motion the mark is the same (tested).

**Contrast, recomputed independently (WCAG 2), on the sheet's paper (#FFFFFF light, #1C1F25 dark):**

| Theme | Mark against the paper | Mark against the heard tint | Text on the mark |
|---|---|---|---|
| light (#B08400) | 3.42 | 3.18 | 5.20 |
| dark (#F2DC3A) | 11.85 | 8.39 | 12.75 |

All are at least 3:1 (D-711), and the text is at least 4.5:1. They match the PR body. `test_the_mark_stands_out_from_the_paper_and_from_a_heard_sentence` reads the served `app.css`. It kills U9, and a control test proves that it detects the old yellow on white (1.2:1).

**Screens.**
- I looked at Listen in light and dark, and Focus in light and dark, at 1280 px.
- The mark is a calm solid block, and the cut stays struck inside it. The tint on the heard sentences reads clearly as different from the mark.
- In light mode the mark is now a deep amber, not the Reading Yellow of DESIGN.md ("Reading Yellow: the sentence being read"). That follows from D-711, because no light yellow reaches 3:1 on white. The KB should note it with D-709 and D-711.

## Runs, in my own clean worktree at 682aad8

- Fast suite: 6,599 passed, 2 skipped.
- Browser suite (Chromium): 147 passed, 1 skipped (screens without their label).
- PR checks on 682aad8: all green on Linux, including CI passed, the browser job, ZAP and CodeQL. Non-critical, so no ci:full.

## Mutants (D-676), rerun

Command: `python m451r2.py <clean worktree at 682aad8> unit|js`. It execs the author's `plans/working-reader-d3-mutants.py` and applies each mutant in place, with `PYTHONPATH=src`.
- Unit set: `test_web_design.py`, `test_web_listen.py` and `test_web_languages.py`. Baseline: 145 passed. **U1 to U9 are all killed.**
- Browser set (Chromium): `test_focus.py`, `test_listen.py` and `test_settings.py`. Baseline: 34 passed. **44 of 45 are killed.** B22 survives; it was ruled equivalent in round 1.
- In all, 53 of 54 are killed, as the PR body claims. My round 1 survivors R1 to R6 are now the author's B43, B44, B41, B45/B46 and B42, and all of them are killed. R8 (`pad()`) is still likely equivalent.

## Leftovers

None needs an issue. One note, with no change asked:
- The contrast unit test reads the light block and the system dark block, but not the chosen dark block (`data-theme="dark"`). Today that block has the same `--now` and `--on-now`, and the probe confirms it renders the same. A future change to only that block would not be caught.

## Before the merge

- Squash-merge pinned to 682aad8, with the PR title and `Closes #394`, `Closes #447`, `Closes #452`.
- The branch's own commits (12fd90d..682aad8, without the merges) contain no closing keywords.
- Main is still 1adf152, so no update is needed.
- KB: D-709 and D-711 change DESIGN.md's "Reading sweep" and the light-mode colour of the sentence being read, and D-300's underline is replaced by D-711's contrast. This is for the KB thread's note.
