# Plan: implement "The Working Reader" design

Status: **proposal, waits for the coordinator's approval** (critical: it changes the app's interface contract and bundles third-party fonts). Nothing is filed on GitHub yet.

Sources read: sci2audio-design main b4a7523 (PR #51): `IMPLEMENTATION-PROMPT.md`, `PRODUCT.md`, `DESIGN.md`, `README.md`, `prototype/app/` (file list, fonts, sprite, key handling); sci2audio main a9e0e2d: `CLAUDE.md`, `.github/lanes.yml`, `src/sci2audio/web/` (templates, `player.py`, `static/`), `src/sci2audio/app/settings.py`, `output/readalong.py`; KB decision log (D-45, D-46, D-57, D-295, D-414, D-453–D-460, D-626/627); `plans/roadmap-after-v1.md`; open issues on GitHub (15 Nov 21:58 UTC).

## 1. Decision drafts for the KB thread

### D-663 · Adopt "The Working Reader" as the app's design

- Subject: the design proposal "The Working Reader", merged by Colin into sci2audio-design main as b4a7523 (PR #51).
- Decision: "The Working Reader" is the binding design for the whole sci2audio interface.
  - `DESIGN.md` and `.impeccable/design.json` (tokens, named rules, components, do's and don'ts) are binding for every interface PR. `PRODUCT.md` replaces the earlier hosted-service `PRODUCT.md`. `IMPLEMENTATION-PROMPT.md` is the input for planning the issues; the plan is `plans/working-reader-plan.md` (project files).
  - The hosted-service design files (`FUNCTIONAL-BRIEF.md`, `CRITIQUE-FINDINGS.md`, `REVIEW-FINDINGS.md`, `GUIDED-TEST-PROMPT.md`, `TESTANLEITUNG.md`, every `prototype/` folder except `app/`) are superseded and kept as a record.
  - Existing rules stand and win where the prototype differs: one interface, server-rendered Jinja with plain JS and no hash router (D-45); faithful text and marked edits (D-57); layout does not move text (D-414); 127.0.0.1 only; pages load nothing from the internet, so fonts, icons and scripts are bundled.
  - The prototype's synthetic data (`data.js`), review switches and simulated audio and job progress do not enter the product.
  - Not decided by this entry: the study layer (captures, their storage and the Zotero, Obsidian and Anki export). It needs its own ADR before its first issue. The wordmark is a proposal, not a logo.
- Status: **Decided** (Colin, 15 Nov 2026 21:53:49 UTC, his words: "I've merged dubidu22/sci2audio-design#51 … into main" and "log adopting the design as a decision in the knowledge base").
- Record: sci2audio-design PR #51 (b4a7523); `IMPLEMENTATION-PROMPT.md`; `plans/working-reader-plan.md` (project files).

### D-664 · The player bar shows on Listen and Focus only, at first

- Subject: does the docked player bar show on every page, or only on the Listen page at first?
- Decision: **only on the Listen page and in Focus listening** at first. Every other page shows a "Continue listening" item at the top of the rail's "Reading and recent" shelf instead: title, the remembered position ("Continue from 3:12") and the listened meter. Clicking it opens the Listen page at that position, which still does not start playing by itself (#153).
  - Reasons:
    1. The pages are server-rendered (D-45), so any navigation unloads the page and stops the audio. A bar on every page would play only until the next click and then fall silent mid-sentence. That breaks the design's own promise that the audio's state follows what the user does.
    2. Keeping audio alive across pages needs navigation without a page load: a client router or a persistent frame around the pages. The prototype's hash router is explicitly left out of the product, and either way is a larger change to the interface's contract than the redesign itself.
    3. The remembered position (#153, PR #373) already makes leaving and returning cheap: the shelf item resumes at the exact sentence.
    4. The installers with an app window (#215, v1.3) change the shell anyway; the question is better decided with that window in hand.
  - Revisit: a "Later" issue, "Keep playing while moving between pages", decided after the installers.
- Status: Decided (Claude) (coordinator, 15 Nov 2026, under D-80 as extended by D-462 and D-553; asked by Colin to decide, 21:53:49 UTC).
- Record: `plans/working-reader-plan.md` (project files); D-663; IMPLEMENTATION-PROMPT.md "Choices to make".

## 2. Conflicts and open points to flag

With KB rules:

1. **Text as printed vs. "footnotes read after their mark" on the sheet.** No conflict in practice: the listen view already shows a note read at its mark right after the block it is read in, and only where the audio did so (`player.py` `build_view`, `_heard_moves`, #213). Layout still does not move it (D-414). The new sheet must keep that rule, not show every note at its mark.
2. **Pencil strikes and "said as" tooltips must show the edits the audiobook was made with**, not today's switches. The view rebuilds the step run with the built-in steps; if the user switched a category since, the sheet would show changes the audio does not have. Acceptance criterion for the Listen issue: strikes and readings come from the job's recorded settings, with the read-along as the check (as `_heard_moves` does for moves). Text the voice does not read is already a `Piece` with no element, so strikes need no new data; "said as" needs the replacement text of each edit, which the view can take from the step run (web lane only, no core or read-along change).
3. **"Changes" in the Listen panel are read-only.** Switching a category changes what is heard only after the audiobook is made again (span-based edits, D-57). The panel says so and links to Prepare, instead of switching in place.
4. **"Pause, resume and cancel" while making.** The job API has no pause. Today a cancel already keeps the spoken sentences for a rerun. Recommendation for the Prepare issue: "Pause" is today's cancel (everything kept), "Resume" is a rerun from the cache, and "Cancel" also frees the speech cache, with a confirm. No change to the app's job runner.
5. **"Failures keep finished chapters".** Today a failure keeps the spoken sentences for a rerun; no audio files are written for the chapters already finished. The failure notice must say what is really kept ("12 of 17 chapters were spoken and are kept for a rerun"). Writing a partial audiobook on failure is new output behaviour: a separate issue (Later), not part of the redesign.
6. **Study layer exports and the network rule.** Zotero's and Anki's usual integrations are local HTTP servers (Zotero's local API, AnkiConnect); the reference screen `captures-anki-offline-dark.png` assumes one. A call to another program on 127.0.0.1 is a network call under the hard rule. The ADR must decide between file exports only (Markdown for Obsidian, RIS or BibTeX for Zotero, a CSV or `.apkg` for Anki) and an explicit, user-started local connection. Recommendation: files first.
7. **Captures change `sci2audio.core`** (a capture model with span, time and type), so the study layer is critical and single-threaded in the core lane.

With the roadmap (D-453–D-460):

8. **Milestone placement.** The roadmap has v1.2 (better listening for Colin's papers, 43 open) and v1.3 "ready for others" (installers, plugin interface, update check). The installers wrap the interface in an app window, so the redesign should land first. Recommendation: a new milestone **"v1.3 The Working Reader"** for batches A to D; the current v1.3 becomes **v1.4 "ready for others"**; the study layer gets **"v1.5 Study layer"** once its ADR is decided. This reorders a roadmap Colin decided (D-458): the coordinator decides whether that needs his word. If not, the fallback is to keep v1.3 and add the design issues to it.
9. **Open web-lane issues the redesign touches** (the web lane is single-threaded, so they either fold into a batch or wait):
   - #365 (axe while the document page reloads, P1 quarantined): fold into batch C, since that batch rewrites the page.
   - #314 (VoiceOver navigation, v1.0.1): its findings become acceptance criteria of every batch; close it with batch D.
   - #351 (subtitles as a track in the player, v1.2): the design has no subtitle track; the sheet itself is the text track. Recommendation: close as superseded by D-663, or move to Later.
   - #293 (show the figure, table or formula where its notice is spoken, v1.2): fits the design's notice lines. Do it after batch D, on the new sheet.
   - #155 (read-along on the PDF page images, v1.2, D-102): the design shows the text in Literata, not page images. Recommendation: Later, as a second view of the sheet to be designed.
   - #14 (visual regression for the read-along view): replaced by the screenshot workflow in batch A.

## 3. Proposed issues

Repository dubidu22/sci2audio. Lane label `lane:web` unless stated (the app/release lane of D-626). Every issue: acceptance criteria from its prototype page and screenshot; strings in `strings/en.toml` and `strings/de.toml` with the same keys, German wording from `prototype/app/i18n.js` ("Captures" is "Fundstücke"); `uv run pytest -m browser` (keyboard, axe light and dark); reduced motion; no fluorescent on chips, buttons or navigation; checked at 1440 and 1280 px, light, dark and German; below 1280 px the panel becomes an overlay.

### Batch A, PR 1: foundation and shell (critical, risk:high: third-party fonts and a CI workflow)

**WR-1 · web: design tokens, bundled fonts and the icon sprite** (lane:web, lane:infra for the workflow). Port the light and dark tokens from `prototype/app/app.css` into `src/sci2audio/web/static/app.css` (dark under `prefers-color-scheme` and under an explicit `data-theme`), bundle the five woff2 files (280 KB) with the two OFL 1.1 licence texts, list them in `THIRD_PARTY_LICENSES.md`, check the wheel includes them, and add the inline SVG sprite (34 symbols). Nothing loads from the internet; a test asserts no `http` address in any template or static file.

**WR-2 · ci: screenshots of every page on a label** (lane:infra). A label-triggered workflow (`ui:screens`) renders each page at 1440 and 1280 px, light, dark and German, with corpus documents only, and uploads the images as an artifact, so a review thread compares them with `prototype/app/screens/` without running them. Images are not golden files (no pixel diff across systems). Replaces #14.

**WR-3 · web: the cobalt rail replaces the header and footer** (lane:web). New `base.html`: wordmark, Library, Captures (hidden until the study layer), Open a document, Voices; the "Reading and recent" shelf as a slot (filled in WR-5); Settings, Privacy, Keyboard shortcuts at the foot; the running job as a shelf item with its progress. Skip link and landmarks kept.

**WR-4 · web, app: a Settings page** (lane:web, lane:app). Appearance (system, light, dark), interface language (moved from the header), default output folder and default speed, and "announce each sentence to screen readers" (off by default). New fields go into the interface's saved settings; the command line still reads them and never writes them. Sounds wait for the study layer.

### Batch B, PR 2: library and the quiet pages (non-critical)

**WR-5 · web: the library as a table, and the shelf** (lane:web). `/` shows title and authors, a state chip with icon and word, listened (from `position.json`), last opened, and "Made on the command line" rows (#154). Open a file or paste text inline at the top. First run and an empty library; one notice with a link to Voices when a voice is missing. The rail shelf lists papers being read and made, with meters, and the "Continue listening" item of D-664. The captures column waits for the study layer. "Last opened" is a small new record in the document's work folder.

**WR-6 · web: Voices, Privacy, not found and the removal dialog in the new design** (lane:web). Voices: packs per language with files, sizes, licences, hosts, explicit consent and download progress (today's behaviour, restyled). Privacy: restyled, every statement still checked against the code. `missing.html` and `_remove.html` restyled with no prototype page.

### Batch C, PR 3: prepare and making (non-critical)

**WR-7 · web: the document page as Prepare, with the job inline** (lane:web). The paper header with Prepare and Listen tabs (shared with Listen). The three steps restyled: changes by category with a switch, a count and "printed → read as → why" examples; chapters (choose, deselect, reorder); language; voice and speed; make. Progress sits at the top of the page: chapter, sentences, time left, with Pause, Resume and Cancel as in conflict 4. A failure names the chapter and the reason and says what is kept (conflict 5). `/jobs/{id}` stays as a route, rendered in this layout. Folds in #365.

### Batch D, PR 4: listening (non-critical; Opus high review recommended for its size)

**WR-8 · web: the Listen sheet with the reading sweep** (lane:web). The sheet in Literata (66ch), the yellow sweep advancing with the audio (whole sentence under reduced motion), already-read text held in a pale tint, skipped text struck in pencil and "said as" words with their reading as a tooltip (from the audiobook's own edits, conflict 2), notes after their mark only where heard, notice lines for tables, figures and formulas, page-break marks. Fast on books of 1,000+ pages. No screen-reader announcement per sentence unless the setting (WR-4) is on.

**WR-9 · web: the resume bar, the context panel and the docked player on Listen** (lane:web). Resume bar ("Continue from 3:12", #153). One context panel with Changes (read-only, conflict 3) and Outline; Captures waits for the study layer. The 88 px dock: timeline with chapter ticks, previous, play, next, title and tabular time, speed (#152), the AI-voice label. Shown on Listen and Focus only (D-664). Closes #314 if its findings are met.

**WR-10 · web: Focus listening and the keyboard shortcuts sheet** (lane:web). F toggles Focus (no rail, no panel, the current sentence at display size), Esc leaves. The `?` dialog lists Space, ← →, ⇧← ⇧→, − +, F, P, ?, Esc (N Q C M follow with the study layer). Letter keys are ignored while typing and while ⌘, Ctrl or Alt is held; no collision with browser or system shortcuts.

### Batch E: the study layer (own milestone, critical, after its ADR)

**WR-11 · docs: ADR for the study layer** (lane:docs, KB). Scope of the first version, the capture model and where it is stored (per document work folder), undo, and the export route (conflict 6). Product scope: recommend Colin confirms it.
**WR-12 · core: the capture model** (lane:core, risk:high). After WR-11.
**WR-13 · web: capture while listening** (lane:web). N, Q, C, M at the current sentence; quote and mark save at once with a sound and an Undo toast, within 1.2 s of a sentence start they belong to the one before; note and card pause and open a box in the panel; flags at the sheet edge and on the timeline; the sounds setting.
**WR-14 · web: the Captures page and review** (lane:web). Captures as ruled marginalia, filters, removal by cancel with restore, card review; the library's captures column and the shelf's flag strips.
**WR-15 · app, web: export captures** (lane:app, lane:web). As the ADR decides.

### Later

**WR-16 · web: keep playing while moving between pages** (D-664's revisit). **WR-17 · app, output: write the finished chapters when a job fails** (conflict 5).

## 4. Order and threads

A → B → C → D, each batch one PR after the previous one merged (each needs the foundation and the rail; the web lane is single-threaded). One web-lane implementation thread (Opus high) holds batches A to D, with a fitness check before each batch; one review thread for the batch series (Opus high for A, medium for B to D). The textprep lane goes on with v1.2 in parallel; the files do not overlap. The study layer starts only after D is merged and its ADR is decided.

## 5. KB decision texts for the KB thread (D-663 to D-666)

D-663 and D-664 stand as drafted in section 1. Add to D-663's record: sci2audio Issues #385 to #401. Add to D-664's record: Issue #400 (the revisit, Later).

### D-665 · The Working Reader plan approved; issues filed

- Subject: the plan for implementing "The Working Reader" (`plans/working-reader-plan.md`, project files).
- Decision: the coordinator approved the plan with its recommendations, and 17 issues were filed in sci2audio on 15 Nov 2026:
  - Batch A (PR 1, critical): #385 tokens, fonts and sprite (risk:high), #386 screenshots on the `ui:screens` label, #387 the cobalt rail, #388 Settings.
  - Batch B (PR 2): #389 the library and the reading shelf, #390 Voices, Privacy, not found and removal.
  - Batch C (PR 3): #391 Prepare with the job inline (folds in #365).
  - Batch D (PR 4): #392 the Listen sheet and sweep, #393 resume bar, context panel and dock (closes #314), #394 Focus and the shortcuts sheet.
  - Batch E, the study layer: #395 ADR, #396 the capture model (risk:high), #397 capture while listening, #398 the Captures page and review, #399 export.
  - Later: #400 keep playing between pages (D-664's revisit), #401 write the finished chapters when a job fails.
  - Batches A to D run in order in one web-lane implementation thread (Opus high), one PR per batch, with a fitness check before each batch. One review thread for the series: Opus high for batch A, medium for B to D. The study layer starts after batch D and its ADR; its scope is Colin's.
  - Choices adopted: while making, Pause is today's cancel (everything kept), Resume reruns from the speech cache, Cancel also frees the cache after a confirm, with no change to the job runner. A failure says what is really kept; a partial audiobook is #401. The Listen "Changes" panel is read-only. Strikes and "said as" come from the edits the audiobook was made with (the job's recorded settings), not today's switches. Study-layer exports are files first; the ADR may propose a user-started local connection to Zotero or Anki as a later option, because such a call is a network call under the hard rule.
  - Issue changes: #351 closed as superseded (the sheet is the text track); #155 moved to Later (a second view of the sheet, to be designed); #365 folds into #391; #314 folds into #393; #14 closes when #386 lands.
- Status: Decided (Claude) (coordinator, 15 Nov 2026 21:58 UTC, under D-80 as extended by D-462 and D-553, and D-626). Follows D-663 and D-664.
- Record: sci2audio Issues #385 to #401, #351 (closed), #155 (Later), #365, #314, #14; `plans/working-reader-plan.md` (project files).

### D-666 · Milestones for the Working Reader (status to be checked by the KB thread)

- Subject: where the Working Reader issues go in the roadmap.
- Decision, as the coordinator relayed it: a new milestone "v1.3 The Working Reader" for batches A to D (#385 to #394); the current v1.3 "ready for others" becomes v1.4 and keeps its issues; a new milestone "v1.5 Study layer" for #395 to #399; #400 and #401 go to Later. If so, this amends D-458 (installers in v1.3) and D-459 (public plugin interface in v1.3), which then land in v1.4.
- Status: the coordinator reports Colin's choice of option 1 on its decision card at 15 Nov 21:59 UTC (the KB thread checks the card's answer). Colin then wrote the go in this thread at 22:03:51 UTC, his words: "Go: in dubidu22/sci2audio, rename milestone v1.3 to v1.4, create milestones 'v1.3 The Working Reader' and 'v1.5 Study layer', and assign #385 to #401 to them." So: **Decided** (Colin).
- Carried out 15 Nov ~22:05 UTC: milestone 5 renamed v1.4 (description and issues kept); new milestone 8 "v1.3 The Working Reader" holds #385 to #394; new milestone 9 "v1.5 Study layer" holds #395 to #399; #400 and #401 are on Later (6).
- Record: GitHub milestones of sci2audio; Issues #385 to #401; `plans/working-reader-plan.md` (project files); D-458, D-459, D-665.
