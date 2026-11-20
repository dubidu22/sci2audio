# #80 release plan: sci2audio 1.0.0 on PyPI

Written 14 Nov 2026, 01:10 UTC, on main f1a334a (after PR #218). **Approved** by the coordinator 01:05–01:06 UTC as D-484 to D-489; additions D-490 and D-492 (01:24 UTC) are in section 8 and in the steps below. Status 01:30 UTC: R1 merged as PR #224 (2819458); R2 is PR #225, in review. Nothing gets tagged or published before the coordinator approves the tag.

## 1. Where #80 stands today

| #80 acceptance criterion | State on main f1a334a | Work |
|---|---|---|
| Wheel installs on clean Linux, macOS and Windows runners and runs `sci2audio script` on a corpus PDF (CI job in the release workflow) | **Missing.** `release.yml` only builds and publishes. CI's smoke test runs `uv run sci2audio script` from the source tree, not from an installed wheel. | PR R1 |
| `THIRD_PARTY_LICENSES.md` complete; licence check passes | The `licences` CI job is green. Completeness against the wheel's run-time dependencies is not yet checked by hand. | PR R2: check every run-time dependency, the Kokoro model and voices, the spaCy model, and ffmpeg (imageio-ffmpeg) against the file |
| README: install per system, privacy statement, licence, before/after example from our own text, "convert only texts you may use" | **Pre-release text.** "Not ready for use yet", "What it will do", "Installing (once released)". No before/after example, no "texts you may use" note. | PR R2 |
| `CHANGELOG.md` and version 1.0.0 | Version is `0.0.1.dev0` (`src/sci2audio/__init__.py`; hatch reads it there). The changelog's "Unreleased" section covers only 13 issues (#7 #12 #18 #21 #23 #24 #72 #73 #76 #78 #79 #120 #136). | PR R2 |
| Release checklist done | See section 4. ZAP has no run on `main` yet, and the mutation workflow has never run. | Section 4 |
| Learning notes in `docs/learning/` | Only `phase-template.md`. The template is first person (hours spent, what Colin would tell a client). | PR R2 adds a draft from the record, marked for Colin to correct |
| No quarantined tests | Met: `uv run pytest -m quarantined --collect-only -q` collects none (checked today). | none |

Also open: `[project.urls] Homepage = "https://sci2audio.com"` in `pyproject.toml`. PyPI shows that link on the project page, so the domain should answer before the release (Colin's step, section 5). The name `sci2audio` is still free on PyPI (`/pypi/sci2audio/json` answers 404 today).

## 2. Two PRs before the tag

Both are `risk:high` and critical (packaging and release workflow), so each needs the coordinator's plan approval and a review thread. They split cleanly: R1 is workflow only, R2 is docs and version only.

### PR R1: `release: the wheel is installed and tried on three systems before it is published (#80)`

Changes to `.github/workflows/release.yml`. Every action stays pinned by SHA, and zizmor must be clean.

1. **`build`** (as today): `uv build` makes the sdist and the wheel. It also checks that the tag equals `v` + `sci2audio.__version__`, and fails the release if not.
2. **`smoke`** (new), a matrix over ubuntu-latest, macos-latest and windows-latest. It needs `build`, checks out the repo for the corpus PDF only (`persist-credentials: false`), and downloads `dist/`:
   - `uv tool install dist/sci2audio-*.whl` with uv-managed Python 3.12.16 or newer (D-378). On Linux it adds `--torch-backend cpu`, which is the README's command and avoids 5.6 GB of CUDA.
   - `sci2audio --version` prints the tag's version.
   - `sci2audio script tests/corpus/papers/joss2021-waskom-seaborn.pdf -o … --work-folder … --ignore-settings`, from a folder outside the checkout so the source tree cannot be imported, followed by the same three non-empty output files that CI checks.
   - No voice download: the release smoke test stays offline, as in CI. The nightly run already covers the real voice.
3. **`publish`**: now `needs: [build, smoke]`, so nothing reaches PyPI unless all three systems passed. It keeps environment `pypi`, `id-token: write` and trusted publishing, with no stored token.
4. **`github-release`** (new, after `publish`): creates the GitHub release for the tag. The notes are the tag's section of `CHANGELOG.md`, and the sdist and wheel are attached. Only this job gets `contents: write`.
5. **`from-pypi`** (new, after `publish`, three systems): `uv tool install sci2audio==<version>` from PyPI (on Linux with `--torch-backend cpu`), retried for up to 10 minutes while the index catches up, then the same `script` run. This automates the checklist's "install from PyPI on a clean machine".

Testing before the merge:
- zizmor and actionlint on the workflow.
- On the branch, a copy of the build and smoke jobs runs through `workflow_dispatch`. This needs a temporary `workflow_dispatch` trigger with publish skipped, removed before the review.

The PR body names the exact run.

### PR R2: `release: version 1.0.0, changelog, README and learning notes (#80)`

- `src/sci2audio/__init__.py`: `__version__ = "1.0.0"`. No golden file holds the version string (checked with grep), so snapshots stay byte-identical.
- `CHANGELOG.md`: "Unreleased" becomes `## [1.0.0] - <release date>` plus a new empty "Unreleased". It covers every merged PR since the pivot (70 merged PRs, #1 to #218), grouped as Keep a Changelog wants: Added by stage (input formats, layout, text rules, voice, audiobook output, app and command line, interface and player, privacy and security, testing), Changed, and Fixed. Process-only PRs (#30, #44) and test-only PRs (#84, #137, #170, #182, #218) go under one "Development" line. Each line keeps its issue numbers. Comparison links at the bottom.
- `README.md` rewritten for release, keeping its tone:
  - What it does today.
  - Install per system: the existing uv and pipx commands, ffmpeg bundled through imageio-ffmpeg with an ffmpeg on PATH as fallback, and the no-Intel-Mac note.
  - First run: `sci2audio ui`, `voices download`.
  - Privacy statement: the same points as `/privacy`.
  - What the rules do, with one before/after from a corpus text whose licence allows quoting (from `tests/corpus/LICENSES.md`), never a third-party text outside the corpus.
  - "Convert only texts you may use".
  - The synthetic-voice (AI) label.
  - Licence.
  - Where to report problems.
- `docs/release-checklist.md`: the "(not yet possible)" marks come off the listening test, screen-reader pass and install-from-PyPI items, because the code exists now.
- `docs/learning/v1.0.md`: a draft from the record (KB decisions, the plans folder, the review rounds) in the template's headings. "Hours spent" and "What I would tell a client" are left for Colin. The draft says it is a draft.
- `THIRD_PARTY_LICENSES.md`: rows checked against `uv export --no-dev` for the wheel's run-time set, and any gap filled.

## 3. The tag and what the release workflow then does

Once R1 and R2 are merged, the checklist (section 4) is done, and the coordinator approves the tag:

1. **Release branch (D-490).** Right after PR #225 merges, the #80 review thread cuts `release/1.0` from its merge commit. v1.1 PRs land on `main` only. The release-day PR targets `release/1.0`: the changelog date (the build job refuses a tag without `## [1.0.0] - YYYY-MM-DD`), `docs/listening-tests/1.0.0.md` and the M4 rows in `docs/baseline.md`. A later PR then merges it forward into `main`.
2. The coordinator, or a thread it names, pushes the annotated tag `v1.0.0` on `release/1.0` after the release-day PR, never on `main`: `git tag -a v1.0.0 -m "sci2audio 1.0.0"`, `git push origin v1.0.0`. This thread does not tag without that approval.
3. `release.yml` runs: build and the version check → smoke on three systems → publish to PyPI (it waits there for the reviewer of the `pypi` environment, if Colin sets one; recommended) → GitHub release with the changelog section → install from PyPI on three systems.
4. After that: close #80 and the v1.0 milestone, add one chat line for Colin, and send the release to the daily KB batch.

If a job before `publish` fails, nothing has been published. Delete the tag, fix it in a PR, and tag again. Once `publish` has run, PyPI never accepts 1.0.0 again, so any fix is 1.0.1. That is why the smoke job sits before publish.

## 4. Release checklist (`docs/release-checklist.md`), who does what

Automatic, this thread or the coordinator:
- CI on main green; last nightly green. The 02:17 UTC nightly run on f1a334a is the first one that includes #208 and #218.
- No open Dependabot security alert. This needs a look in the repo's Security tab: the API path is blocked in these sessions.
- CI, nightly and release on uv-managed CPython 3.12.x (log lines).
- No quarantined tests: met.
- **ZAP baseline scan**: start a run by hand (`workflow_dispatch`) **with ref `release/1.0`, not `main`** (D-490), once that branch exists. Paste `zap-summary.md` into #80. The pinned ZAP image must be less than 3 months old. Note: the walk is flaky (#177, v1.2), so a red run at "audiobook files exist already" gets re-run once, not counted as an alert.
- **Mutation run**: start `mutation.yml` by hand **with ref `release/1.0`**, look at survivors in `textprep/`, and add tests where a survivor changes what users hear. That would be a small PR R3 if needed.

## 5. Colin's own steps

These need Colin's hands or accounts; no thread can do them:
1. **Listening test**: `docs/listening-tests/template.md`, the same 10 paragraphs, saved as `docs/listening-tests/1.0.0.md`.
2. **Screen-reader pass**: one full job (open a file, read the pre-analysis, start, play, read-along), keyboard only, with VoiceOver on macOS and NVDA on Windows. Each problem becomes an issue.
3. **Speed run on the MacBook Pro M4**: `uv run sci2audio voices download`, then `uv run python scripts/speed.py` (about 10 minutes). Paste the rows into `docs/baseline.md` and keep the JSON. This also checks #136's criterion 2.
4. **PyPI trusted publisher**:
   - On pypi.org → Account → Publishing → "Add a new pending publisher": PyPI project name `sci2audio`, owner `dubidu22`, repository `sci2audio`, workflow `release.yml`, environment `pypi`.
   - On GitHub → repo Settings → Environments: create `pypi`. Recommended: add himself as required reviewer, so the publish step waits for his click.
   - If he limits the `pypi` environment to selected branches and tags ("Deployment branches and tags"), he must allow the **tag pattern `v*`**, not the branch `main`: the release runs on the tag, which sits on `release/1.0` (D-490).
5. **Retire the hosted demo** (playbook phase 1).
6. **sci2audio.com**: make the domain answer (a simple page or a redirect to the GitHub repo), or tell us to change `Homepage` in `pyproject.toml` in PR R2 before the tag.
7. Optional: the install-from-PyPI try on his own machine after the release. The `from-pypi` job covers clean runners.

## 6. Order and rough size

1. Approval of this plan.
2. R1 and R2 in parallel: R1 is about 1 to 2 hours with the branch run, R2 is about 2 to 3 hours (the changelog over 70 PRs and the README). One review thread each, or one thread for #80 per D-376.
3. Then ZAP and the mutation run on main, plus R3 if survivors need tests.
4. Colin's steps 1 to 6. The tag waits for them, because steps 1 to 3 are on the checklist and step 4 is needed for `publish` to work.
5. PR #225 merged → `release/1.0` cut (D-490) → `main` moves to `1.1.0.dev0` (D-492) → ZAP and mutation on `release/1.0` → release-day PR on `release/1.0`.
6. The coordinator approves the tag → `v1.0.0` on `release/1.0`.

## 7. Choices in this plan (for the decision log)

- a. The version is **1.0.0** and the tag **v1.0.0** (SemVer; the milestone stays "v1.0").
- b. The release workflow tries the built wheel on three systems **before** publishing, and installs from PyPI on three systems after.
- c. The workflow makes a GitHub release with the changelog section and the files.
- d. The smoke test stays offline: no voice download in the release workflow.
- e. The tag waits for Colin's hand steps (listening, screen reader, M4 speed) and the trusted publisher. **Alternative:** tag as soon as R1 and R2 are in and he has set up the trusted publisher, and do the hand steps on 1.0.0 with any problem going to v1.0.1. That gets the release out sooner but breaks the "checklist done before release" rule, so I recommend waiting.
- f. The learning note is drafted by Claude from the record and finished by Colin.

## 8. Additions after approval (coordinator, 14 Nov 01:24 UTC)

- **D-490, release branch.**
  - The #80 review thread cuts `release/1.0` from PR #225's merge commit right after the merge, and the tag `v1.0.0` goes there.
  - v1.1 PRs land on `main` only.
  - The release-day PR (changelog date, listening-test file, M4 rows) targets `release/1.0` and is then merged forward into `main` by a PR.
- **ZAP and mutation runs**: started by hand with ref `release/1.0`, not `main`, once the branch exists. The results go to the coordinator.
- **D-492, main moves on.** Once `release/1.0` exists, a small PR on `main` sets `__version__ = "1.1.0.dev0"`. R2 already leaves an empty "Unreleased" section above 1.0.0, so the changelog needs no change there. The #80 review thread reviews and merges it.
- **The `pypi` environment** (Colin's step 4): if it is limited to selected branches and tags, allow the tag pattern `v*`, not the branch `main`.
- **Date guard** (review of PR #225, F3): the build job fails unless `CHANGELOG.md` has `## [<version>] - YYYY-MM-DD` for the tag's version. So the release-day PR must set the date before the tag.
