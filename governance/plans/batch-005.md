# Batch 005: v1.5 Listen while generating, plus the batch-004 audit checks

Composed by the coordinator on 2026-11-23T08:56Z (D-893). There is no dispatcher in the
claude.ai project (D-889): the coordinator asks the project for each thread and writes this file.

## Goal

Milestone 11, v1.5 "Listen while generating" (D-870): #723 (LW-01, critical) first, then
#724, #725 and #726, which depend on it. Also #744, and the checks that the batch-004
audit and `ledger_tool.py stats` asked for (D-891, D-892).

## Settings (frugal, ruleset 1.13.0 until #751 merges)

- At most 2 implementation threads at once, one per lane (LANE-02).
- Implementation and critical work on Opus 5.5 high. Review on Opus 5.5 medium, critical review on Opus 5.5 high.
- Non-critical PRs: at most 2 rounds. Critical: at most 4, then Colin.
- Tag pushes are refused from the cloud (HTTP 403); branch pushes work.

## Slot A: #723 LW-01 (critical)

Labels risk:high, lane:output, lane:app. Plan first, to the coordinator (PLAN-02). The plan
says how the PRs split by lane (`.github/lanes.yml`): output and app are different lanes.
Then #725 and #726 (lane:app, lane:web) follow in this slot once #723 has merged. They wait for
#724 if they share web files with it (LANE-02).

## Slot B: one item after another

1. #744 (lane:voices, risk:low): espeak-ng on Windows with a non-ASCII data folder. It needs a three-system run, since the fault is Windows-only.
2. After #751 merges (the lane:infra lock), one critical infra PR, with an Issue opened first for each check:
   - F1: `ledger_tool.py check` fails on a PR entry with no merge record whose `(#N)` closes a squash subject on main or release/*;
   - F2: a round field `deferred: <n>`, and `check` fails when fewer `deferred/pr<N>-*.yaml` exist;
   - narrating-comment: one step up META-03, a lint check (the fix in #712 regressed in #739);
   - PREF-01: drop the advisor sentence (D-892), regenerated through the governance skill (META-01, Colin's word in D-892).
3. #724 (lane:web), after #723 has merged.

## End of the batch

The batch audit (critical PRs ran), one KB decision-log PR for D-891 onward, the batch report, and the v1.5 release if the milestone is complete.

## Progress (coordinator)

| Slot | Thread | Items | State |
|---|---|---|---|
| A | impl-723 | #723 | plan approved 09:03Z (D-895); PR A #754 merged f1a9c1f (2 rounds, D-897), main CI 45155540428 green on three systems; PR B (lane:app) started 10:35Z |
| B | impl-744 | #744 | requested 08:56Z |

Outside the batch: #751 (Colin's ruleset 1.14.0) merged c63fc76 after 3 rounds (D-896); main CI 45155227469 green. Slot B item 2 may now start once #744 is done.

## Batch report (coordinator, 2026-11-23T19:42Z)

Batch 005 is finished; work pauses (D-894, D-915).

| PR | Issue | Squash | Rounds | Critical |
|---|---|---|---|---|
| #754 | #723 (PR A, output) | f1a9c1f | 2 | yes |
| #761 | #723 (PR B, app) | 9f622af | 2 | yes |
| #753 | #744 | 8965914 | 1 | no |
| #760 | #756 #757 #758 #759, ruleset 1.15.0 | e3a328e | 1 | yes |
| #764 | #724 | eab9fb2 | 1 | yes |
| #762 | #725/#726 PR 1 (output) | 51dd21d | 2 | yes |
| #765 | #725/#726 PR 2 (app, cli) | ebd6e40 | 2 | yes |
| #768 | #725 (web) | 1fbff7c | 2 | no |
| #769 | #726 (web) | see rounds/pr769-round2.yaml | 2 | no |
| #751 (outside) | #750, ruleset 1.14.0 | c63fc76 | 3 | yes |

- Main CI green on all three systems after every merge; 0 of 41 merged PRs reverted.
- Deferred: #765 S1 -> #767 (planned). Follow-ups filed: #755 (Later), #766, #767, #772 (v1.5).
- Audit (plans/audit-batch-005.md): 0 blocking, 2 should-fix (D-913).
- Decision log: #771 (D-891 to D-912). D-913 onward wait in pending-decisions.md.
- Repeated finding kinds (ledger_tool.py stats): missing-test regressed after #765 and #768 fixes (next step in D-915); vacuous-test fixed by the shared output_helpers (#762, holding).
- v1.5 open: #766 (bug), #767, #772. No release cut.
