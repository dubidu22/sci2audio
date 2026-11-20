# Plan: issue #78, the player with read-along on the original text (OU-02)

Thread "Build the player with read-along", 13 Nov 2026, on main 8f0aee6 (after #77, PR #121).
Sources read: Issue #78; `CLAUDE.md`, `.claude/rules/tests.md`, `.claude/rules/licences.md`; KB D-55, D-61, D-98, D-101, D-102 (Q9), D-115, D-117, D-119, D-154, D-165, D-197, D-244 to D-261, the legal notes on the AI label in the player (`doc-voice-and-model-licensing.md`, `audit-legal-readiness.md`); plans `issue77-main-flow-plan.md`, `issue69-output-plan.md`, `issue71-audio-job-plan.md`, `issue76-server-plan.md`; `docs/readalong-format.md`; code on main: `output/readalong.py`, `app/audio.py` (`audio.json`, `document.json`), `app/chapters.py`, `app/report.py` (`Pages`), `textprep/placeholders.py`, `web/*`, `tests/browser/*`.

## 1. What the person gets

A **Listen** page per document, `/documents/{id}/listen`, once an audiobook of it exists:

```
Listen: <document name>
[AI notice: read by a synthetic voice (Kokoro, Heart), made with sci2audio]
┌ player bar (sticky) ─────────────────────────────────────────────────────────┐
│ [Play/Pause] [◀ Sentence] [Sentence ▶] [◀ Chapter] [Chapter ▶]  Chapter 2 of 5 │
│ <audio controls> (seek, volume)       [x] Scroll with the reading            │
└──────────────────────────────────────────────────────────────────────────────┘
Chapters: 1 Introduction · 2 Methods · ... (each a button that plays from its start)
Not in this audiobook: References
── 2 Methods ─────────────────────── (chapter heading)
Page 4
Paragraph text, every sentence the voice reads is one element; the one being read is
highlighted, and a click on any sentence plays from there.
┌ Formula 3 is skipped. ┐  (the notice the audiobook reads, with the text found in the file folded away)
```

- Linked from: the job page when an audio job is done ("Listen with the text"), the document page's step 3 when an audiobook exists, and the home page's "audiobook made".
- Plays the job's audio **by chapter**: one MP3 per chapter, moving on to the next chapter by itself.
- Shows the original block text, highlights the sentence being read, scrolls with it, jumps on click; formulas, tables and figures appear with their notice.
- Keyboard: every control is a native button in the tab order; screen readers are not flooded (no announcement per sentence).

## 2. Where the data comes from (no change to app, output or core)

| Need | Source |
|---|---|
| block text, kinds, labels, sections, pages | `<work>/document.json` (D-165, written by the audio job for exactly this) through `core.export.from_data(Document, …)` |
| which chapters, voice, settings, file names, duration, chunk counts | `<work>/audio.json` (D-165) |
| when each sentence is spoken and which span it reads | `<Book>.readalong.json` in the output folder, read with `output.read_readalong` (refuses any version but 1) |
| where the output folder is | **new, web-owned**: `<work>/audiobook.json` = `{"format": "sci2audio-web-audiobook", "version": 1, "folder": "<absolute path>"}`, written by the web's audio task after the job succeeds (question 2) |
| chapter block ranges | `app.chapters.find_chapters(document)`, the app's own chapter rule (Q6) |
| printed page of a block | `app.report.Pages` (page label as printed, D-74) |
| placeholder notices | the two built-in notice steps (`FormulaNoticeStep`, `TableFigureNoticeStep`) run on the stored document, when their category was on in the audio's settings (question 6) |

**Checks before showing anything** (a wrong highlight is worse than none): the read-along file exists (it is written last, so the audio is complete, D-119), its duration equals `audio.json`'s, its chunk count equals `chunks.total − chunks.skipped`, every span lies inside its block (`Document.check_span`), and every audio file it names exists. If any check fails, the page says which in plain words ("The audiobook files are no longer in /…/sci2audio. Make the audiobook again.", or "The files in that folder now belong to another audiobook.") and links back to the document page.

### 2a. Path checks (condition on D-295)

- `audiobook.json` holds `{"format": "sci2audio-web-audiobook", "version": 1, "document": "<id>", "folder": "<absolute path>"}`; a record of another format or version, another document id, or a folder that is not absolute is ignored (the fallback folders are tried).
- The document id must equal the first 16 hex digits of `audio.json`'s `source.sha256` (the id rule of D-198), else the page refuses.
- Every file name (from `audio.json`'s `files`) must be a bare name: no separator, not `.` or `..`, no drive, no NUL; the file is opened only as `<folder>/<name>`, its resolved parent must be the resolved folder, and it must be a regular file.
- The candidate folders are only: the recorded folder, the saved output folder, the server's default output folder. A request names a file, never a folder.
- The read-along file found there must pass the checks of §2 (duration, chunk count) before any of its files is served or shown.

## 3. Server additions (web layer only)

| Route | Does |
|---|---|
| `GET /documents/{id}/listen` | the page; 404 page for an unknown document; a "no audiobook yet" page state with a link to step 3 |
| `GET /api/v1/documents/{id}/audiobook/{name}` | one file of the document's latest audiobook, **only** a name listed in `audio.json`'s `files` (M4B, MP3s, read-along), from the recorded folder; Range requests (206) for seeking; `?download=true` as on the other file routes; 404 for any other name, `..`, or a missing file |

`web/tasks.py`: `audio_work` writes `audiobook.json` (atomic, through `app.files.write_texts`) after `run_audio` returns. A failure to write it does not fail the finished job (the audiobook is complete); the player then falls back to the saved output folder and the default one, each tried with the checks of §2.

## 4. The page in detail

- **Text**: the blocks of the chapters that are in the audiobook, in reading order, under one `<h2>` per chapter (title as printed). Heading blocks become `<h3>`–`<h6>` by section level, so a screen reader can move by headings. **Furniture is left out** (running heads, page numbers, stamps: read as noise between sentences); instead a small **"Page 39"** marker (printed label, else the PDF page number) stands where a new page starts, so every sentence stays referenceable. Text the voice does not read (a removed citation inside a sentence, a removed reference list block) is shown as printed; a block with nothing read gets a muted style and "not read" in words, not colour alone. The text region carries `lang` from the document (D-50).
- **Sentence elements**: each read-along chunk with a non-empty span is one `<span>` around exactly its characters; chunks with an empty span (the later parts of a long replacement, a figure without text) attach to the element before them in the block, or to the block. Chapters not chosen are named in one line ("Not in this audiobook: References").
- **Placeholders**: a notice box with the sentence the audiobook says ("Formula 3 is skipped.") and, folded in a `<details>`, the text extraction found, if any. The box is the element highlighted while the notice is read.
- **Audio**: MP3 per chapter when the job wrote them (every browser plays MP3); if only an M4B exists and the browser can play AAC (`canPlayType`), the M4B with chapter offsets; else the page says the browser can't play it and offers the download. Time inside a chapter's MP3 = `chunk.start − chapter.start` (docs/readalong-format.md).
- **Highlight**: while playing, a `requestAnimationFrame` loop finds the chunk by binary search over the chunk starts and sets `aria-current="true"` plus a class on its element; between sentences the last one stays highlighted. Background colour plus an underline, AA contrast in light and dark. No live region follows the reading.
- **Scrolling**: when the highlighted sentence leaves the visible area, the page scrolls it into view (smooth unless `prefers-reduced-motion`), never moving the focus. When the person scrolls by hand (wheel, touch, keys), following stops and a **[Back to the reading]** button appears; it, a click on a sentence or a jump turns following on again. A checkbox "Scroll with the reading" switches it off for good.
- **Jumps**: a click on a sentence plays from its start (screen readers' Enter on a sentence does the same, as NVDA and JAWS activate clickable text). Buttons: Play/Pause, previous/next sentence, previous/next chapter, and the chapter list (one button per chapter). When paused, a sentence jump moves the position and the highlight without starting playback. The native `<audio controls>` element stays for seeking and volume.
- **Announcements**: the polite status region speaks only after an action the person took ("Chapter 2: Methods", a load error), never per sentence.
- **Player bar**: sticky at the top, with `scroll-padding-top` so nothing focused hides under it (WCAG 2.2, 2.4.11).
- **AI notice**: "This audiobook is read by a synthetic voice (<voice>), made with sci2audio.", as the KB's legal notes say the player shows (AI Act Art. 50 marking beside the file metadata).
- Every new string goes into `web/strings/en.toml` (D-256), so #79 only adds `de.toml` keys.

## 5. Modules

| File | Holds | Size |
|---|---|---|
| `web/player.py` (new) | pure view model: load and check the three files, chapter ranges, blocks to elements with chunk indices, page markers, notices; `PlayerError` with the reason a person reads | ~280 |
| `web/pages.py` | the `/documents/{id}/listen` route; links on the job, document and home pages | ~60 |
| `web/api.py`, `web/tasks.py`, `web/documents.py` | the audiobook file route; `audiobook.json` written after the audio job; `StoredDocument.audiobook_folder` | ~90 |
| `web/templates/listen.html` (+ small edits to `job.html`, `document.html`, `index.html`) | the page | ~120 |
| `web/static/player.js` (new, loaded only on this page) | playback, chapter switching, highlight, follow/scroll, jumps, status | ~350 |
| `web/static/app.css` | player bar, highlight, notice, page markers, light/dark | ~60 |
| `web/strings/en.toml` | `listen.*` and the script's strings | ~45 |

No change to app, output, core, textprep, the KB or any golden file; no new dependency. So not critical.

## 6. Tests

- **Unit (fast, three systems)**: `player.py` on a hand-built Document + read-along: each chunk becomes one element around exactly its characters; empty spans attach as described; furniture left out, page markers at page changes with printed labels; placeholders get the step's notice, and the printed text when their category was off; chapters not chosen listed; every check of §2 refuses with its message (missing read-along, missing MP3, duration differs, count differs, span outside its block, read-along version 2, broken `document.json`). Hypothesis: for any document and any non-overlapping spans, the rendered text, with the markup removed, equals the blocks' text (nothing lost or doubled) and every chunk has exactly one target element.
- **TestClient (fast)**: the page renders after a real audio job with the fake voice and real ffmpeg (a few seconds, allowed in the fast tier); escapes `<script>` in block text and names; 404 for an unknown document; "no audiobook yet" state; the audiobook route serves each listed name (200, `audio/mpeg`), answers Range with 206, 404s any other name, `..`, a name of another document, a removed file; `audiobook.json` written after a done job, not after a failed or cancelled one; disk full while writing it leaves the job done and the player using the fallback folder; the string-table test covers the new keys.
- **Browser (`tests/browser/test_player.py`, `browser` marker)**: after an audio job made through the API with the fake voice: play → the first sentence is highlighted, the highlight moves to the next sentence as time passes and to the next chapter's MP3 when one ends; click a sentence in chapter 2 → audio switches to chapter 2's MP3 at that sentence's time and it is highlighted; next/previous sentence and chapter buttons; paused jumps don't start playback; following stops on a manual scroll and "Back to the reading" restores it; a placeholder notice is highlighted while it is read. Keyboard-only run of the same (Tab order, visible focus ring on every stop, focus never lost on a chapter change). **axe** in light and dark on: ready, playing, no audiobook yet, files missing. The status region gets no text while playing on its own (the "no flood" criterion, checked over 30 s with Playwright's clock where possible, else over a real 5 s).
- Before the PR: the CLAUDE.md check list, `pytest -m browser`, the nightly Hypothesis profile on the web tests, the layer check, deptry.

Rough size: ~1,000 lines of code, template, script and styles; ~900 lines of tests.

## 7. Out of scope (follow-up issues if wanted)

- Read-along on PDF page images (after v1.0, D-102).
- Playback speed in the player (Chromium's native control has one; a speed menu for all browsers is small but not asked for).
- Remembering the listening position across server runs (the port changes each run, so browser storage forgets it; it needs a server-side record).
- A player for audiobooks made with the command line into another working folder.

## 8. Design questions and decisions

**Decided** by the coordinator, 13 Nov 2026 08:02 UTC, under D-80: all ten as recommended. D-numbers: 1 = **D-294**, 2 = **D-295**, 3 = **D-296**, 4 = **D-297**, 5 = **D-298**, 6 = **D-299**, 7 = **D-300**, 8 = **D-301**, 9 = **D-302**, 10 = **D-303**. Condition on D-295: no path from `audiobook.json` is trusted without checks; see §2a.

1. **Where the player lives**: its own page `/documents/{id}/listen`, linked from the job result, the document page and the home list. Alternatives: a fourth section on the document page (that page already holds up to 500 rows per category, the text would double it, and a screen reader's heading list gets crowded); on the job page (jobs are forgotten when the server stops, the audiobook is not).
2. **How the server finds the audiobook files**: a small web-owned record `<work>/audiobook.json` with the output folder, written by the web's audio task after success; checks of §2 before use; fallback to the saved and the default output folder. Alternatives: add the output folder to the app's `audio.json` (changes an app record with a golden file, and D-137/`settings_data` keeps folders out of records on purpose as machine-specific); always use the saved folder (wrong as soon as another document's audiobook went elsewhere, since the folder is saved per start, D-246).
3. **What audio plays**: the per-chapter MP3s, moving to the next chapter by itself; the M4B only when no MP3s were written and the browser plays AAC. Alternative: the M4B always (one timeline and no file switch, but AAC support varies: open-source Chromium builds and Firefox on Linux depend on the codecs they were built or installed with, while MP3 plays everywhere; the issue also asks for playback by chapter).
4. **What text is shown**: the chosen chapters' blocks in reading order, furniture left out, printed page markers where pages change, unread text shown as printed, chapters not chosen named in one line. Alternatives: the whole document including unchosen chapters (long, with nothing to play); furniture shown muted (page numbers and running heads between sentences, read by screen readers as noise).
5. **How sentences are reached**: sentences are clickable but not tab stops; keyboard and screen-reader users jump with the player's buttons (sentence, chapter), the chapter list and the native seek bar; a screen reader's Enter on a sentence plays from it. Alternatives: a roving tab stop over sentences (needs a composite role such as listbox, which hides the text's headings and structure from screen readers); every sentence a link or button (thousands of tab stops); global single-key shortcuts (clash with screen readers' single-key navigation).
6. **Placeholder notices**: run the two built-in notice steps on the stored document to get the sentence the audiobook said, when their category was on; the printed text found in the file folded in a `<details>`. Alternatives: a generic notice from the strings table (could differ from what was said); a `said` field per chunk in the read-along file (changes output's file and its golden file, so critical, and duplicates the script).
7. **Highlight and announcements**: `aria-current` plus a colour-and-underline class on the sentence element, updated per animation frame while playing; the status region speaks only after the person's own actions. Alternative: announce each sentence (floods a screen reader; the voice is already reading it).
8. **Scrolling**: follow the reading, stop following when the person scrolls by hand with a [Back to the reading] button, and a checkbox to switch following off. Alternative: always follow (fights a person who scrolls back to look at a table).
9. **The script**: a second static file `player.js`, loaded only by the listen page (D-101 named the player "the one page with real JavaScript"). Alternative: all in `app.js` (every page would load the player code).
10. **AI notice on the player**: a line naming the synthetic voice above the player, as the KB's legal notes say the player shows. Alternative: none (the notes would then be wrong about v1.0).

## 9. Sequencing

One PR (lane web). I start now on the parts no answer changes (player view model, the page, the audiobook route, tests), and adjust if the coordinator decides a question differently. I merge main when the browser-CI fix from the #77 thread lands, and again when #79 changes the strings table.
