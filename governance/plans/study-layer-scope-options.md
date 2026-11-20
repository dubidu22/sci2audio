# Study layer: the scope choices for Colin

Written 20 Nov 2026 by an assist thread for Colin, so he can decide the first version of the Study layer (v1.5). The ADR (#395) is written only after these three choices are made; the milestone "v1.5 Study layer" (#396, #397, #398, #399, #418, #475) waits on the ADR.

Read for this: #395 and the six milestone issues; "The Working Reader" (dubidu22/sci2audio-design b4a7523: `DESIGN.md`, `IMPLEMENTATION-PROMPT.md`, `PRODUCT.md`, `prototype/app/`); `plans/working-reader-plan.md` and `plans/general-marker-plan.md`; D-57, D-663, D-665, D-723; the hard rules in `CLAUDE.md`.

What exists today (v1.3, shipped in v1.4): one capture type, the **Marker** with an optional note (#474), set with M on the sentence being read, listed in the Listen side panel, stored in `<work folder>/markers.json`, anchored to the document's text (block, offsets, printed sentence), removed at once with Undo from the toast only (D-723).

What the design shows for v1.5: four capture types with their own keys and colours (N note green, Q quote blue, C card pink, M mark orange), flags at the sheet edge and on the timeline, a Captures page ("Fundstücke") as ruled marginalia with filters and strike-through cancels, a simple card review (show the answer, Again, Got it), and a "Send to your study tools" panel for Zotero, Obsidian and Anki.

Each choice below gives the options, a recommendation and one sentence of reason. The recommendation is the coordinator's and the assist thread's view; the decision is Colin's.

## Choice 1: which capture types in the first version, and is review in v1.5?

The design's four types and what each stores:

| Type | Key | What the user adds | Saved how |
|---|---|---|---|
| Mark | M | nothing (an optional note today) | at once, no pause, sound and Undo toast |
| Quote | Q | nothing; the printed sentence is the quote | at once, no pause, sound and Undo toast |
| Note | N | free text about the sentence | pauses playback, box in the panel, ⌘/Ctrl+Enter saves, Esc cancels |
| Card | C | a front and a back | pauses playback, box in the panel |

Review in the design is a plain flip-through of the cards (front, "Show the answer", Again or Got it, "Done for now"). It has no spaced repetition; Anki does that.

Options:

- **A. All four types, review in v1.5.** The full design. Largest first version; review is one more page state with its own keyboard and axe tests.
- **B. All four types, review moves to v2.** Capture, the Captures page, filters and export land; cards are reviewed in Anki (or read on the Captures page) until v2.
- **C. Mark, note and quote only; card and review move to v2.** Smallest. The C key stays free; the dock shows three capture keys instead of four, which the design does not show.

**Recommendation: B.** Reason: the four keys, four colours and four flags are one vocabulary in the design and the marker already does one of them, while the in-app review is the one piece that Anki does better and that nothing else in v1.5 depends on.

## Choice 2: the capture model, where it is stored, undo and removal

### 2a. What a capture is (the record)

The ADR has to fix the fields of the core dataclass (#396). The marker already settled the hardest part: a capture is anchored to the **document's text**, not to an audiobook time, because times change on every new audiobook and the text does not. Proposed record, the same for all four types:

- `id`, `type` (mark, quote, note, card), `created`, `changed`
- `anchor`: block index, start and end offsets, and the printed sentence verbatim (the quote is the printed text, never the spoken form; D-57)
- `text`: the note's text; for a card `front` and `back`; empty for a mark and a quote
- the time in the audiobook is not stored; the Listen page computes it from the anchor on every load, as it does for markers (a capture whose sentence a later audiobook does not read is listed as "Not read in this audiobook", never dropped)

Options:

- **A. Text anchor only, time derived (as the marker today).** Captures survive a new audiobook, a layout fix and a sentence-boundary change.
- **B. Text anchor plus the audiobook time and chunk stored as well.** Faster to place, but stale after every rerun and a second source of truth.

**Recommendation: A.** Reason: #475 must carry the v1.3 markers over without loss, and the marker's anchor already does everything the four types need.

What a v1.3 marker becomes (#475): a marker without a note becomes a **mark**; a marker with a note becomes a **note** whose text is the marker's note. The anchor stays as it is; created and changed times stay. Alternative: every marker becomes a mark and keeps its note as an optional note on the mark; this keeps "mark" and "note" blurred, which the design does not do.

### 2b. Where captures are stored

- **A. One file per document in its work folder, `captures.json`, replacing `markers.json`** (read once by #475 and rewritten in the new format; the old file is kept untouched beside it until the user removes the document). Removing a document removes its captures with it, as today, with the extra warning line of #474.
- **B. One file for all documents** in the settings folder. The Captures page needs no scan of the work folders, but a document's captures outlive its removal and one broken file hides every capture.

**Recommendation: A.** Reason: #396 and #395 already say "per document work folder", the marker file works this way, and a broken file then costs one document, not all.

### 2c. Undo and removal

- **A. Removal takes the capture out of the file at once; Undo from the toast only (60 s or until the next capture action), as the marker does today (D-723 ruling 1).** The file never holds anything the user removed. The Captures page shows no struck-through rows.
- **B. Removal by cancel, as the design draws it:** the capture stays in the file with a `removed` time, is shown struck through in pencil with a dashed rule and a Restore action on the Captures page, and leaves the file only when the user empties the removed captures (or after 30 days). Undo from the toast as well.

**Recommendation: A.** Reason: it is built, tested and proven on the marker, the file never carries data the user asked to remove, and the design's strike-through can be added later without changing the record (a `removed` field is additive).

If Colin prefers B, #398's acceptance criterion "removing a capture cancels it in place with restore" stays as written; with A it is reworded to "removing a capture offers Undo in the toast".

## Choice 3: export, files first

The hard rule: no network calls. Zotero's local API and AnkiConnect listen on 127.0.0.1, and a call to them is a network call (D-665), so any program connection is a later, user-started option, decided in its own ADR, and not part of v1.5.

What each file format gives:

| Target | File | What arrives there | What is lost against the design |
|---|---|---|---|
| Obsidian | Markdown, one file per paper, into a folder the user picks | all four types, grouped by chapter, with page and quote; readable anywhere, not only in Obsidian | nothing |
| Anki | CSV (front, back, tags) or `.apkg` | the cards, imported as a deck with Anki's own importer | `.apkg` needs Anki's SQLite format and probably a dependency; CSV needs the user to pick the import once |
| Zotero | RIS or BibTeX, quotes as notes | a new item with the paper's reference and the quotes | the design's "notes on the paper's existing item, matched by DOI or title" is only possible through the local API; the paper's DOI and authors are often not in the extracted text, so the reference can be thin |

Options:

- **A. Markdown only.** One export, covers Obsidian and anything else that reads Markdown; cards and quotes are in it too.
- **B. Markdown for Obsidian and CSV for Anki.** Two writers, both plain text, both imported natively by their program without loss.
- **C. Markdown, CSV and RIS or BibTeX for Zotero.** All three targets as files; the Zotero file creates a new item rather than attaching to the existing one.
- **D. Files plus a user-started local connection.** Not in v1.5: a network call under the hard rule, needs its own ADR.

**Recommendation: B.** Reason: Markdown and CSV carry everything the four types hold with no loss and no new dependency, while a Zotero file cannot do what the design promises (attach to the paper's existing item) and would arrive thin, so Zotero waits for the connection decision in v2.

Every export writes to a folder the user chooses and never overwrites a file without asking (#399).

## Which issues stay in v1.5 and which move, under the recommended scope (1B, 2A/2A/2A, 3B)

Stay in v1.5:

- #395 the ADR (written by the coordinator after Colin's answers)
- #396 the capture model (core, critical)
- #475 carry the v1.3 markers into the capture model (core, critical; mark or note as above)
- #397 capture while listening (N, Q, C, M, flags, sounds)
- #398 the Captures page, narrowed: marginalia, filters, Undo from the toast; **card review and the strike-through cancel come out**
- #399 export, narrowed to Markdown and Anki CSV
- #418 the Library's captures column and the shelf's flag strips (small, and it is the part of the design the library already has a slot for)

Move to v2 (new issues the coordinator files; nothing is deleted):

- card review on the Captures page (from #398)
- removal by cancel with Restore on the Captures page (from #398), if Colin chooses 2c A
- Zotero export as RIS or BibTeX (from #399)
- a user-started local connection to Zotero or Anki, with its own ADR (D-665)

If Colin chooses 1C instead, #397 and #398 also drop the card type and the C key, and the Anki CSV in #399 moves to v2 with the card.

## The three questions, as asked in chat

1. Capture types and review: A all four with review, B all four without review (recommended), C mark, note and quote only.
2. The model: text anchor only (recommended) or anchor plus stored time; per-document file (recommended) or one file; removal with toast Undo only (recommended) or cancel-in-place with Restore.
3. Export first: A Markdown only, B Markdown and Anki CSV (recommended), C also RIS or BibTeX for Zotero. Local connections wait for v2 in every case.

## Colin's decisions

(appended when Colin has answered)
