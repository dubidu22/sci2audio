# Plan: infra lane, batch B-I3 (#683, D-848, D-849)

Thread: implementation infra-b-i3, Opus 5.5 high. Date: 2026-11-20. Base: `main` at 9066c3d.
**Critical** (CRIT-01, META-01): it changes the ruleset, its config, the role extracts and the governance check. Labels `lane:infra`, `risk:high`. Waits for coordinator approval (PLAN-02).
One PR, branch `claude/infra-b-i3-ruleset-lanes`, title `infra: the ruleset carries the lanes of #665 and the promised-tests rule (#683)`.

## What I found

1. **The ruleset is generator output today.** The skill's `generate_project_rules.py --from-json governance/governance-config.json` reproduces `claude-project-rules.yaml` and all six extracts byte for byte (checked in a scratch folder). So `project_profile` and the extracts follow from `governance-config.json`.
2. **The stock generator cannot carry two of the approved edits.**
   - PLAN-01's text is hard-coded in the generator (line 969).
   - An unknown config key such as `governance_paths` is dropped with a warning, and the normalized config it writes back loses that key.
   - A plain re-run would therefore undo D-849 and the new key.
3. **The stock scaffold cannot reproduce today's `governance_paths`.** `scaffold_workspace.py --github` writes `pr-checks.json` with `governance_paths` derived from `workspace_root`, which gives `["governance/**"]`. Today's file holds the seven docs-lane working-file globs. The order of the `lane:docs` globs also differs: today's file has `*.md` first, the config has `docs/**` first.
4. **The project has no tool of its own for this.** The generator and the scaffold live in the claude.ai skill, outside the repository (about 2,400 lines). The skill folder states no licence, so vendoring them is refused by the licence gate.

## Design

**(a) Config and `project_profile`, aligned with today's `pr-checks.json`.**
- `governance/governance-config.json`:
  - `critical_paths` appends nine globs: `governance/claude-project-rules.yaml`, `governance/rules/**`, `governance/project_instructions.md`, `governance/governance-config.json`, `governance/tools/**`, `governance/kb/README.md`, `governance/kb/**/adr-*.md`, `governance/kb/**/playbook-*.md`, `governance/kb/**/doc-*.md`. These are the #683 list plus #691's KB globs, in today's order.
  - `label_paths` appends the six `lane:infra` entries of #683.
  - The `lane:docs` entries are reordered and extended to today's order: `*.md`, `docs/**`, `docs/design/**`, `.claude/**`, then the seven governance working files.
  - A new key, `governance_paths`, holds the seven working-file globs.
- `github-setup/**` stays `lane:infra` but is **not** critical, as in today's `pr-checks.json`. D-848's wording ("github-setup and tools as lane:infra and critical") is read against the instruction that the file must stay byte-identical. If the coordinator wants `github-setup/**` critical, that changes `pr-checks.json` and `labeler.yml` as well. **This is the one open point.**
- `project_profile` in the ruleset and in all six extracts is regenerated from the config with the stock generator, into a scratch folder. Only `claude-project-rules.yaml` and `rules/*.yaml` are copied over; the generator's own `governance-config.json` and `project-state.yaml` outputs are thrown away. `governance_paths: [...]` is then inserted after `doc_paths` by exact replace, in the ruleset and in all six extracts.

**(b) PLAN-01.** An exact replace of the rule text in `claude-project-rules.yaml` and in `rules/implementation.yaml` (the only extract that carries PLAN-01) with the D-849 wording, verbatim.

**(c) Extracts.** Regenerated as in (a), with the two exact replaces of (a) and (b). Then the line counts are compared and every edited YAML file is parsed once with `uv run python -c "import yaml..."`, following the memory rule on verifying state-file edits.

**(d) Dry run and a lasting guard.** The PR body records two things:
- The stock-scaffold dry run: `scaffold_workspace.py --from-json governance/governance-config.json --out-dir <scratch> --github`, then `diff` against `.github/governance/pr-checks.json`. I expect it to be identical except for `governance_paths` (see finding 3), and the body shows that diff.
- The in-repo derivation (below), which gives a byte-identical result.

Because the stock tools cannot hold the edits, the guard goes one step up (META-03), as CI tests that fail when a re-run reverts them:
- `tests/unit/test_lanes.py` gains a derivation that mirrors the scaffold's `pr_checks_config`, about 15 lines. It groups `label_paths`, copies `critical_paths` and `doc_paths`, sets the open, lock and locked labels, and reads `governance_paths` from the config. It asserts `json.dumps(derived, indent=2) + "\n"` equals the bytes of `pr-checks.json`.
- A new `tests/unit/test_ruleset.py` pins three things:
  - PLAN-01 is the D-849 wording in the ruleset and in the implementation extract.
  - Every rule block and the `project_profile` block of each extract equal the ruleset's.
  - `project_profile`'s `critical_paths`, `label_paths` and `governance_paths` equal the config's.
  - It uses a line parser, because PyYAML is only a transitive dev dependency (as in `test_lanes.py`). The flow lists are JSON, so they are read with `json.loads`.
- Not chosen: a repo tool `governance/tools/pr_checks_config.py` that writes `pr-checks.json`. It would be a second copy of the scaffold to maintain. The test is the check that matters, and the stock scaffold stays the writer.

**(e) A near-miss heading fails.** Changes to `.github/governance/promised_tests.py`:
- When the exact heading `## Tests promised in the plan` is absent, a line outside fenced code blocks that matches the heading loosely is a near-miss. That means any case, 0 to 6 `#`, leading spaces, an optional `**` or `__`, `the` optional, and a trailing `:` or `.`.
- `check` then prints `FAIL promised tests: near-miss heading "<line>"; write it exactly as ## Tests promised in the plan` and exits 1.
- A body without any such line still passes as before. The KB thread's decision-log PRs, Dependabot PRs and fix-only PRs have no plan, so absence cannot fail on every PR. PLAN-01 binds implementation threads, and the reviewer checks that the heading is present. The `(opt-in)` message stays.
- `files` keeps returning nothing for a near-miss, so no collection runs.
- The docstring says so.
- No workflow change is needed: the existing step already fails the job on exit 1.

## Tests promised in the plan

Written first. On `main`, 9 of these 20 cases fail. The other 11 pass there and guard against a revert or against over-matching, as the PR body lists (round 1, N2):
- `tests/unit/test_promised_tests.py::test_a_near_miss_heading_fails` (parametrized: `### …`, trailing `:`, a leading space, lower case, a bold plain line, a line without `#`)
- `tests/unit/test_promised_tests.py::test_a_near_miss_inside_a_code_block_is_not_a_heading`
- `tests/unit/test_promised_tests.py::test_the_exact_heading_wins_over_a_near_miss`
- `tests/unit/test_promised_tests.py::test_a_fenced_example_of_the_heading_does_not_start_the_section` (round 1, S1)
- `tests/unit/test_promised_tests.py::test_a_fenced_heading_does_not_hide_a_near_miss` (round 1, S1)
- `tests/unit/test_lanes.py::test_pr_checks_json_is_derived_from_governance_config`
- `tests/unit/test_ruleset.py::test_plan_01_carries_the_promised_tests_wording`
- `tests/unit/test_ruleset.py::test_every_extract_repeats_the_rules_and_the_profile_of_the_ruleset`
- `tests/unit/test_ruleset.py::test_the_profile_holds_the_paths_of_the_config`

The existing tests stay green: `tests/unit/test_lanes.py` as a whole, and `tests/unit/test_promised_tests.py::test_a_body_without_the_heading_passes_the_check`.

## Checks, PR, ledger

- Local checks, one `uv run` at a time: `uv run ruff check && uv run ruff format --check && uv run lint-imports && uv run deptry src && uv run pytest -m "not slow and not benchmark and not browser" -k "not espeak"`, and `uv run zizmor --offline .github/workflows`.
- PR body:
  - `Closes #683`, D-848, D-849.
  - The section `## Tests promised in the plan` with the node IDs above, so the check runs on its own PR.
  - The dry-run diff.
  - Licence note "none". Risk: the governance check gets stricter and the ruleset changes.
- Ledger: `governance/ledger/prs/pr-<N>.yaml` like `pr-692.yaml`.
- `github-setup/pr-checks.json` (the scaffold's stale copy) is left as it is.
- Size: config about 30 lines, ruleset and extracts about 15, script about 20, tests about 150.

## Out of scope, follow-ups

- The skill's generator and scaffold should read `governance_paths` and keep the D-849 PLAN-01 wording, so a re-run needs no hand step. That is an upstream skill change and the owner's call. I will name it in the PR body; the tests above catch a revert until then.
- `governance/github-setup/pr-checks.json` is stale against `.github/governance/pr-checks.json`. It gets an Issue only if the coordinator wants one.

Handoff (THR-07): goal: PR #707 (#683, D-848, D-849) merged. Done: approved (D-855), PR open at ffb0d7b, Linux and three-system run (44814898215) green, ci:full removed, Issue #706, ledger pr-707.yaml. Next: wait for plans/review-pr707-round1.md, then one fix commit and plans/answer-pr707-round1.md.
