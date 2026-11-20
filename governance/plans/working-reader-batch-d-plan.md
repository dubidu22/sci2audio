# Working Reader, batch D: Listen, Focus and the library follow-ups (#392 #393 #394 #416 #417 #419 #435)

App/release lane (web), new lane thread, base main 7a3b3ec. Binding: DESIGN.md and `prototype/app/` at sci2audio-design b4a7523 (`listen-1280.png`, `listen-dark.png`, `focus.png`, `library.png`, `voices.png`), `plans/working-reader-plan.md` (D-664, D-665 conflicts 1 to 3), the batch A to C tokens, sprite, rail, records and CSP rules, and the batch C lessons (hold tests, fragments, poll bounds, tab order, stream events, WebKit failing twice is a fix).

Remaining v1.3 issues: #392 #393 #394 #416 #417 #418 #419 #435 (#385 to #388 are closed with batch A). Three PRs.

## Order

| PR | Issues | Base | Risk |
|---|---|---|---|
| D1 Listen | #392, #393 (part of #314) | main | not critical (my reading), Opus high review for size |
| D2 Library, voices and CLI | #416, #417, #419, #435, #432 | main, built while D1 is in review | not critical |
| D3 Focus and shortcuts | #394 | main after D1 merges | not critical |

D1 and D2 touch different templates; both add to `app.css`, `app.js` and the strings, so the second to merge takes main in by a merge commit (never a rebase or force-push). D3 needs D1's markup and `player.js`, so it starts after D1 merges. No stacked branches.

## D1: the Listen page (#392, #393)

### The sheet (#392)

- `listen.html` becomes: paper header (`_paper.html`, Listen tab current), the resume bar, the sheet, the context panel, the dock. The sheet is Literata, at most 66ch plus 64 px padding, the One Sheet shadow, chapter and section heads as in DESIGN.md.
- **The sweep.** The current sentence is filled left to right with Reading Yellow over its duration by the Web Animations API (`element.animate` on `background-size`), not an inline style (the CSP forbids `style=""`; WAAPI and CSSOM are not blocked by it). The animation's `currentTime` is set from the audio's time on every sentence change, seek and play; it pauses with the audio and its `playbackRate` follows the speed. Sentences already read get a class with the pale tint. Under `prefers-reduced-motion` no animation runs: the whole sentence gets the highlight class at once.
- **Strikes and "said as" (conflict 2).** Inside each sentence element, the pieces are split at the accepted edits of the settled run that the view already computes with the job's recorded `switched_off` (the same run that `_heard_moves` and `_joins` use). A REMOVE edit is `<s class="cut">` in pencil at 0.92em; a REPLACE edit is a dotted underline whose reading is a `title` tooltip plus visually hidden text "(read as …)" so a screen reader gets it too. Text between sentences that the voice skips stays as today (not an element) and is struck the same way when an edit removed it. Today's switches in `settings.json` are never read for this.
- **The check against the audiobook.** The read-along file holds spans, not spoken text, so it cannot prove an edit inside a sentence. My rule: marks are drawn only when `audio.json`'s `sci2audio` version equals the running version (the steps that made the audio are then the steps that rebuild the run), and every read-along span lies inside its block (the existing check). Otherwise the sheet shows the text without marks and one pencil line: "Made with sci2audio {version}: the changes are not marked here. Make it again to see them." (link to Prepare). A wrong mark is worse than none (`player.py` docstring). No new record and no change to `audio.json`. **Ruling asked (Q2).**
- Notes read at their mark stay where `_heard_moves` puts them (conflict 1, D-414). Tables, figures, formulas and code are dashed notice lines (restyle of today's notice boxes, the "found in the file" disclosure kept). Page marks restyled.
- **Announcements.** The `announce` cookie (D-671) is passed to the page. Off: no live region changes while playing (today's D-300). On: one polite region receives the sentence text once per sentence change, never on `timeupdate`.
- **Long documents.** Chapter sections get `content-visibility: auto` with a `contain-intrinsic-size`, and a sentence change touches only the old and new sentence (no loop over the sheet). Server side, `build_view` stays linear; the mark split is one pass over each block's sorted edits.

### Resume bar, panel, dock (#393)

- **Resume bar:** "You stopped in this chapter at 28:14." with "Continue from 28:14" (primary) and "Start of the chapter", from today's `#resume` logic (#153). Buttons drawn disabled, as now.
- **Context panel** (340 px, desk ground, hairline) with two tabs: **Changes** and **Outline**. Captures waits for the study layer.
  - Changes: one ruled row per category with its count of accepted edits in this audiobook and its state (on / off, icon and word, from the recorded settings), read-only, with the sentence "A switch takes effect after you make the audiobook again." and a link to Prepare (conflict 3).
  - Outline: the chapter list (today's chapter buttons, now with start times), the chapters left out, and the "Follow the reading" switch (today's checkbox, D-301).
  - A panel button in the sheet header (`aria-expanded`) hides and shows it. Below 1280 px it is a fixed overlay from the right with the Pop shadow: focus moves into it on open, Esc and the button close it and return focus, the reading column keeps its measure.
- **The dock** (88 px, Listen only now, Focus in D3, D-664): a 3 px timeline that is an `<input type="range">` (keyboard and screen reader operable, `aria-valuetext` "28:14 of 1:08:00"), chapter ticks drawn as a server-rendered SVG with percentage `x` attributes (no inline style), previous sentence, play/pause (round, `aria-pressed` off; label changes Play/Pause), next sentence, title with chapter and tabular time, the speed select (#152), and the AI-voice label. The native `<audio controls>` is no longer shown (the element stays, without `controls`). "Back to the reading" stays and shows in the dock when the person scrolled away (D-301). Chapter moves are in Outline and come as ⇧← ⇧→ in D3.
- **Every server-drawn button wired by `player.js` is drawn disabled** and enabled as it is wired (batch C lesson); one hold test covers all of them.
- **#314.** Landmarks (`main`, `nav` rail, `complementary` panel, `region` dock "Player"), one h1, headings in order, every control labelled. #314 is VoiceOver, which only a person on a Mac can check, so D1 says "Part of #314". I propose #314 closes after the v1.3 release's VoiceOver pass by Colin (as D-678 did for v1.1). **Ruling asked (Q3).**
- Strings en and de with the same keys, German from `prototype/app/i18n.js`.

### Tests (D1)

- **Unit** (TestClient and `build_view`):
  - a REMOVE inside a sentence gives a struck piece inside that sentence's element, the element still covering exactly its span;
  - a REPLACE gives the said-as piece with its reading in both tooltip and hidden text;
  - a category off in `audio.json` gives no marks of that category, and changing the categories in `settings.json` after the job changes nothing on the page;
  - a different `sci2audio` version in `audio.json` gives no marks and the note;
  - notes after their mark only where heard (existing tests kept), notice lines, page marks;
  - Changes counts per category and state; Outline chapters and left-out list; resume bar states;
  - the dock's ticks (percent per chapter start), time strings;
  - announce cookie on and off reaches the page;
  - strings: same keys, none unused.
- **Browser** (Chromium in CI, the three browsers nightly):
  - the sweep: an animation runs on the current sentence; pause pauses it; seek and speed change its time and rate; read sentences carry the tint;
  - reduced motion: no animation, the whole sentence highlighted;
  - announce off: the live region never changes over five sentences; on: one change per sentence;
  - keyboard: dock in tab order (play, previous, next, timeline, speed), the timeline seeks with the arrow keys, the panel tabs, the overlay below 1280 px opens with focus inside and Esc returns focus;
  - the hold test for every server-drawn button on Listen;
  - long document: a generated 1,000-page document (about 30,000 sentences, made in the test, nothing in the repo) loads, and one sentence step changes at most the two sentence elements (MutationObserver count, no timing);
  - axe in light, dark and German at 1440, 1280 and 320 px; no highlighter colour on a control (existing check); nothing scrolls sideways at 320 px;
  - existing player tests (resume, position, follow, back to reading, chapter files) updated, none weakened;
  - `listen` and `listen-dark` added to `test_screens` (`ui:screens`).
- A `benchmark` test of `build_view` plus render on the generated long document, with a row in `docs/baseline.md`.
- **Audit fix-now (coordinator, 08:41Z):** `test_a_damaged_file_shows_the_apps_message` (`tests/browser/test_flow.py:409`) gets `settled(page)  # #365` before its `check_axe`, ported word for word from release/1.1 at 08d5965 (D-701). Its own commit, first in D1.
- Before the PR: fast suite, Chromium browser suite, one-line mutants on the mark split, the version guard and the announce gate, with command and clean baseline in the PR body (D-676).

Size: about 1,800 to 2,200 lines (templates and CSS ~700, `player.py` ~150, `player.js` ~350, strings ~120, tests ~700).

## D2: library and voices follow-ups, and the CLI chapter number (#416, #417, #419, #435, #432)

- **#416 search.** A GET form `/?q=` above the table, server-filtered (D-45); `app.js` filters the rows in place as the person types. Match on title, authors (`about.json`) and file name, case and accents ignored (`casefold` after NFKD with combining marks dropped). No match: "No document matches “{q}”." The count line and the rail count stay the counts of all documents.
- **#417 drop.** The opener takes one dropped file and starts today's "Open and analyse" request (same API, errors, size limit). `.drop.over` while a file is over it; two files or an unsupported type give today's error in the status region. The server draws the hint without dropping; `app.js` swaps in the drop hint once it has wired the drop. The file input stays the keyboard way.
- **#419 voice cards.** One card per voice: name, language and accent, a Play preview button (existing `/api/v1/voices/preview`, the same sentence as the document page). A voice whose pack is missing is a disabled card with "Not installed" and the pack's download size from the existing pack data; nothing is fetched. One preview plays at a time; the audio keeps no position (D-664). Play buttons drawn disabled, hold test.
- **#435.** The `download` attribute on every `?download=true` link (Prepare's side column, the job card's files). Listen has none today. A unit test fails if any template's `?download=true` link lacks it.

- **#432.** The CLI's progress line (`cli.py:640`) numbers the chapter among the spoken chapters with `AudioProgress.chapter_number` (D-695), stepping to the next chapter when `chapter_done` is set and more is to come, the same reading as the web card; its line key follows the same number. A CLI test with a left-out chapter pins the number and fails on today's `event.chapter + 1`. Milestone set to v1.3 when the work starts.

### Tests (D2)

- Unit: the filter (case, accents, authors, file name, empty `q`, no match string), counts unchanged under a filter, voice cards installed and missing (size shown, no request), the download-attribute template test, strings.
- Browser: typing filters in place and the GET form works with the script held; the synthetic drop (one file uploads, two files and a wrong type show the error, `over` class on and off; nothing leaves the test server); voice preview plays, a second Play stops the first; hold tests for the new buttons; #435: hold `app.js`, click the report download, release it, `#update` and `#make` become enabled (must fail without the attribute); axe light, dark and German.
- Size: about 600 to 800 lines.

## D3: Focus listening and the shortcuts sheet (#394)

- **Focus** is a mode of the Listen page, toggled by F and by the Focus button in the sheet header, with no page load (the audio keeps playing; no fragment, after the D-698 WebKit lesson). The rail and the panel get `inert` and are hidden; the stage shows the previous, current (Display size, with the sweep) and next sentence from the sheet's own elements; the dock stays. Esc or Close leaves and returns focus to the Focus button. **Ruling asked (Q4)**: no address for Focus.
- **Shortcuts** on Listen and in Focus: Space play/pause, ← → sentence, ⇧← ⇧→ chapter, − + speed step, F Focus, P panel, ? the sheet, Esc leave/close. Ignored while typing (input, textarea, select, contenteditable), while ⌘, Ctrl or Alt is held, and Space or arrows on a focused control do what the control does. No plain-letter browser shortcut is taken (Ctrl/⌘ combinations are never touched).
- **The shortcuts sheet:** a `<dialog>` opened by ? on every page and by a "Keyboard shortcuts" item at the rail foot (drawn disabled until `app.js` wires it). N Q C M are not listed until #397.
- Tests: unit for the rail item and the dialog's markup and strings; browser for F and Esc with focus return, each key, every ignore rule (typing in the speed select and the library search, Ctrl+F, ⌘+…, Alt+…, nothing moves), the dialog open and close with focus return, hold test, axe light, dark and German in Focus and on the dialog, reduced motion. `focus` added to `test_screens`.
- Size: about 600 to 800 lines.

## Deferred

- **#418** (captures on the library and the shelf): its first criterion is "once the capture model (#396) exists". I propose moving it to milestone v1.5 Study layer. **Ruling asked (Q5).**
- Captures tab, capture keys N Q C M, flags on the sheet and timeline: study layer (#397), as the issues say.
- Not in batch D: #437 (stays open until five green nightlies), #411 (no milestone), #293 (v1.2, after D1 as the plan says).

## Rulings asked

1. **Q1 risk:** all three PRs non-critical. None changes a layer contract, `sci2audio.core`, a record, a golden file or a deletion path. D1 is large, so I suggest its review on Opus high.
2. **Q2 marks guard:** draw strikes and "said as" only when the audiobook's recorded `sci2audio` version is the running one; otherwise no marks and a one-line note.
3. **Q3 #314:** D1 says "Part of #314"; it closes after Colin's VoiceOver pass in the v1.3 release.
4. **Q4 Focus:** a client-side mode with no address of its own.
5. **Q5 #418:** move to v1.5.
7. **Dock buttons:** previous/next are sentences as in the prototype; chapters move through Outline and ⇧← ⇧→.

## Rulings (D-704, coordinator, 16 Nov 08:42Z)

The plan is approved as D-704:

- **Q1:** all three PRs non-critical. D1 is reviewed on Opus high in the Working Reader review thread.
- **Q2 (D-704b):** the version-equality guard. Marks are drawn only when `audio.json`'s `sci2audio` is the running version; otherwise no marks and the one-line note, which gets a unit test in both languages.
- **Q3:** D1 says "Part of #314". #314 closes after Colin's VoiceOver pass at the v1.3 release.
- **Q4:** Focus is a client-side mode with no address.
- **Q5:** moving #418 out of v1.3 is scope, so it is Colin's call; the coordinator asks him. Batch D is D1 to D3 without #418. If he keeps it in v1.3, it becomes a D4 after #396 is clarified.
- **Point 6:** dock previous/next are sentences.
- **Audit items:** the `settled(page)` port goes into D1.
- **Q6 (08:42:22Z, amends the line above it):** #432 joins D2 under milestone v1.3.
- **Order:** D1 starts now off main 7a3b3ec. D2 may be built in parallel but opens for review only after D1's round 1 is in.
