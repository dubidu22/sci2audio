# Review PR #444, round 1 (Listen page, batch D1: #392, #393, part of #314)

Head reviewed: **11a628d**, on main 7a3b3ec. Plan: working-reader-batch-d-plan.md (D-704). Not critical (D-704 Q1), reviewed at full attention.

**Verdict: changes needed.** Nothing blocks. Four should-fix items and three notes.
- The marks guard checks the version but not the language, so a plausible flow draws wrong marks.
- Below 1280 px the panel overlay lets the focus go to controls it covers.
- The `settled(page)` port is half done.
- Two behaviours have no test.

The core of the PR is right. Each piece of a sentence keeps its span, the run is rebuilt with the job's own switches, and the version guard and the announce gate both hold.

## What held

**Runs, in a clean worktree at 11a628d:**
- Fast suite: 6,334 passed, 2 skipped.
- Browser suite (Chromium): 115 passed, 1 skipped (screens without their label).
- Both match the PR body. PR checks on Linux are green.

**The marks (#392):**
- `_marks` takes the accepted REMOVE and REPLACE edits of the run that `_settled` rebuilds with `record.switched_off`. Today's switches are never read, and the M8 mutant proves it.
- Accepted edits never overlap: the run settles overlaps, and the earlier step wins. So `_parts` splits a piece cleanly, and its parts join up to the piece's text.
- An empty-span REPLACE (an insertion) is skipped, and a REPLACE always has a replacement (`core/edits.py:69`). A "said" mark can therefore never read "Read as “”".
- The element of a sentence still holds exactly its span.

**The version guard (D-704b):**
- `marked = bool(made_with) and made_with == __version__`.
- Every audio.json since 795c2d2 (14 Nov) has `"sci2audio"`.
- The note is unit-tested in English and German (M13 is killed). The counts are hidden when there are no marks (M6 is killed).

**The rest:**
- **Announcements:** the region exists only with the cookie on, and only text changes inside it while playing.
- **Hold test:**
  - every `#dock` button and input, every `#context` button and `#panel-toggle` is drawn disabled, then enabled;
  - Resume keeps its own hold test (`test_player_position.py:126`);
  - `#speed` and `#follow` are read when they are used, so an early change to them is not lost.
- **CSP:** no `style=` in markup. The sweep uses the Web Animations API, and `--fill`, `--dock-h` and scroll padding are set through the CSSOM, as before. No URL, and nothing from the internet.
- **The tint across a chapter file change (probe):** playing from the last sentence of chapter 1 into chapter 2's MP3, the left sentence keeps `done`.
- **Screens (local, Chromium):**
  - Checked: 1280 light and dark, 1024 with the overlay, and 320.
  - Compared with `listen-1280.png`: the sheet, the struck citation in pencil, the page mark, the dock with the timeline, chapter tick, round play button, clock, speed and "AI voice", and the Changes/Chapters panel with the follow switch all match.
  - Expected differences for D1: no Captures tab, no Focus button (D3), and the panel sits under the page header rather than full height.

## Mutants (D-676)

Command: `python m444.py <clean worktree at 11a628d> unit|js [names]`. It runs the author's list from `/mnt/project-files/plans/working-reader-d1-mutants.py` plus mine, in place, with `PYTHONPATH=src`.
- Unit set: `test_web_listen.py`, `test_web_player.py`, `test_web_chapter_order.py`, `test_web_pages.py`. Baseline: 88 passed, 1 deselected (the benchmark).
- JS set (Chromium): `test_listen.py`, `test_player.py`, `test_player_position.py`. Baseline: 25 passed.

**The author's 20 claims hold.** M1 to M9, M11 to M13 and J1 to J8 are all killed.

Mine:

| Mutant | Result |
|---|---|
| R4 any status counted in Changes | killed |
| R5 every tick at 0 % | killed |
| R7 dock always pinned | killed |
| R8 a block's marks dropped | killed |
| R11 the old sweep is not stopped | killed |
| **R1 tint without the adjacency check** (a far jump while playing tints the sentence left) | **survived (S4)** |
| **R6 a timeline move keeps no position** | **survived (S4)** |
| R2 tint while paused | survived: the adjacency check covers the tested paused jump |
| R3 the same-element guard off | survived: no test has a sentence element standing for several chunks (note) |
| R9 announce while paused | survived: no test moves while paused with announcing on (note) |
| R10 a resize keeps the narrow overlay open | survived (note) |
| R12 timeline seek without its own highlight | survived: equivalent, because `seek()` highlights through `update()` once the file is ready |

## Ruling: the heard-sentence tint

The author's reading is accepted. DESIGN.md says "Already-swept text stays held in a pale yellow tint". The tint is therefore for sentences the voice swept, in order, while playing.
- A sentence jumped over is not tinted, and neither is one left by a far jump.
- A sentence left by "Next sentence" while playing counts as moved past in order and keeps the tint. The adjacency check does that today, and it is fine.
- The tint is not kept across reloads. No new record is wanted for it.

## Findings

**S1. The marks follow the document's current language, not the audiobook's.**
- `_settled` runs the steps with `StepContext(document.language)` from today's `document.json`.
- The language of the text is chosen per document (#212, D-521). Changing it runs the analysis again and rewrites `document.json`, but the audiobook stays.
- `audio.json` records only the setting (`settings.language`, "" for automatic), and the guard does not compare it.
- Probe: the same record and read-along, with the document's language swapped, gives `ms` "Read as “milliseconds”" for `en` and "Read as “Millisekunden”" for `de`. In both cases the citation is struck and `marked` is True.
- Scenario: a German note is made in English (setting "en", the flow of `test_the_language_of_the_text_is_chosen_for_this_document_only`). The person then switches back to automatic and updates the analysis. Listen now draws German readings on an English audiobook. A wrong mark is worse than none (D-704b's own reason).
- `_heard_moves` already had this exposure before this PR. The marks make it visible.

**S2. Below 1280 px, the open panel lets the focus go to controls it covers (WCAG 2.4.11).**
- At 1024 × 768 with the panel open, Tab from the follow switch leaves the panel, which stays open, and goes on through the page.
- `#panel-toggle` then takes the focus under the panel: `elementFromPoint` at its centre is inside `#context`. The screenshot shows the toggle hidden.
- At 320 px the panel is 100 % wide, so every control behind it is covered.
- Esc works only while the focus is inside the panel.

**S3. The `settled(page)` port from 08d5965 is half done.**
- 08d5965 changed three browser tests:
  - the pasted-text test, already on main with its quarantine lifted;
  - the damaged-file test, now in 93bcda9;
  - **`test_subtitles.py::test_subtitles_are_chosen_on_the_page_and_chromium_reads_them`**: `settled` added to the import, and `settled(page)  # axe below must not run while the page reloads after its analysis (#365)` after `expect(page.locator("#summary")).to_be_visible()`.
- The third is still missing on main and in this PR. It is the same race: the "subtitles summary" WebKit nightly failure in run 43787351861 was in this test.

**S4. Two behaviours are untested (survivors R1 and R6).**
- (a) The PR says a jump does not tint what was skipped, but the only test jumps while paused, where `!audio.paused` already blocks the tint. With the adjacency check removed, a jump while playing tints the half-read sentence, and every test passes.
- (b) A timeline move calls `keep(c, time)` like every other move (#153), but no test checks that the position is saved after it.

**N1. The timeline can't reach the end.**
- With `step="5"` and `max` = the duration (12.3 s here), End stops at 10.
- `showTime` writes the voice's time into `value`, which the browser snaps to a step, so the thumb never reaches the end while playing either.
- Fix it, for example with `step="any"` and the arrow keys moving 5 s in a keydown handler, or by clamping `max` to a multiple of 5 and the seek to the duration. Or file an issue.

**N2. A cut tells a screen reader nothing.**
- A "said" piece carries visually hidden text "(read as …)", but a cut is only `<s>`. Screen readers do not announce `<s>` by default, so someone reading the text by screen reader can't tell what the voice left out. Sighted readers see it struck (WCAG 1.3.1).
- Add visually hidden "(not read)" text to a cut, as with "said". Or file it under #314's VoiceOver pass.

**N3, no change asked.** These are notes only.
- The announcement is the element's `textContent`, so it includes a cut citation and the hidden "(read as …)" text. That is the same text a screen reader finds on the page.
- Survivors R3, R9 and R10 are small gaps with no known bug.
- `#back-to-reading` is drawn hidden and not disabled, which is fine: it only appears after the script runs.

## Fix list (one fix commit, then round 2, the final round)

1. **S1:**
   - Draw marks and Changes counts only when the run is rebuilt in the language the audiobook was spoken in. Otherwise show no marks and a note, either the version note or a language variant of it, in English and German.
   - Suggested way: compare `audio.json`'s `settings.language` with the language setting of the analysis that made today's `document.json` (its report or record). With the same file, version and setting, the resolved language is the same.
   - A unit test where the audiobook was made with "en" and the document is now analysed as "" (German): no marks, no counts, the note. It must fail without the fix.
   - If `_heard_moves` is left out of the guard, say so in the PR body and file an issue.
2. **S2:**
   - Below 1280 px the open panel must not let the focus reach what it covers. Either close it, without moving the focus, when the focus leaves it, or make it modal (`aria-modal`, the rest `inert`, Esc anywhere).
   - A browser test at 1024 px: open the panel, Tab past its last control, and check that the focused element is not covered (`elementFromPoint`). It must fail on 11a628d.
3. **S3:** port the `test_subtitles.py` part of 08d5965 word for word (the import and the `settled(page)` line). It can go into the fix commit or a separate commit.
4. **S4:**
   - (a) A browser test: while playing, click a sentence two or more ahead. The sentence left has no `done`. It must fail without the adjacency check.
   - (b) A test that a timeline move saves the position (the `position.json` write, or the request, as in `test_player_position`). It must fail without `keep(c, time)`.
5. **N1, N2:** fix each, or file one issue each (milestone v1.3, lane:web) and name them in the PR body.
6. **PR body:** the round 1 answer, and each new mutant with its command and clean baseline.
