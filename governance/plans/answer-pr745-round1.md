# PR 745, answer to review round 1

Thread: ruleset-d882. Round report: `plans/review-pr745-round1.md` (head 4473133). One fix commit: `095cb2a`.

## Fixed

- **M1 (unsound-guard).** The ledger-gate step now runs directly after checkout, before `pr_checks.py` and the promised-tests collection, which run the PR's code and could otherwise rewrite `$GITHUB_ENV`, `$GITHUB_PATH` or the runner for a later step. The title step gets `if: ${{ !cancelled() }}`, so it still runs when the gate fails first. `governance/github-setup/pr-checks-workflow.yml` is byte-equal again. The step comment now says why it is first. `test_the_governance_check_gates_a_risk_high_pr_on_the_ledger_of_branch_governance` pins checkout first, the gate second and `if: !cancelled()` on every later named step. The PR body's guarantee and residual risk are reworded to match.
- **S1 (weak-guard).** `approved` counts only a full 40-character SHA, equal to `--head`, in the round's `head`, its `updated_head` and an override's `head` (`exact_head`). The CLI refuses a short `--head` with exit 2. The README says to write round and override heads in full. New test: `test_approved_needs_the_full_head`. `gate` keeps prefix matching (N4 is left as is).
- **S2 (missing-test).** `test_the_approved_command_exits_0_1_or_2` runs the CLI as CI does: 0 for the approved head; 1 for another head and another PR; 2 for a short or missing `--head` and a missing ledger.
- **S3 (missing-test).** `test_the_ledger_readme_documents_the_d882_formats` pins the gos row and section, `merged`, `updated_head` and the `approved` lines.
- **S4 (incomplete-residual-risk).** The release branches run their old workflow without the gate. This is named in the PR body and deferred to #747 (lane:infra, risk:high).
- **N6.** The revert message now says "no round or PR entry that records a merge".
- **N7.** The step starts with `set -o pipefail`, so a failed `git archive` fails as itself. The test pins it.

## Not changed

- **N1–N3:** owner-approved wording, for a later ruleset.
- **N4:** `gate` keeps prefix matching and the override-at-`updated_head` behaviour it had before.
- **N5:** the merge-date fallback; harmless on the live ledger.
- **N8:** the bootstrap fallback stays until this PR is on main, because this PR's own runs need it. `seam_status` has no seam groups here.

## Checks on 095cb2a (local, macOS)

- ruff check and ruff format --check are clean. zizmor finds nothing in the workflows.
- 145 tests pass in `test_ruleset.py`, `test_ledger_tool.py`, `test_ci_workflows.py`, `test_lanes.py` and `test_promised_tests.py`.
- The moved step was run under `bash -e` against the live `governance` ledger:
  - #742 with its full head: exit 0;
  - #742 with a 7-character head: exit 2;
  - #745 at 4473133: exit 1 (round 1 changes_requested);
  - no `risk:high` label: exit 0.
