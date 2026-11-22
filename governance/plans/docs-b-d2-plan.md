# docs-b-d2 plan: #746 (D-874), batch 004, slot B item 3

Thread `docs-b-d2`, Opus 5.5 high. Ruleset 1.12.0. Issue #746 (milestone v1.4,
`lane:infra`, `risk:high`).
**Critical** (CRIT-01): it adds a CI check under `.github/` (a safety
mechanism, CI workflow) and changes once how branch `governance` takes in
`main`. One PR, `lane:infra` + `lane:docs`, `risk:high`, author `ci:full` run
before review (D-698). Waits for the coordinator's approval (PLAN-02).

## 1. What counts as a working file

| Path on main | Verdict | Why |
|---|---|---|
| `governance/plans/**` | working file, removed | THR-13: plans, round reports, batch files |
| `governance/ledger/**` | working file, removed | THR-13: ledger entries (`implementation.md`, `review.md` are the old hand tables, still appended on governance) |
| `governance/project-state.yaml` | working file, removed | THR-13: state |
| `governance/kb/pending-decisions.md` | working file, removed | THR-13; `kb/README.md` already calls it one |
| `governance/plans/README.md`, `governance/ledger/README.md`, `governance/ledger/deferred/since.txt` | **kept** | written on main by the ruleset generator through ruleset PRs (#728, #730; #745 edits `ledger/README.md` now), so main holds the copy that counts, as THR-14 says for the ruleset |
| rest of `governance/kb/**` (decision log, KB documents, `merged-batches/`), `governance/memory/**`, `governance/release/**`, `governance/workflow-export.md` | kept | not in THR-13's list; the decision log changes on main by PR (THR-14); the others are archives, byte-equal on both branches today |

On main today: 768 files under `plans/` besides its README, 2 ledger tables,
the state file and the pending file: **772 deletions**. Every one exists on
`origin/governance` (checked: `git diff --name-status origin/main
origin/governance -- governance` shows 166 A and 4 M, no D).

## 2. Readers of these paths on main (all searched: workflows, `.github/**`, `governance/tools`, `governance/github-setup`, `tests/`, `src/`, `docs/`, `CLAUDE.md`, `.claude/`, `pyproject.toml`)

| Reader | What it does with the paths | After this PR |
|---|---|---|
| `.github/governance/pr_checks.py` + `pr-checks.json` (`governance pr checks`) | matches PR paths against `governance_paths` and `label_paths` globs; reads no file | unchanged; `governance_paths` unchanged, so the decision-log PR stays governance-only |
| `.github/governance/promised_tests.py` | reads the PR body only | unchanged |
| `.github/workflows/governance-pr-checks.yml` | today: none. #745 (D-882) adds a step that reads the ledger from `origin/governance` (`git archive`) | consistent with this PR; no edit, so no overlap with #745 |
| `governance/tools/ledger_tool.py` | reads `--ledger`, default `../ledger` next to the script; `seam_status` reads `governance-config.json` beside the ledger | unchanged; the dispatcher and coordinator run it in the governance worktree, where all entries stay; run from a main checkout it now sees an empty ledger (gate fails closed) instead of a stale one |
| `tests/unit/test_lanes.py` | path strings only; `tracked_files("governance/kb")` needs more than 40 files (about 50 remain) | passes unedited |
| `tests/unit/test_promised_tests.py`, docstrings in `tests/**` and `src/sci2audio/textprep/citations.py` | name plan files as references | unchanged; the files are on branch governance, which some already say |
| `pyproject.toml` ruff `extend-exclude = ["governance", ...]`; `testpaths = ["tests"]` | plan scripts (`plans/**/*.py`) are neither linted nor collected | unchanged |
| `CLAUDE.md` | `governance/project-state.yaml` once, `rules/project-state.yaml` five times (a path that does not exist) | all six say "`project-state.yaml` on branch `governance`" |
| ruleset text (`claude-project-rules.yaml`, `project_instructions.md`, `dispatcher_instructions.md`, `claude-md-snippet.md`) | `./governance/...` paths read in the governance worktree | unchanged (META-01; THR-13 already says where they live) |
| `.claude/rules/*`, `docs/**`, other workflows, `.github/scripts/*` | none | — |

## 3. Design

Files:

1. **Delete** the 772 working files (section 1).
2. **New `governance/README.md`**, exactly one line, also the check's hint:
   ``Working files (plans, round reports, batch files, ledger entries, `project-state.yaml`, `kb/pending-decisions.md`) live only on branch `governance` (THR-13, D-874): `git worktree add ../sci2audio-governance governance`.``
   Worded so it is also true on branch governance, where the merge brings it.
3. **New `.github/scripts/working_files.py`** (standard library, beside
   `ci_passed.py` and `isolate.py`): `WORKING` prefixes and files, `KEPT` (the
   three generator files), `POINTER`, `working_files(paths) -> list[str]`, and
   `main(argv) -> int` that reads `git ls-files -z` (optional `--root`). Exit 1
   with one line per hit `working file on this branch: <path>`, then `POINTER`;
   exit 0 with `no working files on this branch`.
4. **`.github/workflows/ci.yml`**: one step in job `lint and layers`, after
   deptry: `name: No working files on this branch (D-874)`,
   `run: python3 .github/scripts/working_files.py`. `CI passed` needs `lint`, so
   the required check goes red.
5. **`CLAUDE.md`**: the six state-file mentions (section 2).
6. **New `tests/unit/test_working_files.py`** (section 4).

Choices, with the alternatives:

- **Check location: a project-owned script plus a `ci.yml` step** (chosen).
  (a) Add it to `pr_checks.py` / `pr-checks.json`: these are the governance
  skill's generated files with byte-equal scaffold twins (#710); the next
  ruleset regeneration would drop the check unless the skill learns it, and
  `governance-pr-checks.yml` is also what #745 edits. (b) A fast pytest test
  that scans `git ls-files` itself: no `.github` change, but it would fail
  whenever pytest runs in the governance worktree, so it would need a branch
  name test inside the test. The CI step exempts branch governance by its
  triggers instead, and the unit tests keep the logic tested.
- **Tree scan, not diff scan** (chosen): the check lists the tracked files of
  the checkout (on a PR, the merge commit), so it says "no working file is on
  this branch", which is what D-874 asks, whatever the PR's diff status (add,
  rename, copy). A diff scan would also pass a branch that still has stale
  copies. Release branches cut before this PR do not carry the step, so a PR
  into `release/1.4` is not affected.
- **Governance branch exemption by trigger** (chosen): `ci.yml` runs on
  `pull_request` and on `push` to `main` and `release/**`; branch governance
  never opens a PR into main (THR-14), so it never runs there. A test pins the
  push branches. No branch name in the script. If a PR from governance into
  main were ever opened, failing is right.
- **Pointer: one new `governance/README.md`** (chosen). Alternatives: a line
  at the top of `plans/README.md` and `ledger/README.md` (generator-owned, lost
  on the next regeneration); a one-line stub at each removed path (stubs look
  like files, and the governance merge would have to keep 772 of them out).
  Cost: no lane owns `governance/README.md`, so `governance pr checks` prints
  one `unowned` WARN (not a failure), in this plan-approved PR.
- **The three generator files stay on main** (chosen): removing
  `ledger/README.md` would collide with #745 and with every regeneration.
- **One-time merge of main into governance keeps the working files**
  (required, not optional). Simulated in a scratch repository: a plain
  `git merge main` silently deletes every working file governance has not
  changed since the move (most of the 768 plans) and stops with
  modify/delete conflicts on the four it changed. The dispatcher's THR-14 merge
  after this PR therefore runs, in the governance worktree:

  ```
  git pull --rebase && git fetch origin main
  old=$(git rev-parse HEAD)
  git merge --no-ff --no-commit origin/main
  git checkout HEAD -- governance/plans governance/ledger governance/project-state.yaml governance/kb/pending-decisions.md
  git diff --cached --stat "$old" -- governance/plans governance/ledger governance/project-state.yaml governance/kb/pending-decisions.md
  git commit -m "Merge main into governance after #<N>; working files kept (D-874)" && git push
  ```

  The `diff` prints nothing only when every working file is kept (kept
  generator files are identical on both sides today, so they do not show).
  In the simulation the next plain merge was safe: main never touches these
  paths again, which the check guarantees. The PR body repeats these lines
  under "After the merge (dispatcher)".

## 4. Tests promised (PLAN-01)

All fast, no network, in `tests/unit/test_working_files.py`; the temporary
repositories use the `git` every runner has.

- `tests/unit/test_working_files.py::test_a_working_file_is_found` (parametrized: a plan, a round report, a batch file, `ledger/prs/pr-1.yaml`, `ledger/rounds/pr1-round1.yaml`, `ledger/deferred/pr1-1.yaml`, `ledger/implementation.md`, `project-state.yaml`, `kb/pending-decisions.md`)
- `tests/unit/test_working_files.py::test_the_generated_files_stay_on_main` (parametrized: the three kept files)
- `tests/unit/test_working_files.py::test_other_governance_files_are_not_working_files` (parametrized: decision log, `kb/README.md`, a merged batch, memory, release, `workflow-export.md`, the ruleset, `tools/ledger_tool.py`, `github-setup/pr_checks.py`)
- `tests/unit/test_working_files.py::test_every_working_path_is_a_governance_path` (so `pr_checks.py` keeps treating them as governance files)
- `tests/unit/test_working_files.py::test_the_check_fails_on_a_tracked_working_file` (exit 1; the hit line and the pointer line)
- `tests/unit/test_working_files.py::test_the_check_passes_on_a_clean_tree`
- `tests/unit/test_working_files.py::test_the_pointer_file_is_the_line_the_check_prints`
- `tests/unit/test_working_files.py::test_ci_runs_the_check_in_the_lint_job`
- `tests/unit/test_working_files.py::test_ci_pushes_run_on_main_and_release_branches_only`

Test first: the failing-check test and the CI-step test are written before the
script and the step; the repository's own clean tree is proven by the CI step
on the PR itself. Existing suites that must stay green unedited:
`tests/unit/test_lanes.py`, `tests/unit/test_ci_workflows.py`,
`tests/unit/test_ledger_tool.py`, `tests/unit/test_promised_tests.py`.

## 5. PR split and size

One PR, `infra: working files leave main, and a check keeps them off (#746)`,
labels `lane:infra`, `lane:docs`, `risk:high`. Not split (D-75): the check
fails CI until the deletions are in, so an infra PR cannot merge alone, and a
docs-only deletion PR would leave main without the guard and need a second
one-time governance merge. `lane:infra` files: `.github/scripts/working_files.py`,
`.github/workflows/ci.yml`. `lane:docs` files: the deletions, `CLAUDE.md`.
Lane-free: `governance/README.md` (one WARN), `tests/unit/test_working_files.py`.
Waits for the open `lane:infra` PR #745 to merge (LANE-02, the lock); no file is
shared with it.

Size: 772 deletions (mechanical, listed with `--diff-filter=D`); about 60 lines
of script, about 130 of tests, 2 lines of `ci.yml`, 1 line of pointer, 6 lines
of `CLAUDE.md`. `governance pr checks` will WARN on two deleted probe files that
look like tests (`plans/b8-review/test_zz_probe_fold.py`,
`plans/review-pr481-round1-probes/test_gaps481.py`); neither is collected
(`testpaths = ["tests"]`), and both stay on branch governance.

## 6. Open choice for the coordinator

One: whether the three generator files (`plans/README.md`, `ledger/README.md`,
`ledger/deferred/since.txt`) stay on main as this plan says, or go as well
(which needs the governance skill to stop writing them on main, and collides
with #745). Recommended: keep them.

## Handoff (THR-07)

- Goal: #746 (D-874): working files off main, a one-line pointer, and a CI check that fails when one comes back.
- Done: plan approved (D-883, the three generator files stay). Branch `claude/docs-b-d2-746` at deca673 (pushed, no PR): 772 deletions, `.github/scripts/working_files.py`, the `ci.yml` step, `CLAUDE.md`, `governance/README.md`, `tests/unit/test_working_files.py` (all 31 pass). ruff, format, lint-imports, deptry clean.
- Next: question to the coordinator (below); then rebase onto main after #745 merges, fast checks, PR with `ci:full`, ledger entry.

Status: question. The approved pointer path breaks an existing test.
`tests/unit/test_lanes.py::test_every_file_of_the_workspace_and_the_design_record_has_exactly_one_lane`
fails on `governance/README.md`: no lane owns it (section 3 expected only an `unowned` WARN from
`governance pr checks` and missed this test). Fixing it means deviating from the plan (PLAN-01), so it needs a D-number.
Options: (a) add `governance/README.md` to `lane:docs` in `governance-config.json` `label_paths`,
`.github/lanes.yml`, `.github/governance/pr-checks.json` and its byte-equal copy in `github-setup/`. These are
lane:infra files, and the config is the generator's input, so the entry survives a regeneration. #745 changes only
`ruleset_version` in the config, a different hunk. It breaks AC6 of #746 ("no generator file changes"). (b) Put the
pointer in an owned, non-working path, e.g. `governance/kb/00-index/working-files.md` (a KB record), which is harder to find.
Recommended: (a).
Unrelated: `tests/unit/test_textprep_numbers_statistics_de.py::test_a_german_job_reads_the_same_on_a_second_run`
failed locally under the dev Hypothesis profile (paragraphs `1–1`, `←−=1`). The branch changes no `src/`, and main CI
on 4ca072a is green. I added this example to #597 (the same kind).
