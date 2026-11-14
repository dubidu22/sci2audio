# Release checklist

Copy this list into the release Issue and tick each item.

## Automatic (must be green)

- [ ] CI on `main` is green (`CI passed`).
- [ ] Last nightly run is green: slow tests, property tests with many examples, benchmarks.
- [ ] No open Dependabot security alert.
- [ ] CI, nightly and release ran on a uv-managed Python 3.12.16 or newer (each job's log says `Using CPython 3.12.x`, never an interpreter at a runner path such as `/usr/local/bin` or `hostedtoolcache`) (D-378).
- [ ] No quarantined tests (D-374): `uv run pytest -m quarantined --collect-only -q` collects none, and the "Quarantined tests" list in the CI job summary says "none". Fix each one and close its issue first.
- [ ] **OWASP ZAP baseline scan** (#12, D-364 to D-372): the last run of the "ZAP baseline scan" workflow on `main` is green (no High or Medium alert, every Low one accepted with a reason in `scripts/zap/accepted.toml`, every route scanned in English and German). Paste its `zap-summary.md` (the run's summary page) into the release Issue. Start a run by hand (Actions → ZAP baseline scan → Run workflow) if the last one is older than the release candidate.
- [ ] The ZAP image pinned in `scripts/zap_scan.py` is less than three months old; if not, update the digest in a PR of its own and let the scan run on it (D-370).

## By hand (about an hour)

- [ ] **Listening test:** follow `docs/listening-tests/template.md` with the same 10 paragraphs; save the result as `docs/listening-tests/<version>.md` and compare with the last release.
- [ ] **Screen-reader pass:** one full job (open a file, read the pre-analysis, start, play, use read-along) with VoiceOver on macOS and NVDA on Windows, keyboard only. Note every problem as an Issue.
- [ ] **Mutation run:** Actions → Mutation testing → Run workflow; look at surviving mutants in `textprep/` and add tests where a survivor would change what users hear.
- [ ] **Speed:** after `uv run sci2audio voices download`, run `uv run python scripts/speed.py` on the MacBook Pro M4 (about 10 minutes: MPS and CPU); paste its rows into `docs/baseline.md`, keep its JSON file with the release notes, and compare with the performance budget there.
- [ ] **Install from PyPI** on a clean machine or fresh user account and convert one corpus file. The release workflow's `from-pypi` jobs do this on clean Linux, macOS and Windows runners after publishing (#80); a person's own machine is still worth one try.

## Release

- [ ] `CHANGELOG.md` updated, and the version's heading carries the release date: `## [X.Y.Z] - YYYY-MM-DD` (the release workflow refuses a tag whose version has no dated heading); version bumped in `src/sci2audio/__init__.py`.
- [ ] Tag `vX.Y.Z` pushed; the release workflow publishes to PyPI.
- [ ] Learning note for the phase written in `docs/learning/`.
