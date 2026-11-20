# CI speed plan (18 Nov 2026)

Asked by Colin (cmsg_011gr2YyZJypGaV6NbzgSXQE2cgupaDcF5ps8T8bUaQjHG): "think about how to make the ci faster. this is not sustainable."
Status: DONE 18 Nov 2026 (approved as D-759, Colin "i approve this plan. lets do it"). All merged after review: #545 nightly (2cad344), #546 isolate.yml (bb8e1e3), #551 scoped mutation (closes #549), #553 PR browser shards + "CI passed" reads every job (025b67a, closes #548), #554 Firefox/WebKit reported only on web PRs (1797ceb). Item 6 applied by Colin (up-to-date requirement off). Measured result: PR CI 5.2 min wall (was about 9). Open: #550 (textprep Hypothesis find); Firefox/WebKit become required when #437 closes (drop "reported only" from the job name, add browser-reported to the needs of "CI passed", accept skipped for non-web PRs).

## 1. What was measured

Source: GitHub Actions API, every run of CI, Nightly, ZAP, ci:full label and screenshots created 17 Nov 00:00Z to 18 Nov ~16:10Z (301 runs, 1,057 jobs; skipped and cancelled jobs left out). Times are job wall time (start to end) in minutes. Repo is public, so hosted runners are free; ubuntu-latest has 4 vCPU.

### PR CI (ci.yml, Linux only unless ci:full)

| job | runs | median | p90 | max |
|---|---|---|---|---|
| browser (Linux, Chromium) | 52 | **8.2** | 9.3 | 14.4 |
| tests (ubuntu-latest) | 54 | 4.1 | 4.8 | 5.2 |
| tests (macos-latest), ci:full | 8 + 21 dispatch | 6.0 | 6.8 | 12.9 |
| tests (windows-latest), ci:full | 10 + 25 dispatch | 5.6 to 6.7 | 7.4 | 7.6 |
| lint / licences / security | 55 each | 0.5 / 0.3 / 0.3 | | |
| ZAP (path-filtered) | 31 | 1.6 | 1.9 | 3.4 |

- One PR run is about **9 min wall clock**, and the browser job is the whole critical path: 173 browser tests run one at a time, 516 to 526 s in the test step alone (run 44336723114: "173 passed in 523 s").
- Fast suite: 7,029 tests in 248 s with `-n auto`.
- Setup is already cached: setup-uv, cache restore and the Chromium install take 5 to 22 s per job. Caching more saves under 30 s per job.
- Queue time is not the problem for PR CI: Linux jobs start within 0.4 min (p90); macOS p90 5.1 min.
- ci:full runs macOS and Windows in parallel with Linux, so it adds about 0 to 4 min of wall clock, not a second 9 min.

### Nightly (nightly.yml): 2 scheduled runs, 20 started by hand in 2 days

| job | median (by hand) | p90 | max |
|---|---|---|---|
| property-based tests, many examples | **29.2** | 36.9 | 38.4 |
| slow tests (ubuntu / macos / windows) | 16.1 / 18.4 / 19.0 | 24.2 | 24.4 |
| browser firefox / webkit-linux / webkit-mac / chromium | 11.6 / 10.8 / 12.8 / 8.3 | 20.5 | 41.0 |
| benchmarks | 7.9 | 9.8 | 10.2 |

- A full Nightly run takes **25 to 40 min wall clock** (one took 62 min). property-deep sets that floor: it runs the whole fast suite (7,029 tests) with 2,000 Hypothesis examples **without `-n`**, on one core of four. Slow tests also run without `-n`.
- Queue time does matter here: when several Nightly/isolation runs overlap, jobs wait up to 26 min (Linux) and 35 min (macOS) before they start (p90 14 min). Inferred cause: the account's concurrent-job limit (GitHub documents 20 jobs and 5 macOS jobs for a free account; I did not measure the limit itself).
- Both scheduled runs on main (17 and 18 Nov) were red: browser Firefox or WebKit. So "wait for a green nightly on the branch" often waits for something that is red on main too (D-731 then has to be applied by hand).

### 40-run isolation runs (D-682, TST-08)

- Done today by pushing a throwaway branch that edits nightly.yml (ci/isolate-reload-timing, -2 ... -6): **7 runs, 19 to 41 min each, one after another**, about 3.5 h of waiting for one flaky-test question.
- Each of the 40 iterations is a new `uv run pytest` process on one runner: 15 tests x 40 = 600 test executions, about 27 min on Chromium and 38 to 45 min on Firefox/WebKit.
- A red run is only known at the end (no early stop). Round 1 of #519 also lost a round because the hand-written loop ignored failures.
- Threads cannot delete remote branches, so every isolation run leaves a ci/isolate-* branch behind.

### Mutation (mutation.yml)

Whole `src/` (34.8k lines) against the whole fast suite in one job; dies after about 5 h (#246). No run in the window.

### Local check (this container, 4 cores, slower than a runner)

- Chromium browser suite, one at a time: 173 passed in 483 s (CI: 523 s, so this container is close to a runner).
- Same suite with `-n 4`: 170 s, **but one failure**: tests/browser/test_flow.py::test_replace_waits_until_the_page_script_runs, one of the reload-timing tests under isolation today. Parallel load inside one runner brings out timing flakes.
- Fast suite with `-n 4`: 7,027 passed in 159 s. No single slow test dominates (slowest 8 s), so there is little to gain by moving tests out of it.
- Only 142 of the 7,029 fast tests carry Hypothesis's `hypothesis` marker. Those 142 with the nightly profile (2,000 examples) and `-n 4`: **394 s (6.6 min)**, against 29 min for the property-deep job today.

## 2. Where the time goes

1. **Loops, not single runs.** PR CI is 9 min. The waits that hurt are the 25 to 60 min Nightly and isolation runs, started again and again (22 Nightly runs in 2 days, 7 isolation runs today), often queued behind each other.
2. **One-core jobs on four-core runners**: property-deep (29 min) and slow tests (16 to 19 min) run without `-n`; the browser jobs run one test at a time.
3. **Throwaway YAML edits for isolation**: a branch, a full run of setup per iteration, no early stop, no strict exit built in.
4. **Flaky Firefox/WebKit tests** (#437, #440, #517, #518, #525, #541, #542) turn every Nightly into a triage and a re-run. This is not a CI-config problem; the options below make each re-run cheaper but do not remove the cause.

## 3. Options, expected saving, and what each changes about gating

Savings are estimates from the numbers above unless marked measured.

**O1. Isolation workflow (new `isolate.yml`, workflow_dispatch).** Inputs: ref, test node ids, browsers, repeat count (default 40), mode `full` (all repeats, fail rate for the issue) or `stop-at-first-failure` (confirming a fix). Fans the repeats out over 4 runners per browser (4 x 10), one pytest process per runner with a strict exit and a per-test pass/fail table in the job summary, traces uploaded on failure. No branch edit, nothing left behind.
- Saving: 27 to 45 min becomes about 8 to 12 min per isolation run (inferred: a quarter of the iterations per runner plus setup); a failing run in stop-at-first-failure mode ends at the first failure.
- Gating: none changed. TST-08's 40-run requirement is kept; the record in the issue is the job summary.
- Note: keeping one pytest process for many repeats needs pytest-repeat (a new dev dependency, uv.lock change) or a loop; first version loops, no new dependency.

**O2. Nightly: use the four cores and run only what was asked.**
- property-deep: `-n auto`, and only the 142 Hypothesis tests (`-m hypothesis`, the marker Hypothesis's pytest plugin adds; the other 6,887 tests already run on every PR with the same inputs). Measured locally: 6.6 min instead of 29 to 37 min.
- slow tests: `-n 2` (models are large; 2 workers to stay inside runner memory). Saving: 16 to 19 min becomes about 10 min (inferred; needs one trial run).
- Browser jobs: split each browser job into 2 shards on 2 runners (same tests, half each, no extra load per runner). Saving: 10 to 13 min becomes about 6 to 7 min.
- Inputs on workflow_dispatch: which parts to run (browser, slow, property, benchmarks; default all). A branch check that needs only browsers no longer pays for slow tests and benchmarks, and holds fewer runner slots (less queue for everyone).
- `concurrency`: a newer dispatch on the same non-main ref cancels the older one (main and schedule unchanged).
- Net: Nightly wall clock 25 to 40 min becomes about 10 to 12 min (slow tests become the floor). Gating: none changed.

**O3. PR CI: shard the Chromium browser job in 2 (or 3) runners.** Job id stays `browser`, so "CI passed" and test_ci_workflows.py (which checks the needs list) are unchanged; the check names become "browser (Linux, Chromium, 1/2)" and "2/2". The split is by file, from a small script in .github/scripts, so a new test file needs no YAML edit.
- Saving: PR wall clock 9 min becomes about 5 min (the fast-suite job, 4.6 min, becomes the critical path). With 3 shards the browser job is about 3.5 min, but the fast suite still bounds the run.
- Why not `-n 4` inside one runner: it is faster (measured 170 s against 483 s) but made a known timing-sensitive test fail locally; separate runners keep each test's conditions as today.
- Gating: none changed ("CI passed" still requires every shard).

**O4. Gating change (needs the coordinator's ruling): Firefox and WebKit-Linux in PR CI for web PRs, instead of a branch Nightly before merge.** When a PR changes src/sci2audio/web/**, src/sci2audio/app/** or tests/browser/**, ci.yml also runs the Firefox and WebKit-Linux browser jobs (sharded like O3, in parallel, so about 0 to 2 min extra wall clock). Other PRs skip them. WebKit-macOS stays nightly (scarce macOS runners).
- Saving: removes the 25 to 60 min branch Nightly re-run from web PRs (#524 waited on one), and the queue it causes.
- Gating: either (a) they count toward "CI passed" from the start, which makes web PRs red whenever a known flaky test fails, or (b) they report but are not in "CI passed" until #437's 5 green WebKit nightlies, and a red one is read by the reviewer like a nightly result today (D-731). I recommend (b).

**O5. Scoped mutation runs.** mutation.yml gets an input `paths` (the files a PR changed) and runs mutmut 3.8.1 only on those modules, with the fast suite minus browser, split over 4 runners by module.
- Saving: a critical PR's mutation run finishes in under 1 h instead of dying at 5 h (inferred; depends on the size of the changed modules). Review threads then read results instead of running mutants locally.
- Gating: none changed (REV final-round mutation stays).
- Measured 18 Nov 17:00Z (local, main 2cb10c5, `mutmut run "sci2audio.textprep.links*"`): mutmut first runs the whole fast suite once, serially, to map tests to mutants ("Running stats"), 20.7 min here, before any mutant. On main that baseline FAILS: tests/unit/test_web_design.py::test_every_font_is_the_licence_tables_file_byte_for_byte reads THIRD_PARTY_LICENSES.md, which `[tool.mutmut] also_copy` does not copy into mutants/. So mutation.yml cannot give a result on main today, whatever the time limit. PR 5 adds the file to also_copy and limits the test selection for a scoped run so the stats phase is minutes, not 20+.
- Measured 18 Nov 18:00 to 18:50Z (local, 4 cores, `THIRD_PARTY_LICENSES.md` added to also_copy, test selection limited to the 4 links test files, `mutmut run "sci2audio.textprep.links*"`): the project has **42,805 mutants**; textprep/links.py (1,097 lines) alone has 1,567, and 1,566 of them took the whole 50 min (1,196 killed, 365 survived, 5 timeouts). At that rate the whole project is about 23 h on one runner, which is why the hosted run dies at 5 h. So PR 5 scopes by mutant name down to functions (globs such as `sci2audio.textprep.links.x_name*`, from the functions a PR changed) and spreads the globs over up to 4 runners; a whole module stays possible but is about an hour per 1,500 mutants.

**O6. The "up to date with main" requirement (added 18 Nov 16:40Z at the coordinator's request).**
Measured: the main ruleset (id 26932142) requires "CI passed" with `strict_required_status_checks_policy: true`, squash only, linear history. main moved 16 times in the 2 days measured. #524 ran CI on 8 heads today, 3 of them only to catch up with main after approval (6bfe161 at 15:11, cc30e40 at 16:16, 5d5a6ce at 16:33), each 10 to 13 min for Linux plus a three-system dispatch when the PR is critical (the rule MRG-02 reads "the reviewed head").

Three ways out, with what each changes about gating:
- **O6a. Keep strict, but a catch-up head needs Linux CI only.** The three-system run stays on the reviewed head; after `update-branch` the reviewer confirms the PR diff is unchanged (as today) and merges on Linux "CI passed". The push to main then runs all three systems anyway. Saving: about 10 min per catch-up for critical PRs (O3 later makes the Linux run about 5 min). Gating: MRG-02 changes from "reviewed head" to "reviewed head, plus Linux on the catch-up head"; macOS/Windows breakage from the combination is caught on main after merge. Rules edit only, no ruleset change.
- **O6b. Drop the up-to-date requirement (recommended).** "CI passed" stays required on the PR's own head, but the PR no longer has to contain the newest main. A textual conflict still blocks the merge (GitHub refuses it). Saving: every catch-up loop goes away, so an approved PR merges at once. Gating: two PRs that are each green but break each other (a semantic conflict, for example two lanes both changing corpus snapshots) are found only by the CI run on main after the second merge (three systems, about 9 min). That needs a new rule: a red main is fixed or reverted by the lane that merged last before anything else merges. LANE-02 already keeps lanes that share files, goldens, regression cases or a layer contract from running side by side, which is where such conflicts come from, so I expect them to be rare (inferred, not measured). Ruleset change: one flag, Colin's or an admin's hand step in Settings, Rules, main; same for the release ruleset if wanted.
- **O6c. Merge queue.** GitHub tests each PR on top of main plus the PRs ahead of it, then merges; nobody updates branches by hand, and ci:full could run only in the queue. It is the strictest option, but GitHub offers merge queues only to repositories owned by an organization; dubidu22/sci2audio is owned by a personal account. It would need the repository moved to a (free) organization, which changes its address, the PyPI trusted-publisher setting and every link. That is Colin's call; I do not recommend it now.

Recommendation: O6b, with the red-main rule. If the coordinator prefers to keep strict, O6a.

**Applied 18 Nov ~19:25Z:** Colin turned off "Require branches to be up to date before merging" on ruleset main (O6b); rules 1.4.5 carry it as MRG-03/MRG-04. No workflow change was needed.

**Found while doing items 1 and 2 (18 Nov, 17:00 to 17:45Z)**
- **"CI passed" can be green with a cancelled macOS leg.** PR CI run 44349877322 (#546): `tests (macos-latest)` waited 34 min without a runner and was cancelled; "CI passed" then ran and passed, because `needs.tests.result` of a matrix job stays `success` when one leg is cancelled. MRG-02 already says to check the macOS and Windows jobs themselves; PR 3 will make "CI passed" read every job of its run through the API and fail on any leg that did not succeed.
- **macOS legs waiting about 35 to 40 min are being cancelled without a runner** (CI runs 44349424754, 44349877322; isolation try 44349709407). I did not cancel them and found no workflow that does; inferred: GitHub's hosted macOS capacity today. Keep macOS fan-out small (isolation defaults to 2 runners).
- **`playwright install --with-deps` has long tails**: median 0.3 min for Firefox and 0.6 for WebKit, but p90 7.7 min (Firefox) and up to 29 min (WebKit), all apt. Possible O7 later: run the Linux browser jobs in Playwright's own container image, which has the system packages built in. Not measured; not started.

**Considered and not recommended**
- More caching: setup is 5 to 22 s per job today; under 30 s to gain.
- Test selection by changed paths for the fast suite: saves about 2 to 3 min on a job that is not the critical path after O3, and risks missing layer-contract and golden breakage. Not worth it.
- Dropping matrix cells: macOS/Windows already run only on ci:full and pushes to main; WebKit-macOS is the app window's engine (D-47). Push-to-main three-system runs block nobody.
- Cancel-in-progress for PR CI: already on.

## 4. Recommended order

1. **O2 + O1 together** (nightly.yml + new isolate.yml): biggest saving on the actual waits, no required check touched, nightly is not required for merging. One PR, critical (CI), lane:infra.
2. **O3** (ci.yml browser shards): PR CI 9 to about 5 min. One PR, critical. Touches the required workflow but not "CI passed".
3. **O4** after a ruling on (a) or (b), and after O3 so the extra jobs are already sharded.
4. **O5** when the next critical PR needs mutation.

O6 is independent of the others and has the fastest effect: O6b is one ruleset flag plus a rules line, so it can go first, today.

Every PR above touches only .github/ (workflows and a helper script). If test_ci_workflows.py needs a new assertion for a new workflow, that is a tests/unit change and I will name it in the PR plan first. Each PR proves itself with one dispatched run whose times go into the PR body next to the numbers above.

## 5. What I need from the coordinator

- Approval of the order (O2+O1 first).
- A ruling on O4: (a) required at once, or (b) reported only until #437 closes (recommended).
- A ruling on O6: drop the up-to-date requirement with a red-main rule (O6b, recommended; Colin or an admin flips it in the ruleset), or keep it and run Linux only on catch-up heads (O6a).
- Whether rules TST-08 and the "nightly re-run before merge" practice should name isolate.yml and O4 once they land (a rules edit is yours, D-713).
