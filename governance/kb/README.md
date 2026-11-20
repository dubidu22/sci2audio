# kb/ — knowledge base for sci2audio

Durable project knowledge that every new thread reads before acting:

- `decision-log.md` — a pointer: sci2audio's decision log lives in the repository
  `dubidu22/sci2audio-design` (`docs/kb/00-index/decision-log.md`), where the KB thread
  merges one PR per day. `merged-batches/` keeps the Project's pending batch files as history.
- `architecture.md` — layer order, contracts, invariants (critical).
- `process.md` — how batches, reviews and releases run here (critical).

- `pending-decisions.md` — decisions made but not yet in the log. The
  coordinator is its only writer.

The KB thread is the only writer of `decision-log.md`. On the cadence set by
`execution_profile.token_economy.kb_pr_cadence` it compiles the entries of
`pending-decisions.md` into the log, unchanged and in D-number order
(`ROLE-08`), and it never edits the pending file; the coordinator removes
entries from there once they are in the log.
The log changes by a decision-log pull request to `main`, which
the KB thread merges itself without code review. The pending file is a working
file on branch `governance` (`THR-13`).
Changes to the other KB documents are critical and go through normal review.

An entry that records an owner decision quotes the owner's message and its
date; without the quote it ranks as a Claude decision (`KB-01`). The owner's
newest message on a point outranks older entries (`ROLE-01`).
