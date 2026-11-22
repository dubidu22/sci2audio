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

Started 2026-11-22T16:02Z (17:02 Berlin) by dispatcher thread 1 (Sonnet 5.5).
Threads exist only once their first line says so.

| Slot | Thread | Items | State |
|---|---|---|---|
| A | infra-b-i5 | #709 #710 #711, brittle-test check (ledger `fixed` dropped, D-877) | proposed as a session card 17:43Z (task_7448ae31), waits for Colin's click; not started |
| B | layout-b-l3 | #679 | proposed as a session card 17:43Z (task_8512e06f), waits for Colin's click; not started |

Queue for slot B after layout-b-l3: voices-b-v1 (#663), docs-b-d2 (D-874), then
#720 (see note).

Notes:
- #720 carries lane:web, not app, cli or infra, so it moves to slot B as the
  last item (after docs-b-d2). Slot A item 2 is dropped.
- #709 carries lane:textprep and risk:high, while slot A is lane:infra. The
  slot A plan must say how the PR lanes are split (one PR per lane, `.github/lanes.yml`).
- #710 and #711 are risk:low, lane:infra; they can ride with the critical PR or be a PR of their own.
- The batch file says composed 16:05Z; the Mac clock read 16:02Z at start.

D-877 (coordinator, 2026-11-22): the ruleset is regenerated so the dispatcher runs
on Opus 5.5 high; a Sonnet dispatcher cannot start Opus sessions. After that PR
merges, an Opus dispatcher takes over this batch from this file and starts the
workers itself. Slot A item 3 (hand-written `fixed` value in
`tools/ledger_tool.py`) is dropped: the regenerated ledger tool brings a `fixed`
decision, and the coordinator re-records `ledger/deferred/pr715-1.yaml` with it.
Slot A therefore keeps #709 #710 #711 and the brittle-test check (item 4).

Handoff for the successor (THR-07):
- Goal: close milestone v1.4 (#709 #710 #711, #720, #679, #663, the D-874 docs change, the brittle-test check); v1.5 is batch 005.
- Done: read the instructions and this file; no worker thread was ever started; starter blocks written and withdrawn; only this file changed.
- Next: after the ruleset PR merges, start `infra-b-i5` (slot A, critical plan to the coordinator) and `layout-b-l3` (slot B) yourself; then voices-b-v1, docs-b-d2, #720.
- Kept notes: #720 is lane:web, so it is the last item in slot B. #709 is lane:textprep and risk:high while slot A is lane:infra, so the slot A plan must split PRs by lane. Local constraints for workers: one `uv run` at a time; three real-espeak tests exit the interpreter, deselect them locally (#663); do not touch the shared checkout; never force-push. Starter text is in the shared notes folder, `batch-004-starters.md`, withdrawn but reusable.

Dispatcher thread 2 (Opus 5.5 high) took over 2026-11-22T17:36Z (18:36 Berlin).
- Main CI for #730 (880b170, run 45049808113) passed on all three systems at 17:42Z.
- Start limit: this dispatcher was itself started by a session, so the app refuses
  direct session starts from it (and from any turn an automated event starts).
  Workers therefore go up as session cards (on Opus 5.5 high, each in its own
  worktree) that Colin starts with one click. Told the coordinator once.
- #731 (coordinator advisor start, lane:infra, v1.4) is not in this batch; left for the coordinator.

Handoff for the successor (THR-07, dispatcher 2):
- Goal: as above.
- Done: main green after #730; cards for infra-b-i5 and layout-b-l3 proposed.
- Next: once each thread's first line names its role and model, watch it; relay
  infra-b-i5's critical plan to the coordinator; start review threads (critical:
  Opus 5.5 high; otherwise Opus 5.5 medium); merge go only via `ledger_tool.py gate`.

Merge gates: none yet.
Escalations: none yet.
