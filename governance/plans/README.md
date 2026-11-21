# plans/

Working documents shared between threads. One file per unit of work, numbered
so that order is obvious at a glance. Every file has one writer; nobody edits
another thread's file (`THR-04`).

| File | Writer | When |
|------|--------|------|
| `plan-<NNN>-<lane>-<slug>.md` | implementation thread | before writing tests or code |
| `review-pr<N>-round<K>.md` | review thread | end of every review round |
| `batch-<NNN>.md` | coordinator composes it, then the dispatcher is its only writer | when a batch is composed |

Every plan and round report ends with a three-line handoff, kept current:
`Goal:` what this thread is for, `Done:` what is finished and where,
`Next:` the next step. A fresh thread starts from those three lines (`THR-07`).
Under them, when there is something to say: `Ruled out:` what was tried and
did not work, each with the evidence (the command and what it printed, or the
file and line). It is what stops the next thread from spending an hour on the
same dead end.

A report's first word is its status (`THR-15`): `done`, `question`, `blocked`,
`review` or `handoff`. `question` and `blocked` are followed by the evidence
and one line `Recommended: <one action>`.

A plan states: goal, lane and labels, whether the work is critical (`CRIT-01`),
files it expects to touch, tests it will add first, open questions. A round
report states: head SHA, verdict, in round 1 the reviewer's own finding on
whether the PR is critical (`CRIT-03`), verified checks, numbered findings
(B/M must-fix, S should-fix, N note) and, on the next round, how each finding
was answered (fixed with test proof, deferred with issue link, or declined
with reason). A finding is fixed at its root: a comment or a note that
explains a workaround is not a fix (`REV-05`). Each PR and each round also gets a ledger entry
(`../ledger/README.md`).

These files are committed on branch `governance` by their writer,
never on a product branch and never by force-push (`THR-13`). A thread that
works on a product branch keeps a second worktree for them:

    git worktree add ../<repo>-governance governance
