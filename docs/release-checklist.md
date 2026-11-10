# Release checklist

Copy this list into the release Issue and tick each item. Steps marked *(not yet possible)* are skipped until the code they test exists; remove the mark when it does.

## Automatic (must be green)

- [ ] CI on `main` is green (`CI passed`).
- [ ] Last nightly run is green: slow tests, property tests with many examples, benchmarks.
- [ ] No open Dependabot security alert.

## By hand (about an hour)

- [ ] **Listening test:** follow `docs/listening-tests/template.md` with the same 10 paragraphs; save the result as `docs/listening-tests/<version>.md` and compare with the last release. *(not yet possible)*
- [ ] **Screen-reader pass:** one full job (open a file, read the pre-analysis, start, play, use read-along) with VoiceOver on macOS and NVDA on Windows, keyboard only. Note every problem as an Issue. *(not yet possible)*
- [ ] **OWASP ZAP baseline scan** against the running local server; no high or medium findings. *(not yet possible)*
- [ ] **Mutation run:** Actions → Mutation testing → Run workflow; look at surviving mutants in `textprep/` and add tests where a survivor would change what users hear.
- [ ] **Speed:** run the speed script on the MacBook Pro M4; add a dated row to `docs/baseline.md`; compare with the performance budget. *(not yet possible)*
- [ ] **Install from PyPI** on a clean machine or fresh user account and convert one corpus file. *(not yet possible)*

## Release

- [ ] `CHANGELOG.md` updated; version bumped in `src/sci2audio/__init__.py`.
- [ ] Tag `vX.Y.Z` pushed; the release workflow publishes to PyPI.
- [ ] Learning note for the phase written in `docs/learning/`.
