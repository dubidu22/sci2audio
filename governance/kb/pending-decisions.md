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
