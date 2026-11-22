# Review PR #740, round 1 (#710, #711, #734: scaffold copies, promised-tests base note, brittle-test check)

Thread: review-b004-a (Opus 5.5 high), batch 004 slot A. Author: infra-b-i5. Head reviewed: 465b96f3b95729ace33e8a2ef88dd8f19b037219. Base: 1bebb96 (main is now 3fb4d1b, #741; GitHub says CLEAN, no file in common). Date: 2026-11-22.
**Critical: yes** (CRIT-01: `.github/workflows/governance-pr-checks.yml` and `.github/governance/promised_tests.py` are CI workflow and a safety check; `risk:high`, `lane:infra`). Plan: `plans/infra-b-i5-plan.md`, approved as D-878.

**Verdict: changes requested** (0 must-fix, 2 should-fix, 3 notes). Both should-fixes are small and fit in one fix commit; nothing blocks the gate (`must_fix: 0`).

## Verified

- **#734, the check is red on main and green on the head (VER-02).** I loaded the PR's `findings()` and ran it over main's `tests/` (exported from 3fb4d1b): 25 hits in 13 files, the same list the body names. On 465b96f: 0 hits. 25 `# clock-bound:` allowances were added outside the check file, one per hit.
- **The rules match plan §2.** Clock calls (`time.x()` and bare imports, `_ns` forms), `elapsed` names and attributes, names filled by assignment, subscript store, method-call argument (`append`, `setdefault`), loop target, nested functions and lambdas, to a fixed point. Upper bounds only, chained comparisons step by step. `slow`/`benchmark` on functions, classes and `pytestmark` skip; `tests/browser/`, corpus and snapshots are not read; `conftest.py` and `web_helpers.py` are. Allowances on any line of the assert or alone on the line above; empty reason and stale allowance both fail. The unit cases cover each rule: removing any one branch (the `Gt` side, the method-call fill, the loop fill, the above-line rule, the alone-on-its-line test, the `pytestmark` read, the decorator read, the `elapsed` attribute) turns at least one parametrized case red, by reading the cases against the code.
- **The 25 hits, one by one.**
  - 7 wait-loop deadlines (10 to 120 s): allowance only. Correct.
  - 12 "did not wait" bounds: each reason's failure time checked against the code. `< 3` against hangs that never end behind a 0.2 s limit (4 plugin tests, `test_app_plugins`); `< 30`/`< 25` against `reader_targets.hanging_read`, which is `page_then_hang(..., 30)`; `< 5` against the 10 s sentence; `SHUTDOWN_WAIT + 2` (7 s) against `Background.stop(timeout=SHUTDOWN_WAIT + 10)` (`web/launch.py:209`); the event order in `test_extraction_pdf_process.py:645`; the EPUB cap. All hold.
  - 5 loosened to 5 s. Each still fails on its bug (TST-02): the three cancel latencies and the web one are followed by `thread.join(10)` / `wait(..., timeout=10)`, and an unwatched cancel waits out the 30 s hang or a slot that is held until `finally` (`test_extraction_pdf_progress.py:210`), so the result key is missing and the bound fails as well. `test_extraction_pdf_broken.py:469` runs under `timeout(10)` on 1 MB tails, where the old quadratic search took 53 s for 100 KB. `test_the_cancel_is_looked_at_every_tenth_of_a_second` still pins the 0.1 s poll. No assert was removed.
  - 1 kept tight: `1.0 <= took < 1.5` (`test_extraction_pdf_progress.py:150`). Keeping it is right (plan §2 allows it where loosening hides the bug), but the reason does not say why; see S1.
- **#711.** `collected()` keeps only lines that start with `tests/` (`promised_tests.py:138`), the `browser_shard.py` rule. The third file is optional and only adds a `note` line. In the workflow `PR_BASE` comes through `env`; `run:` has no `${{ }}`; one `uv run`, no `uv sync`; permissions unchanged (`contents: read`, `pull-requests: read`); `persist-credentials: false` stays. `uv run zizmor --offline .github/workflows`: no findings (3 ignored, 13 suppressed, as on main; the PR adds no ignore comment).
- **The base collection really imports the base.** I ran the step's commands by hand (macOS, bash 3 so `mapfile` replaced by an array) with the head's `.venv`, a base tree of 1bebb96 and a body holding one old and two new promises: `37 tests collected`, `sci2audio.__file__` resolved to the base's `src/`, output `ok   promised tests: 3 of 3 collect` and a `note` naming only the old promise. In the PR's own CI run (45062348886) no note printed, which is right: all 12 promises are new.
- **#710.** All six kept copies under `governance/github-setup/` are byte-equal to their live files (`cmp`): `pr-checks-workflow.yml`, `labeler.yml`, `labeler-workflow.yml`, `pr_checks.py`, `pr-checks.json`, `pr-check-exemptions.json`. `test_each_scaffold_copy_equals_its_live_file` covers all six; `CODEOWNERS` and `create-labels.sh` have no twin.
- **Lanes.** Changed files: `.github/**` and `governance/github-setup/**` (lane:infra) and `tests/unit/*` (lane-free). `governance pr checks` is green on 465b96f.
- **Tests.** Locally on 465b96f: `pytest tests/unit/test_clock_bounds.py test_promised_tests.py test_ci_workflows.py test_lanes.py`: 136 passed. `ruff check`, `ruff format --check`: clean.
- **CI on 465b96f.** `CI passed`, `tests (ubuntu-latest)`, `tests (macos-latest)`, `tests (windows-latest)`, both Chromium shards, lint and layers, licences, security, web paths, CodeQL, `governance pr checks`: all green. The `ci:full` label is off.
- **Form.** Title `infra: ... (#734)`; body has `Closes #734 #711 #710`, plan, the promised node IDs, test summary, licence (none), risk, out of scope. REV-06: the body names the cause the five loosened bounds remove (they timed process teardown and HTTP round trips, not the code).

## Findings

### Should-fix

- **S1 (kind: vague-reason).** `tests/unit/test_extraction_pdf_progress.py:149`: the one bound kept tight says "it catches a limit stretched by the 0.1 s slices; timed before the join (#366)". It names neither number, which plan §2 asks for ("the allowance names both numbers"), and it hides the real reason 1.5 cannot be loosened: when the parent's own limit does not hold, the child's watch still ends the step at twice the step time (`isolate.py:281`, `_watch(memory, 2 * step_seconds)`, exit `TIME_EXIT`), and `_wait` then returns the same `Stopped("time", "page 1 of 1")` (`isolate.py:239-242`). So the bug this test exists for reads `took` = 2.0 s, and any bound at or above 2 s hides it. The next thread that meets a flaky 1.5 would otherwise loosen it to 5 like the others.
  - **Fix wanted:** replace the comment at line 149 with: `# clock-bound: with the parent's limit broken, the child's own watch still stops the step at 2 x 1.0 s with the same result, so the bound must stay below 2 s; timed before the join (#366)`. No code change.
- **S2 (kind: weak-guard).** `tests/unit/test_clock_bounds.py:117` and `:102-110`: a function counts as `slow` when any decorator merely *contains* `X.mark.slow` anywhere in its expression. So `@pytest.mark.parametrize("n", [pytest.param(1, marks=pytest.mark.slow), 2])` skips the whole function, although the `2` case runs in the fast suite. Probe: that source with `assert time.monotonic() - started < 3` gives `findings() == []`. No test has this form today, but it is a hole in the check this PR claims removes `brittle-test` for good (REV-06), and plan §2 rule 3 says "decorated with `pytest.mark.slow`", not "a decorator holding it".
  - **Fix wanted:** in `is_unmarked`, look only at the decorator itself (and at the elements of a `pytestmark` list or tuple), not at every node under it:
    ```python
    def is_mark(expr: ast.AST) -> bool:
        target = expr.func if isinstance(expr, ast.Call) else expr
        return (
            isinstance(target, ast.Attribute)
            and target.attr in UNMARKED
            and isinstance(target.value, ast.Attribute)
            and target.value.attr == "mark"
        )

    def is_unmarked(expr: ast.AST) -> bool:
        items = expr.elts if isinstance(expr, (ast.List, ast.Tuple)) else [expr]
        return any(is_mark(item) for item in items)
    ```
    and add to `test_slow_benchmark_and_browser_tests_are_not_read` the case `["@pytest.mark.parametrize('n', [pytest.param(1, marks=pytest.mark.slow), 2])", "def test_x(n):", *bound]`, expected to give one finding. Check that the case is red before the change. I tried both on a scratch copy of the head's check: the case fails without the change (`0 == 1`) and passes with it, and the other 23 unit cases stay green.

### Notes (no change needed this round)

- **N1.** `test_clock_bounds.py:31`: `ALLOWANCE` makes the colon optional, so `# clock-bound 60 s hang` passes with reason "60 s hang" (probe). The docstring and the failure message name the form `# clock-bound: <reason>`. Harmless; if S2's fix commit is made anyway, `r"#\s*clock-bound:(.*)"` with `# clock-bound` (no colon) reported as "without a reason" would make the form one.
- **N2.** `.github/workflows/governance-pr-checks.yml:50-55`: when the base collection fails (an import error on the base, say), `|| true` drops the note with no trace in the log. That matches the plan ("the note is left out"), and the note only informs the reviewer. A reviewer who relies on the note should look at whether `base-collected.txt` had any test line; nothing to change now.
- **N3.** `governance/github-setup/README.md:6` adds a line the plan did not name (PR-06). It states the invariant the new test enforces and is under `doc_paths`; accepted.

## Before the final round

The fix commit touches only test files (`tests/unit/test_extraction_pdf_progress.py`, `tests/unit/test_clock_bounds.py`). The `ci:full` run on 465b96f is green on all three systems; round 2 needs Linux CI green on the fix head and, for this critical PR, a three-system run of that head before the merge (D-580, CRIT-02).
