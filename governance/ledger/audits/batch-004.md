# Audit: batch 004 (#737, #741, #742, #740, #745, #749; critical_only)

- Mode: critical_only (ROLE-09), audit thread audit-batch-004, 23 Nov 2026. Report: `plans/audit-batch-004.md`.
- Verdict: **pass, 0 blocking, 3 should-fix, 7 notes.**
- Should-fix: F1 the ledger shows #741 and #721 as open though both are merged by hand (`merged: ""`), so `stats` undercounts (check: `check` matches `(#N)` squash subjects on main and release/*). F2 #745's S4, deferred to #747 in the approving round, has no `deferred/` entry and `triage` misses it (check: a round `deferred:` count). F3 milestone v1.4 still holds #731 (owner, or the coordinator closes it as superseded by #751).
- Held: all six squash trees equal the reviewed or override head merged onto main; three systems green on every reviewed final head; D-883 governance merge clean (tag f12fe96, empty diff); no critical PR touched src, dependencies, licences, corpus or snapshots.
- Notes: N1 two ruleset overrides in one day (owner, if it repeats); N2 the gate's PR-tool fallback is live for #747's release port (check); N3 review tags in `governance/tools` are outside `test_review_tags.py`'s roots (check); N4 lane config still lists the working paths (leave); N5 clock-bound margins (leave); N6 ledger details, the go is D-890 (leave); N7 batch settings stale (leave).
- Repeated kinds in this batch: `weak-guard` (#740, #745), `missing-test` (#745). META-03 proposal: each new check under `.github/` or `governance/tools/` lands with a must-fail case and a near-miss.
