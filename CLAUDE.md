# sci2audio: instructions for AI agents

sci2audio is a free, open-source, local-only desktop app (GPL-3.0-or-later) that turns scientific texts into faithful audiobooks. Owner: Colin, who decides the roadmap and product scope. While the autonomy grant in `rules/project-state.yaml` holds, Claude makes all other decisions and reviews and merges all PRs (D-80, D-462, D-702a). Implementation threads implement Issues; they never merge.

## Product and current goal

PDF, EPUB, Markdown or text in; a faithful listening script and MP3/M4B with chapters out; entirely offline; English and German. The current goal is the milestones in progress in `rules/project-state.yaml` and the roadmap in the KB decision log. Scope = the Issues in the milestone being worked on. Anything else becomes a new Issue, never part of the current PR.

## Hard rules

- **No network calls** except a voice or model download the user started. No telemetry, no analytics, no crash upload, no paid APIs.
- **The web interface binds to 127.0.0.1 only.**
- **Licence gate:** every new dependency, copied file, model, voice or sample text names its licence in the PR body and in `THIRD_PARTY_LICENSES.md` (or `tests/corpus/LICENSES.md`). AGPL, SSPL, non-commercial and unclear licences are refused. Third-party texts never enter the repo.
- **Faithful text:** text steps propose marked edits (remove, replace, pause, ask) with a reason; nothing rewrites text silently and nothing summarises (D-57).
- **Implementation threads never merge, never push to `main`, never force-push.** The coordinator merges a PR only after it passed review in a separate thread, by telling the review thread to merge it. While the autonomy grant in `rules/project-state.yaml` holds, this covers critical PRs too (D-80, D-702a).

## Architecture (D-46): one program in layers

```
cli → web → app → [extraction | layout | textprep | voices | output] → core
```

- `core`: shared data objects only (document, spans, edits, audio chunks).
- The five pipeline stages import only `core`, never each other and never `app`, `web` or `cli`.
- `app`: job runner and settings; wires the stages together.
- `web`: local FastAPI server and the HTML interface. `cli`: command line.
- `lint-imports` enforces this in CI. Fix the design, never the contract.

Keep a later web version possible: no global state (each job gets its settings and working folder passed in); file access and the job runner behind small interfaces; the pipeline never stops mid-run to ask the user.

## Workflow

The full rules are the project instructions in the claude.ai project and the decision log in `dubidu22/sci2audio-design` (`docs/kb/00-index/decision-log.md`); this is a short summary. The machine-readable summary of the active rules is `rules/project-rules.yaml` in the claude.ai project files, with the current state in `rules/project-state.yaml`.

1. **Autonomy and reporting.** While the autonomy grant in `rules/project-state.yaml` holds, the coordinator reviews and merges all PRs, critical ones included, and decides everything except roadmap and product scope (D-80, D-462, D-702a). Colin is told only when he asks about progress or when a decision is critical; a critical merge gets one line (D-626, D-702g).
2. **Lanes.** PRs are batched by lane (extraction/voices, layout, textprep, app/release): one PR per lane covers several related Issues. Several lanes run in parallel while they do not block each other, with at most one implementation thread and one review thread per lane; lanes that touch the same files, golden files, regression cases or layer contract wait for each other (D-741, LANE-02). A lane thread lives for one batch (D-626). A PR changes files of its own lane only (`.github/lanes.yml`). An Issue without acceptance criteria is not started; ask the coordinator for them first (PLAN-04).
3. **Plan first.** Post a plan (modules or types, design choices, tests, rough size) before any code or tests. Non-critical work whose plan is clearly better than the alternatives starts at once; critical work, or a plan with a real open choice, waits for the coordinator's approval (D-72, D-80).
4. **Tests first:** a failing test for a bug; a characterisation test before moving or splitting code; a regression case before any text rule change. A PR that adds the first code of a kind also adds its tests and CI wiring (table in `.claude/rules/tests.md`, D-58).
5. **Before opening the PR** run `uv run ruff check && uv run ruff format --check && uv run lint-imports && uv run deptry src && uv run pytest -m "not slow and not benchmark and not browser"`; for a change to the interface also `uv run pytest -m browser`.
6. **PR title** `<area>: <outcome> (#N)`; body with `Closes #N`, feature ID (e.g. `WI-02`), test summary, licence note, risk, and out-of-scope follow-ups. Never write a closing keyword ("fixes #N") in a commit message. No fixed size limit: split a PR only when its parts can be reviewed and merged on their own (D-75).
7. **Review.** Every PR except the daily decision-log PR is reviewed in a separate thread that did not write it, one review thread per batch (D-626, D-702c). A PR goes to review only after its Linux CI is green, and a critical PR also after the author's own `ci:full` run is green, after which the author removes the `ci:full` label so fix commits run Linux only; during a review round the author freezes the branch and pushes one fix commit per round (D-698). At most two rounds, leftovers become Issues; a critical PR may go to round four, then waits for Colin (D-626). Findings are answered by listing exactly what was fixed and why; anything deferred gets an Issue (D-68). Mutation, nightly seeds and the three-system run are for critical PRs on the final round only, apart from the author's pre-review `ci:full` run (D-626, D-714).
8. **Merge.** The review thread squash-merges on the coordinator's go, pinned to the reviewed head, once `CI passed` is green on it. A critical PR also needs a green run on Linux, macOS and Windows of that head (D-580). Check that `tests (macos-latest)` and `tests (windows-latest)` succeeded on it; `CI passed` alone can still show the earlier Linux-only run. PRs into a `release/N.N` branch start Linux CI only; a critical one still gets a `ci:full` three-system run on its final round before merge (D-702g, D-703b).
9. **Flaky tests.** A test that fails twice without a code cause is quarantined the same day with a linked Issue and fixed before the next release (D-374, D-702f); a test with a known code cause is fixed, not quarantined; after the same-day quarantine, run the test alone 40 or more times and record the result in its Issue; if that finds a code cause, fix the test and lift the quarantine (D-682, D-739).
10. **KB.** One KB thread writes and merges one decision-log PR per day, without review (D-373, D-626); implementation threads do not open KB PRs. Other KB changes (process, contract and architecture documents) are critical and reviewed like code (D-703c).

## Critical and `risk:high` (full plan and review process; while the autonomy grant in `rules/project-state.yaml` holds, the coordinator approves the plan and the merge, D-80, D-702a)

A PR is **critical** if it changes a layer contract (the `lint-imports` layers, the voice plugin contract, the text-step interface), the core dataclasses (`sci2audio.core`), the KB's process, contract or architecture documents (`sci2audio-design/docs/kb`; the daily decision-log PR is exempt, D-703c) or a golden file (corpus truth files, snapshots, English regression cases), whatever its label says (D-69). Label it `risk:high`.

Also `risk:high`, and so critical: licences and third-party content; anything that deletes or overwrites user files; any network call; packaging, release and CI workflows; safety mechanisms.

## Commands

```bash
uv sync                        # set up
uv run pytest -m "not slow and not benchmark and not browser"   # fast tests (as in CI)
uv run playwright install chromium  # once: the browser for the browser tests
uv run pytest -m browser       # the interface in Chromium (main flow, keyboard, axe-core)
uv run pytest                  # all tests
uv run pytest --snapshot-update  # accept changed golden files (review the diff)
uv run zizmor --offline .github/workflows  # workflow security
uv run mutmut run && uv run mutmut results  # mutation testing (slow)
uv run ruff check --fix        # lint and fix
uv run ruff format             # format
uv run lint-imports            # layer rules
uv run deptry src              # unused or missing dependencies
```

## More rules

@.claude/rules/licences.md
@.claude/rules/tests.md
