# Tests

Testing strategy: D-58. One runner (pytest) for everything except the browser, where Playwright runs inside pytest.

## Basics

- Fast tests (no marker) run on every PR on Linux in three shards (`.github/scripts/shard.py`), and on macOS and Windows, whole, when the PR carries the label `ci:full` and on every push to `main` and `release/*` (D-580). Python 3.13 runs them on Linux on pushes to `main` and `release/*`, on runs by hand and under `ci:full`, not on an ordinary PR (#1131).
- Budget: an ordinary Linux PR gets "CI passed" in about 6 minutes, judged on the median of the last 20 such runs. The nightly job "pull-request wait (budget 6 min)" goes red above it; then a person opens the speed issue (#1131, #1133). Each fast-suite shard prints its 25 slowest tests.
- A test that loops over sample documents may take a small fixed set, named where it is defined, under the `ci` and `dev` profiles and every sample under `nightly`; mark it `deep` so the nightly property job runs it. Golden files, the English regression cases and the conformance suite's default (every sample document) are never sampled (#1134).
- Mark tests that need voices, models, audio or the full sample corpus with `@pytest.mark.slow`; speed measurements with `@pytest.mark.benchmark`. Both run nightly (`.github/workflows/nightly.yml`).
- Browser tests live in `tests/browser/` and get the `browser` marker there: they run in their own CI job on Linux with Chromium in three shards on every PR, and with Chromium, Firefox and WebKit nightly (D-259). Run them with `uv run pytest -m browser` after `uv run playwright install chromium`. They fail on any request the page makes outside the test server.
- Exception: a test that encodes or decodes only a few seconds of generated audio with ffmpeg may stay in the fast suite, so every three-system run (`ci:full`, `main`, `release/*`) proves the bundled ffmpeg works on all three systems (#69).
- Hypothesis profiles: `dev` (local default), `ci` (every PR, deterministic), `nightly` (many examples). Set with `HYPOTHESIS_PROFILE`.
- Golden files (syrupy): accept a wanted change with `uv run pytest --snapshot-update` and explain the diff in the PR.
- Never weaken or delete a test to make CI green. If a test is wrong, say why in the PR.
- No network in tests. Mock downloads.

## Moving code in and changing text rules

- Moving code in: first copy its existing tests, then add a characterisation golden file that pins today's output on a sample from `tests/corpus/`. The move is done when that output is identical, or the PR explains every difference.
- Text rules: add the input and the expected spoken script to the English regression cases before changing a rule; the PR shows the before/after diff. `scripts/second_run.py` shows a text's first and second run.

## First of its kind

A PR that first adds a module of a stage, a plugin interface, the server, the interface, a voice, a long step, file writing, an installer or the window also adds that kind's test pipeline: `docs/agents/first-of-its-kind.md` names what each needs.

## Before each release

Follow `docs/release-checklist.md`: listening test, screen-reader pass, OWASP ZAP baseline scan (the last run of `.github/workflows/zap.yml` on `main`, #12), mutation run, speed numbers.
