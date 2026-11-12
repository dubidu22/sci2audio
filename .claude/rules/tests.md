# Tests

Testing strategy: D-58. One runner (pytest) for everything except the browser, where Playwright runs inside pytest.

## Basics

- Fast tests (no marker) run on every PR on Linux, macOS and Windows; keep the whole fast suite under about 2 minutes.
- Mark tests that need voices, models, audio or the full sample corpus with `@pytest.mark.slow`; speed measurements with `@pytest.mark.benchmark`. Both run nightly (`.github/workflows/nightly.yml`).
- Hypothesis profiles: `dev` (local default), `ci` (every PR, deterministic), `nightly` (many examples). Set with `HYPOTHESIS_PROFILE`.
- Golden files (syrupy): accept a wanted change with `uv run pytest --snapshot-update` and explain the diff in the PR.
- Never weaken or delete a test to make CI green. If a test is wrong, say why in the PR.
- No network in tests. Mock downloads.

## Moving code in and changing text rules

- Moving code in: first copy its existing tests, then add a characterisation golden file that pins today's output on a sample from `tests/corpus/`. The move is done when that output is identical, or the PR explains every difference.
- Text rules: add the input and the expected spoken script to the English regression cases before changing a rule; the PR shows the before/after diff.

## First of its kind: the PR that adds the code also adds its test pipeline

A PR is not done if it introduces one of these for the first time without the matching tests and CI wiring. This keeps every testing method of D-58 in place from the moment it can exist.

| When a PR first adds ... | it must also add ... |
|---|---|
| a module in `textprep/` | unit tests, a Hypothesis property test (no crash on any text; edit spans valid; idempotent), and an entry in the English regression cases |
| the text-step or voice plugin interface | the conformance suite in `sci2audio.testing` that every plugin must pass, run against the built-in plugins |
| a module in `extraction/` | golden files for corpus samples and a set of deliberately broken files that must fail with a clear message |
| a module in `layout/` | corpus truth tests (columns per page, furniture in both directions: truth furniture only in furniture blocks and furniture blocks only truth furniture, verbatim sentences read in order), a golden file of every block for the corpus papers, and Hypothesis property tests (never fails on any `Content`, every item in exactly one block) (D-70) |
| the FastAPI server in `web/` | TestClient tests, Schemathesis against the OpenAPI schema, and tests for 127.0.0.1-only binding, start-up token and origin check |
| the HTML interface | Playwright tests (pytest-playwright) for the main flow with axe-core checks (`axe-playwright-python`), wired into CI |
| a voice in `voices/` | a `slow` integration test (text → audio file) and the speech-recognition round-trip (faster-whisper) in the nightly run |
| a pipeline step that can take long | a `benchmark` test and a row in `docs/baseline.md` |
| resume, download or any file writing | fault-injection tests: kill mid-run and resume, no network, disk full, file removed during the run |
| installers or the app window | an installer smoke test on all three systems in the release workflow |

## Before each release

Follow `docs/release-checklist.md`: listening test, screen-reader pass, OWASP ZAP baseline scan, mutation run, speed numbers.
