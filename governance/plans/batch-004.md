# Batch 004: the v1.4 remainder and two ledger checks

Composed by the coordinator on 2026-11-22T16:05Z (D-876). From now on the
dispatcher is this file's only writer (ROLE-11, THR-05).

## Goal

Close milestone v1.4: #709, #710, #711, #720, #679 and #663, plus two
process checks (META-03) and the D-874 docs change. v1.5 (#723 to #726) is
batch 005 and does not start in this batch.

## Settings (ruleset 1.12.0 since D-880, frugal)

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
| A | infra-b-i5 | #709 #710 #711, brittle-test check (ledger `fixed` dropped, D-877) | running, Opus 5.5 high confirmed (local_f085fc59-3aa0-4778-9297-574cf5ff13da); opened #734 (brittle-test check); critical plan `plans/infra-b-i5-plan.md` (PR A lane:infra #710 #711 #734, PR B lane:textprep #709, both risk:high) approved by the coordinator (D-878), who told the thread directly; implementing; PR A (#710 #711 #734) committed on `infra-b-i5-a`, fast suite running; PR B (#709) test written; idle 19:02Z with a finished suite, nudge 1 at 19:30Z; PR A open as #740 (#710 #711 #734, risk:high), ci:full green on 465b96f at 19:43Z, author told to remove the label; card withdrawn (D-881); critical review of #740 and #742 runs as one dispatcher subagent review-b004-a (Opus, high, own worktree) since 20:06Z; PR B open as #742 (#709, lane:textprep, risk:high, ci:full green on 85dd312 at 19:58Z; author told to remove the label and write its handoff); review-740 takes it after #740. infra-b-i5 has now handled 2 PRs (THR-02): fix rounds go to a fresh thread started from its plan's handoff |
| B | layout-b-l3 | #679 | running, Opus 5.5 high confirmed (local_3f956e8c-d059-4c66-b72a-ee630dc3270f); PR #735 (head 401c78f, lane:layout, risk:low) open 18:05Z; body fixed, Linux CI and governance pr checks green 18:14Z; review thread review-735 (Opus 5.5 medium) started on Colin's go (local_27a9761d-ffb5-453b-a305-e86b0c1db8bc); round 1 approved, critical: no, must_fix 0 (234bfcb); gate open, merge go given 18:50Z pinned to 401c78f |

Slot B: layout-b-l3 done, #735 merged as 204c188 (main CI running). voices-b-v1 (#663)
started on Colin's go (local_718d5252-0d42-443c-889d-a35b1c464728); PR #739 (head 74e4d1d, lane:voices only, risk:low; cause: espeak-ng exits on data paths over 159 bytes) open; Linux CI red 19:37Z on test_a_non_ascii_path_is_measured_in_bytes, fixed in four commits (path-length independence plus Windows boundary-test fixes); green on all three systems at 744cc83, ci:full off. Review subagent review-b004-b (Opus, medium) running. Then docs-b-d2 (D-874), then
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

Outside the batch: #737 (ruleset 1.11.0, autonomy until v1.6, Colin's own change,
lane:infra, risk:high, head f9ef427). Critical review card review-737 (Opus 5.5 high)
proposed 18:40Z at the coordinator's request, started on Colin's go (local_ad2c2b47-68b1-452b-9bbb-c8f3d3eca845); the coordinator gives
the merge go. Round 1: changes requested, critical: yes, 2 must-fix (5529b81); the author is fixing and runs ci:full before round 2. After its merge: merge main into governance (THR-14). It shares
lane:infra with infra-b-i5's PR A, so whichever merges second rebases.

Reporting note: the coordinator reads only my first 400 characters, and the
wrap-up recap comes first. So on a ROLE-17 event, the recap itself starts with
`COORDINATOR:`. The 18:03Z plan hand-back was lost this way.

#737 merged as 1bebb96 at 18:55Z after round 1 with must-fix open; owner
override recorded as D-879 by the coordinator; review-737 stays idle. main merged
into governance (d06f563, ruleset 1.11.0). Main CI passed on all three systems for
204c188 (#735, run 45057369204) and 1bebb96 (#737, run 45057845400) at 19:07Z.

Watch for the coordinator (outside the batch): #741 (ruleset 1.12.0) ci:full on f9c4d5a; green on all three systems plus both browser shards at 19:47Z, and I told settings-max-autonomy (local_55e5365e-12fa-45a7-98ea-163c5932e7ad). The merge go is the coordinator's.

#741 (ruleset 1.12.0, autonomy until Colin says stop) merged by Colin as 3fb4d1b before any review; owner override D-880. The coordinator holds the old #741 review card; do not start it. main merged into governance (a1e4715, extracts 1.12.0). Main CI for 3fb4d1b passed on all three systems at 19:58Z (45062705718).

D-881 (Colin's word, via the coordinator): no more cards. Every implementation and review thread starts as a background dispatcher subagent (Agent tool, opus, worktree isolation when it writes files). The subagents write their own ledger entries. infra-b-i5 stopped after 2 PRs; its handoff is in plans/infra-b-i5-plan.md.

Slot A round 1 (review-b004-a, 2a80bc4): #740 changes requested, 0 must-fix,
2 should-fix (S1 the 1.5 s bound's reason, S2 a slow mark on one parametrize value),
fixed by the fresh subagent infra-b-i6 (Opus high). #742 approved, critical, gate
open; merge go asked of the coordinator.

#740 round 1 fixed by infra-b-i6 in e24fa58 (S1, S2; nothing deferred). Round 2
(aae0a89): approved, 0 must-fix, 0 should-fix. ci:full on e24fa58 running; then the
coordinator's go.

Merge gates: #735 gate open, go given, merged 204c188. #742 gate open (critical); the
coordinator gave the go pinned to 85dd312. Pre-merge check passed (macOS, Windows, Linux
and CI passed green; ci:full off). The app's permission check refused relaying the merge
to the review subagent, so the merge waits for Colin (pinned command in chat).
Escalations: none yet.
