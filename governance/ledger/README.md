# ledger/ — one small file per PR and per review round

The ledger is what the coordinator and the dispatcher read instead of chat
messages. Each entry is its own file with one writer, so two threads never
edit the same file. Nobody maintains a table by hand; print one when needed:

    python3 tools/ledger_tool.py table      # PRs and rounds as tables
    python3 tools/ledger_tool.py stats      # rounds per PR, compactions per PR, PRs per thread
    python3 tools/ledger_tool.py check      # entries with missing or malformed fields
    python3 tools/ledger_tool.py gate 12    # may PR 12 be merged? (run before every merge, MRG-01)
                                            # add --head <sha> when an owner override exists and no round is recorded
    python3 tools/ledger_tool.py approved 12 --head <full sha>
                                            # does the latest round approve exactly this head? `governance pr checks`
                                            # runs it for a risk:high PR, on the ledger of branch governance (D-882);
                                            # it counts only a full 40-character SHA in `head`, `updated_head` or an
                                            # override, so write round and override heads in full
    python3 tools/ledger_tool.py triage     # what was left behind without a decision; run before a new batch (THR-16)
    python3 tools/ledger_tool.py flags      # one line per thing an audit should judge (ROLE-15)

| File | Writer | Written |
|------|--------|---------|
| `prs/pr-<N>.yaml` | the implementation thread that opened PR N | when the PR opens; `compactions` updated at its hand-offs |
| `rounds/pr<N>-round<K>.yaml` | the review thread | at the end of round K; `merged` filled in after the merge |
| `reverts/pr-<N>.yaml` | the review thread that merges the revert | when merged PR N is reverted |
| `gos/pr-<N>.yaml` | the coordinator | when it gives the merge go for critical PR N (`MRG-01`) |
| `overrides/pr-<N>.yaml` | the coordinator, on the owner's word | when the owner lets PR N merge although the gate stops it (`MRG-02`) |
| `deferred/pr<N>-<k>.yaml` | the coordinator | one per should-fix finding a merged PR left open, or point a thread set aside (`THR-16`) |
| `audits/batch-<NNN>.md` | the audit thread | after a merged batch (`ROLE-09`, `ROLE-15`) |

`prs/pr-<N>.yaml`:

```yaml
pr: 12
opened: 2026-01-31
thread: impl-app_cli-2        # the name this thread was started under
lane: app_cli
labels: "lane:cli"
plan: plans/plan-003-app_cli-import.md
critical: no                  # the author's statement from the plan (CRIT-01)
compactions: 0                # how often this thread's context was compacted while on this PR
fixes_kinds: ""               # optional: finding kinds this PR claims to remove for good (REV-06), e.g. "timer-workaround"
handback: ""                  # the first word of the thread's last report when it is not done: question | blocked |
                              # review | handoff (THR-15). question, blocked and review stop the merge gate
recommended: ""               # with question or blocked: the one next action the thread proposes
merged: ""                    # the merge commit SHA, only when no round records the merge (an owner override,
                              # a merge by hand); written by whoever records that merge
```

`rounds/pr<N>-round<K>.yaml`:

```yaml
pr: 12
round: 1
date: 2026-02-01
thread: review-1
head: 3f9c2ab
critical: no                  # round 1: the reviewer's own finding from the diff (CRIT-03)
verdict: changes_requested    # approved | changes_requested
must_fix: 2                   # open B/M findings after this round
should_fix: 1
kinds: "timer-workaround, missing-test"   # a short name per kind of finding, reused across PRs (REV-05);
                              # use narrating-comment and unsolicited-file for PR-05 findings
report: plans/review-pr12-round1.md
merged: ""                    # merge commit SHA, last round only
updated_head: ""              # MRG-01: the new head after merging main into a behind PR and re-verifying;
                              # gate, approved and the go file then take it beside `head`
```

`reverts/pr-<N>.yaml`:

```yaml
pr: 12                        # the merged PR that was reverted
date: 2026-02-09
by: "#19"                     # the PR or commit that reverted it
reason: "import broke files with a BOM"
```

`gos/pr-<N>.yaml` (the coordinator's merge go for a critical PR):

```yaml
pr: 12
head: 3f9c2ab                 # the reviewed head the go is for: the latest round's `head` or `updated_head`
by: "coordinator (session coordinator-1)"
time: 2026-02-03T14:05Z
```

`gate` passes a PR whose round 1 says `critical: yes` only with this file, and
only for the head it names. A go for another head does not carry over.

`overrides/pr-<N>.yaml` (only when the owner decides against the gate):

```yaml
pr: 12
date: 2026-02-03
by: "owner, chat message of 2026-02-03"   # who decided; always the owner
head: 3f9c2ab                 # the commit the override is for; it does not carry over to a later head
reason: "Hotfix for the broken release build; the open finding is tracked in #40"
```

An override is a record of one decision, for one PR at one head. It is not a
setting and nobody keeps it "on". The file is a record, not proof: the merge
still happens on the owner's own message, and the coordinator names every
override in its next report to the owner.

`deferred/pr<N>-<k>.yaml` (one per leftover; `k` counts them per PR):

```yaml
pr: 12
date: 2026-02-03
what: "S2: the import dialog does not remember the last folder"
decision: open                # open | fixed | planned | postponed | dropped
commit: ""                    # fixed: the commit that fixed it (also before the merge, in the PR itself)
issue: ""                     # planned: the issue that carries it
until: ""                     # postponed: a milestone, a date or an event
reason: ""                    # postponed and dropped: why
by: ""                        # dropped: the owner, and where they said it
```

`triage` lists every entry that is still `open` and every merged PR whose
last round left more should-fix findings than there are entries. It exits 1
while anything is listed, and no batch starts then. Planning and postponing
are the coordinator's call, and so is `fixed` when the commit is named;
dropping is the owner's. Merges dated before the
day in `deferred/since.txt` are not counted, so an older ledger is not asked
to account for the time before this rule.

What the numbers are for:

- **Merge go.** A PR may be merged only when its latest round has
  `must_fix: 0` (`MRG-01`).
  The dispatcher grants merge go only when round 1 says `critical: no`
  (`ROLE-11`); everything else goes to the coordinator, whose go is the
  file `gos/pr-<N>.yaml`. For a `risk:high` PR the required check
  `governance pr checks` also fails until the latest round on branch
  `governance` approves the PR's current head; the review thread re-runs
  it after pushing that round entry.
- **Quality.** `stats` shows the share of merged PRs that were reverted.
  Faster or cheaper is only better if this number does not go up.
- **Repeated findings.** `stats` lists finding kinds that came up in more
  than one PR. The same correction twice means the fix belongs in a check
  (lint rule, type, test, CI check) or in the design, not in another review
  comment (`REV-05`, `META-03`).
- **Did the fix hold.** A PR that claims to remove a finding kind names it
  in `fixes_kinds`. `stats` derives the standing from the entries: pending
  (not merged), holding, or regressed (a round of another PR, dated after
  the merge, names the kind again). Nobody writes "fixed" by hand. A
  regressed fix did not remove the cause; the next one goes a step up the
  ladder in `META-03`. A PR that branched before the fix and was not updated
  can show up here too; the reviewer says so in the round report.
- **Audit flags.** `flags` prints one line per thing worth judging: a PR
  with three or more rounds, a thread compacted twice on one PR, a finding
  kind seen in several PRs, a regressed fix, a revert, an override, a waiting
  hand-back, an untriaged leftover. The audit thread starts from these lines
  and gives each one of five verdicts (`ROLE-15`). Nobody writes a flag by hand.
- **Overrides.** `stats` counts the owner's overrides of the merge gate.
  Several for the same reason mean the rule is wrong: change the rule.
- **Replacement.** A worker thread is replaced after `replace_after_prs` PRs
  (`THR-02`); `stats` counts them per `thread`.
- **Package size.** A work package that regularly causes a compaction or a
  third review round is too big; a run of one-line PRs from fresh threads is
  too small.
- **Model routing.** A cheaper routine model only pays off if rounds per PR
  do not go up; compare `stats` before and after a routing change.

Tables from an older setup (`implementation.md`, `review.md`) are history:
keep them, do not add to them.
