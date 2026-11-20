# Web lane v1.3, PR A: Listen and Focus follow-ups (#461, #462, #471, #472)

Status: change list prepared under D-723 (coordinator, 16 Nov 2026 19:36Z); section 3 rewritten for D-724 (Colin, 20:35Z). Non-critical (no core, no contract, no golden file, no file writing, no delete path). Start signal given 17 Nov 2026 03:28Z; branch `web-v13-pr-a` from main 4bb8f81 (no file under src/sci2audio/web, tests/browser or the web unit tests changed between 7cd84bd and 4bb8f81, so the line numbers below still hold). PR B after it: the marker (#474, plans/general-marker-plan.md).
Base read: main 7cd84bd. Line numbers below are main 7cd84bd; the author re-reads them on the branch's base.
Lane: web (lane:web). PR title: `web: Focus and Listen follow-ups: pale reading mark with margin bar, panel key, housekeeping (#461, #462, #471, #472)`.

Earlier PRs in this batch that built on a model this PR changes: none (first PR of the batch). Earlier merged PRs whose work this changes: #451 (D3, the P key and Focus), #444 (D1, the panel's focus return), #452/D-711 (the mark contrast test, now on the bar, D-724), D-716 (the mark colour, now the bar's colour in light mode); each is listed at its item.

## 1. #461: after P closes the panel, Space and the arrows act on the player again

- `static/player.js` panel code (`set(open)`, about line 620): give `set` a second argument `keep` (default false). `if (!open) toggle.focus()` becomes: when closing, move the focus to the toggle only if `!keep`, or if the focus is inside the panel (it is about to be hidden). Expose a `panelKey()` function (inside the panel setup, wired to the keys code) that calls `set(!isOpen(), true)`.
- `static/player.js` keys handler (about line 458): P calls `panelKey()` instead of `document.getElementById("panel-toggle").click()`.
- Kept as is: the toggle button and the close button return the focus to the toggle (D1); Esc in the narrow overlay returns it to the toggle; P opening the narrow overlay focuses the selected tab.
- Tests (`tests/browser/test_focus.py`), each failing on main:
  - wide window, nothing focused: P, then Space plays (audio not paused), Space pauses; P again, then → moves the highlight to the next sentence.
  - narrow (1024 px), overlay opened by P, focus inside the panel on a tab: P closes it and the focus is on the toggle (not lost to the body).
  - unchanged checks: clicking the toggle still focuses it; `test_every_key_on_the_listen_page` passes as it is.

## 2. #462: housekeeping

2.1 Changes counts match what the sheet marks (F3). Choice: count only the edits that are drawn (not a hint), so the panel and the sheet never disagree.
- `web/player.py`: split the loop of `_marks` (line 669) into `_drawn(document, run)`, which yields `(edit, start, end, kind, said)` for every accepted edit that is drawn, with today's exact rules (empty span, `_UNMARKED_STEPS`, block cut whole, look-alike replacement). `_marks` builds its dict from `_drawn`.
- `_changes` (line 650) counts per category over `_drawn` (not `run.outcomes`), and also skips edits in blocks shown as a notice box (`notices`, from `_notices`), which `build_view` passes in. The `marked` / None rule (D-704b) and the "block is read" rule (#213) stay.
- Tests (`tests/unit/test_web_listen.py`): one document holding, in read blocks, a line-end hyphen join, a whole-block cut, a look-alike replacement (NFKC only), an edit inside a placeholder read as its notice, and one drawn REMOVE and one drawn REPLACE: the counts are 1 and 1 in their categories and 0 for the others' categories. `test_an_edit_in_a_chapter_left_out_is_not_counted` keeps its count check. A corpus check: for every corpus paper with a made audiobook in the fast fixtures, the sum of the counts equals the number of drawn `cut`/`said` parts on the page.

2.2 Settings leftovers (F4).
- `web/pages.py` `settings_page` docstring (line 1273): "Appearance, language, announcements and the keyboard shortcuts switch (cookies, D-671) ...".
- `templates/settings.html:71`: the keys form's button uses a new key `settings.keys_save`; `en.toml` "Save", `de.toml` "Speichern", beside `announce_save`. The strings parity test covers it.

2.3 Search cap in the script too (F5).
- `templates/index.html:54`: the search input gets `maxlength="200"`.
- `static/app.js` `librarySearch()` (line 247): `const query = input.value.split(/\s+/).filter(Boolean).join(" ").slice(0, 200);` (the same order as the server: spaces folded, then cut at 200).
- Test (browser, `tests/browser/test_library.py` or where #416's tests live): a 250-character query set through the page script (`input.value = ...; dispatchEvent(new Event("input"))`) shows the same rows and the same `?q=` as the page loaded with that query from the server.

## 3. #471 (D-720, D-724): Focus only slightly larger, one pale reading mark with a margin bar, no tint on heard text

D-724 (Colin, 16 Nov 2026 20:35Z, option b): the fill gets much paler and may sit below 3:1; a thin bar in the left margin beside the sentence is the second, non-colour cue and itself passes 3:1 against the page. Not an underline (D-709). Focus and normal Listen identical (D-720). D-711's 3:1 rule now applies to the bar, not to the fill, for the reading mark only.

3.1 Tokens (`static/app.css` lines 53, 75, 89; the two dark blocks stay identical, as their test requires). Three tokens, used by both views and nowhere else:
- `--now` (the fill), `--on-now` (the text on it), `--now-bar` (the bar).
- Light: `--now: color-mix(in srgb, var(--hl-read) 30%, var(--paper))` (≈ #FFF8C9; 1.07:1 against the paper), `--on-now: var(--ink)` (16.6:1 on the fill), `--now-bar: #B08400` (D-716's deep amber, 3.42:1 against the paper, 3.18:1 against the fill).
- Dark (both blocks): `--now: color-mix(in srgb, var(--hl-read) 18%, var(--paper))` (1.59:1 against the paper), `--on-now: var(--ink)` (8.6:1 on the fill), `--now-bar: var(--hl-read)` (#F2DC3A, 11.8:1 against the paper).
- The comment above `.read-along .s` (app.css:289-292) is rewritten: pale fill plus margin bar, the bar carries the 3:1 (D-724), the fill keeps the text at AA.

3.2 The bar.
- One element per view, drawn by the template and placed by the script, `aria-hidden="true"`: `<span class="now-bar" id="now-bar" aria-hidden="true" hidden></span>` as the first child of `.sheet` (already `position: relative`, app.css:269), and `<span class="now-bar" id="focus-bar" aria-hidden="true" hidden></span>` in `.focus-stage`'s `.cur` paragraph (made `position: relative`).
- CSS, shared by both: `.now-bar { position: absolute; width: 0; border-left: 3px solid var(--now-bar); border-radius: 0; pointer-events: none; }`. A border, not a background, so Windows High Contrast (forced colours) keeps it (it maps to CanvasText) while the fill disappears there; add `@media (forced-colors: active) { .now-bar { border-left-color: Highlight; } }`. No transition or animation on it in any mode (D-709 static; the reduced-motion block covers it anyway).
- Sheet: left edge at `left: calc(var(--sheet-pad-left) - 12px)` where `.sheet` gets `--sheet-pad-left: 64px` (48px at ≤1399 px, 16px at ≤760 px, matching the three paddings at app.css:270, 681, 700), so the bar sits 9 px left of the text column and at least 4 px inside the sheet's edge. Top and height: from the top of the sentence's first line box to the bottom of its last (`getClientRects()` of the `.s.now` element, first and last rect, relative to the sheet). It spans whole lines, also where the sentence starts or ends mid-line; the fill tells which words.
- Focus: the current sentence is the whole `.cur` paragraph, and the bar runs from the top of `#focus-now`'s first line box to the bottom of its last (the same calculation), 12 px left of the leftmost of those line boxes (the paragraph is centred, so the bar follows its left edge).
- `static/player.js`: a function `placeBar(bar, element, box)` sets `hidden`, `top`, `height` from the element's client rects; called from `highlight()` (and `stage()` for Focus) whenever the mark moves, and from a `ResizeObserver` on `#text` and on `.focus-stage` (wrapping changes with width, font loading and Settings' theme); `hidden` when no sentence is marked. One rAF per change at most.
- Placeholder notice boxes (`#b{n}`, a block element) get the same fill and bar (the same function handles a block element).
- PR B (the marker) hangs its flags off the sheet's RIGHT edge; nothing of it uses the left margin.

3.3 No tint on heard text, and the hover tint.
- `static/app.css:297`: `.read-along .s:hover, .read-along .s.done { background-color: var(--held); }` is deleted. Hover gets no fill; a sentence keeps its `cursor: pointer` (app.css:294). Reason: a hover fill would now look like the pale mark without its bar, and Colin asked for less colour on the text.
- `static/player.js:152-155`: the `done` class is no longer added (nothing else uses it). `--held` has no other user (checked: app.css:297 only), so its three definitions (lines 53, 75, 89) go.

3.4 Focus type (`static/app.css:635-651`).
- `.view .focus-stage .cur`: `font: 400 24px/1.6 var(--read); letter-spacing: normal; max-width: 60ch;` (was `500 clamp(30px, 3.4vw, 48px)/1.35`, 28ch). 1.2 times the sheet's 20 px.
- `.view .focus-stage .prev, .next`: `font: 400 18px/1.6 var(--read)`, `max-width: 60ch` (was 22 px). Slightly below the sheet, in pencil as today.
- Under 760 px: `.cur` 20 px (1.11 times the sheet's 18 px), `.prev, .next` 16 px.
- `text-wrap: balance` stays on `.cur`; `#focus-now`'s padding stays.

3.5 Tests.
- `tests/unit/test_web_design.py` (D-711 test, line 212 onward), renamed `test_the_reading_bar_stands_out_and_the_text_on_the_mark_reads_well`: in light and dark, `--now-bar` ≥ 3:1 against the paper and against the fill; `--on-now` on the fill ≥ 4.5:1; the fill is NOT required to reach 3:1 (D-724). `test_the_contrast_check_finds_the_reading_yellow_on_white` turns into a check that the measure catches a bar in the reading yellow on white (1.2:1). Add: `--now`, `--on-now`, `--now-bar` are the same in both dark blocks; no CSS rule outside the two mark rules and `.now-bar` uses them.
- `tests/browser/test_listen.py`: `test_the_sentence_being_read_is_marked_plainly_and_a_heard_one_keeps_its_tint` becomes `..._and_a_heard_one_has_no_tint`: the reading sentence has the fill and no underline or animation; the bar is visible, its top within 1 px of the sentence's first line box and its bottom within 1 px of its last, its left edge in the sheet's left padding (between the sheet's edge and the text column); after the next sentence takes the mark the bar has moved to it and the heard one's background is transparent with no `done` class; paused and at 1.5× the same.
- Bar follows reflow: with a sentence marked, resizing from 1440 to 700 px moves the bar to the sentence's new lines (within 1 px); under 760 px it stays inside the sheet.
- Hover: hovering a sentence that is not being read leaves its background transparent.
- Focus vs sheet: computed `background-color` and `color` of `#focus-now` equal those of `#text .s.now`, and `border-left-color` and width of `#focus-bar` equal those of `#now-bar`, in light and dark (`emulate_media(color_scheme=...)` and `data-theme="dark"`); `#focus-bar` spans `#focus-now`'s lines.
- Forced colours (`emulate_media(forced_colors="active")`, Chromium): the bar is still visible (non-zero border width, colour not transparent).
- Reduced motion: the bar's `transition-duration` and animations are none in both modes.
- Size: the computed font size of `.focus-stage .cur` is at most 1.25 times that of `.sheet` at 1440 px and at 700 px.
- Colin's case: a long German sentence (the German fixture's longest, or a test text of 60+ words) in Focus at 1512 × 900 fits the stage without page scroll (document.scrollingElement.scrollHeight ≤ innerHeight) in light and dark.
- axe in Focus and on the sheet, light and dark, en and de; the 320 px reflow check for Focus. The Focus keyboard tests (#451, #461) unchanged.

## 4. #472: no "Not in this audiobook" line in the Chapters panel

- `templates/listen.html:157`: delete the `{% if view.left_out %}...{% endif %}` line.
- `strings/en.toml:294`, `strings/de.toml:299`: delete `listen.left_out` in both.
- `web/player.py`: `PlayerView.left_out` (line 508) and its filling (lines 633, 640) go; no other reader (checked: only the template line).
- Tests: `tests/browser/test_player.py:89` asserts the panel lists only the chosen chapters and contains no "Not in this audiobook" (en) / "Nicht in diesem Hörbuch" (de) text; `tests/unit/test_web_player.py:562` asserts the text is absent; the `view.left_out` asserts at `tests/unit/test_web_player.py:219`, `:334` and `tests/unit/test_web_listen.py:217` are removed, each test keeping its other checks. axe on the panel in light and dark.
- Unchanged: the "Not read:" labels on the sheet (`listen.not_read`).

## 4a. #480 is not in PR A

#480 has an app-lane half (a new short pause for `continues=True` pieces in `app/audio.py`, with exact read-along timing) and a web half (one sentence element across a cut sentence's pieces, positions and markers still resolving). That is two lanes and a change to the audio plan, not small; it goes into the web lane's next PR after PR B (or one app/web PR, as the coordinator decides), not into PR A.

## 5. Process

- Tests first for #461 and the #462 counts (each fails on main), then the changes.
- Before review: `uv run ruff check && uv run ruff format --check && uv run lint-imports && uv run deptry src && uv run pytest -m "not slow and not benchmark and not browser"` and `uv run pytest -m browser`; Linux CI green. Non-critical: Opus medium review, at most 2 rounds, no mutation or three-system run.
- Screenshots for the review report: Focus and Listen at 1512 × 900, light and dark, English and German (Colin's case), so the coordinator can show Colin the new mark.
- Size: about 170 lines of code and CSS, about 320 lines of tests.
- Ledger line in /mnt/project-files/ledger/implementation.md.
- Closes #461, #462, #471, #472.
