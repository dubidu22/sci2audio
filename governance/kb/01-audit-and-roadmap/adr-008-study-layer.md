# ADR-008: The Study layer, first version (v1.5)

`[ADR]` · Status: **Decided**. The scope is Colin's (20 Nov 2026, 19:04 UTC, D-850); the three points he left to this ADR, and where the code lives, are decided by the coordinator (D-854, under D-80 and D-702a) · Decider: Colin (scope), coordinator (the rest) · Closes: Issue #395 · Related: `decision-log.md` D-57, D-663, D-665, D-723; `plans/study-layer-scope-options.md` and `plans/docs-b-d1-plan.md` (both on branch `governance`); "The Working Reader" (dubidu22/sci2audio-design b4a7523, `DESIGN.md`, `IMPLEMENTATION-PROMPT.md`)

---

## 1. Context

- "The Working Reader" (adopted by D-663) draws a study layer: while listening, the user captures at the sentence being read (N note, Q quote, C card, M mark), sees each capture as a flag at the sheet edge and on the timeline, reviews cards on a Captures page, and sends captures to Zotero, Obsidian and Anki. D-663 left the study layer to its own ADR; Issue #395 asks for it before the first code issue.
- v1.3 already has one capture: the **marker** with an optional note (#474, D-722, D-723), set with M, kept in `<work folder>/markers.json` (format `sci2audio-web-markers`, version 1), anchored to the document's text, removed at once with Undo from the toast only.
- Hard rules that bound the choice: no network calls except downloads the user started and the opt-in update check, so a call to Zotero's local API or AnkiConnect on 127.0.0.1 counts as a network call (D-665); faithful text: a quote is the printed text, nothing is rewritten or summarised (D-57); the web interface binds to 127.0.0.1 only.
- `sci2audio.core` holds shared data objects only, and the pipeline stages import only `core` (D-46).

## 2. Decision

### 2.1 Colin's scope (D-850)

Answered on 20 Nov 2026 at 20:04 CET (19:04 UTC) on three question cards in the assist thread "Study layer scope options"; his chosen option labels, verbatim:

1. "Study layer v1.5: which capture types ship first, and is card review in v1.5?" → **"Mark, note, quote only"**
2. "The capture record: how is it anchored, stored and removed?" → **"As the marker today (Recommended)"**
3. "Which export files come first? Local program connections (Zotero API, AnkiConnect) wait for v2 in every case (D-665)." → **"Markdown, CSV and RIS/BibTeX"**

What follows from them:

1. **Capture types: mark (M), note (N), quote (Q).** The card type, the C key and card review move to v2.
2. **The capture record**, one shape for all three types:
   - `id`, `type` (`mark`, `note` or `quote`), `created`, `changed`;
   - `anchor`: `block` (block index), `start` and `end` (character offsets in that block's text), and `text`, the printed sentence verbatim, never its spoken form (D-57);
   - `text`: the note's text; empty for a mark and a quote.
3. **No time is stored.** The time in an audiobook changes with every new audiobook of the document, while the text does not; so the Listen page computes the time from the anchor on each load, as it does for markers. A capture whose sentence the current audiobook does not read is listed as "Not read in this audiobook", and one whose anchor is not found as "Not found"; neither is dropped. The stored anchor is never rewritten.
4. **Storage: one `captures.json` per document, in its work folder** (format `sci2audio-captures`, version 1). Only the interface's server writes it, with one read, one change and one atomic write per change, as `markers.json` today. The job runner, the audio job and the command line never read or write it. A file this version cannot read is never written, renamed or removed; capturing is off for that document until the user fixes or removes the file. Once written, `captures.json` stays, also when it holds no capture any more. Removing a document removes its captures with it, and the remove box counts them.
5. **v1.3 markers carry over (#475).** A marker without a note becomes a mark; a marker with a note becomes a note whose text is the marker's note. Anchor, `created` and `changed` stay as they are. The carry-over runs only when a document has `markers.json` and no `captures.json`: its markers are read and `captures.json` is written from them, with `migrated_from: markers.json` in the file. `markers.json` is the user's own file from v1.3, not something the user removed: it stays untouched beside `captures.json`, and sci2audio does not read it while `captures.json` exists. So removing `captures.json` by hand brings the v1.3 markers back as they were in `markers.json`, on purpose; this is the recovery path for a broken or unwanted `captures.json`, and it also brings back markers removed after the carry-over. An unreadable `markers.json` is left untouched and reported, and capturing stays off for that document, because writing `captures.json` would hide its markers for good.
6. **Removal is at once, with Undo from the toast only** (D-723 ruling 1): the capture leaves the file immediately and the server keeps it in memory for the toast's Undo. The record has no `removed` field and the Captures page shows no struck-through rows.
7. **Exports are files**: Markdown for Obsidian, RIS for Zotero (2.2 A) and a CSV (2.2 C), each written to a folder the user chooses, never overwriting a file without asking. In every export, `document` is the document's title as the Library shows it, and `page` is the number of the PDF page on which the sentence starts; for EPUB, Markdown and text, which have no pages, `page` is empty. No export makes a network call. A user-started local connection to Zotero or Anki waits for v2 and its own ADR (D-665).

### 2.2 The points Colin left to this ADR

**A. The Zotero file is RIS, not BibTeX.**

- Each capture becomes its own `N1` line, which Zotero imports as one child note on the new item. BibTeX has one `note` or `annote` field per entry, so every capture of a paper would arrive as one note.
- RIS needs no escaping beyond line breaks (how a line break inside a note or a sentence is written, so that no line reads as a new tag, is settled in #399 with a test). BibTeX needs TeX escaping of braces, `%`, `&`, `_`, `#`, `$` and `\`, and older tools also need every non-ASCII letter escaped. Scientific quotes are full of these (statistics, Greek letters, umlauts), and an escaping slip changes the quote, which D-57 forbids.
- A BibTeX entry needs a citation key built from author and year, which the extracted text often lacks; a RIS record needs only `TY` and `ER`.
- Citavi, EndNote and Mendeley read RIS too.
- The reference holds only what the document itself states: its title, and its authors, year and DOI where extraction found them. Nothing is guessed or invented. The type is `TY  - GEN` unless extraction records an explicit type for the document. The file is UTF-8.
- The Zotero file makes a new item; attaching notes to the paper's existing Zotero item needs Zotero's local API and waits for v2.

**B. The dock shows three capture keys: Note N, Quote Q, Mark M.**

- The design's capture group (flag, word and key cap per type, in the order note, quote, card, mark) without the card, left to right, in a group labelled "Capture". There is no empty slot and no disabled C button; the group is one key narrower and the rest of the dock keeps its place.
- Each key is a button with its type's flag icon, its word and its key cap (`aria-keyshortcuts`), like today's Mark button. At 1399 px and below the words drop and the key caps stay, as `DESIGN.md` says. Highlighter colour appears only on the flag, never on the button.
- C is not bound in v1.5: it does nothing and no string names it. The keyboard-shortcuts sheet and the Focus foot list N, Q and M.
- On a sentence that already has a capture: M and Q toggle (pressed again on the same sentence they remove that mark or quote, with Undo in the toast), as M does today; N always opens the note box, on the sentence's existing note if it has one. A sentence holds at most one capture of each type; its flags stand side by side at the sheet edge, in the dock's order.

**C. The CSV ships in v1.5, as a plain table of all captures.**

- One row per capture, in reading order within each document, with a header row and the columns `document`, `type`, `page`, `sentence`, `text`. `document` and `page` are as 2.1 item 7 defines them; `sentence` is the printed sentence verbatim; `text` is the note's text and empty for marks and quotes. RFC 4180 quoting, UTF-8. No time column, for the reason in 2.1 item 3.
- It is useful at once: in a spreadsheet, as a reading log, or in Anki's own CSV import with sentence and note mapped to front and back.
- How a cell that starts with `=`, `+`, `-` or `@` is written, so that a spreadsheet does not run it as a formula while the quote stays verbatim (D-57), is settled in #399 with a test.
- In v2 the card type brings its own Anki file (front, back, tags) beside this one; this CSV's columns do not change for it.

### 2.3 Where the code lives

- `sci2audio.core` (#396): the capture dataclasses and their JSON form, as pure functions to and from a dict, with the format checks.
- `sci2audio.app`: reading and writing `captures.json`, the marker carry-over (#475) and the three export writers, behind its file-access functions.
- `sci2audio.web`: the keys, the dock, the Captures page and the export dialog; it calls `app` and writes no file itself.

This is the layer rule of D-46 applied to the study layer; #396's "reading and writing captures for a document" is met in `app`.

## 3. Why

| Need | How the decision meets it |
|---|---|
| A small first version that ships | Three types and no review page: the capture keys, the Captures page and the exports land without a fourth type's editor and a review state with its own keyboard and axe tests |
| Captures outlive a new audiobook | The text anchor is the marker's, proven in v1.3; the time is derived, so a rerun, a layout fix or a sentence-boundary change loses nothing |
| No v1.3 marker is lost | Each marker maps to a mark or a note one to one, with its anchor and times; `markers.json` is never changed |
| No capture the user removed stays on disk | Removal takes the capture out of `captures.json` at once; Undo lives in memory only. A v1.3 `markers.json` stays as the user's own file, as it was, until the document is removed (2.1 item 5) |
| No network call | Every export is a file the user places; program connections wait for their own ADR |
| Faithful text | Quotes and sentences are the printed text in every export; RIS needs no escaping; no reference field is invented |

## 4. Options considered

| Option | Why not (now) |
|---|---|
| All four types, with or without card review | Colin chose three types (D-850); cards and review are v2 issues |
| Store the audiobook time and chunk with each capture | Stale after every new audiobook and a second source of truth (D-850) |
| One captures file for all documents | A broken file would hide every capture, and captures would outlive their document (D-850) |
| Removal by cancel, struck through with Restore | Keeps removed data on disk; additive later as a `removed` field (v2 issue) |
| BibTeX for Zotero | One note per entry, TeX escaping risks the quote, needs a citation key the text often lacks |
| RIS and BibTeX both | Two writers and their tests for one target |
| A fourth, disabled card slot in the dock | A control that does nothing; the app shows no unfinished features |
| Hold the CSV until cards exist | Drops a target Colin chose, for no saving in v1.5 |
| A local connection to Zotero or Anki in v1.5 | A network call under the hard rule (D-665); needs its own ADR |

## 5. Consequences

| Issue | Change |
|---|---|
| #396 core: the capture model | Stays: the record of 2.1, data objects and JSON form in `core`; its file part (reading and writing `captures.json`) is in `app` (2.3), so the issue also carries `lane:app` |
| #475 core: carry the v1.3 markers into the capture model | Stays: 2.1 item 5; the carry-over reads and writes files, so it is in `app` (2.3) and the issue also carries `lane:app` |
| #397 web: capture while listening | Narrowed: N, Q, M; no card and no C; the dock of 2.2 B |
| #398 web: the Captures page and review | Narrowed: no card review; removal with Undo in the toast, no strike-through cancel |
| #399 app, web: export captures | Narrowed: Markdown, RIS and the CSV of 2.2 C; no Anki card file |
| #418 web: captures on the library and the shelf | Stays: counts the three types |
| New, v2 | #702 the card type, the C key and the Anki export of cards; #703 card review; #704 removal by cancel with Restore; #705 a user-started local connection to Zotero or Anki with its own ADR (risk:high) |

`docs/design/PRODUCT.md` no longer lists the study layer's scope as undecided; it points here.

**Negative:** the design's four-key vocabulary ships with three keys, so the dock and the shelf's flag strips differ from the prototype until v2; the Zotero file makes a new item rather than adding notes to the paper's existing one; a capture's audiobook time is computed on each load, never read from the file.

## 6. Revisit triggers

- The card type is planned for v2: the record gains `front` and `back` (or a typed body) in a critical core change, and the dock its fourth key.
- A local connection to Zotero or Anki is proposed: it needs its own ADR, as a user-started call under the hard rule.
- Users ask for removed captures to be kept or restored after the toast is gone.
- A capture type needs a time that cannot be computed from the text (for example a voice note).
