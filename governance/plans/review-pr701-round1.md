# Review PR #701, round 1 (batch B-D1, #395)

Thread: review-docs-b-d1 (Opus 5.5). Head reviewed: b6905d2 (commits 0c55b87 and b6905d2 on `main` 9066c3d; `ci:full` label set, head unchanged). Date: 2026-11-20.
**Critical: yes** (CRIT-01: a KB architecture document, `governance/kb/01-audit-and-roadmap/adr-008-study-layer.md`, the `adr-` prefix since #691; D-703c). `risk:high` is set. Plan `plans/docs-b-d1-plan.md`, approved as D-854. It records Colin's scope D-850 (`plans/study-layer-scope-options.md`, "Colin's decisions").

**Verdict: changes requested** (0 must-fix, 3 should-fix, 4 notes).

## Verified

- Diff `git diff 9066c3d...b6905d2`: three files, +120/−4: the new ADR (116 lines), `governance/kb/00-index/README.md` (2 lines), `docs/design/PRODUCT.md` (lines 55 and 78). Nothing else.
- Format: like ADR-007, with the `[ADR]` status line (status, decider, closes, related), `---`, and sections 1 Context, 2 Decision, 3 Why (table), 4 Options considered (table), 5 Consequences (issue table plus Negative), 6 Revisit triggers. ADR-007's sections 7 and 8 (advisor pre-analysis, open questions) have no counterpart here, and that is right: nothing is left open.
- Colin's decisions (`adr-008:18-22`): I compared the three questions and the chosen labels byte for byte with the scope file, and they are identical ("Mark, note, quote only", "As the marker today (Recommended)", "Markdown, CSV and RIS/BibTeX"). The time is given as "20 Nov 2026 at 20:04 CET (19:04 UTC)", the same as the scope file; the status line has "20 Nov 2026, 19:04 UTC". KB-01 is met: the labels are quoted with their date.
- The three points match D-854:
  - A, RIS (`:39-46`): one `N1` per capture, so one child note each; no TeX escaping (D-57); no invented citation key; only what the document states (title, authors, year and DOI where extraction found them); UTF-8. BibTeX and "both" are rejected in the options table.
  - B, the dock (`:48-53`): Note N, Quote Q, Mark M, in a group labelled "Capture"; no fourth slot and no disabled C; C unbound and named by no string; M and Q toggle, N opens the note box. The design facts hold. In `prototype/app.js:434` the order is note, quote, card, mark in a `role="group"`. In `DESIGN.md:256`, at 1399 px and below the labels drop and the key caps stay. `DESIGN.md:223` is the Highlighter Rule.
  - C, the CSV (`:55-60`): ships in v1.5 with the columns `document`, `type`, `page`, `sentence`, `text`, RFC 4180, UTF-8 and no time column. The formula-prefix safeguard is left to #399, with a test.
- The record and the layering match plan 2.1 to 2.3:
  - The fields `id`, `type`, `created`, `changed`, `anchor{block,start,end,text}` and `text` are the v1.3 marker's. `web/markers.py:49-50` has the same anchor keys; `note` there becomes `text`.
  - `anchor.text` is the printed sentence, never the spoken one, and the time is never stored, for the stated reason (`:31`).
  - One `captures.json` per document, written only by the server, one atomic write per change. A file this version cannot read is never written, renamed or removed (`:32`). `markers.py:10-16` docstring confirms each "as `markers.json` today" claim, and the in-memory Undo (`UNDO_SECONDS`, `UNDO_KEPT`).
  - `markers.json` is migrated once and left untouched; an unreadable one is reported and capturing stays off (`:33`).
  - Removal is at once, with Undo only (`:34`, D-723 ruling 1).
  - Core holds data objects and their JSON form, app the files and the writers, web calls app (`:62-68`, D-46).
- The cited decisions say what the ADR claims. D-663 left the study layer to its own ADR. D-665 says "such a call is a network call under the hard rule". D-723 ruling 1 is removal with Undo from the toast only. The hard-rule sentence at `:11` matches `CLAUDE.md:11` on `main`, which includes the opt-in update check.
- Hard rules: no network call (every export is a file, and the connections wait for v2 and their own ADR); 127.0.0.1 is unchanged; the quote is verbatim (D-57). Nothing contradicts D-665.
- The consequences table (`:97-105`) has the right issue titles. #396 "core: the capture model", #397, #398, #399, #418 and #475 are open in milestone v1.5 Study layer. #702 to #705 are open in milestone v2 and say what the ADR claims: #702 card type, C key and Anki file; #703 card review; #704 cancel with Restore and an additive `removed` field; #705 local Zotero or Anki connection, its own ADR, `risk:high`, `lane:app`. Each has acceptance criteria and "Follow-up of #395".
- #397, #398 and #399 on GitHub: I compared the edit history (`userContentEdits`) before and after the 20 Nov 20:40 UTC edits.
  - Each body gained the "Scope per D-850 / ADR-008" paragraph at the top. Only the criteria named in plan section 4 changed.
  - #397: N, Q, M; a note pauses and quote and mark save at once; three keys; M and Q toggle.
  - #398: "and the review of cards" is gone from the intro, and the "Card review" and strike-through criteria are replaced by removal with Undo.
  - #399: the targets are named, and a D-57 and formula-prefix criterion is added.
  - No other line was lost or changed. No body still mentions a card except to say it is v2.
- KB index: the folder row and the file list name ADR-008. The count went from 15 to 16, and the folder holds 16 files.
- `PRODUCT.md:55` and `:78` point at ADR-008. `git merge-tree 1636cc7 b6905d2` (with #700) is clean.
- Local run in a fresh `/tmp/review-701` at b6905d2: `uv run ruff check` clean; fast suite `-m "not slow and not benchmark and not browser" -k "not espeak" -n auto`: 8638 passed, 6 skipped, 6 xfailed.
- CI on b6905d2: `CI passed`, `tests (ubuntu-latest)`, the Chromium shards and `governance pr checks` are green. The `ci:full` run 44815099595 was in progress at review time: `tests (windows-latest)` success, `tests (macos-latest)` running. The coordinator checks it before the merge go (MRG-01).

## Findings

### Should-fix
- **S1 (issue-scope-drift). `adr-008:99-100` mark #396 and #475 "Stays", but `:65` moves part of each into `app`.** Section 2.3 puts the reading and writing of `captures.json` and the marker carry-over in `sci2audio.app`. Both issues still carry `lane:core` only (core is single-threaded in `.github/lanes.yml`), are titled "core: …", and were not edited. #396's second criterion still reads "Reading and writing captures for a document", and #475's second criterion reads a v1 `markers.json`. Failure scenario: the coordinator schedules #396 or #475 by its label in the core lane alone, while an app-lane thread runs. Two threads then change `src/sci2audio/app/` at once (LANE-02). Or an implementer who reads only the issue puts file reading in `core` to fit the label, and breaks D-46. Fix: in the ADR rows, write "Stays; its file part is in `app` (2.3), so the issue also carries `lane:app`". On GitHub, add `lane:app` and one "Scope per ADR-008 2.3" line to #396 and #475. Like the #397 to #399 edits, that is not in the PR.
- **S2 (underspecified-contract). `adr-008:57` fixes the CSV columns but not what `page` and `document` hold.** In `core.content.Page`, a page is "one page of a PDF, one spine document of an EPUB, or the whole of a text file". For EPUB, Markdown and text there is no printed page, and a sentence can run across a page break. Failure scenario: #399 writes the EPUB spine index or a constant 1 into `page`, and a student who looks up "page 7" in the e-book finds nothing. For `document` it chooses between the title, which may be missing or repeated, and the file name, and one CSV of several papers cannot be sorted back to its sources. Fix: one sentence in 2.2 C. For example, `page` is the printed page where the sentence starts in a PDF and empty for other formats, and `document` is the document's title as the Library shows it. Or the ADR leaves both to #399 explicitly, as it does for the formula prefix, and #399 gets the criterion.
- **S3 (self-contradiction). Leaving `markers.json` untouched (`adr-008:33`) breaks two other claims of the ADR.**
  - (a) The Why table (`:77`) says "Nothing the user removed stays on disk: Removal leaves the file at once". For a migrated capture this is false. When the user removes a mark or note that came from v1.3, it is still in `markers.json` with its note text until the document is removed. A user who deletes a private note believes it is gone from the computer.
  - (b) `:33` says `markers.json` "is never read again", but the trigger is "has `markers.json` and no `captures.json`". If the user removes an unreadable `captures.json`, as `:32` invites, or an implementer deletes the file when the last capture goes, the trigger fires again. Every v1.3 marker comes back, including the ones the user removed after the carry-over.
  - Fix, within D-854 ("migrated once and left untouched"): qualify the `:77` row ("… except that a v1.3 `markers.json` keeps its markers as they were until the document is removed"). State in item 4 or 5 that `captures.json`, once written, stays even when it holds no capture. State in item 5 what removing it brings back. If the coordinator would rather remove or rename `markers.json` after a successful carry-over, that changes D-854 and is the coordinator's call, not a fix in this round.

### Notes
- N1: "`TY  - GEN` unless the document says otherwise" (`:45`) leaves open what counts as the document saying so. Under "nothing is guessed" it can only be an explicit type the extraction records. #399 can settle it in a line.
- N2: "RIS needs no escaping beyond line breaks" (`:42`) does not say how a line break in a note or a sentence is written. A line starting `XX  - ` would read as a new tag. Like the formula prefix, this belongs in #399 with a test. It could be named there.
- N3: "Related" (`:3`) cites `plans/study-layer-scope-options.md` and `plans/docs-b-d1-plan.md`. Both live on branch `governance`, not on `main` where the ADR is. "(branch `governance`)" would help a reader on `main`.
- N4: the issue paragraphs say "Scope per D-850 / ADR-008 (21 Nov 2026)" (and the plan, `pending-decisions.md` D-850 to D-855 and `ledger/prs/pr-70{0,1}.yaml` say 21 Nov). GitHub dates the edits 2026-11-20T20:40Z, and the clock read 20 Nov 21:51 CET at this review. This is for the coordinator; the ADR itself carries no 21 Nov.

Verdict: changes requested for S1 to S3. They are wording in the ADR plus two label and body edits on GitHub; the decisions themselves match D-850 and D-854. Round 2 checks the fix commit, the edits on #396 and #475, and the three-system run on the new head.
