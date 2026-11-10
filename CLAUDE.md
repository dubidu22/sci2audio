# sci2audio: instructions for AI agents

sci2audio is a free, open-source, local-only desktop app (GPL-3.0-or-later) that turns scientific texts into faithful audiobooks. Owner and product decisions: Colin. Agents implement Issues; they never merge.

## Goal of v1.0

PDF, EPUB, Markdown or text in; a faithful listening script and MP3/M4B with chapters out; entirely offline; English first. Scope = the Issues in the milestone "v1.0". Anything else becomes a new Issue, never part of the current PR.

## Hard rules

- **No network calls** except a voice or model download the user started. No telemetry, no analytics, no crash upload, no paid APIs.
- **The web interface binds to 127.0.0.1 only.**
- **Licence gate:** every new dependency, copied file, model, voice or sample text names its licence in the PR body and in `THIRD_PARTY_LICENSES.md` (or `tests/corpus/LICENSES.md`). AGPL, non-commercial and unclear licences are refused. Third-party texts never enter the repo.
- **Faithful text:** text steps propose marked edits (remove, replace, pause, ask) with a reason; nothing rewrites text silently and nothing summarises (D-57).
- **Never merge, never push to `main`, never force-push.**

## Architecture (D-46): one program in layers

```
cli → web → app → [extraction | textprep | voices | output] → core
```

- `core`: shared data objects only (document, spans, edits, audio chunks).
- The four pipeline stages import only `core`, never each other and never `app`, `web` or `cli`.
- `app`: job runner and settings; wires the stages together.
- `web`: local FastAPI server and the HTML interface. `cli`: command line.
- `lint-imports` enforces this in CI. Fix the design, never the contract.

Keep a later web version possible: no global state (each job gets its settings and working folder passed in); file access and the job runner behind small interfaces; the pipeline never stops mid-run to ask the user.

## Workflow

1. One Issue → one branch → one PR, in one lane (`.github/lanes.yml`). Stop if the Issue lacks acceptance criteria.
2. Tests first: a failing test for a bug; a characterisation test before moving or splitting code; a regression case before any text rule change.
3. Run before opening the PR: `uv run ruff check && uv run ruff format --check && uv run lint-imports && uv run deptry src && uv run pytest -m "not slow"`.
4. PR title `<area>: <outcome> (#N)`; body with `Closes #N`, feature ID (e.g. `WI-02`), test summary, licence note, risk, and out-of-scope follow-ups.
5. Keep PRs small. More than about 400 changed lines of non-generated code: split.

## `risk:high` (Colin reads the whole diff)

Licences and third-party content; anything that deletes or overwrites user files; any network call; packaging and release workflows; the voice plugin contract and the text-step interface; the layer contract.

## Commands

```bash
uv sync                        # set up
uv run pytest -m "not slow"    # fast tests
uv run pytest                  # all tests
uv run ruff check --fix        # lint and fix
uv run ruff format             # format
uv run lint-imports            # layer rules
uv run deptry src              # unused or missing dependencies
```

## More rules

@.claude/rules/licences.md
@.claude/rules/tests.md
