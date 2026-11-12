# sci2audio: instructions for AI agents

sci2audio is a free, open-source, local-only desktop app (GPL-3.0-or-later) that turns scientific texts into faithful audiobooks. Owner: Colin. Until v1.0, Claude makes the product and design decisions and tells Colin of each one in the project chat (D-80). Implementation threads implement Issues; they never merge.

## Goal of v1.0

PDF, EPUB, Markdown or text in; a faithful listening script and MP3/M4B with chapters out; entirely offline; English first. Scope = the Issues in the milestone "v1.0". Anything else becomes a new Issue, never part of the current PR.

## Hard rules

- **No network calls** except a voice or model download the user started. No telemetry, no analytics, no crash upload, no paid APIs.
- **The web interface binds to 127.0.0.1 only.**
- **Licence gate:** every new dependency, copied file, model, voice or sample text names its licence in the PR body and in `THIRD_PARTY_LICENSES.md` (or `tests/corpus/LICENSES.md`). AGPL, non-commercial and unclear licences are refused. Third-party texts never enter the repo.
- **Faithful text:** text steps propose marked edits (remove, replace, pause, ask) with a reason; nothing rewrites text silently and nothing summarises (D-57).
- **Implementation threads never merge, never push to `main`, never force-push.** The coordinator merges a PR only after it passed review in a separate thread, by telling the review thread to merge it. Until v1.0 this covers critical PRs too; Colin is informed with one project-chat line per decision and per merge (D-68, D-77, D-80).

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

1. One Issue → one branch → one PR, in one lane (`.github/lanes.yml`). Stop if the Issue lacks acceptance criteria.
2. Plan first: post a plan in the thread (modules or types, design choices, tests, rough size) before any code or tests. Non-critical work whose plan is clearly better than the alternatives starts at once; critical work, or a plan with a real open choice, waits for the coordinator's approval (D-72; until v1.0 the coordinator approves instead of Colin, D-80).
3. Tests first: a failing test for a bug; a characterisation test before moving or splitting code; a regression case before any text rule change.
4. Run before opening the PR: `uv run ruff check && uv run ruff format --check && uv run lint-imports && uv run deptry src && uv run pytest -m "not slow and not benchmark"`.
5. A PR that adds the first code of a kind also adds its tests and CI wiring (table in `.claude/rules/tests.md`, D-58).
6. PR title `<area>: <outcome> (#N)`; body with `Closes #N`, feature ID (e.g. `WI-02`), test summary, licence note, risk, and out-of-scope follow-ups.
7. No fixed size limit for PRs. Split a PR only when it splits naturally into parts that can be reviewed and merged on their own.
8. Every PR is reviewed in a new thread that did not write it. Answer findings by listing exactly what was fixed and why; anything deferred gets an Issue (D-68).

## Critical and `risk:high` (full plan and review process; until v1.0 the coordinator approves the merge, D-80)

A PR is **critical** if it changes a layer contract (the `lint-imports` layers, the voice plugin contract, the text-step interface), the core dataclasses (`sci2audio.core`), the KB (`sci2audio-design/docs/kb`) or a golden file (corpus truth files, snapshots, English regression cases), whatever its label says (D-69). Label it `risk:high`.

Also `risk:high`, and so critical: licences and third-party content; anything that deletes or overwrites user files; any network call; packaging and release workflows.

## Commands

```bash
uv sync                        # set up
uv run pytest -m "not slow and not benchmark"   # fast tests (as in CI)
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
