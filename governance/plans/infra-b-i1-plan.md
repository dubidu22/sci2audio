# Plan: infra lane, batch B-I1 (#664, #665)

Thread: implementation, infra lane, Opus 5.5 high. Date: 2026-11-20.
**Critical** (CRIT-01): every file changed is under `.github/**` (CI workflows, the governance PR check, the labeler). Waits for coordinator approval (PLAN-02).

Facts checked on 2026-11-20:
- Default setup is already off: `GET code-scanning/default-setup` → `state: not-configured`. No hand step left for Colin.
- PR #680 (`codeql-advanced`, head 15b5faf, same repository): CodeQL legs pass; `security` (zizmor: unpinned `@v7`/`@v4`) and `governance pr checks` (title, no lane label) fail.
- Alerts 8, 9, 10 dismissed; no open alert in `src/**` (6 is fixed).
- `governance/` on `main` holds more than #665 names: `github-setup/`, `tools/`, `memory/`, `release/`, `workflow-export.md`, `governance-config.json`. All get an owner below.
- `pr_checks.py` reads lanes from `.github/governance/pr-checks.json` (`label_paths`), not from `lanes.yml`, and skips every path matching `governance_paths` (today `governance/**`) in the ownership check. So `lanes.yml` entries alone change nothing a machine checks.

## (a) #664: CodeQL in advanced setup

`.github/workflows/codeql.yml` (replaces the generated file; comments trimmed to the why):

```yaml
# Advanced setup because only it takes paths-ignore (#664); categories keep the default
# setup's names so alert history and the dismissals of 8, 9 and 10 carry over.
name: CodeQL
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  schedule:
    - cron: "34 13 * * 3"
permissions: {}
jobs:
  analyze:
    name: Analyze (${{ matrix.language }})
    runs-on: ubuntu-latest
    permissions:
      contents: read
      security-events: write
    strategy:
      fail-fast: false
      matrix:
        language: [actions, javascript-typescript, python]
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
      - uses: github/codeql-action/init@1bd86f2fdb4b86187fa4059f16f31a3202acc9ea # v4.39.4
        with:
          languages: ${{ matrix.language }}
          build-mode: none
          config-file: ./.github/codeql/codeql-config.yml
      - uses: github/codeql-action/analyze@1bd86f2fdb4b86187fa4059f16f31a3202acc9ea # v4.39.4
        with:
          category: "/language:${{ matrix.language }}"
```

`.github/codeql/codeql-config.yml`:

```yaml
name: sci2audio
# Not shipped and not run in CI: the clickable design prototype and the governance workspace
# (the template copy of pr_checks.py lives there; the copy CI runs is in .github/governance/).
paths-ignore:
  - docs/design/prototype/**
  - governance/**
```

Choices:
- Languages: the same three as the default setup (`actions`, `javascript-typescript`, `python`), `build-mode: none` (nothing compiled). Triggers: push and PR to `main`, weekly, as the default setup did. PRs into `release/*` are not scanned today either; unchanged.
- Permissions: `{}` at the top, the job gets `contents: read` and `security-events: write` only. Dropped from the generated file: `packages: read` (private CodeQL packs, none) and `actions: read` (needed in private repositories only; this one is public). Removed the dead `manual` build step and the `swift` runner switch.
- Pins: SHA-pinned like every other workflow; `persist-credentials: false`. zizmor offline must report nothing.
- **`.github/governance/**` stays scanned (recommendation).** `pr_checks.py` runs on every PR with the PR's title and file list as input; it is code that runs in CI, exactly what the `actions`/`python` queries are for. Alert 10 stays dismissed with its reason; a new alert there is worth a look, not noise. The duplicate under `governance/github-setup/` (alert 8) is a template nobody runs, so it is ignored with the rest of `governance/**`.

Delivery: **commit on top of `codeql-advanced`**, so Colin's PR #680 becomes the batch PR. Retitle `infra: CodeQL scans the shipped code only (#664)`, replace the empty template body, add `lane:infra` (`risk:high` is already set). Plain push to the existing branch, no force-push. Reason: it keeps Colin's commit and the CodeQL run history on one PR, and the generated file must change anyway (zizmor fails it). A fresh branch would only add a PR to close.

## (b) #665: owners of `governance/**` and `docs/design/**`

`.github/lanes.yml`, explicit lists, no `governance/**` catch-all, so a new top-level file shows up as unowned:

```yaml
  infra:
    # the ruleset, its role extracts and the tooling threads run: only the owner changes them (META-01)
    paths: [.github/**, pyproject.toml, uv.lock, .pre-commit-config.yaml,
            governance/claude-project-rules.yaml, governance/rules/**, governance/project_instructions.md,
            governance/governance-config.json, governance/github-setup/**, governance/tools/**]
    single_threaded: true
  docs:
    paths: ["*.md", docs/**, docs/design/**, .claude/**,
            governance/kb/**, governance/plans/**, governance/ledger/**, governance/project-state.yaml,
            governance/memory/**, governance/release/**, governance/workflow-export.md]
```

Beyond the issue's proposal: `governance-config.json` → infra (it configures the ruleset, already in CODEOWNERS); `github-setup/**` and `tools/**` (`ledger_tool.py`, the merge gate) → infra, being executable governance; `memory/**`, `release/**` (ZAP summary) and `workflow-export.md` → docs, being records.

Matching changes, so a machine checks what `lanes.yml` says:
- `.github/governance/pr-checks.json`: `label_paths` mirror `lanes.yml` exactly. `critical_paths` add the four rules paths (`governance/claude-project-rules.yaml`, `governance/rules/**`, `governance/project_instructions.md`, `governance/governance-config.json`). **`governance_paths` narrows** from `governance/**` to the docs-lane working files (`governance/kb/**`, `plans/**`, `ledger/**`, `project-state.yaml`, `memory/**`, `release/**`, `workflow-export.md`), so a governance-only PR of working files still skips title and lane checks, but a PR that changes the ruleset, extracts, `github-setup/` or `tools/` now needs the title format, `lane:infra` and `risk:high`. Without this narrowing the lane entries are prose: `pr_checks.py` would skip every governance path.
- `.github/labeler.yml`: the same four rules paths under `risk:high`.
- `.github/CODEOWNERS`: add `/governance/project_instructions.md` (the other three are there). Not enforceable on a single-account repo, kept for consistency.
- `governance/github-setup/` (the skill's template copies) stays unchanged: it is the generic template, not this repository's config.

**Open choice for the coordinator:** the `governance_paths` narrowing (recommended above) changes what the governance-branch sync PRs must carry when they include a ruleset or extract change (title `<area>: <outcome> (#N)`, `lane:infra`, `risk:high`). The alternative keeps `governance/**` and adds only `critical_paths`; then a ruleset change still fails without `risk:high`, but lane ownership of governance files is never checked. I recommend narrowing (META-03: a check, not prose).

## (c) One PR or two

One PR (#680) for both issues: same lane, same batch, all files under `.github/**`, about 250 lines (LANE-01). The PR is Colin's, but nothing in it needs his hand any more (default setup is already off), so it need not stay alone. Body: `Closes #664`, `Closes #665`.

## (d) Tests first, then the change

New tests written and run red before the change:
- `tests/unit/test_ci_workflows.py` (CodeQL part, read as text like the existing tests): the workflow names the three languages, `config-file` points at an existing config, top-level `permissions: {}`, job permissions exactly `contents: read` and `security-events: write`, every `uses:` pinned to a 40-hex SHA, `persist-credentials: false`; the config's `paths-ignore` is exactly the two globs; no tracked file under `src/` or `.github/` matches an ignored glob (`src/**` results unchanged, `.github/governance/` scanned).
- `tests/unit/test_lanes.py`:
  - every tracked file (`git ls-files`) under `governance/` and `docs/design/` matches exactly one lane in `lanes.yml` (glob semantics from `pr_checks.glob_to_regex`, loaded by path like `ci_passed.py`);
  - `lanes.yml` and `pr-checks.json` `label_paths` agree lane for lane; `labeler.yml` `risk:high` globs equal `critical_paths`;
  - `run_checks` gives the expected lane for one sample path per new entry: e.g. `governance/rules/implementation.yaml` with `lane:docs` → ownership FAIL, with `lane:infra` → ok, without `risk:high` → critical FAIL; `governance/plans/x.md` alone → scope ok (governance-only); `docs/design/DESIGN.md` with `lane:docs` → ok.
  - `lanes.yml` is parsed with a small line parser (its `paths:` lines are flow lists), not PyYAML: PyYAML is only a transitive dev dependency and adding it would touch `pyproject.toml`, `uv.lock` and the licence file for a test helper.

Checks before review: `uv run zizmor --offline .github/workflows`, the fast checks (espeak tests deselected locally, #663), then `ci:full` on the PR, green, label removed. After the PR's CodeQL run: `code-scanning/alerts` shows no open alert in `docs/design/prototype/` or `governance/`, and the open `src/**` alerts equal today's (none); recorded in the PR body. The same check on `main` after the merge is the reviewer's last step.

Licence: none (no new dependency, action versions only). Risk: `risk:high`. Size: about 250 lines, roughly half tests.

Follow-ups (Issues, v1.4, if approved): which `governance/kb/**` files are process, contract or architecture documents (critical per CRIT-01) cannot be told by path today; a path convention would let the labeler mark them.
