# Lean CI (D-580): plan

Thread: Release v1.0 with Colin's hand steps (app/release lane). Critical (workflows), waits for coordinator approval.

## What I found (main e9167e3/aec6e6a)

- `ci.yml` runs on every PR, on pushes to `main`, and on dispatch. `tests` is a matrix over ubuntu, macos and windows. `lint`, `licences`, `security` and `browser` run on Linux only.
- **The only required check is `CI passed`.** It is the last job, `needs` all the others, and fails when any of them failed, was cancelled or was skipped. The ruleset on main and on release/* (checked via the rules API on 14 Nov) names only "CI passed", so **no repo setting has to change**. Matrix legs that are left out of the matrix never exist, so they are never "skipped".
- Concurrency is already there: `ci-${workflow}-${PR number or ref}` with `cancel-in-progress: true`. That also cancels a running `main` push when the next merge lands. D-580 says pushes to main must not be cancelled.
- Caching:
  - The uv cache is on (setup-uv `enable-cache: auto`). PR runs restore main's cache.
  - `cache-python` is **false**, so every job downloads CPython 3.12.16 again (21–33 MB, because of `UV_PYTHON_PREFERENCE=only-managed`).
  - Playwright's Chromium (and ffmpeg) is downloaded on every run in `ci.yml`, `zap.yml` and nightly `browsers`.
  - The voice and whisper models are already cached in nightly `slow-tests` and `benchmarks` (actions/cache, pinned key).
  - espeak-ng comes inside the `espeakng-loader` wheel, so it is in the uv cache already.
  - `release.yml` has `enable-cache: false` on purpose (no cache poisoning in the publish path). It stays that way.
- Timing of the last main run: Linux jobs take 20 s (lint, licences, security) to 3.5 min (tests, browser). macOS takes 3.5 min, at 10× the quota rate; Windows takes 4 min, at 2×.

## Changes

1. **`ci.yml` triggers**
   - `pull_request` gets `types: [opened, synchronize, reopened, labeled]`, so adding the label starts a run.
   - `push` gets `branches: [main, "release/**"]`.
   - `workflow_dispatch` stays.
   - No tag trigger: `release.yml` already installs and runs the built wheel on all three systems for every `v*` tag before it publishes. A CI run on the tag would only repeat that.
2. **`tests` matrix by event.**
   - `os: ${{ fromJSON(<full> && '["ubuntu-latest","macos-latest","windows-latest"]' || '["ubuntu-latest"]') }}`.
   - `<full>` is true for every event except `pull_request`. On a PR it is true only when the PR carries the label `ci:full`.
   - Lint, licences, security and browser stay on Linux, unchanged.
3. **`CI passed` says what ran.**
   - Its job summary gets one line: "Systems: Linux, macOS, Windows", or "Linux only: add the label ci:full for macOS and Windows".
   - Its pass/fail logic and its name stay unchanged, so the rulesets keep working.
4. **Concurrency.**
   - In `ci.yml`: `cancel-in-progress: ${{ github.event_name == 'pull_request' }}`. On a PR, a newer push or label cancels the older run. On main, release/* or dispatch, nothing is cancelled.
   - `zap.yml` gets the same block, keyed on workflow plus PR number or ref, cancelling on PRs only.
   - `mutation.yml` and `nightly.yml` get a group with `cancel-in-progress: false`. A second dispatch then waits instead of running twice in parallel.
   - `release.yml` gets nothing.
5. **Caching.**
   - `cache-python: true` on every setup-uv step outside `release.yml`. The uv-managed CPython then comes from the cache.
   - The Playwright browser folder (`~/.cache/ms-playwright`) gets an actions/cache keyed on runner OS, browser and the `playwright` version from `uv.lock`, in `ci.yml` browser, nightly `browsers` and `zap.yml`.
   - `playwright install --with-deps` keeps running, because the system packages still need apt. It skips the download on a hit.
   - Nothing else: the models and espeak-ng are already covered.
6. **Docs.**
   - `CONTRIBUTING.md` gets a short "CI" paragraph: what runs on a PR, what `ci:full` adds, and when to add it.
   - `.claude/rules/tests.md` lines 7 and 10: "fast tests run on every PR on Linux; on macOS and Windows with the label ci:full, on every push to main and release/*, and nightly through the slow tests". The ffmpeg exception keeps its point: main pushes prove ffmpeg on all three systems.
   - `CLAUDE.md` workflow step 8: a review thread adds `ci:full` before it merges, and merges only on a three-system green run of the reviewed head.
   - The KB text goes to the daily KB thread (D-580).
7. **Label.** `ci:full` is created in the repo with a description via the labels API, if the proxy allows it. If not, Colin creates it, which is one click.

## What this does not enforce

GitHub cannot require a label. A PR without `ci:full` can show "CI passed" after a Linux-only run. The three-system rule rests on the review threads (CLAUDE.md step 8) and on the summary line. The next push to main also runs all three systems, so a break there shows within minutes of the merge. The alternative, making "CI passed" fail on unlabelled PRs, would turn every new PR red until review. I don't recommend it.

## Tests

- `uv run zizmor --offline .github/workflows` is clean.
- The PR's own run shows the Linux-only path and the summary line.
- Then I add `ci:full` to the PR itself. The labelled run shows all three systems, and the second run shows Python and browser cache hits.
- A workflow_dispatch on the branch shows the full path.
- Size: about 40 lines of YAML across 5 workflows, plus the docs.

## Risk

`risk:high` (workflows). The publish path (`release.yml`) is not touched. Rolling back means reverting one PR.
