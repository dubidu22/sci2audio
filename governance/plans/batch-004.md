# Batch 004: the v1.4 remainder and two ledger checks

Composed by the coordinator on 2026-11-22T16:05Z (D-876). From now on the
dispatcher is this file's only writer (ROLE-11, THR-05).

## Goal

Close milestone v1.4: #709, #710, #711, #720, #679 and #663, plus two
process checks (META-03) and the D-874 docs change. v1.5 (#723 to #726) is
batch 005 and does not start in this batch.

## Settings (ruleset 1.9.0, frugal)

- At most 2 implementation threads at once, one per lane (LANE-02).
- Models: implementation and critical work on Opus 5.5 high, review on
  Opus 5.5 medium, but critical review on Opus 5.5 high (CRIT-02).
- A thread is replaced after 2 PRs or 1 compression (THR-02). Watchdog
  every 120 min (THR-03).
- Non-critical PRs: at most 2 review rounds. Critical PRs: at most 4, then
  Colin (REV-01).

## Slot A: app/release lane, lane:infra lock (one thread, `infra-b-i5`)

1. #709, #710, #711 (follow-ups from D-860: review tags in regression goal
   strings, which touches golden files and so is critical; the other stale
   `github-setup` copies; audit N4, the base-commit listing).
2. #720. If its labels put it outside app, cli or infra, move it to slot B
   and note that here.
3. Ledger: `ledger_tool.py` gets a deferred decision `fixed` that requires a
   commit SHA contained in the merged PR's pinned head, with a test. This is
   needed because #715's S1 was fixed after its last round and could only be
   recorded as `planned` against #715 (`ledger/deferred/pr715-1.yaml`).
   After the merge the coordinator re-records that entry as `fixed`; the
   coordinator writes deferred entries, and neither this thread nor the
   dispatcher does. `governance/tools/**` is critical.
4. META-03 check for the finding kind `brittle-test` (#680, #715): a fast
   test that fails on a wall-clock bound in an assert in the fast suite
   (`elapsed <`, `time.monotonic()` or `perf_counter()` differences) unless
   the test is marked `benchmark` or `slow`, or the line carries a
   reason-marked allowance. The plan decides the exact form. Set
   `fixes_kinds: brittle-test` in the PR entry.

The thread opens an Issue for items 3 and 4 before its plan (PLAN-04,
GH-01; milestone v1.4, lane:infra, risk:high). Items 1 to 4 may be one PR or
two, split along files (D-75). The plan goes to the coordinator: it is
critical work (PLAN-02).

## Slot B: one lane after another, a new thread each

1. Layout #679 (`layout-b-l3`).
2. Voices #663 (`voices-b-v1`): the real-espeak tests that exit pytest on
   macOS. If its fix touches `pyproject.toml` or `conftest` markers it
   carries lane:infra and waits for slot A's PR to merge (LANE-02).
3. Docs D-874 (`docs-b-d2`): main's stale working-file copies (plans,
   ledger, project-state.yaml, pending-decisions.md) become a one-line pointer
   to branch `governance`, with a check that fails when a working file
   reappears on main. The thread opens the Issue first. The check sits in
   `.github`, so the PR is lane:infra and waits for slot A like item 2.

## End of the batch

- Batch audit: yes, since this batch has critical PRs (`critical_only`).
- KB thread: one decision-log PR for D-834 onwards (`per_milestone_or_batch`).
- Report to the coordinator once: PRs merged with squash SHAs, deferred
  findings with their Issues, and repeated finding kinds from
  `ledger_tool.py stats`.

## Progress (dispatcher)

_Not started._
