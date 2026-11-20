# docs-b-d1: the Study-layer ADR, and two docs leftovers

Thread docs-b-d1, docs lane, batch B-D1 (D-853). Written 20 Nov 2026.
Read: `rules/implementation.yaml`, `CLAUDE.md`, Issues #395 to #399, #418, #475, #678, #686; `plans/study-layer-scope-options.md` ("Colin's decisions"); D-850 in `kb/pending-decisions.md`; D-57, D-663, D-665, D-723 in `kb/decision-log.md`; ADR-007 as the format; "The Working Reader" at b4a7523 (`DESIGN.md`, `IMPLEMENTATION-PROMPT.md`, `prototype/app/app.js`); `src/sci2audio/web/markers.py` (the v1.3 marker); `plans/audit-batch-2026-11-20.md` (F3).

## 1. Two PRs

| PR | Closes | Critical | Labels | Files |
|---|---|---|---|---|
| 1 `docs: ADR for the Study layer (#395)` | #395 | yes (KB architecture document, CRIT-01, D-703c; `adr-` prefix since #691) | `lane:docs`, `risk:high` | new `governance/kb/01-audit-and-roadmap/adr-008-study-layer.md`; `governance/kb/00-index/README.md` (the folder row and the file list name ADR-008); `docs/design/PRODUCT.md` lines 55 and 78 (the study layer is no longer "undecided": one line each pointing at ADR-008) |
| 2 `docs: PRODUCT.md wording and the missing CHANGELOG lines (#678)` | #678, #686 | no | `lane:docs`, `risk:low` | `docs/design/PRODUCT.md` line 40; `docs/design/prototype/app.js` line 578 (see 4.1); `CHANGELOG.md` Unreleased > Fixed |

ADRs live in `governance/kb/01-audit-and-roadmap/` (ADR-001 to 005 and 007; 006 is in `03-monetization-and-economics/`), so the next number is **ADR-008**. Both PRs branch from current `main`; no code, so no new tests. Before each PR: `uv run ruff check` and the fast suite once (`-k "not espeak"`). PR 1 and PR 2 both touch `PRODUCT.md`, in different hunks (40 vs 55/78); whichever merges second merges `main` in only if git reports a conflict (INV-08). The plan promises no test, so neither PR body carries `## Tests promised in the plan`.

## 2. PR 1: ADR-008, the Study layer for v1.5

Format as ADR-007: status line (Decided: Colin for the scope, 20 Nov 2026 19:04 UTC, quoted; the three open points Decided (Claude) under D-80/D-702a once the coordinator approves), Context, Decision, Why, Options considered, Consequences (issue table), Revisit triggers.

### 2.1 Recorded as Colin decided (D-850), not re-argued

1. **Capture types in v1.5: mark (M), note (N), quote (Q).** The card type, the C key and card review move to v2.
2. **The record, as the v1.3 marker:** `id`, `type` (`mark` | `note` | `quote`), `created`, `changed`, `anchor` (`block`, `start`, `end`, `text` = the printed sentence verbatim, never the spoken form, D-57), `text` (the note's text; empty for a mark and a quote). The audiobook time is never stored: the Listen page computes it from the anchor on each load; a capture whose sentence the audiobook does not read is listed "Not read in this audiobook", one whose anchor is not found "Not found", never dropped. The stored anchor is never rewritten.
3. **Storage:** one `captures.json` per document in its work folder (format `sci2audio-captures`, version 1), written only by the server, one atomic write per change, as `markers.json` today. A file this version cannot read is never written, renamed or removed; capturing is off for that document until the user fixes or removes it. Removing a document removes its captures; the remove box counts them (as #474).
4. **v1.3 markers (#475):** a marker without a note becomes a mark, with a note a note whose text is the marker's note; anchor, `created` and `changed` stay as they are. When a document has `markers.json` and no `captures.json`, its markers are read once and `captures.json` is written from them; `markers.json` is left untouched beside it and never read again. An unreadable `markers.json` is left untouched and reported, and capturing stays off for that document (otherwise its markers would be hidden for good).
5. **Removal:** at once, out of the file, with Undo from the toast only (D-723 ruling 1, the marker's in-memory undo); no `removed` field, no struck-through rows. A later cancel-with-Restore adds a field and changes nothing else (v2).
6. **Exports are files**, written to a folder the user chooses, never overwriting a file without asking (#399): Markdown for Obsidian, one Zotero file (2.2 A), CSV (2.2 C). No network call. A user-started local connection to Zotero or Anki on 127.0.0.1 is a network call under the hard rule (D-665) and waits for v2 and its own ADR.

### 2.2 The three points D-850 leaves to the ADR, with my recommendation

**A. RIS or BibTeX for Zotero → RIS.**
- RIS is one tag per line; each quote and note becomes its own `N1` line, which Zotero imports as one child note per line on the new item. BibTeX has one `note`/`annote` field per entry, so all captures would arrive as one note.
- RIS needs no escaping beyond line breaks. BibTeX needs TeX escaping of braces, `%`, `&`, `_`, `#`, `$`, `\` and, for older tools, every non-ASCII letter: scientific quotes are full of these (statistics, Greek letters, umlauts), and an escaping slip corrupts the quote, which D-57 forbids.
- A BibTeX entry needs a citation key built from author and year, which the extracted text often lacks; RIS needs only `TY` and `ER`.
- RIS is also read by Citavi, EndNote and Mendeley, which German-speaking students use.
- Rule for the reference: only what the document itself states (title, and authors, year, DOI where extraction found them); nothing is guessed or invented. `TY  - GEN` unless the document says otherwise. UTF-8.
- Rejected: BibTeX (reasons above; a LaTeX user can export a .bib from Zotero after import). Both: twice the writers and tests for one target.

**B. The dock with three capture keys.**
- The design's dock group (flag + label + key cap per type, in the order note, quote, card, mark) without the card: **Note N, Quote Q, Mark M**, left to right, in a group labelled "Capture". No empty slot, no disabled C button; the group is one key narrower and the dock's other parts keep their places.
- Each key is a button with its type's flag icon, its word and its key cap (`aria-keyshortcuts`), as today's Mark button. At 1399 px and below the labels drop and the key caps stay, as DESIGN.md says. Highlighter colour only on the flag, never on the button.
- C is not bound in v1.5: it does nothing and no string mentions it. The keyboard-shortcuts sheet and the Focus foot list N, Q and M.
- Keys on a sentence that already holds a capture: M and Q toggle (pressed again on the same sentence, they remove that mark or quote, with Undo in the toast), as M does today; N always opens the note box, on the sentence's existing note if it has one. A sentence may hold one capture of each type; its flags stand side by side at the sheet edge in the dock's order.
- Rejected: keeping a fourth slot for the card ("coming later"): it is a control that does nothing, and the app shows no unfinished features.

**C. The CSV → ships in v1.5 as a plain table of all captures.**
- Columns, one row per capture, in reading order per document: `document`, `type`, `page`, `sentence`, `text`. `sentence` is the printed sentence verbatim; `text` is the note's text, empty for marks and quotes. RFC 4180 quoting, UTF-8, a header row. The audiobook time is not exported, because it changes with every audiobook.
- Why now: Colin chose "Markdown, CSV and RIS/BibTeX"; a plain table is useful at once (a spreadsheet, a reading log, Anki's own CSV import with sentence and note mapped to front and back), and it shares the folder choice and no-overwrite code with the other two writers, so it costs one small writer and its tests.
- In v2 the card type brings its own Anki file (front, back, tags) beside this one; this CSV's columns do not change for it.
- Left to #399, with a test: how a cell that starts with `=`, `+`, `-` or `@` is written so a spreadsheet does not run it as a formula without changing the quoted text (D-57).
- Rejected: waiting for cards: it drops a target Colin chose, for no saving in v1.5.

### 2.3 One more point the record needs: where the code lives

`sci2audio.core` holds only data objects (D-46), so #396 puts there the dataclasses and their JSON form (pure to-dict and from-dict with the format checks); reading and writing `captures.json` and the export writers live in `app`, behind its file-access functions, and `web` calls them. The job runner, the audio job and the command line never read or write `captures.json`, as for markers. This is the layering rule applied, not a new choice; #396's second criterion ("reading and writing captures for a document") is met in `app`.

### 2.4 Consequences table in the ADR

#396 stays (the record above). #475 stays (2.1 item 4). #397, #398, #399 narrowed (section 4). #418 stays (the Library column and the shelf strips count three types). Four new v2 issues (section 4).

## 3. PR 2: #678 and #686

**#678.** `docs/design/PRODUCT.md:40` becomes: "**Entirely local.** No account, no upload, no telemetry. The update check is off until the user turns it on in Settings; then sci2audio asks GitHub once a day for the number of its newest version, one request with no version number, no identifier and no cookie, and downloads and installs nothing. Otherwise the only network access is a voice download the user starts, shown file by file with size and licence first." (wording from `privacy.updates`). The acceptance criterion's grep also finds `docs/design/prototype/app.js:578`, the prototype's privacy text ("no update check" / "keine Update-Prüfung"): I change only those words to "no update check unless you turn it on" / "keine Update-Prüfung, außer du schaltest sie ein". `PRODUCT.md:75` ("an opt-in update check") is already right. The 1.4.0 release notes ("No update check") are history and stay.

**#686.** Two lines under `## [Unreleased]` > `### Fixed`, after the #684 line, in the CHANGELOG's style (what the listener notices, then the issue numbers):
- "Accents a PDF draws apart from their letter are read with it: names such as "Marasović" and "Šmejkal" keep their accent, and braces reaching below a line no longer join it to the next line of a reference (#125, #126)."
- "Headings set with a rule or numbered like a list, plots without a caption and their labels, and tables without rules on a two-column page are read where they belong (#181, #54, #59, #55, #56)."

## 4. GitHub actions (not in a PR)

Each narrowed body gets a paragraph at the top: "**Scope per D-850 / ADR-008 (20 Nov 2026):** …"; the old criteria are edited to match, nothing else in the body changes.

- **#397:** N, Q, M (no C, no card); the note pauses and opens the box; quote and mark save at once; the dock shows three keys as ADR 2.2 B; M and Q toggle.
- **#398:** no card review; removal at once with Undo in the toast, no strike-through cancel and no Restore; the Captures page lists the three types with filters.
- **#399:** Markdown (Obsidian), RIS (Zotero), the CSV of 2.2 C; no `.apkg`, no Anki card file.
- **#396, #475, #418:** unchanged.

Four new issues, milestone v2, each with acceptance criteria and "Follow-up of #395 (D-850, ADR-008)":
1. `web: the card type, the C key and the Anki export of cards` (lane:web, lane:app, risk:low; `core` change for the type goes in its own critical issue when planned).
2. `web: card review on the Captures page` (lane:web, risk:low).
3. `web: remove a capture by cancel, with Restore` (lane:web, risk:low; additive `removed` field).
4. `app: a user-started local connection to Zotero or Anki, with its own ADR` (lane:app, risk:high; network call, D-665).

## 5. Order, ledger, hand-offs

1. This plan; one chat line and "plan written: plans/docs-b-d1-plan.md" to the coordinator.
2. PR 2 at once (non-critical, plan clearly the better one).
3. PR 1 after the coordinator approves this plan (critical); issue edits and the four v2 issues right after PR 1 opens, because they cite ADR-008.
4. Ledger `ledger/prs/pr-<N>.yaml` for each PR when it opens, completed at merge. One line to the coordinator when each PR is open and when its Linux CI is green. Review rounds: frozen branch, one fix commit per round, answers in `plans/answer-pr<N>-round<K>.md`.

Rough size: PR 1 one ADR of about 150 lines plus four changed lines; PR 2 four changed lines.

## Handoff (THR-07)

- Goal: ADR-008 (#395) and PR 2 (#678, #686) merged; #397/#398/#399 narrowed; four v2 issues filed; ledgers complete.
- Done: this plan.
- Next: PR 2 now; PR 1 after approval.
