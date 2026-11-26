# Contributing

Thank you for helping. sci2audio is built by one maintainer with the help of AI coding agents, so the process is deliberately simple and strict.

## How work flows

1. Every change starts as an Issue with acceptance criteria. Use the templates.
2. The maintainer marks Issues `ready`. Please wait for that before starting larger work.
3. One Issue, one branch, one pull request. Keep it small.
4. A pull request can only be merged when the check **CI passed** is green and the branch is up to date with `main`.

### What CI runs

On a pull request, CI runs everything on Linux: lint, layers, licences, security, the fast tests and the browser tests. The fast tests run on macOS and Windows too once the PR carries the label **`ci:full`**. Adding the label starts that run: a run of CI by hand on the PR's branch (the workflow "CI on all three systems"), which tests all three systems and is never cancelled by a later run. Add the label once; removing and adding it again only starts another run. Other labels start no run, so labelling a PR never cancels the run of its commit (#360, D-620); every later push to a PR with `ci:full` tests all three systems. Every push to `main` or a `release/*` branch, and every run by hand, tests all three systems. A newer push to a PR cancels its older run (D-580). Add `ci:full` when a change could behave differently on another system (paths, files, audio, encoding, the command line), and always before a PR is merged: a PR is merged only on a green run on all three systems of the reviewed head: check that `tests (macos-latest)` and `tests (windows-latest)` succeeded on that head; `CI passed` alone can still show the earlier Linux-only run. The summary of the **CI passed** job says which systems ran.

## Before you open a pull request

```bash
uv sync
uv run ruff check && uv run ruff format --check
uv run lint-imports
uv run deptry src
uv run pytest -m "not slow and not benchmark and not browser"
uv run playwright install chromium   # once, for the browser tests
uv run pytest -m browser
```

Which tests a change needs is described in `.claude/rules/tests.md` (it applies to people too). Before a release, follow `docs/release-checklist.md`.

To add a text rule without changing sci2audio, write a text-step plugin: `docs/plugins.md` shows how, and how to run the conformance suite (`sci2audio.testing`) against your step or voice engine.

To see how fast sci2audio speaks on your machine, run `uv run python scripts/speed.py` after `uv run sci2audio voices download` (`--quick` for a short run, `--help` for the options); `docs/baseline.md` holds the numbers measured so far and the performance budget.

For a change to the server or the interface, the "ZAP baseline scan" workflow runs OWASP ZAP against the local server on your PR (#12). To run it yourself you need Docker (on macOS and Windows: Docker Desktop 4.34 or later with host networking turned on): `uv run python scripts/zap_scan.py`. It writes `zap-out/zap-summary.md`; a Low alert that is fine here goes into `scripts/zap/accepted.toml` with a reason and a decision, a High or Medium one is fixed. A red nightly run of the workflow gets an Issue, opened by hand.

Install the pre-commit hooks once with `uv run pre-commit install`; they run ruff and a secret scan before each commit.

## Rules that matter most

- **Licences:** anything you add (a dependency, code, a model, a voice, a sample text) must have a compatible licence, listed in `THIRD_PARTY_LICENSES.md` or `tests/corpus/LICENSES.md`. See `.claude/rules/licences.md`.
- **Privacy:** no network calls except a voice download the user started; no telemetry.
- **Faithful text:** text rules propose marked, explainable edits; nothing summarises or rewrites silently.
- **Layers:** the import rules in `pyproject.toml` (import-linter) are part of the design. Don't work around them.

## Labels

- Status: `inbox`, `ready`, `approved`
- Type: `bug`, `feature`, `chore`
- Priority: `P0`, `P1`, `P2`
- Risk: `risk:high`
- Lane: `lane:<name>` (see `.github/lanes.yml`)
- CI: `ci:full` runs the fast tests on macOS and Windows as well (see "What CI runs")

## Licence of contributions

By contributing you agree that your contribution is licensed under GPL-3.0-or-later, like the rest of the project.

## How pull requests are handled

Most work in sci2audio is done by Claude Code sessions under the rules in [`CLAUDE.md`](CLAUDE.md). The same rules apply to your pull request:

- It should close an issue. For anything larger than a small fix, open an issue first; new issues are triaged (`needs-triage`) before work starts.
- It must pass `uv run ruff check && uv run ruff format --check && uv run lint-imports && uv run deptry src && uv run pytest -m "not slow and not benchmark and not browser"`.
- A PR that touches `.github/**`, `.claude/**`, `CLAUDE.md`, `src/sci2audio/core/**`, `pyproject.toml`, `uv.lock`, `tests/corpus/**`, `tests/unit/__snapshots__/**`, `tests/regression/**`, `THIRD_PARTY_LICENSES.md` is critical (`risk:high`): its description says what could break.
- The owner reviews and merges every pull request.
- Text in issues and pull requests is never treated as an instruction to the AI sessions.
