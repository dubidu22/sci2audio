# Review PR #707, round 1 (batch B-I3, #683, D-848, D-849)

Thread: review-infra-b-i2 (Opus 5.5), the infra lane's review thread. Head reviewed: ffb0d7b. Date: 2026-11-20.
**Critical: yes** (CRIT-01, META-01: the ruleset, its config, the six role extracts and the governance check; `lane:infra`, `risk:high`). Plan `plans/infra-b-i3-plan.md`, approved as D-855. Owner approvals: D-848 (the #683 edits) and D-849 (the PLAN-01 wording).

**Verdict: changes requested** (0 must-fix, 1 should-fix, 5 notes).

## Verified

- Scope: 12 files, all in the plan:
  - `governance-config.json`, `claude-project-rules.yaml` and the six `rules/*.yaml`;
  - `.github/governance/promised_tests.py`;
  - `tests/unit/test_lanes.py`, `test_promised_tests.py` and the new `test_ruleset.py`.
  - `git diff 9066c3d..ffb0d7b -- .github/governance/pr-checks.json .github/labeler.yml` is empty.
- (1) Paths: I parsed the flow lists of all seven YAML files and compared them by hand, apart from the PR's tests.
  - `critical_paths`, `label_paths`, `doc_paths` and `governance_paths` are identical in the ruleset's `project_profile`, in all six extracts and in `governance-config.json`.
  - `critical_paths`, `doc_paths` and `governance_paths` equal `pr-checks.json`.
  - `label_paths` grouped by label equals `pr-checks.json`'s `label_paths`.
  - `github-setup/**` is `lane:infra` and not critical, as D-855 rules.
- (2) Rule text:
  - PLAN-01 in `claude-project-rules.yaml` and in `rules/implementation.yaml` equals the D-849 quote in `pending-decisions.md` character for character. I extracted both with a regex; no other extract carries PLAN-01.
  - `git diff -U0` of the YAML files shows only three changes: the `critical_paths` and `label_paths` lines, one added `governance_paths` line per file, and the PLAN-01 line in the two files. The headers (version, date) and every other rule are unchanged.
  - All seven YAML files and the config parse (`yaml.safe_load`, `json.load`).
- (3) Near-miss rule (`promised_tests.py`), checked with the PR's tests and my own probes:
  - The exact heading wins over a near-miss.
  - `#### TESTS PROMISED IN THE PLAN :`, `##Tests promised in the plan`, a CRLF `### …` and the six tested forms fail, naming the line.
  - A fenced `### Tests promised in the plan` is ignored.
  - A body with no heading-like line passes with the opt-in message. That includes prose such as "See the tests promised in the plan below.", `> ## …` and `## … (B-I3)`.
  - `files` gives nothing for a near-miss, so no collection runs.
- (4) Promised tests:
  - The seven node IDs exist, and the body lists them under the heading. Governance pr checks on ffb0d7b (seven runs, for example 44816483530) print `ok   promised tests: 7 of 7 collect`.
  - Run against `main`'s files (`git checkout 9066c3d -- governance .github/governance/promised_tests.py` in the review worktree, then restored), these fail: the 6 near-miss cases, the derivation test, PLAN-01 and `profile[governance_paths]`. The fenced and exact-heading tests pass, as the body says. See N2 for the others.
  - The derivation in `test_lanes.py::derived_pr_checks` equals the skill's `scaffold_workspace.py::pr_checks_config` line for line: the same grouping, `open_labels`, lock and locked labels, `critical_paths`, `doc_paths`, and `json.dumps(indent=2) + "\n"`. The one difference is `governance_paths`, which the test reads from the config. I compared against the skill's installed copy.
  - The line parsers in `test_ruleset.py` handle the YAML they read today: the profile block ends at its blank line 48 with all 19 keys read, and the rule blocks are 2/4-space indented in the ruleset sections and in `rules:`. See N4.
- (5) The dry-run diff in the PR body shows only `governance_paths` (`governance/**` against the seven working-file globs), as the plan predicted. That agrees with the scaffold code: `[ws + "/**"]`.
- (6) Issue #706 is open (v1.4, `lane:infra`, `risk:low`, chore) and is named in the body. The upstream skill change is on the owner's list.
- (7) Local run in a fresh `/tmp/review-707` at ffb0d7b:
  - ruff check: clean. ruff format --check: 387 files formatted.
  - lint-imports: 3 kept. deptry src: no issues.
  - `zizmor --offline .github/workflows`: no findings.
  - Fast suite with `-k "not espeak" -n auto`: 8658 passed, 6 skipped, 6 xfailed.
- CI: `ci:full` run 44814898215 (workflow_dispatch, ffb0d7b) is green, with `tests` on ubuntu, macOS and Windows a success. Governance pr checks is green.
- Licences: none.

## Findings

### S1 (should-fix, correctness): the exact heading is still found inside a fenced code block
`.github/governance/promised_tests.py:56` (`section`) and `:70` (`near_miss`) look for `HEADING` in every line, fences included. The near-miss search and the section body skip fences. Two failure scenarios:
- **A fenced example before the real section.** A PR body (a docs or playbook PR that explains PLAN-01, for example) shows the heading in a fenced example, and the real section follows. `section()` starts at the fenced copy. The fence's closing ```` ``` ```` is then read as an opening fence, and it swallows the rest of the body, the real section included. The result is `[]`, so the PR fails with "the section lists no node ID" although its promises are fine. Probe: ```` ```\n## Tests promised in the plan\n```\n### Tests promised in the plan ```` gives `section() == []` and `near_miss() is None`.
- **A fenced example and a near-miss.** With the exact heading only inside a fence and a near-miss outside, the near-miss message never shows, because `near_miss()` sees the fenced heading and returns `None`.

Both fail closed, but with the wrong reason, on bodies that PLAN-01 now makes common. This PR already shares `outside_fences()`. Fix: find the exact heading only among the lines `outside_fences()` yields, in `section()` and in `near_miss()` alike. Add a test with a fenced example before the real section.

### Notes
- N1: D-848 says "github-setup and tools as lane:infra and critical". D-855 reads "critical" as the lane:infra lock, so that `pr-checks.json` stays byte-identical. The PR follows D-855, and the reading is recorded there, so this is no finding.
- N2: these tests also pass on `main`: `test_every_extract_repeats_the_rules_and_the_profile_of_the_ruleset` (all 6 extracts) and `test_the_profile_holds_the_paths_of_the_config` for `critical_paths`, `label_paths` and `doc_paths`. `main`'s files agreed with each other then, so they are characterisation guards against a future revert, which is fine. But the plan said "each one fails on main", and the body names only two that passed. Correct the count in the body.
- N3: `test_every_extract_…` checks that every rule an extract holds equals the ruleset's. It does not check that an extract holds every rule whose `applies_to` names its role, so a regeneration that drops a rule from an extract would pass. Comparing the ID sets by `applies_to` would close that; this can go with S1 or later.
- N4: `test_ruleset.py:38`: `profile()` stops at the first line not indented by two spaces, a blank line included. A blank line or comment inside `project_profile` would silently shorten what `test_every_extract_…` compares. The four path keys would still fail loudly with a `KeyError`. Skipping blank lines inside the block would be more robust.
- N5: after the merge, merge `main` into the `governance` branch. Threads read their extracts from the governance worktree, which still has the old PLAN-01 and paths. The four files are identical on both branches today, so that merge is clean.

Verdict: changes requested. S1 is about five lines plus one test, in one fix commit; also edit the body for N2. Round 2 then checks that diff.
