# Working Reader batch B: library, shelf and the quiet pages (#389, #390)

Web lane. Non-critical: no layer contract, core dataclass, KB, golden-file or licence change. Branches start from main e517873, which has batch A (#409) merged.

**Binding:**
- DESIGN.md and `prototype/app/` at sci2audio-design b4a7523
- D-45: server-rendered, plain JS, nothing from the internet
- D-414: layout and the interface never move text
- D-664: "Continue listening" on the shelf, no player bar outside Listen and Focus
- Batch A's tokens, sprite, rail, cookies, CSP rules and `[hidden]` rule
- German in the "Sie" form (D-292); wording otherwise follows `prototype/app/i18n.js`

**Two PRs, stacked.** PR B1 is #389. PR B2 is #390, opened with B1's branch as its base so its diff shows only #390. Once B1 is squash-merged, I merge main into B2 (a merge, never a force-push) and retarget B2 to main. They share `app.css` and the string tables, and the library rows host the removal disclosure that #390 restyles. Kept separate, each still reviews on its own.

## PR B1 (#389): the library as a table, and the reading shelf

### What the library shows

| Part | Source | Notes |
|---|---|---|
| View title "Library" and "{n} documents on this computer" | the store | plural forms as in D-290 |
| Voice notice (first run, or a pack missing) | `missing_files`, the per-pack check of today | One wait-washed notice with an alert icon, a title, a body naming the download size of the English pack (from `download_plan`), and an ink "Set up the voice" link to `/voice`. Partly installed: the same notice with today's "partly" wording. |
| Opener card | today's two forms | **Open a document:** a dashed slot icon, a title, the hint (types, size limit) and a real `<input type=file>` styled through `::file-selector-button`, beside the primary "Open and analyse". **Or paste text:** a `<details>` disclosure on the right holding today's paste form. Behaviour, ids and the JS flow stay as they are. Drag and drop is left out, and the hint does not promise it. |
| Table `<table class="papers">` | per document | Columns: thumbnail (aria-hidden), Document, State, Listened, Opened. Captures waits for the study layer. A real table, so screen readers get the column headers. |
| Document cell | `about.json` (new) | The title links to Listen when there is an audiobook, else to the document page. Meta line: authors, then "N pages" for PDFs, then the audiobook's length from `audio.json`, joined by " · ". The removal disclosure sits below the meta line (restyled in B2). Before the first analysis the title is the file name and the meta line is empty. |
| State chip | computed | Every chip has an icon and a word, and none uses a highlighter colour. **Making audio** or **Analysing**: an ink-outline pill, when the running job works on this document. **Stopped**: error wash, when this server's latest job on the document failed. **Ready**: a hairline outline with a check, when there is an audiobook. **Checked, no audio yet**: idle, when a report exists. **Not analysed yet**: idle otherwise. |
| Listened | `position.json` and `audio.json` | With an audiobook: a `<progress class="meter listened">` (yellow) and "38 % listened", or "Not started". While making: an ink meter and "64 % made" from the job (the poll of batch A updates the shelf; the table is drawn at load). Otherwise "—", with a visually hidden "no audiobook yet". |
| Opened | `opened.json` (new) | "Today, 09:14", "Yesterday", "Mon 12 Nov", with the year added when it is not this year. Local time of this computer. German: "Heute, 09:14", "Gestern", "Mo., 12. Nov.". Empty when there is no record. |
| Command-line audiobooks (#154) | `state.config.outside` | Rows in the same table, state chip "From the command line" (ready style), the title linking to their Listen page, the folder in the meta line, no removal. |
| Empty library | no documents and no outside rows | The design's empty panel: "Your library is empty" with its body, and the "As printed / As sci2audio reads it" specimen in Literata, in English or German by interface language. The specimen is the design repository's own synthetic sentence, not third-party text. |

The search field of the prototype is out of scope; it gets a follow-up issue.

### Two small records in the document's work folder

Both are written by `web/` only. Reading one never fails a page: a missing, oversized, symlinked or malformed file, or any OSError, reads as nothing.

- **`opened.json`**: `{"format": "sci2audio-web-opened", "version": 1, "opened": "<UTC ISO time>"}`. The document page and the Listen page write it on GET, atomically, through the existing `write_texts`. A failed write is logged and ignored, and the page still answers 200.
- **`about.json`**: `{"format": "sci2audio-web-about", "version": 1, "title", "authors", "pages"}`. The web script task writes it after a successful analysis, from `ScriptJob.result.document`: `document_title()` from `app.chapters`, `content.metadata.authors`, and the page count for PDFs only. A failed write never fails the job.

### Listened fraction

`player.listened(work, document_id)` gives the fraction or None. It is a light reading of `position.json`: the same format, version, document and audiobook-stamp checks as `read_position`, plus `0 <= time <= duration` from `audio.json`, but without parsing the read-along file. The stamp uses the existing cached `_stamp`. The library and the shelf share this helper.

### The shelf (rail, every page)

`_page` builds a `shelf` list in place of batch A's single `running` item, with at most five items:

1. **Continue listening (D-664):** the document whose `position.json` is newest and still valid. It shows the title, "Continue from 3:12" and the yellow listened meter, and links to `/documents/{id}/listen#continue`. On Listen, `player.js` sees `#continue` and applies the existing resume offer: it moves to the position and focuses the sentence, but never plays (#153, D-300). Without a valid position there is no item.
2. **The running job:** batch A's item, unchanged (`#shelf-job`, white meter, one stream per job, polling elsewhere).
3. **Up to three recent documents** by `opened.json`, not already shown: the title, then either "38 % listened" with a yellow meter or the state word.

Titles are clamped to two lines. The heading "Reading and recent" shows only when there are items. The item for the page in view gets `aria-current="page"` (its document page or Listen). Captures' flag strips wait for the study layer.

### Strings

New keys in `strings/en.toml` and `strings/de.toml`, with the same keys in both:
- `library.*`: title, sub, opener, columns, chips, listened, made, not started, dates, empty, specimen, notice
- `shelf.*`: continue, listened

Keys that are no longer used are removed, and the key-parity tests stay.

### Tests

**Unit (TestClient):**
- Every chip state, each with an icon and a word.
- Command-line rows.
- The empty panel, and the voice notice: missing, partly missing, and absent when installed.
- `opened.json`: written on the document and Listen GETs; a broken, huge, symlinked or unwritable record still gives 200 with an empty cell (fault injection: OSError on write, a read-only folder, the file removed).
- `about.json`: written by a script job; a broken one falls back to the file name.
- `listened`: a valid record, a stamp mismatch, the wrong document, the time past the duration, and no `audio.json`.
- Date formatting in English and German, today, yesterday, this year and an earlier year, at pinned literal times.
- The shelf: order, cap, aria-current, `#continue` link, no heading when empty.
- Batch A's no-internet, token and highlighter checks keep running over the new templates.

**Browser (Chromium; Firefox and WebKit nightly):**
- The library by keyboard: open and paste still work.
- axe in light, dark and German, at 1440 and 1280 px.
- Reflow at 320 px with a full table: the table scrolls inside its own region and the page does not scroll sideways.
- Reduced motion.
- Highlighter rule on chips.
- The shelf's Continue listening item opens Listen at the saved time, paused (audio `paused`, `currentTime` within one sentence of the position).
- `test_screens` adds `library-empty`, 14 states in all.

### Size

About 600 to 800 lines with tests: `index.html`, `base.html` shelf, `pages.py`, `player.py` (+40), `tasks.py` (+15), `app.css` (+150), `player.js` (+10), and the strings.

## PR B2 (#390): Voices, Privacy, not found and the removal disclosure

Behaviour stays as it is; this is a restyle with the same ids, forms and API calls.

- **Voices:**
  - View title and sub line.
  - One `.pack` panel per language (English, German). Each has a header with the voices icon, the pack name and a chip, "Installed" (ready) or "Not installed" (idle, download icon), and a ruled files table (file, size, licence), grouped by `DownloadFile.pack`.
  - The foot shows the hosts line, then the consent checkbox and the primary "Download (355 MB)" with today's form, digest and job page.
  - The voice cards with previews in the prototype are out of scope (no behaviour change; preview stays on the document page).
- **Privacy:** a prose page, 15.5px/1.6 at 68ch, on a paper panel, with headings and the same statements. The existing privacy code-checks stay untouched.
- **Not found (`missing.html`):** the view title, the reason, and a "Back to the library" link inside a panel with an alert icon.
- **Removal (`_remove.html`):** still a disclosure (D-359 to D-362).
  - The summary becomes a small quiet button with a trash icon.
  - The body becomes a ruled box saying what goes and what stays, with a danger-style "Remove …" button.
  - The busy note uses the wait wash.
  - The same markup serves the library row and the document page.
- **Strings:** `setup.*`, `privacy.*`, `remove.*` and `common.not_found_*` keep their keys where the meaning holds. New keys only for pack headers and chips.
- **Tests:**
  - Existing voice, privacy, not-found and removal tests stay as they are.
  - Unit: the packs are grouped by language, and each file shows once with its licence.
  - Browser: axe in light, dark and German, the removal by keyboard on the library and on the document page, and reflow.
  - `test_screens` adds `voices-installed-de` if a German-pack state is cheap to set up; otherwise the existing states cover it.

## Out of scope, with follow-up issues

- Library search.
- Drag and drop onto the opener.
- The Captures column, and flag strips on shelf items and rows (study layer, #395 to #399).
- The voice cards with previews on Voices.
- The keyboard shortcuts rail item (#394).
