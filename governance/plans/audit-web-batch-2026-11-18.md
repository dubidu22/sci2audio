# Light batch audit: web batch (v1.3 PR A/B, #480 C1/C2, resume, release port, nightly-green PRs 1-2), 18 Nov 2026

Scope: the eight squash commits on main read as one diff, base 4bb8f81 to tip 96de4a3: #489 9377cd8 (PR A: pale mark + bar, P keeps focus, counts), #490 fc7406a (PR B: markers, critical), #495 3c7482f (#480 C1: clause pause + read-along `joins`, critical), #503 344db7a (#480 C2: one sentence on the page and for markers), #505 11b8b13 (resume keeps replace, free-cache confirm, critical), #507 1e461a7 (release/1.1 port), #510 68f322d (WebKit focus/Tab, Close focuses toggle), #511 96de4a3 (key chords, theme transitions, dock). #492 5812d2d (output names) sits inside the range but is not part of the batch; looked at only for overlap (none).

Looking only for cross-PR inconsistencies (same thing solved twice, later PR undoing an earlier one, duplicated helpers, diverging shortcut/focus rules, drifted marker/resume/read-along formats) and unannounced touches of contracts, `sci2audio.core`, goldens, regression cases, CI or `docs/readalong-format.md`. Read-only, one pass, Opus medium. No mutation, nightly or test runs; the per-PR review reports cover those.

Method: `git diff 4bb8f81 96de4a3` per area; the cumulative `player.js` diff (#489 #490 #503 #510 touch it); `api.py`/`pages.py`/`markers.py`/`player.py` marker paths (#490 then #503); `readalong.py`, `output/model.py`, `docs/readalong-format.md` (#495) against their reader `player.sentence_starts` (#503); `_making.html`/`app.js`/`jobs.py` (#505) against what `clean_work_folder` deletes; en/de string key parity; keyboard sheet and hints; browser-test helpers (#510 #511) against the rest of `tests/browser`.

## Verdict

**The batch is sound. Missed findings: B 0, S 2, N 4.** No core dataclass, golden, regression case, lint-imports layer or CI workflow was touched. The one contract touch, `docs/readalong-format.md` with the additive `chunks[].joins` (#495), was announced in the PR, the commit body and the review (critical, three systems), and keeps version 1 correctly. The two S items are small seams where #503's "one sentence = its first piece" model did not reach code #490 wrote two hours earlier, and where #490's new key did not reach #394's hint text.

What holds (checked, consistent):
- **One grouping rule for sentences.** #503 put it in one function, `player.sentence_starts` (player.py:983), used by the page (`_block_view`), the player data (`sentences`), and the marker API (`_Book.firsts`). Every player.js path that steps or times by sentence goes through `firstOf`: Next/Previous (player.js:301-310), M's 1.2 s look-back (510), ticks (658), list time (691), Go to (718). Pieces share one element id, so `markersOn`, `markerState`, flags and the Focus `order` dedupe group by sentence without extra code. No path still steps by chunk.
- **`joins` writer vs reader.** #495 writes it only on a non-first piece within a block and never on a chapter's first chunk (review T11); #503 ignores any other `joins` (same block, drawn neighbour, not skipped), so a hand-made file can't split page and markers. Read-along stays v1; `from_json` refuses a non-bool `joins`, matching the format's "true or left out".
- **Marker data format.** `markers.json` v1 (#490) unchanged by #503; #503 only widens the span a new anchor stores (whole sentence instead of a piece). Old piece anchors are still found (step 1/2 of `_Finder.find`) and grouped by `on_sentence`, and a second press removes them rather than adding a twin (set's `existing` goes through `on_sentence`, api.py:472; restore's clash check too, api.py:527).
- **Destructive paths.** #505's free-cache confirm deletes only `chunks/` (`app/chunks.py:101`), never `markers.json`, `position.json` or the records, so it does not undercut #490. Marker removal stays confirm-free with Undo (D-723) and cache freeing asks (D-733): different on purpose (one can be undone, one can't), not a drift.
- **Focus rules.** #489 (P keeps focus, `set(open, keep)`), #490 (`show()` opens the Markers tab with `keep`), #510 (Close always focuses the toggle) compose: button/Esc close → toggle; P close → back where P found the focus; note Esc stops propagation before the panel and the global handler. #510's extra `toggle.focus()` after `set(false)` does not undo #489's P rule (P never goes through Close).
- **Keys.** M sits behind `shortcutsOn()`/`typing()` like the rest (player.js:868-880), is on the shortcuts sheet (base.html:84), the Focus foot and the button's `aria-keyshortcuts`. #511's dropped Left-arrow chords match the handler's single modifier guard (player.js:861).
- **Strings.** en/de key sets identical after all eight PRs.
- **Release port (#507).** No overlap with #505/#510 files; nothing from release/1.1 reverted by a later batch PR.

## Findings

### Should fix

**S1. The marker API and the page data name a marker's sentence by the piece that overlaps it most, while everything else names a sentence by its first piece (#490 model vs #503).**
`markers.place` (markers.py:384-388) picks the chunk with the largest overlap. Since #503 a new anchor spans the whole cut sentence, so for a sentence whose second piece is longer, `MarkerOut.chunk` (api.py:418) and the page's `data.markers[].chunk` (pages.py:1149) carry the second piece, while `MarkerIn.chunk`, the element's `data-chunk`, `PlayerView.sentences` and every JS use say "first piece". Nothing shows wrong today, because every JS reader maps through `firstOf` and every server reader through `on_sentence`; but `models.py:246` documents the field as "the chunk it is shown on", which it is not, and the v1.5 Study layer (#475: list/export of markers) will read this field.
Fix: map to the sentence's first piece where the placed chunk leaves the server. In `api._marker_out`: `chunk=None if placed.chunk is None else book.firsts[placed.chunk]`. In `pages._markers_data`: compute `firsts = sentence_starts(located.readalong)` once and emit `"chunk": None if p.chunk is None else firsts[p.chunk]`. Change the description at models.py:246 to "the sentence's first chunk in this audiobook, or null". Test: a joined read-along whose second piece is longer, whole-sentence anchor; GET page data and POST answer both give the first piece. Lane web, non-critical, v1.3 or fold into the next web PR.

**S2. The Settings hint for the keys switch lists "Space, F and P" but not M (#394 text vs #490's new single-letter key).**
en.toml:534 `keys_hint` and de.toml:539. This is the text that explains the WCAG 2.1.4 off switch; #490 added a fourth single-letter key that the switch also turns off.
Fix: en `"Single keys such as Space, F, P and M work while you listen. ..."`; de `"Einzelne Tasten wie Leertaste, F, P und M wirken beim Hören. ..."`. If a unit test pins the string, update it. Fold into the next web PR.

### Notes

**N1. `markerCall` builds its JSON request by hand (player.js:521-528) instead of app.js's `json(method, body)` (app.js:74), which #505's `restart` and the rest of app.js use.** Fix: `return await send(url, body ? json(method, body) : { method });`. Pure cleanup.

**N2. The theme-change wait lives in one test file.** #511 added `change_theme` (test_listen.py:61) for #500, but `check_axe` (conftest.py:234-240) and the theme loops in test_focus.py (158, 759), test_markers.py (324), test_library.py (110), test_shell.py (89, 119), test_prepare.py (57, 70), test_screens.py (42), test_settings.py (50), test_chapter_order.py (51), test_player_position.py (71), test_player_speed.py (41) still call `emulate_media` bare. Today only `input.switch` transitions (app.css:218-219), axe's contrast rule skips text-less inputs and none of those loops asserts `getAnimations()==0`, so this is not a live flake. Fix when next touched: move `change_theme` to conftest.py and use it inside `check_axe` and the loops, so the next transition added to app.css does not reopen #500 in a dozen places.

**N3. `docs/readalong-format.md:54` does not state the invariants the web reader relies on.** The row says when `joins` is true, not that it never appears on a chapter's first chunk and only between neighbouring chunks of one block, nor that a reader should treat any other `joins` as false (the rule in `sentence_starts`' docstring, player.py:984-990). A third-party player could group differently. Fix (critical doc, so in a reviewed PR, could ride with the next contract change): append to the row "It is never set on a chapter's first chunk and only joins a chunk to the one before it in the same block; a reader treats any other `joins` as false."

**N4. #507 changed `pyproject.toml` (`[tool.mutmut] also_copy` gains `.github/`, line 146) without `risk:high`.** It is mutmut test tooling, not packaging or a workflow, and a word-for-word port of an already reviewed release/1.1 fix, so no action; recorded so the "packaging" wording in CLAUDE.md is read as `[project]`/build sections, not every `pyproject.toml` line.

## Contract touches (checked)

- **`docs/readalong-format.md`, `output.model` (`Pause.CLAUSE`, `Spoken.continues`, `OutputSettings.clause_pause`), `readalong.ChunkTimes.joins`:** #495 only; announced, critical, three systems, old-reader and old-file tests (`tests/unit/readalong_v1_0.py`, D-730 lesson). Output layer, not `sci2audio.core`.
- **`sci2audio.core`, lint-imports layers, voice contract, text-step interface:** untouched.
- **Goldens, corpus truth, regression TOMLs, snapshots:** untouched (no file under tests/corpus, tests/regression, tests/sentences or any snapshot in the range).
- **CI workflows:** untouched; `scripts/zap_scan.py` gained the marker routes (#490) and the free-cache confirm step (#505), both announced.
- **New web formats:** `markers.json` v1 (#490, documented in markers.py header, versioned, refused-not-overwritten when unreadable); `JobOut.overwrite` (#505, additive response field). `position.json` unchanged.

## Issues I would file (coordinator decides; none filed)

1. S1 "Marker API names a cut sentence by its longest piece, not its first" (lane:web, v1.3 or v1.2.x).
2. S2 "Keys switch hint omits M" (lane:web, v1.3), or fold with S1 into one web PR without its own issue.
3. N3 "readalong-format: state where `joins` can appear" (lane:docs, critical doc, v1.2.x).
N1, N2: no issue; fold into the next web PR that touches player.js / tests/browser.

## Workflow verdict

| | B | S | N |
|---|---|---|---|
| Found by the batch reviews (#489 r1-2, #490 r1-2, #495 r1, #503 r1-2, #505 r1, #507 r1, #510 r1, #511 r1) | 0 | 7 (#489 3, #490 2, #503 2) | 3 (#489 1, #490 2) |
| Missed, found by this audit | 0 | 2 (S1 cross-PR #490/#503; S2 cross-PR #394/#490) | 4 |
| Post-merge defects | | #490: #496 (test harness, WebKit Tab order, not code) | |

**Was the web thread's length right (PR A + PR B, 3 compressions)?** Yes for this batch, but it was the limit, and it should not be the plan for the next one. The thread wrote #489 at 0 compressions and #490 (critical, 2,900 lines) from 2 to 3; the rule says replace at 2 "at the next hand-off", and the next hand-off fell inside #490's single review round, where replacing is forbidden. Quality did not visibly drop: #490's review found no functional defect, only unpinned re-anchoring rules (test gaps the reviewer's mutants exposed), the old #491 bug was caught on the way, and its only post-merge defect was a WebKit harness issue. Neither audit S item comes from context loss: S1 comes from a different thread (#503) changing the anchor span after #490 merged, S2 from a string written in batch D. Judgement: **keep "one batch per lane thread, replace at 2 compressions"**, and size web batches so that the critical PR comes first or alone: a batch with one critical PR of ~3k lines should be planned as its own thread, since that is what pushed this one to 3. The C1/C2 thread (1 compression, 0 functional findings) and the nightly-green threads (2 and 0) show the shorter shape works. One more: the thread that ported release/1.1 (#507) also wrote #510, a different batch, and reached 2 compressions; a thread should not carry into the next batch even when it has the context (LANE rule "lives for one batch").

Plan-template suggestion (from S1): a PR that changes what an id or index means (here "a sentence is its first piece") lists every place that emits that id to a client, not only the places that consume it.
