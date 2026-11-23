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

## D-913 (2026-11-23, coordinator)

Batch 005 audit (`plans/audit-batch-005.md`, d33f280): 0 blocking, 2 should-fix, 5 notes.
- S1: #766 (lane:cli) and #767 (lane:app) now carry milestone v1.5 and risk:low.
  - #766 is a bug in `convert --with-script --keep-settings`, so v1.5 is not complete.
  - No v1.5 release is cut in this batch. Under D-894 the work stops here, and Colin decides the next batch.
- S2: report-only WebKit failures are tallied in #772 (v1.5, lane:web), with the D-374 rule as acceptance criteria.

## D-914 (2026-11-23, owner)

Correction to D-907, which the log (#771) ranked as a Claude decision because it had no quote. Colin chose it himself on a decision card in the project chat at about 16:36Z, picking the option "Start web PR 3 now". D-907 therefore records an owner decision (KB-01).

## D-915 (2026-11-23, owner)

Batch 005 is finished, and all work pauses (D-894, Colin's "stop working after this batch is finished.", 2026-11-23T09:00:47Z, confirmed on a card at 09:35Z).
- `paused: true`. No batch 006 is composed and no thread is started.
- Merged in batch 005: #754, #761 (#723), #764 (#724), #762, #765, #768 (#725), #769 (#726), #753 (#744), #760 (#756 to #759). Outside the batch: #751. All main CI runs are green on three systems, and none was reverted.
- v1.5 is not complete. #766 (a bug), #767 and #772 are open in it, so no release has been cut.
- META-03 for the next batch: `missing-test` came back after the fixes claimed in #765 and #768 (seen again in #768 and #769), so it goes one step up the ladder. The proposed step: the review template asks "which assertion fails if this line is removed" for each new branch.
