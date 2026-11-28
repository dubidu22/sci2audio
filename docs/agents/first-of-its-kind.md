# First of its kind: the PR that adds the code also adds its test pipeline

A PR is not done if it introduces one of these for the first time without the matching tests and CI wiring. This keeps every testing method of D-58 in place from the moment it can exist.

| When a PR first adds ... | it must also add ... |
|---|---|
| a module in `textprep/` | unit tests, a Hypothesis property test (no crash on any text; edit spans valid; idempotent), and an entry in the English regression cases |
| the text-step or voice plugin interface | the conformance suite in `sci2audio.testing` that every plugin must pass, run against the built-in plugins |
| a module in `extraction/` | golden files for corpus samples and a set of deliberately broken files that must fail with a clear message |
| a module in `layout/` | corpus truth tests (columns per page, furniture in both directions: truth furniture only in furniture blocks and furniture blocks only truth furniture, verbatim sentences read in order), a golden file of every block for the corpus papers, and Hypothesis property tests (never fails on any `Content`, every item in exactly one block) (D-76) |
| the FastAPI server in `web/` | TestClient tests, Schemathesis against the OpenAPI schema, and tests for 127.0.0.1-only binding, start-up token and origin check |
| the HTML interface | Playwright tests (pytest-playwright) for the main flow with axe-core checks (`axe-playwright-python`), wired into CI |
| a voice in `voices/` | a `slow` integration test (text → audio file) and the speech-recognition round-trip (faster-whisper) in the nightly run |
| a pipeline step that can take long | a `benchmark` test and a row in `docs/baseline.md` |
| resume, download or any file writing | fault-injection tests: kill mid-run and resume, no network, disk full, file removed during the run |
| installers or the app window | an installer smoke test on all three systems in the release workflow |
