# Review PR #745, round 2 (#743: ruleset 1.13.0, the dispatcher changes of D-882)

Thread: review-745 (Opus 5.5), critical review subagent. Author: ruleset-d882. Head reviewed: 095cb2a5596ce0c7671b2db746df09e41569a307 (one fix commit on 4473133). Base: 4ca072a (main). Date: 2026-11-22.
**Critical: yes** (as in round 1). Answer file: `plans/answer-pr745-round1.md` (commit 39e1c6f).

**Verdict: approved** (0 must-fix, 0 should-fix, 3 notes). Final round. Before the merge: a three-system run of 095cb2a (D-580, CRIT-02), the `governance pr checks` re-run after this entry is pushed (MRG-01), and the coordinator's go file `gos/pr-745.yaml` for this head.

## Round 1 findings against the code

- **M1, fixed.** In `.github/workflows/governance-pr-checks.yml` the gate step is now the first step after `actions/checkout`, ahead of `pr_checks.py` and the promised-tests collection, so no PR code has run in the job when it decides. The title step has `if: ${{ !cancelled() }}`. I checked in run 45074844131 on 095cb2a that the later steps still run after the gate fails: title, setup-uv and promised tests all succeeded there. `governance/github-setup/pr-checks-workflow.yml` is byte-equal (`cmp`). The test now asserts checkout first, the gate second, and `if: !cancelled()` on every later named step. VER-02: I put the 4473133 workflow back under the new test and it fails (`steps[1]` is the title step), then I restored it. The step comment and the PR body ("directly after checkout and before any step that runs the PR's code"; "Not covered") now match the code. The bootstrap copy is still taken from the PR, but only while the base has no `def approved(`, which stops being true once this PR is on main.
- **S1, fixed.** `exact_head` accepts only two equal 40-hex SHAs, compared case-insensitively. `approved` uses it for the round's `head`, the round's `updated_head` and an override's `head`. The CLI refuses an `--head` shorter than 40 characters with exit 2. `test_approved_needs_the_full_head` covers short round heads, short `--head` values, short override heads and upper case. `gate` keeps prefix matching, as I asked. The README usage line says to write heads in full (see N1).
- **S2, fixed.** `test_the_approved_command_exits_0_1_or_2` runs the tool with `subprocess` against a `tmp_path` ledger. It expects 0 for the approved head; 1 for another head and for another PR; 2 for a short `--head`, a missing `--head` and a missing ledger.
- **S3, fixed.** `test_the_ledger_readme_documents_the_d882_formats` pins the gos writer row, the gos format heading, the PR format's `merged` comment, the `updated_head` line and both `approved` usage lines.
- **S4, deferred.** The body names it under "Not covered" with #747 (`risk:high`, `lane:infra`, open). The issue has no milestone (N3).
- **Round 1 notes.**
  - N6 and N7 are fixed: the revert message is reworded, and the step now starts with `set -o pipefail`, which the test pins.
  - N1–N5 and N8 stay as they are, for the reasons the answer file gives. I accept them.

## Anything the fix broke

- The diff 4473133..095cb2a touches only the six files the answer file names. The ruleset, the extracts, the config and `dispatcher_instructions.md` are unchanged since round 1, so the round 1 extract and rule checks still hold.
- Live ledger, running the head's tool against it (`--ledger /Users/colinmeng/Projekte/sci2audio-governance/governance/ledger`): `check` reports no problems. `approved 745` at 095cb2a fails, as the CI log of run 45074844131 shows: "round 1 is for head 4473133…, not for this head". That is right before this round entry exists.
- The only open PR on GitHub is #745, so stopping on short heads breaks no PR in flight. `rounds/pr721-round1.yaml` (`050fb99`) and `overrides/pr-741.yaml` (`f9c4d5a`) have short heads, but neither PR is open.
- Local checks on 095cb2a:
  - `ruff check` and `ruff format --check` are clean.
  - `lint-imports`: 3 contracts kept, 0 broken.
  - `pytest tests/unit/test_ruleset.py test_ledger_tool.py test_ci_workflows.py test_lanes.py test_promised_tests.py`: 145 passed.
- CI on 095cb2a:
  - CodeQL is green and `CI` is running (Linux).
  - `governance pr checks` (45074783044, 45074821058, 45074844131) fails only in the gate step, as designed until this entry is on `governance`.
  - No three-system run of 095cb2a exists yet.

## Notes (no change needed)

- **N1.** `governance/ledger/README.md`: the format examples still show `head: 3f9c2ab` for a round entry and for an override, while the new usage line says to write those heads in full. A thread that copies the example gets a red check with a clear message: "the check takes only a full 40-character SHA". This fails closed. Align the examples when the README is next touched.
- **N2.** The new comments and docstrings cite "review-745 M1/S1/S2/S3", a thread name, not a durable reference. Each one also says why, so it is not a narrating comment. #745 would be the lasting reference when the file is next touched (PR-05).
- **N3.** #747 has no milestone (GH-01 asks for milestone, lane label and risk label). This is for the coordinator; it is not part of this PR.
