# Tests

- Fast tests (no marker) run on every PR on Linux, macOS and Windows; keep the whole fast suite under about 2 minutes.
- Mark tests that need voices, models, audio or the full sample corpus with `@pytest.mark.slow`; they run nightly.
- Moving code in: first copy its existing tests, then add a characterisation test that pins today's output on a sample from `tests/corpus/`. The move is done when that output is identical, or the PR explains every difference.
- Text rules: add the input and the expected spoken script to the English regression cases before changing a rule; the PR shows the before/after diff.
- Never weaken or delete a test to make CI green. If a test is wrong, say why in the PR.
- No network in tests. Mock downloads.
