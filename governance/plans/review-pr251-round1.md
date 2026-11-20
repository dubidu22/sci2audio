# Review: PR #251 (release-day PR, replaces #245), round 1

14 Nov 2026 ~08:15 UTC on head 84589cd (draft, base release/1.0 87ba1f5, branch release-day/1.0.0). Content review only: **no merge** until Colin's listening test and screen-reader pass are in and the coordinator gives the go.

**Verdict: content approved, no fixes.**

- Diff against release/1.0 (87ba1f5): `docs/listening-tests/1.0.0.md` (new) and `docs/baseline.md`. The listening sheet is byte-identical to #245's (98388c2), so the #245 round-1 approval carries over (plans/review-pr245-round1.md).
- M4 rows (6582d04), checked:
  - Speed-script table: MPS 100.8 chars/s, real-time factor 6.41, load 16.62 s; CPU 135.2, 8.6, 1.52 s. Commit 87ba1f59d51b is release/1.0's tip. The machine is named by model, cores and memory, not host name (D-285).
  - Audio-job table, acl2023-hardt-ellipsis: speaking real-time factors match audio/speaking (1550.7/167.75 = 9.24 MPS, 1550.7/161.3 = 9.61 CPU). Characters per second is the job's own count, as for the Linux rows.
  - Budget lines: speech faster than real time with the device the app picks (MPS 9.24, needs at least 1): met. Estimate within ±25 %: met (MPS largest 24 %, CPU 8 %). Encoding at least 50× real time: met (1550.7 s / 10.3 s ≈ 150×, CPU ≈ 152×). Preparation 1.28 s for 9 pages: met.
  - Voice-engine table: M4 row with both devices and the note that CPU is as fast or slightly faster on this machine, with a 16.6 s MPS model load against 1.5 s. Install size left empty (not a checklist item).
- Still to come before the merge: Colin's listening scores and screen-reader pass, the dated changelog heading as the last commit, the branch up to date with release/1.0, and "CI passed" green.
- Merge note: the new "release branches" ruleset (target refs/heads/release/*) matches main's (deletions, force pushes, linear history, squash-only PRs, "CI passed" strict) except `require_extra_approval_for_unattributed_changes: true` (main: false). If the squash merge is refused for an approval, Colin turns that off.
