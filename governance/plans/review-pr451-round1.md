# Review PR #451, round 1 (D3: Focus listening, the keys and the shortcuts sheet; #394, #447)

Head reviewed: **0af3d91**, on main 12fd90d. Mergeable state: clean. Non-critical (D-704 Q1), the last batch D PR, max two rounds.

**Verdict: changes needed, all small.** Nothing blocks. The #447 deviation is accepted, and so is the B22 equivalence. There are three behaviour fixes (Esc on the Speed select, a press that never ends, and a way to switch the single keys off) and five missing tests. Colin's static highlight (D-709, #452) joins the same fix commit, and round 2 checks it.

## What held

**Runs, in a clean worktree at 0af3d91:**
- Fast suite: 6,592 passed, 2 skipped.
- Browser suite (Chromium): 139 passed, 1 skipped (screens without their label).
- Both match the PR body. PR checks on Linux are all green, including CI passed, the browser job, ZAP and CodeQL.

**(1) #447, the deviation: accepted.** My one-line suggestion (return when `relatedTarget` is null) was wrong. The probes are at 1024 px in Chromium.
- When you Tab past `#follow`, the panel's `focusout` has `relatedTarget` **null**, and the focus goes to `BODY`, which is the browser's own bar. After `#context`, the only focusable element in the document is `#keys-close`, and it sits inside the closed dialog. So an early return on null would leave the panel open and break S2.
- A click on text inside the panel moves the focus to `main#main` (tabindex −1), not to null. So the null rule would not even have fixed #447.
- The author's rule holds. A press inside the panel is not leaving it, and a `focusin` outside closes it. Tab past the last control closes it. `test_below_1280_px_a_click_on_text_inside_the_panel_leaves_it_open` kills B1, B2 and my R7. There is one hole, S2 below.

**(2) B22 (the sheet's explicit focus return): equivalent, accepted.**
- Counterexample search: I ran 9 open and close paths with and without the line and compared where the focus ended:
  - the rail item clicked and Close clicked;
  - `?` in the Focus view, then Esc;
  - `?` on Focus's Close, then Enter;
  - `?` on `main`, then Esc;
  - `?` on the body, then Esc;
  - the opener hidden while the sheet is open;
  - the opener disabled while the sheet is open;
  - the opener removed and put back while the sheet is open;
  - `close()` called from a script.
- All 9 end in the same place. The one difference straight after the key is the opener disabled while the sheet is open: the focus is left on `#keys-close` with the line and on `BODY` without it, and focus fixup takes both to the body a frame later.
- This is the HTML standard's dialog close steps: the "previously focused element" is focused again after a modal dialog closes. The line is a fallback for an engine that does not do this. The Firefox and WebKit nightly runs the same sheet test.

**(3) The keys.**
- **No key acts while you type.** Typing means the Speed select, the library's search and the pasted-text field (B3, B19 and B20 are killed).
- **No key acts with a modifier held.** Ctrl, ⌘ and Alt, also with Shift, leave the page unchanged. I tried Ctrl+Shift+F, Alt+Shift+→, ⌘+Shift+P, Ctrl+=, Ctrl+− and Ctrl+Space (B4 is killed).
  - AltGr: on Windows it is sent as Ctrl+Alt, so it is excluded. On Linux and macOS it changes the character, so the key is no longer f or p. Playwright's synthetic `AltGraph+f`, which keeps the character f, is not a real layout.
- **No key acts under the open sheet.** Esc closes the sheet only and stays in Focus, and the focus goes back to `#focus-view` (B5 is killed).
- **Esc leaves Focus and gives the focus to the Focus button.** That is what the plan asks (batch D plan, D3: "Esc or Close leaves and returns focus to the Focus button"). It works from the timeline, Play and Next. The Speed select is the exception, see S1.
- **No address.** F and Esc leave `location`, the hash and `history.length` unchanged.
- **Reload.** A reload in Focus brings back the normal page with Focus off, and F works again. Back from the library also shows the normal page.
- **Tab order in Focus.** It goes Focus's Close, then the browser bar, then the dock. Nothing hidden takes the focus, and there is no trap.

**(4) D-706 and D-704b in Focus.**
- **The tint (D-706).** Playing from the first sentence into the third while in Focus, sentences 1 and 2 get `done` on the sheet and keep it after Esc. A far jump (⇧→) while playing in Focus leaves no tint on the sentence it left.
- **The marks (D-704b).** The stage clones the sheet's own child nodes.
  - The cut citation in "Things happen (Smith, 2020) (not read) and more." keeps `<s class="cut">`, its line-through and its hidden "(not read)".
  - There are no duplicate ids after staging.
  - An unmarked sheet (a version mismatch) gives an unmarked stage, because the stage only copies the sheet.
  - No test covers this yet, see S4 (R1).

**The rest.**
- The hold test covers `#focus-on`, `#focus-off`, `#keys-open` and `#keys-close`.
- The status line `#message` stays visible in Focus, so `say()` is still heard.
- axe runs in light and dark (`check_axe` runs both), in German, at 1024 px, and on the sheet.
- There are no `style=` attributes. The stage's sweep uses the Web Animations API.
- `focus` and `shortcuts` are added to `test_screens`.

## Mutants (D-676)

Command: `python m451.py <clean worktree at 0af3d91> unit|js`. It execs the author's list `plans/working-reader-d3-mutants.py`, adds mine, and applies each mutant in place with `PYTHONPATH=src`.
- Unit set: `test_web_design.py` and `test_web_listen.py`. Baseline: 77 passed. U1 to U4 are killed.
- Browser set (Chromium): `test_focus.py` and `test_listen.py`. Baseline: 21 passed. B1 to B21, B23 and B24 are killed. B22 survives and is equivalent (above).
- **B13 is the same mutant as B2**, with the same pattern and the same replacement. So the list has 28 distinct mutants, 27 of them killed. Please correct the count in the PR body.

Mine:

| Mutant | Result |
|---|---|
| R7 a press never ends (the pointerup and pointercancel listeners gone) | killed |
| R9 Esc leaves Focus only when the focus is off a control | killed |
| **R1 the stage loses the marks** (it copies `textContent`) | **survived (S4)** |
| **R2 a spoken notice is copied whole** (icon and file text) | **survived (S4)** |
| **R3 leaving Focus keeps following off** | **survived (S4)** |
| **R4 leaving Focus keeps "Back to the reading"** | **survived (S4)** |
| **R5 a wheel scroll in Focus counts as scrolling away** | **survived (S4)** |
| **R6 + past the fastest speed** (the upper bound gone) | **survived (S4)** |
| R8 `setFocus` without `pad()` | survived, likely equivalent: `ResizeObserver(pad)` on the dock runs it when the dock's size changes (note) |

## Findings

**S1. Esc does nothing in Focus while the focus is on the Speed select.**
- `typing()` counts a select as typing, which is right for its letters. But the key handler returns before it reaches Escape.
- Probe: F, then focus `#speed`, then Esc, and Focus stays. The dock is visible in Focus, so this is a normal path: Tab to Speed, then Esc.
- A closed select does nothing with Esc, so nothing is taken from it.

**S2. A press that never ends keeps the panel open while the focus walks under it (#447 hole).**
- `pressing` is cleared only by `pointerup` or `pointercancel` on the window. If the release never reaches the page, `left()` returns early on every focus move until the next pointer release anywhere.
- Probe at 1024 px: a `pointerdown` on `#panel-changes` with no release, then Tab from `#follow`. The focus goes to `BODY`, then to the rail links, then to `nav-library`, and the panel stays open each time. Further Tabs reach the controls it covers.
- **Expectation, not verified:** the real trigger is a right click inside the panel, because the context menu opens on the press and takes the release (Linux, macOS). Headless Chromium shows no menu, so I could not reproduce this end to end.

**S3. The single-character shortcuts cannot be switched off (WCAG 2.1.4, level A).**
- F, P, ?, −, + and = act on the whole page, not only while one control has the focus, and there is no way to switch them off or change them.
- 2.1.4 asks for one of three things: a way to switch them off, a way to remap them, or that they act only while a control has the focus.
- The people this affects are speech-input users: dictated words reach the page as letters. Accessibility users are a named core group (PRODUCT.md).
- The plan did not cover this. This PR adds the keys, so this is where the switch belongs. The Settings page already has the pattern: the announcements switch, a cookie, D-671.

**S4. Five behaviours have no test (survivors R1 to R6).**
- **(a) R1:** the stage keeps the sheet's marks.
- **(b) R2:** a spoken notice shows only its words on the stage.
- **(c) R3 and R4:** leaving Focus after a scroll by hand turns following back on and hides "Back to the reading". `test_leaving_focus_brings_the_sentence_into_view` scrolls with `scrollTo`, which never turns following off.
- **(d) R5:** a wheel scroll while in Focus does not count as scrolling away.
- **(e) R6:** + at the fastest speed keeps it. The test checks only − at the slowest.

**N1. A held F, P or ? repeats.**
- Holding F toggles Focus on every key repeat. Probe: one press and two repeats gave 3 class changes.
- This matters for the motor-impaired users PRODUCT.md names. Ignore `event.repeat` for the toggles (F, P, ?).

**N2, no change asked.** R8 is likely equivalent (above).

## D-709 (#452): the static highlight, in the same fix commit

Colin decided that the sentence being read gets a plain static highlight on Listen and in Focus, with no sweep and no underline. The author folds it into the fix commit. Round 2 checks:
- While playing, there is no running animation on Listen or in Focus (`document.getAnimations()` is empty), and no underline on `.now` or on `#focus-now`.
- The highlight stays the same under reduced motion.
- `aria-current` and the announcements (#388) are unchanged.
- The tint (`.done`, D-706) stays and stays distinct from the highlight.
- The sweep tests and B15 go. The screens (`listen`, `focus`) are updated.
- **Colour alone (D-300, WCAG 1.4.1):** D-300 put the underline there so that the reading was never shown by colour alone. Without it:
  - the highlight must differ from the paper and from the tint by more than its hue. I will check a luminance contrast of at least 3:1 between the highlight and both, in light and dark;
  - screen readers keep `aria-current`.
  - The coordinator may rule this differently (D-709 supersedes D-300's underline). In that case the PR body says so.

## Fix list (one fix commit, then round 2, the final round)

1. **S1:** in the keys handler, check Esc for Focus before the `typing()` return and after the open-dialog return, and keep the modifier rule. Add a browser test: F, focus `#speed`, Esc. Focus is left and `#focus-on` has the focus. It must fail on 0af3d91.
2. **S2:** a key press ends `pressing`, for example with `keydown` on the window in the capture phase. `contextmenu` and window `blur` end it too. Add a browser test at 1024 px:
   - open the panel;
   - dispatch a `pointerdown` inside it with no release;
   - focus `#follow` and Tab out;
   - the panel closes and the focused element is `uncovered`.

   It must fail on 0af3d91.
3. **S3:** a Settings switch "Keyboard shortcuts" ("Tastenkürzel" in German), **on by default**.
   - Store it as a cookie through `/appearance`, as with the announcements (D-671).
   - Render it as a `data-` attribute on `<html>` in `base.html`.
   - When it is off, `app.js` and `player.js` ignore every page-wide key except Esc. The rail item still opens the sheet. Write the strings in English and German, and mention the switch in the sheet's note.
   - Unit tests: the switch, the cookie and the attribute.
   - A browser test with the switch off: F, P, ?, −, +, Space and → do nothing, Esc still leaves Focus (entered by the button), and the rail item opens the sheet.
   - If the coordinator rules that this waits, file it instead as a v1.3 issue (lane:web) and name it in the PR body.
4. **S4:** add these tests, each failing under its mutant:
   - (a) with the cut sentence current, `#focus-now` holds `s.cut` with "(not read)";
   - (b) with the skipped figure's notice current, the stage reads only "Spoken notice: Figure 1 is skipped.";
   - (c) wheel-scroll until "Back to the reading" shows, then F and Esc: the sentence is in view, the button is hidden, and following is on;
   - (d) a wheel scroll in Focus shows no "Back to the reading";
   - (e) + at 2× stays at 2×.
5. **N1:** ignore `event.repeat` for F, P and ?, with a test where `keyboard.down("f")` is pressed three times and Focus toggles once. Or file an issue (v1.3, lane:web).
6. **D-709 (#452):** as above, with `Closes #452` in the PR body if it is fully done here.
7. **Mutant list:** remove B13 or give it its own pattern, and drop B15 with the sweep. Add each new mutant with its command and clean baseline.
8. **Main:** if main has moved by then, take it in by a merge commit. Never rebase or force-push.
9. **PR body:** the round 1 answer to each item above.

## Coordinator's rulings (13:18Z)

- S3, the "Keyboard shortcuts" switch, is in scope for this PR.
- The 3:1 contrast requirement for the static highlight, against the paper and against the tint in light and dark, is ruled as **D-711**. Round 2 checks it.
