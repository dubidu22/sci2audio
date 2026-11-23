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

## D-891 (2026-11-23, coordinator)

Outcome of D-890, which was compiled before it was known: #749 squash-merged as 1cbfbd2; main CI run 45139630420 green on Linux, macOS and Windows. Backup tag `governance-before-d874` at f12fe96 was pushed by Colin ("done", 2026-11-23T08:37Z), because the cloud proxy refused tag pushes (HTTP 403). The one-time merge is 6409f52, with both diffs empty. Decision-log PR #752 (0994f97) compiled D-834 to D-890.

Batch 004 audit (`plans/audit-batch-004.md`, 3cd4a3b): 0 blocking, 3 should-fix, 7 notes.
- F1, data: `merged:` filled in `ledger/prs/pr-741.yaml` (3fb4d1b) and `pr-721.yaml` (207ea14, release/1.4). Check: `ledger_tool.py check` fails on a PR entry without a merge record whose `(#N)` closes a squash subject on main or release/*. This goes into batch 005, slot A (lane:infra, critical).
- F2, data: `ledger/deferred/pr745-1.yaml` records S4 as planned in #747. Check: a round entry field `deferred: <n>`, and `check` fails when fewer `deferred/pr<N>-*.yaml` exist. Same batch-005 item as F1.
- F3: v1.4 stays open only for #731. Moving #731 to another milestone goes to Colin (ROLE-01).
- `stats`: `narrating-comment` regressed after #712's fix (seen again in #739), so it goes one step up the META-03 ladder: a lint check in batch 005, slot A.
- Owner PR #751 (ruleset 1.14.0, the claude.ai Project, Colin's "Yes, apply" 23 Nov) gets its critical review now that the lane:infra lock is free.

## D-892 (2026-11-23, owner)

#731 is closed as not planned, so the Fable advisor second opinion of PREF-01 is dropped. Colin chose "Close it as not planned" (2026-11-23T08:48Z) on the card "Move #731 (coordinator's advisor) out of v1.4 so v1.4 can close?", whose consequence read: "The Fable advisor second opinion (PREF-01) is dropped; that rule then needs a ruleset change."
- From now on the coordinator asks no advisor thread before a decision it puts to Colin.
- The PREF-01 text is removed by the next ruleset PR after #751 (META-01, batch 005, slot A), not inside #751, which is under review.
- With #731 closed, milestone v1.4 has no open Issue.

## D-893 (2026-11-23, coordinator)

Batch 004 is done (v1.4 has no open Issue). Batch 005 is composed as `plans/batch-005.md`. Slot A is #723 (critical, plan first), then #725 and #726. Slot B is #744, then the infra check PR (D-891 F1, F2 and narrating-comment, plus D-892's PREF-01 removal) once #751 has merged, then #724. #723 to #726 all carry acceptance criteria (PLAN-04). No dispatcher runs, so the coordinator asks the project for each thread (D-889).

## D-894 (2026-11-23, owner)

Work stops once batch 005 is finished. Colin: "stop working after this batch is finished." (2026-11-23T09:00:47Z). Batch 004 had closed before the message, so it is read as batch 005. The coordinator asked Colin once to confirm that reading.
- `autonomy_horizon` becomes "until batch 005 is finished, then pause".
- Batch 005 runs to its end: its PRs, its audit, its decision-log PR and the batch report. #751, already in flight, finishes too.
- Then the coordinator sets `paused: true`, composes no batch 006 and starts no thread.
