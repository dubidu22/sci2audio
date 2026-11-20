# Review of PR #516, round 1 (final)

PR: https://github.com/dubidu22/sci2audio/pull/516 "docs: tie autonomy wording to the state file, name the current goal"
Branch: docs/claude-md-autonomy-horizon. Reviewed head: f6d1294 (4 commits). Base: main 96de4a3 (main tip at review time, so not behind).
Criticality: critical (CLAUDE.md is a KB process document, CRIT-01), labels risk:high + lane:docs. Review on Opus high.
Reviewed against: rules/project-rules.yaml 1.4.4, rules/project-state.yaml (updated 18 Nov 13:40Z), governance audit 18 Nov items M1 and S6.

## Verdict: APPROVED, 0 blocking findings

## Checks

| Check | Result |
|---|---|
| Diff scope | CLAUDE.md only, +8/-8. No code, test or workflow change. |
| M1: every "until v1.3 is finished" replaced | Yes, all five (intro, hard rule, item 1, critical heading, plus the merge rule). `grep` for v1.3 / v1.0 on the head finds nothing left. New wording "while the autonomy grant in `rules/project-state.yaml` holds" matches AUTO-01 ("until the horizon in project-state.yaml") and state `autonomy_horizon` (D-740). |
| Stale "Goal of v1.0" replaced | Yes: "Product and current goal" points at `milestones_in_progress` in project-state.yaml and the roadmap in the KB decision log (roadmap entries D-453 to D-463, D-573, D-666 are there). "English first" corrected to "English and German" (D-454). |
| PLAN-04 acceptance criteria | Item 2: "An Issue without acceptance criteria is not started; ask the coordinator for them first (PLAN-04)." Matches PLAN-04 word for word in substance; stronger than the old "Stop if...". |
| TST-07/TST-08 order | Item 9: same-day quarantine with linked Issue first, then 40+ isolation runs, result into the Issue, fix and lift quarantine on a code cause. Matches 1.4.3 (D-739). The old contradicting "run 40 times before quarantining" is gone. |
| LANE-02 concurrency | Item 2: several lanes in parallel while they do not block each other, at most one implementation + one review thread per lane, blocking on shared files/goldens/regression cases/layer contract. Matches LANE-02 1.4.4 (D-741). The D-705 one-thread wording is gone. |
| Nothing of Colin's dropped or weakened | Checked each changed line against the old text: roadmap/product scope stays Colin's; round-4 hard stop (item 7) unchanged; implementation threads never merge unchanged; critical definition unchanged; reporting rule (D-626, D-702g) unchanged. |
| PR body | Attribution lines present at the top; no closing keyword; risk and out-of-scope stated. Commit messages have no "fixes #N". |
| CI on f6d1294 | Linux CI green; ci:full three-system run green: tests (ubuntu-latest), tests (macos-latest), tests (windows-latest), browser (Linux, Chromium), lint and layers, licences, security, CodeQL, and both `CI passed` runs success. Read, not rerun. Mutation and nightly seeds do not apply (docs only). |

## Non-blocking notes (deferred to issue #526)

1. Item 2 does not name the LANE-02 exception for a bug Colin marks as priority (own parallel thread, D-732), so it reads stricter than the rule. Coordinator-only rule; no thread is misled into a wrong action.
2. Item 9 omits "per browser" from the 40-run isolation (TST-08, D-682). Pre-existing wording, not introduced by this PR.

Both go into the next CLAUDE.md docs PR: https://github.com/dubidu22/sci2audio/issues/526

## Fix list for the author

None. Branch stays frozen; the review thread merges pinned to f6d1294.
