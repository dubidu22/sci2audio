# General marker with an optional note (v1.3 slice of the Study layer)

Status: scope APPROVED as D-723 (coordinator, 16 Nov 2026 19:36Z), ruling 1 applied (undo from the toast only, no tombstones). Revised 17 Nov 2026 04:10Z for the build: re-read against main 4bb8f81 and PR A (#489, head 39e11d3); adds the D-718 line for PR A, D-727, the full list of test-harness changes (section 7a) and the test paths of this repo. APPROVED as D-728 (17 Nov 04:04Z, rulings in section 11). PR B branches from main after #489 is merged.
Asked by Colin, 16 Nov 2026 19:30Z (cmsg_011gr2YyZJypGaV6NbzgSXQEHB38wd6bmE76FUgKgFCuKE): "add a general marker with optional notes for v1.3 the rest is for v1.5 after the installer work ist done and sci2aduio v1.4 published."
Base read: sci2audio main 7cd84bd, re-read on 4bb8f81 and PR A 39e11d3; design b4a7523 (DESIGN.md "Flags", "Captures as marginalia", Highlighter rule); issues #395 to #399, #418; web/player.py, web/api.py, web/documents.py, templates/listen.html, static/player.js, static/app.js, strings/*.toml.
Issue: #474 (v1.3, lane:web, risk:high). Deferred migration: #475 (v1.5). Comments added on #395, #397, #470.

Earlier PRs in this batch that built on a model this PR changes: PR A (#489). PR B adds a new model (markers) and changes none of the sentence, read-along, position or edit models, but it builds on three things PR A just changed, and the author re-reads them on the merged main before code:
- **PR A's reading mark** (pale fill + 3 px left bar, `placeBars()` in player.js, tokens `--now`, `--on-now`, `--now-bar`, D-724, D-727). A marker adds NO fill to its sentence, so the reading mark stays the only fill (Highlighter rule); its flag hangs off the sheet's RIGHT edge, never in the left padding where the bar is. The flag is placed from the sentence's line boxes like the bar: the line-box code of `placeBar` is pulled out into one helper `linesOf(element)` that both use (a small refactor of PR A's code; PR A's bar tests must stay green unchanged). `test_one_mark_for_the_sheet_and_focus` keeps its exact set of token users: the marker tokens are new and separate (`--marker`, `--marker-edge`).
- **PR A's side panel** (`set(open, keep)`, P keeps the focus, #461; tabs with APG arrows). The Markers tab joins `tabs`; nothing changes in `set`. "Add note" from the toast opens the panel with `set(true, true)` and then focuses the note box itself; the PR A tests `test_after_p_closes_the_panel_...` and `test_p_over_the_page_...` stay green unchanged. Re-checked on 9377cd8 (17 Nov 04:42Z): the #489 review added only `before` to `set` (P gives the focus back where it was, S2). "Add note" calls `set(true, true)` from the toast's button, so `before` is that button; the toast drops the button once the note box is open, so P closing the panel from the box then blurs to the page, which is what PR A wants. The mark is unchanged. No change to this plan.
- **PR A's Focus listening** (24 px, `#focus-bar`, `one_mark`). Focus gets the M key and a flag beside the stage's sentence when it has a marker; the PR A Focus tests stay green unchanged.
Also built on: the sentence-boundary batch (#460 in #481) splits a long sentence into pieces, each its own sentence element today; a marker set on a piece anchors to that piece's span. #480 will later make one element per sentence: the overlap rule in section 3 (step 5) then puts such a marker on the joined element; a test pins that case now.

## 1. Scope

In: ONE capture type, the design's "mark", called **Marker** in the interface (Colin's word). The listener sets or clears a marker on the sentence being read, while listening or with playback paused, and can add, change or clear a free-text note on it. The markers are listed in the Listen side panel with "Go to". One shortcut (M) in the shortcuts sheet, under the existing off switch.

Out (v1.5, see section 9): note, quote and card as separate types, N/Q/C keys, capture sounds, the Captures page, card review, filters, export, the Library column and shelf flag strips, colours per marker, quote extraction, marker search.

## 2. Naming (avoids a clash in the code)

"marks" already means the audiobook's edits drawn on the text (`view.marked`, `_marks`, `marks-note`, D-704b), and "the reading mark" is the spoken-sentence highlight (D-716, D-720). So:
- code, file and API: `marker` / `markers` (`web/markers.py`, `markers.json`, `/markers`);
- interface: en "Marker", "Note", "Add note", "Go to"; de "Markierung", "Notiz", "Notiz hinzufügen", "Zur Stelle". The panel tab is "Markers" / "Markierungen" (v1.5 may rename it "Captures" / "Fundstücke" when more types arrive).

## 3. Data model and where markers live

No change to `sci2audio.core` in v1.3. The marker record is the web layer's own small file, like `position.json` (#153) and `audiobook.json` (D-295): `web/markers.py` with frozen dataclasses and a versioned JSON format. The core capture model stays #396's job; the ADR (#395) decides it and #396 migrates this file (new issue, section 9). This keeps the slice out of the core lane and leaves the ADR free.

File: `<work folder>/markers.json`, beside `position.json`, written only by the server (web and `sci2audio listen` documents alike, as the position is, #154).

```
{"format": "sci2audio-web-markers", "version": 1, "document": "<document id>",
 "markers": [
   {"id": "<16 hex, random>", "created": "2026-11-20T10:31:04Z", "changed": "...",
    "anchor": {"block": 41, "start": 120, "end": 236, "text": "<the block's text[start:end] as printed>"},
    "note": ""}
 ]}
```

- `anchor` is the sentence in the DOCUMENT's text (block index and character offsets into the block's text, as read-along spans are), plus the sentence's printed text. It holds no time and no chunk number: times and chunks belong to one audiobook and change on every run; the text does not.
- The server takes the anchor from the read-along chunk the page names (chunk number + audiobook stamp, the same 409 rule as the position) and from `document.json`. The client never sends a span or a text.
- `note`: plain text, at most 4000 characters, no NUL; shown as text, never as HTML.
- Removing a marker takes it out of the file at once; the file holds no removed markers (D-723 ruling 1). Undo is in sections 4 and 5.
- Limits: at most 2000 markers, file at most 2 MB; a request past them gets 422 with a clear message.

### Never lost by a re-prepare or a second run
- The script job, the audio job and the CLI never read or write `markers.json`. Today a rerun removes `audiobook.json`, `document.json`, covers, chunks and `position.json` by name (app/audio.py `_remove_old_records`, `write_cover`, chunks cleanup; web/tasks.py `remove_position`); none of them touches other names. A test pins this for both the web and the CLI path (section 7).
- A marker survives a NEW audiobook because it is anchored to text, not to the audiobook. On every Listen page the server re-finds each anchor in the current `document.json` (read time only; the stored anchor is never rewritten, so nothing is lost when a later version finds it again):
  1. same block, same offsets, same text (after `shown()` normalisation: line breaks, joined hyphens) → that place;
  2. else the same normalised text in another block → the occurrence nearest the old block index (a layout change such as #454 shifts blocks);
  3. else the same normalised text inside a longer or across a split sentence of the old block's neighbourhood (±20 blocks) → that place (the sentence-boundary batch changes where sentences end);
  4. else NOT FOUND: the marker stays in the list with its quoted sentence and its note, marked "Not found in this audiobook", with no Go to. It is never dropped.
- (step 5) A found place is shown on the sentence element (read-along chunk) that overlaps it most; on a tie the first. A marker whose place lies in text the audiobook does not read (a chapter left out, a block cut whole) is listed with "Not read in this audiobook" and no Go to, never dropped.
- Broken file (bad JSON, other format or version, other document, too large, a symlink): the panel says "Your markers could not be read" and names the file; setting markers is off for that document; the file is never rewritten, renamed or removed by the server. (Like #396: "failing clearly on a broken file and never touching other files".)

### Delete paths that reach the file
- Remove document (D-353, #120) deletes the whole working folder and with it `markers.json`. The removal box (`_remove.html`, the confirmation the press already is) gets one more line when there is at least one marker: "Your {n} markers and their notes go too." (de: "Ihre {n} Markierungen und Notizen werden ebenfalls entfernt."). This is a UI path that deletes user files → critical.
- #469/#470 (per-project folders, delete with warning) must move and count `markers.json` too: a comment on both issues.
- No other path deletes it. The audio job's cleanup, "free the speech cache" (`DELETE /chunks`) and upload replacement (`_place`) touch other names only; tests pin it.

### Writing
Read-modify-write under a per-document lock in the server, written atomically with `write_texts` (a failed write leaves the old file). Two servers on the same work folder: the last write wins (same as the position); stated in the module docstring.

## 4. API (under the existing token and origin checks, schema in OpenAPI so Schemathesis covers it)

- `POST /api/v1/documents/{id}/markers` `{chunk, audiobook}` → 201 with the marker (409 other audiobook, 422 no such chunk or limits, 404, 503 not saved). Setting a marker on a sentence that already has one returns the existing marker (200); the toggle lives in the client.
- `PATCH /api/v1/documents/{id}/markers/{marker}` `{note}` → 200 (422 too long or NUL).
- `DELETE /api/v1/documents/{id}/markers/{marker}` → 200 with the removed marker. The marker leaves the file at once; the server keeps it in memory only (per document, the last 20 removals, for 10 minutes) so the toast's Undo can put it back.
- `POST /api/v1/documents/{id}/markers/{marker}/restore` → 201, writes the kept marker back unchanged (same id, created time, anchor, note); 410 `undo-expired` once the server no longer holds it (after 10 minutes or a server restart), 409 if a marker on that sentence was set again meanwhile (the toast says so). The client never sends the marker's content back.
- The Listen page gets the markers in its data block, already placed (element id, chapter, time in this audiobook), so no extra request on load.

## 5. Interface

All on the Listen page and in Focus listening; nothing elsewhere in v1.3.

- Set or clear: key **M**, or the dock's new "Marker" button (flag icon + word + key cap M when the keys are on, `aria-keyshortcuts="M"`). It acts on the sentence being read; pressed within the first 1.2 s of a sentence it goes to the one that just ended (as #397 has it). With nothing read yet the button is disabled. On a sentence without a marker it sets one at once without pausing; on a sentence with a marker it removes it. Each gives a toast in the existing status line ("Marker set." / "Marker removed.") with **Undo**; screen readers hear it through `say()`.
- Removal never asks; it is undone from the toast only (D-723 ruling 1): "Marker removed. Undo" stays until the next marker action or 60 seconds, whichever comes first, and Undo restores the marker with its note. The row leaves the panel's list at once; there is no struck-through list. A note goes with its marker, so the toast for a marker with a note says "Marker and note removed."
- On the sheet: a small squared flag hangs at the sentence's first line off the sheet's right edge (24×18 px in the right padding; 12×18 px at ≤760 px where the padding is 16 px), body `--marker` (mark orange `hl-mark`), ink flag icon, and a 1.5 px edge `--marker-edge`; a 7×10 tick in `--marker-edge` on the timeline. Both `aria-hidden`; the list is the accessible route. A marked sentence gets NO fill (Highlighter rule: the reading mark of D-724 stays the only fill). Reduced motion: the flag appears without sliding. D-727 applies: the flag's edge and the tick pass 3:1 on every background they sit on (paper, desk, dock and timeline track, light and dark), and the icon passes 3:1 on the flag body. In Focus a flag of the same look stands right of the stage's sentence when it has a marker.
- Side panel: a third tab "Markers (n)" beside Changes and Chapters. Rows in reading order, drawn as ruled marginalia (design): flag, pencil line "Chapter 3 · 12:34", the sentence in Literata italic (three lines, then "Show all"), the note in Atkinson, and the actions **Go to**, **Add note** / **Edit note**, **Remove** (same toast and Undo as M). Not-found markers come last with their notice. Go to moves the reading position to the sentence (as a click on it does, keeping play or pause) and scrolls it into view.
- Note: Add or Edit note opens a text box in the row (label "Note", counter at 3600+ characters); playback pauses while it is open, as #397 pauses for notes. Ctrl/⌘+Enter or Save keeps it, Esc or Cancel leaves it unchanged; an emptied note is saved as no note. The toast after M offers "Add note" too, which opens the panel on that row. Typing in the box never triggers a shortcut (`typing()` already guards).
- Shortcuts sheet: one row under "Listening": "M — Set or remove a marker on the sentence being read". The Settings switch that turns single keys off turns M off too; then the dock button still works. Focus listening: M works there and its foot line shows "M Marker".
- Below 1280 px the panel is the existing overlay; the note box follows its focus rules (no Tab trap below the overlay, clicks pass).
- Strings in en.toml and de.toml with the same keys (existing parity test).

## 6. What is critical

The PR is **critical (risk:high)**, full process: Opus high review, author's `ci:full` before review, up to 4 rounds, final round three-system run, mutation and nightly.
- It writes a file of the user's own words (notes) into the working folder: tests.md requires fault-injection tests for file writing.
- It changes the confirmation of a UI path that deletes user files (remove document now also removes markers).
- Not critical parts: no core dataclass, no layer contract, no golden file, no text rule. If the review finds the slice needs a core change, it stops and comes back for a plan change.

## 7. Tests (written first)

Unit, `tests/unit/test_web_markers.py`:
- round trip of every field; format, version and document checks; size and count limits; note limit and NUL refused.
- broken file (bad JSON, deep nesting, wrong format/version/document, >2 MB, symlink): read fails with the error, file bytes unchanged afterwards, no write is attempted.
- fault injection: the write fails half way (patched `write_texts`), disk full (ENOSPC), file removed between read and write, folder read-only: the old file is intact and the API answers 503.
- the undo store with an injected clock: restore within 10 minutes gives back the identical marker; after 10 minutes, after a restart, or past 20 removals it answers 410; restore after the sentence was marked again answers 409; nothing about a removed marker stays in the file.
- Hypothesis: any sequence of set, note, remove, undo keeps the file valid and readable, ids unique, and the file equal to a simple model of the same steps.
- re-anchoring: same document; a block inserted before (index shift); a line break or joined hyphen changed; a sentence split in two and two joined (the overlap rule); the same sentence twice (nearest wins); text gone (not found, kept with note). Hypothesis over random block insertions and deletions: never raises; a found place has the stored normalised text; anything else is "not found".

Survival, `tests/unit/test_web_markers_survive.py`:
- web: prepare, make the audiobook, set two markers with notes, prepare again and make the audiobook again (the rerun path of web/tasks.py, including `remove_position`): `markers.json` is byte-identical and both markers are found on the new page.
- CLI: `sci2audio` audio job run twice on the same work folder: `markers.json` byte-identical.
- free the speech cache and replace the uploaded file under the same id: `markers.json` untouched.
- remove document: the box names the count; after removal the folder and `markers.json` are gone (extends the #120 tests).

API, TestClient: every status above, token and origin required, 409 after a rerun with the page's old stamp; Schemathesis on the new routes.

Browser (`tests/browser/test_markers.py`, Chromium on PRs, three engines nightly):
- M sets a marker on the spoken sentence, flag and tick appear, toast Undo removes it; M on a marked sentence removes it and the toast's Undo brings it back with its note; the Undo button is gone after 60 s and after the next marker action; the 1.2 s rule.
- the note: add, Ctrl+Enter saves, Esc leaves unchanged, survives a reload; playback paused while the box is open.
- Go to from the list moves the highlight and scroll; not-found row has no Go to.
- keys off in Settings: M does nothing, the button still works; M does nothing while typing anywhere; Focus listening M works.
- keyboard order of the new tab and rows; overlay below 1280 px; reduced motion; axe light and dark; German strings at 1280 px.
- a marker on a cut piece of a long sentence (#460) shows its flag on that piece; the PR A bar and fill on a marked sentence are unchanged (same computed colours as an unmarked one).
- Unit (`tests/unit/test_web_design.py`): the marker tokens pass D-727 (edge and tick 3:1 on paper, desk, dock and fill-free sentence; icon 3:1 on the body) in light and dark; the two dark blocks hold the same marker tokens.

Mutation targets on the final round: the re-anchoring steps, the 409 stamp check, the undo store's expiry and limit, the broken-file guard, the removal-box count.

## 7a. Every change to the test harness

1. `tests/unit/web_helpers.py`: two helpers, `markers_of(work) -> dict` (reads `markers.json` raw, for byte and field checks) and `set_marker(client, doc, chunk, stamp) -> dict` (POST with the token and Host, asserts the status). No existing helper changes.
2. `tests/unit/test_web_schemathesis.py`: the module fixture `served` also makes an audiobook for its seed document with the fake voice (the set-up `test_web_player.make` uses: `audio_fakes`), and seeds one marker; `known` gains `"marker_id"` so the replaced call reaches the real 200/409/410 paths too. Its run time grows by one fake audio job (about 2 s).
3. A fake clock for the undo store: the server's `State` takes an optional `clock` (default `time.monotonic`), so tests pass a list-backed clock; a `fake_clock` fixture in `web_helpers.py`. No real sleeping in any test.
4. The first Hypothesis stateful test in the repo (`RuleBasedStateMachine` in `test_web_markers.py`): rules set, note, remove, undo, reload; invariants file valid, ids unique, equal to a plain list model. It uses the existing `dev`/`ci`/`nightly` profiles; `ci` keeps the default step count, `nightly` raises it.
5. Fault injection: `monkeypatch` of `sci2audio.web.markers.write_texts` (OSError half way, ENOSPC), the file removed between read and write, and a read-only folder (`chmod`; skipped as root and on Windows, as `test_web_library.py` already skips "root writes anyway").
6. CLI survival: `tests/unit/cli_helpers.py` runs the audio job twice on one work root with the fake voice; no change to `cli_helpers.py` is expected (if one is needed, it is listed in the PR).
7. Browser: a new module `tests/browser/test_markers.py` with a helper `marker_flag(page, element)`; the 60 s toast expiry uses Playwright's clock as `test_axe.py` does (`page.clock.install()` before the load, `fast_forward`), only in that one test. Existing browser tests extended, not rewritten: `test_focus.py` (`test_every_key_on_the_listen_page`: M sets and removes; the keys-off test: M does nothing; the shortcuts sheet test: the M row), `test_remove.py` (the count line in the remove box), `test_listen.py` (the Markers tab in the panel's keyboard order). Note: `test_player.highlighted()` takes the first `[aria-current=true]`, which the chapter buttons also carry; marker rows never use `aria-current`, and new tests read `#text .s.now` instead.
8. Mutation on the final round: mutants in `/mnt/project-files/plans/pr-b-mutation/` (as for earlier critical PRs), run by the review thread or the label-triggered workflow.
No change to CI workflows, `conftest.py` fixtures, markers, golden files or the corpus.

## 8. Order, size, lane

- Lane: web (lane:web), with small app-free touches only. One PR, about 350 lines of code (markers.py ~200, api ~90, pages/player ~60, template ~60, player.js ~200, css ~70, strings) and about 900 lines of tests.
- It touches listen.html and player.js, as PR A (#489) does. Order: PR B branches from main after #489 is merged (the sentence-boundary batch is merged: 4bb8f81). If #489's review changes the mark or the panel, this plan's D-718 section is re-checked before code.
- Ledger lines as usual.

## 9. Deferred to v1.5 (Study layer, after v1.4 is published)

Already covered by issues, with a comment linking this slice:
- #395 ADR: decides whether "mark with note" stays a mark or becomes a note, and how v1.3 markers fit the capture model.
- #397: note, quote and card types, N/Q/C keys, sounds, the four capture keys in the dock.
- #398: the Captures page, filters, card review.
- #399: export (files first).
- #418: the Library column and shelf flag strips.
New issue #475 (v1.5): migrate `markers.json` v1 into the core capture model of #396, keeping every marker and note, with a test on a v1 file.
Not planned in any milestone unless Colin asks: colours per marker, marker search.

## 10. Rulings (D-723, coordinator, 16 Nov 2026 19:36Z)

1. Removing a marker is undone from the toast only; no 30-day struck-through list, no tombstones in the file (applied above).
2. M toggles.
3. This thread is the web lane thread for v1.3 with two PRs: PR A = #461, #462, #471, #472 (non-critical, plans/web-lane-v13-pr-a-plan.md), then PR B = this marker (#474, critical). Both carry the D-718 line.

## 11. Approval (D-728, coordinator, 17 Nov 2026 04:04Z)

Plan approved, critical process as in section 6. Rulings:
1. The broken-file guard gets a test that fails without the guard. Re-anchoring step 4 ("never dropped") gets a test that fails if a not-found marker is removed from the list or from the file.
2. A restore (undo) writes the kept marker back only through the same locked read-modify-write path as a set. There is no second write path.
3. The removal box line counts markers from the file at the time the box is drawn. The extended #120 test pins the count.

Order stands: branch from main after #489 merges; re-check the D-718 section if the #489 review changes the mark or the panel; tests first; ci:full before hand-off to the same review thread; state the compression count at hand-off.
