# Answer to review PR #701, round 1

Thread docs-b-d1. Fix commit 92c2894 on b6905d2 (one commit; branch otherwise frozen). Date: 2026-11-20. Rulings for S2 and S3 from the coordinator's message of 20 Nov.

## Fixed in the ADR (`governance/kb/01-audit-and-roadmap/adr-008-study-layer.md`)

- **S1 (issue-scope-drift):** the consequences rows for #396 and #475 now say that the file part (reading and writing `captures.json`; the carry-over) is in `app` (2.3) and that the issue also carries `lane:app`. On GitHub: `lane:app` added to #396 and #475, and each body has a "Scope per ADR-008 2.3 (20 Nov 2026)" paragraph at the top; nothing else in either body changed.
- **S2 (underspecified-contract):** 2.1 item 7 defines for every export: `document` is the document's title as the Library shows it; `page` is the number of the PDF page on which the sentence starts, empty for EPUB, Markdown and text. 2.2 C refers to it. #399 inherits it as a new criterion.
- **S3 (self-contradiction):**
  - (a) the Why row now reads "No capture the user removed stays on disk", says removal takes the capture out of `captures.json`, and says a v1.3 `markers.json` stays as the user's own file, as it was, until the document is removed.
  - (b) 2.1 item 4: once written, `captures.json` stays, also when it holds no capture. 2.1 item 5: the carry-over runs only when `captures.json` is absent, records `migrated_from: markers.json` in the file; `markers.json` is the user's own file, not something removed, and is not read while `captures.json` exists; removing `captures.json` by hand brings the v1.3 markers back as they were, on purpose, as the recovery path, including markers removed after the carry-over. The same paragraph is on #475.

## Notes

- **N1:** 2.2 A now says `TY  - GEN` "unless extraction records an explicit type for the document". Also a #399 criterion.
- **N2:** 2.2 A says how a line break inside a note or sentence is written is settled in #399 with a test; #399 has the criterion.
- **N3:** the Related field says both plans are on branch `governance`.
- **N4 (dates):** today is 20 Nov 2026. The ADR carried no 21 Nov. Corrected to 20 Nov: the "Scope per D-850 / ADR-008" paragraphs of #397, #398 and #399, the plan (`plans/docs-b-d1-plan.md`, lines 3 and 70) and `opened` in `ledger/prs/pr-700.yaml` and `pr-701.yaml`. `pending-decisions.md` is not mine (THR-04); it says 21 Nov for D-850 to D-855.

## Checks

`uv run ruff check` clean; wording only, so the fast suite was not re-run (round 1 ran it on b6905d2: 8638 passed). `ci:full` stays on, so the new head gets its three-system run.
