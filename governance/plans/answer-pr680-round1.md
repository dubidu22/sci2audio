# Answer to review round 1 of PR #680

Thread: infra-b-i1 (implementation, Opus 5.5 high). Head reviewed: c6322ae. Fix commit: dc94e5f (one commit, Linux CI only).

## Fixed

- **S1** `tests/unit/test_ci_workflows.py`: the checkout step is now found by `actions/checkout@` rather than by the literal `# v7.0.1`. Each `uses:` line must have the form `<action>@<40-hex SHA> # v<N>[.<N>...]`, so a Dependabot bump that rewrites the version comment still passes. The `persist-credentials: false` assertion stays. Why: the old match would have failed a correct Dependabot PR.
- **S2** `.github/governance/pr-checks.json` (`critical_paths`) and `.github/labeler.yml` (`risk:high`) add `governance/tools/**`. `test_a_rules_change_needs_risk_high` now includes `governance/tools/ledger_tool.py`; I ran it red before the config change. Why: `ledger_tool.py gate` is the merge gate (MRG-01), a safety mechanism under CRIT-01. `governance/github-setup/**` stays non-critical as the template copy that never runs.
- **S4** The PR body names #681 under "Out of scope".

## Deferred, with an Issue

- **S3** #683 (v1.4, `lane:infra`, `risk:high`) lists the exact edits to `governance/governance-config.json` and `project_profile` in `governance/claude-project-rules.yaml` (`critical_paths`, `label_paths`, `governance_paths`), plus regenerating the extracts, for Colin's approval. These are ruleset files (META-01), so they are not in this PR. The PR body names #683.

## Notes

N1 to N5 are not changed. N1 and N3 stay as the review says. N2 is consistent with PR-05. N4: the two duplicated test helpers have about ten lines each; a shared module is not worth it in this PR. N5: CodeQL runs one job per language on push and PR; a concurrency group is optional, and zizmor reports it only in the pedantic persona.

Checks at dc94e5f: `tests/unit/test_ci_workflows.py tests/unit/test_lanes.py` 49 passed; ruff check and format clean; `uv run zizmor --offline .github/workflows` no findings.
