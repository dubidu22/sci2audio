# Plan: no false red "CI passed" from runs cancelled by a newer one (#360)

Lane: app (CI). Branch `ci/label-runs-360` from main 87c6503. One PR, **critical** (CI,
`risk:high`), so it waits for approval.

## What actually happens

`ci.yml` runs on `pull_request: types: [opened, synchronize, reopened, labeled]`. The trigger
can't filter labels by name, so **every** label starts a full CI run, not only `ci:full`. The
new run cancels the one before it on the same head (concurrency, D-580). The cancelled run's
`CI passed` job (`if: always()`) then sees `cancelled` needs and fails.

That is what happened on #350 and #357: the PR was opened, and then three labels were added
within seconds. Each label was a new run on the **same** SHA, so the red check sat on the head.
A push that cancels an older run is harmless by comparison, because the red check stays on the
old commit and the head is untouched.

## Why "skip when cancelled" is not enough

Rulesets count a **skipped** required check as passing, and the latest check run of a name on a
SHA is the one that counts. Two problems follow:

- With `if: ${{ !cancelled() }}`, a lone run cancelled by hand could leave `CI passed`
  skipped. That would be "green" on a head nothing tested.
- Even a superseded run's skipped or green check would be the newest one on the head until
  the newer run's `CI passed` reports minutes later. A merge in that window would pass the
  ruleset without the tests having finished.

So `CI passed` keeps its strict rule: any cancelled, skipped or failed need fails it. The fix
removes the runs that get cancelled.

## Design (recommended)

1. **`ci.yml` no longer runs on `labeled`.** Its types become `[opened, synchronize,
   reopened]`. A label such as `bug` or `risk:high` starts nothing, cancels nothing and costs
   no CI minutes.
2. **The `ci:full` label starts a full run by hand.** A new small workflow,
   `.github/workflows/ci-full-label.yml`, runs on `pull_request: types: [labeled]`. Its one job:
   - runs only when `github.event.label.name == 'ci:full'` and the PR comes from this
     repository (a fork's token can't dispatch);
   - has job-level `permissions: actions: write` and nothing else, and reads no checkout;
   - runs `gh workflow run ci.yml --ref "$HEAD_REF"`, with the branch name passed through
     `env`, never put into the script (no template injection).

   A run started this way is a `workflow_dispatch` run, so it already tests all three systems
   (D-580). GitHub lets `GITHUB_TOKEN` start `workflow_dispatch` runs; the token is blocked
   only from starting other kinds of runs. That run has its own concurrency group, so it never
   cancels and is never cancelled. Its checks land on the PR's head SHA with the same names,
   `CI passed`, `tests (macos-latest)` and `tests (windows-latest)`, so the review threads'
   check (CLAUDE.md step 8) is unchanged.
3. **Unchanged:**
   - a push to a PR that carries `ci:full` still runs all three systems through the matrix;
   - `CI passed` stays strict, so a lone run cancelled by hand stays red, never green or
     skipped;
   - the main and `release/**` pushes, the concurrency rules and the ZAP workflow are as
     before.
4. **Docs:**
   - CONTRIBUTING "What CI runs": other labels start no run, and `ci:full` starts a full run
     by hand on the PR's branch;
   - the comment at the top of `ci.yml`;
   - a CHANGELOG line under Changed.

## Checks

- `uv run zizmor --offline .github/workflows` stays clean, with the new job's permissions
  scoped to that job. No new action is pinned: `gh` is on the runner.
- A unit test reads the workflow YAML and checks four things:
  - `ci.yml` has no `labeled` type;
  - `CI passed` still has `if: always()` and fails on `cancelled` and `skipped`;
  - the new workflow's job is gated on `ci:full` and same-repository;
  - the new job's permissions are exactly `actions: write`.
- On the PR itself, three checks:
  - **open with two labels:** exactly one CI run on the head, and no red `CI passed`;
  - **add `ci:full`:** one dispatch run tests on Linux, macOS and Windows, and the head shows
    `tests (macos-latest)` and `tests (windows-latest)`;
  - **cancel that dispatch run by hand:** its `CI passed` is red, not skipped.

  The run ids go in the PR body.

## Open choice

**A. Dispatch on `ci:full` (recommended).** This removes the cause, keeps `CI passed`
strict, and saves a full CI run for every other label. The cost is one small workflow with
`actions: write`.

**B. `if: !cancelled()` on `CI passed`.** This is the change the issue first suggested. It
needs no new workflow, but it can leave a skipped, counted-as-green `CI passed` on a head
nobody tested. That is the unsafe case the acceptance criteria forbid. I advise against it.

## Size

About 40 lines of YAML, a 40-line test and the docs. One PR.
