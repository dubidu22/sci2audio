# Pending decisions — sci2audio

Decisions that are made but not yet in `decision-log.md`. One writer: the
coordinator. It adds an entry here at the hand-off where the decision is made,
with the next D-number, and removes an entry once it sees it in the decision
log. The KB thread reads this file and compiles it into the decision log on
its cadence (`ROLE-08`); it never edits this file.

Entry format, the same as in the decision log:

    ## D-<n> (<date>, owner | coordinator)
    What was decided, why, and what it supersedes.
    Owner message: "<the owner's words and their date>"   (owner decisions only, `KB-01`)

Until an entry is compiled it ranks just below the decision log (`authority`).

## Entries

## D-834 (2026-11-20, coordinator)
Triage of milestone v1.4 after release 1.4.0 (Colin, 20 Nov 2026: "close what 1.4.0 already covers, move what belongs to v1.5 or v2, and propose the first batch per lane for the rest"). Nothing is covered by 1.4.0, so nothing was closed; nothing belongs to the study layer. Six reading features moved to v2: #135, #134, #122, #49, #41, #32. Eleven issues stay as 1.4.x work: #217, #216, #203, #181, #172, #125, #126, #59, #56, #55, #54. Three new backlog issues in v1.4: #663 (real-espeak tests exit pytest on macOS), #664 (CodeQL scans the design prototype and the governance workspace; default setup cannot take paths-ignore), #665 (lanes.yml owner of governance/** and docs/design/**). Rule applied: a bug stays, a new reading feature goes to v2.
