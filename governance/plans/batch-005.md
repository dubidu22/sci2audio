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
| A | impl-723 | #723 | plan approved 09:03Z (D-895): PR A (lane:output) first, then PR B (lane:app) |
| B | impl-744 | #744 | requested 08:56Z |

Outside the batch: #751 (Colin's ruleset 1.14.0). Round 1 stopped on preconditions (169a4f7). An implementation thread is merging main into its branch and running ci:full; then round 2.
