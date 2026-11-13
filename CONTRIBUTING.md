# Contributing

Thank you for helping. sci2audio is built by one maintainer with the help of AI coding agents, so the process is deliberately simple and strict.

## How work flows

1. Every change starts as an Issue with acceptance criteria. Use the templates.
2. The maintainer marks Issues `ready`. Please wait for that before starting larger work.
3. One Issue, one branch, one pull request. Keep it small.
4. A pull request can only be merged when the check **CI passed** is green and the branch is up to date with `main`.

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

## Licence of contributions

By contributing you agree that your contribution is licensed under GPL-3.0-or-later, like the rest of the project.
