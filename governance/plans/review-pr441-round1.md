# Review PR #441, round 1 (CLAUDE.md workflow summary)

Head reviewed: ecb4d7a, on main 8fb51ac. Non-critical (docs only). Checked against `rules/project-rules.yaml` 1.1.1 (D-702).

**Verdict: not approvable yet. There is one should-fix item (S1).** Everything else matches the rules.

## What I checked

- **Only `CLAUDE.md` changes:** 15 lines added and 11 removed, in four hunks. These are the intro line, the merge hard rule, the workflow section and the "Critical" heading. The three "until v1.0" lines now read "until v1.3 is finished". The "Goal of v1.0" heading stays, which is right, because it names the goal of v1.0. The commit message has no closing keyword.
- **The ten points against the rules file:**
  - 1 matches AUTO-01 and REP-01.
  - 2 matches LANE-01 to LANE-03 and THR-01.
  - 3 matches PLAN-01 and PLAN-02.
  - 4 matches TST-01 and TST-05.
  - 5 matches PR-04.
  - 6 matches PR-01 to PR-03.
  - 7 matches REV-01 to REV-03, REV-05, THR-05, PR-05 and PR-06.
  - 9 matches TST-07 and TST-08.
  - 10 matches ROLE-07, ROLE-09 and KB-03.
  - The dropped line "Colin is informed with one project-chat line per decision and per merge" was out of date; point 1 now states REP-01.
- **CI:** `CI passed`, `tests (ubuntu-latest)`, the browser run, lint, licences, security and CodeQL are green. `mergeable_state` is clean.

## Fix list

**S1. Point 8 asks for the three-system run before every merge, but point 7 and the rules ask for it only on critical PRs.**
- Point 7 says "the three-system run [is] for critical PRs on the final round only".
- Point 8 says the review thread merges "after a green run on Linux, macOS and Windows of that head", for any PR.
- MRG-02 says "Merge only with 'CI passed' green, and for critical PRs only after macOS and Windows succeeded on the reviewed head", and REV-03 says the same.

Fix: in point 8, write "The review thread squash-merges on the coordinator's go, pinned to the reviewed head, once `CI passed` is green on it. A critical PR also needs a green run on Linux, macOS and Windows of that head (D-580). Check that `tests (macos-latest)` and `tests (windows-latest)` succeeded on it; `CI passed` alone can still show the earlier Linux-only run." Keep the release/N.N sentence as it is.

Out of scope, as the coordinator said: the PR template's Risk comment ("until v1.0").
