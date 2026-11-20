# Plan: infra lane, batch B-I2 (#681, #687)

Thread: implementation, infra lane, Opus 5.5 high. Date: 2026-11-20. Base: `main` at caecf7a (after e76b3a3).
**Critical** (CRIT-01): both change `.github/**`; #687 adds a step to a CI workflow and a check that guards merges. Waits for coordinator approval (PLAN-02). `governance-config.json` and `project_profile` are not touched (#683 stays with Colin).

## One PR or two

**Two**, as the coordinator leans (D-75: each merges on its own):
- PR A (#681) changes only `critical_paths` in `.github/governance/pr-checks.json`, `.github/labeler.yml` and `tests/unit/test_lanes.py`.
- PR B (#687) adds `.github/governance/promised_tests.py`, a step in `.github/workflows/governance-pr-checks.yml`, `tests/unit/test_promised_tests.py` and two tests in `tests/unit/test_ci_workflows.py`.

No file is shared, so they need no order. Branches: `claude/infra-b-i2-kb-critical` and `claude/infra-b-i2-promised-tests`, both from `main`. Titles:
- `infra: KB process, contract and architecture documents are critical by path (#681)`
- `infra: the governance check fails when a promised test does not collect (#687)`

## #681: the path convention

The KB already names its documents by kind with a prefix. I use those prefixes rather than moving files, because a move would break the links across the KB and the decision log.

| Critical (process, contract, architecture) | Records (not critical) |
|---|---|
| `governance/kb/**/adr-*.md` (architecture decisions) | `governance/kb/**/audit-*.md` (dated audits) |
| `governance/kb/**/playbook-*.md` (process) | `governance/kb/**/working-*.md` (open questions) |
| `governance/kb/**/doc-*.md` (contracts and specs: pipeline architecture, accessibility requirements, voice and model licensing, ...) | `governance/kb/**/feature-*.md` |
| `governance/kb/README.md` (states the KB process) | `governance/kb/decision-log.md`, `pending-decisions.md` (D-703c) |
| | `governance/kb/merged-batches/**`, `governance/kb/00-index/**`, `governance/kb/**/tools/**` |

- The four critical globs are added to `critical_paths` in `pr-checks.json` and to `labeler.yml` under `risk:high`, in the same order. The existing test that the labeler matches `critical_paths` keeps them in sync.
- The `governance_paths` exemption does not change: the critical check runs for governance-only PRs too, so a sync PR that edits a playbook now fails without `risk:high`. The daily decision-log PR stays non-critical.
- The META-03 guard: a new KB file with no known prefix fails a test, so it gets a kind before it lands. The records list lives in that test, because it is the definition of "not critical".
- Alternative, not chosen: make all of `governance/kb/**` critical and exempt the decision log in `pr-check-exemptions.json`. That would make every audit and working-file sync `risk:high`, and the label would stop meaning anything.

Tests first (in `tests/unit/test_lanes.py`):
- `tests/unit/test_lanes.py::test_kb_process_contract_and_architecture_documents_are_critical`, parametrized over one `adr-`, `playbook-` and `doc-` file and `governance/kb/README.md`: critical FAIL without `risk:high`, ok with it.
- `tests/unit/test_lanes.py::test_the_decision_log_and_the_kb_records_are_not_critical`: `decision-log.md`, `pending-decisions.md`, an `audit-`, a `working-` and a `merged-batches/` file give no `critical` result.
- `tests/unit/test_lanes.py::test_every_kb_file_is_critical_or_a_record`: every tracked file in `governance/kb/` matches exactly one of the two lists.
- `tests/unit/test_lanes.py::test_the_labeler_marks_the_paths_the_check_holds_critical` exists already and covers the labeler.

Size: about 50 lines.

## #687: promised tests must collect

**Format.** The PR body carries a level-2 heading with this exact text: `## Tests promised in the plan`. The section runs to the next heading of level 1 or 2. Each backticked token in it that looks like a node ID is a promise. A node ID is a path to a `.py` file followed by `::name` one or more times (a class or parameters may follow). CRLF is accepted.

**Parser** (`.github/governance/promised_tests.py`, standard library only, beside `pr_checks.py`; the template copy of `pr_checks.py` stays unchanged):
- `promised(body: str) -> list[str] | None`: `None` when there is no heading, otherwise the node IDs in order with duplicates removed.
- `missing(promised, collected) -> list[str]`: a promise is kept when a collected ID equals it, starts with it plus `[` (a parametrized test named without its parameters), or starts with it plus `::` (a class named without its methods). Anything else is missing.
- CLI:
  - `files BODY`: prints the files to collect (empty when there is no heading).
  - `check BODY COLLECTED`: prints `ok   promised tests: N of N collect`, or `ok   promised tests: no "## Tests promised in the plan" section (opt-in)`, or `FAIL promised tests: not collected on the PR head: <id>, <id>`. It exits 1 on FAIL.
- A heading with no node ID under it is a FAIL ("the section lists no node ID"), so an empty promise cannot pass silently.

**Workflow** (`governance-pr-checks.yml`, same job, so it fails the required check `governance pr checks`; job name unchanged):
1. `astral-sh/setup-uv`, pinned to the SHA in `ci.yml` (v10.3.3).
2. A step "Check that the promised tests exist". `PR_BODY: ${{ github.event.pull_request.body }}` goes in `env:` only; the script runs `printf '%s' "$PR_BODY" > "$RUNNER_TEMP/body.md"`, so there is no `${{ }}` inside `run:` (template injection), and zizmor stays clean.
3. The step reads `files=$(python3 .github/governance/promised_tests.py files "$RUNNER_TEMP/body.md")`. Only when `files` is non-empty does it run `uv run --frozen pytest --collect-only -q -p no:cacheprovider <existing files> > collected.txt` (a non-zero exit is allowed, because collection errors show as missing IDs). A file that does not exist is not passed to pytest, and its IDs are missing.
4. Then `promised_tests.py check`.

Notes on the workflow:
- A PR without the heading never syncs: it costs one `setup-uv` (about 2 s), and nothing else changes.
- With the heading, `uv sync` plus collecting the named files takes about 30 s.
- The `edited` trigger already reruns the check when the body changes.
- What "PR head" means here: the job checks out the `pull_request` merge ref, which contains the head's tests. A test missing on the head is missing there too.
- Security: collecting runs the PR's conftest code, with the same read-only token and no secrets that `ci.yml` already runs PR code with.

Tests first:
- `tests/unit/test_promised_tests.py::test_a_body_without_the_heading_promises_nothing`
- `tests/unit/test_promised_tests.py::test_the_node_ids_under_the_heading_are_the_promises`
- `tests/unit/test_promised_tests.py::test_the_section_ends_at_the_next_heading`
- `tests/unit/test_promised_tests.py::test_a_heading_that_lists_no_node_id_fails`
- `tests/unit/test_promised_tests.py::test_a_crlf_body_reads_like_an_lf_body`
- `tests/unit/test_promised_tests.py::test_a_parametrized_or_class_promise_is_kept_by_its_collected_tests`
- `tests/unit/test_promised_tests.py::test_a_promise_that_does_not_collect_is_named_as_missing`
- `tests/unit/test_promised_tests.py::test_the_check_collects_the_real_files_and_names_the_missing_id`: an end-to-end run with the real `pytest --collect-only` on this file; it promises one existing ID and one invented ID, and expects exit 1 with only the invented ID named.
- `tests/unit/test_promised_tests.py::test_a_promised_file_that_does_not_exist_is_missing`
- `tests/unit/test_ci_workflows.py::test_the_pr_body_reaches_the_promised_tests_check_only_through_the_environment`
- `tests/unit/test_ci_workflows.py::test_the_governance_check_keeps_its_job_name_and_pins_setup_uv`

PR B uses the heading itself, listing the IDs above, so the check proves itself on its own PR. Size: about 90 lines of script, 15 of workflow, 170 of tests.

## Both PRs

- Checks: `uv run zizmor --offline .github/workflows`, and the fast checks locally with `-k "not espeak"`, one `uv run` at a time.
- PRs: labels `lane:infra` and `risk:high`; the body has `Closes`, tests as node IDs, and the licence note "none".
- After Linux CI is green: merge `main` in with a merge commit, set `ci:full`, report, and remove the label after the three-system run is green.
- Ledger: `governance/ledger/prs/pr-<N>.yaml` for each PR.
- No exemption is expected. A file that has to break a check goes in `pr-check-exemptions.json` with its reason.
- Follow-up, waiting for Colin (META-01): the plan-template wording that makes the heading mandatory, and the extracts' "tests first" list as node IDs. I will name it in PR B's body; it gets no Issue unless the coordinator wants one.
