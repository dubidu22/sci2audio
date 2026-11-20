# Release plan: sci2audio 1.1.0 on PyPI

Written 15 Nov 2026, 22:20 UTC, on main a9e0e2d (PR #382), by the thread "Release v1.1". **Status: approved as D-669** (coordinator, 15 Nov 22:05 UTC). `release/1.1` cut from a9e0e2d at about 22:10 UTC; R1 is PR #403, merged into `release/1.1` as 08d5965 at 22:44 UTC after round 1 (B1 file id, C1 to C3). #365 is closed. Nightly 43770960312, ZAP 43770962498 and mutation 43770964278 run on 08d5965. Colin's steps are in `release-v11-colin-steps.md`. The learning note (choice g) is left out of R1.

Basis: Colin's "both yes" (15 Nov 22:00:23 UTC, D-667): v1.1 is released now; v1.2 textprep work resumes in parallel. The pattern is the v1.0.0 release (`plans/issue80-release-plan.md`, D-484 to D-492, D-569/D-570).

## 1. Where v1.1 stands

| Item | State on a9e0e2d |
|---|---|
| Milestone v1.1 (#2) | 46 of 46 closed (milestone itself still open). |
| Code since v1.0.0 | 51 commits on main that are not in v1.0.0 (API compare v1.0.0...main). |
| CI on a9e0e2d | All green: `CI passed`, `tests (ubuntu/macos/windows-latest)`, browser, lint and layers, licences, security, CodeQL. |
| Last nightly on main | Green, 0af10d0 (15 Nov 09:35 UTC). Not yet run on a9e0e2d. |
| Version | `1.1.0.dev0` in `src/sci2audio/__init__.py`. |
| CHANGELOG "Unreleased" | Covers about half of v1.1 (section 3 lists what is missing). |
| README | Line 5 still says "a … file **in English**"; the rest already names German, subtitles and `listen`. |
| Quarantined tests | **One:** `tests/browser/test_flow.py::test_pasted_text_opens_and_is_analysed` (#365, D-634). Section 4. |
| ZAP image | Pinned 2 Nov 2026 (ZAP 2.17.0): under three months, fine. |
| Release workflow | Unchanged since v1.0.0, which it published cleanly (run 43695852014). Tag must equal `v` + `__version__`; CHANGELOG must have `## [1.1.0] - YYYY-MM-DD`. |
| Rulesets | `release/*` ruleset (D-491): PR required, squash/linear, `CI passed` required, no deletion or force-push. Branch **creation** is not restricted, so a thread can cut `release/1.1`. Branches for PRs into it must not be named `release/...` (lesson of PR #245/#251): use `release-prep/1.1.0` and `release-day/1.1.0`. |

## 2. Steps in order

1. **Cut `release/1.1` from a9e0e2d** right after approval (git ref created via the API; this thread). From then on v1.2 work merges to `main` only, as D-490 did for 1.0. This keeps the textprep lane's next PR out of 1.1.0 without pausing it.
2. **PR R1 `release: version 1.1.0, changelog, README and the #365 test fix`**, branch `release-prep/1.1.0`, base `release/1.1`, `risk:high`, `lane:app`. Contents in section 3. One review thread (Opus high, critical). The push to `release/1.1` after the merge runs CI on Linux, macOS and Windows.
3. **Checklist runs on `release/1.1`** after R1 is merged, started by `workflow_dispatch` from this thread: nightly, ZAP baseline scan, mutation run (section 5).
4. **Colin's hand steps** on `release/1.1` (section 6).
5. **PR R2 `release: release day for 1.1.0`**, branch `release-day/1.1.0`, base `release/1.1`: the date in `## [1.1.0] - YYYY-MM-DD`, `docs/listening-tests/1.1.0.md` with Colin's scores, the M4 rows in `docs/baseline.md`. Docs only; same review thread, one round.
6. **Tag**: once R2 is merged, `CI passed` is green on all three systems on the tip of `release/1.1`, and the coordinator approves, Colin pushes the annotated tag `v1.1.0` on that tip (threads cannot push tags). `release.yml`: build and version/date check → wheel smoke on three systems → publish (waits for Colin's click on the `pypi` environment) → GitHub release with the changelog section → install from PyPI on three systems. This thread watches the run and reports.
7. **PR R3 `release: forward release/1.1 into main, main moves to 1.2.0.dev0`**, base `main`: merges `release/1.1` forward (CHANGELOG conflicts with any new "Unreleased" lines from v1.2 PRs resolved by keeping both), and `__version__ = "1.2.0.dev0"`. Same review thread.
8. **After the release**: close the v1.1 milestone; one line to the coordinator; the release record goes to the KB thread's daily batch.

If a job before `publish` fails, nothing is published: Colin deletes the tag (`git push origin :refs/tags/v1.1.0`), we fix it in a PR on `release/1.1` and tag again. Once `publish` has run, 1.1.0 is final and any fix is 1.1.1.

## 3. PR R1 contents

- `src/sci2audio/__init__.py`: `__version__ = "1.1.0"`. (v1.0 checked that no golden file holds the version; the PR re-checks with grep.)
- `CHANGELOG.md`: "Unreleased" becomes `## [1.1.0] - unreleased` until R2 sets the date (the build job refuses the tag without a date, so a forgotten R2 cannot slip through), plus a new empty "Unreleased" on top and the comparison links (`[1.1.0]: …/compare/v1.0.0...v1.1.0`). A short summary paragraph under the heading: German texts read as German (voice, rules, notices, language guess), footnotes at their mark, subtitles, player speed and remembered position, chapter order, `sci2audio listen`, EPUB publisher's pages, PDFs read in a separate process with page progress and cancel, second-run consistency. Existing entries stay as written. **Missing entries to add**, one line each with issue numbers, grouped as the file already groups them:
  - Added: German abbreviations, symbols and units read in full (#113, PR #228); German numbers, dates and statistics (#130, #242); German links and citations (#101, #256); German sentence ends after ordinals and units (#227, #229, #267); German legal-form abbreviations "i. S. v.", "i. V. m." and other German readings, units after "per" (#230, #231, #233, #250, #265, #358, #264, #243, PR #382); code blocks read as one notice, code listings as CODE blocks (#280, #288, #289); alphanumeric citation keys read, a reference list without a heading left out (#254, #92, #377); PDFs read in a separate process with 1 GB memory and 60 s per step (#185, #28, #345, D-616 #363).
  - Fixed: grant and award numbers in brackets not read (#285, #300); the read-along shows a word joined at a line end without its hyphen (#286, #290); an inline fraction reads numerator and denominator apart (#202, #323); German second-run fixes (#253 #263, #266 #270, #269 #273, #271 #279, #303 #311); a deep bracket nest costs what it did before (#313, #317); the job page's buttons wait for their click handlers (#177, #350).
  - Development: macOS and Windows on main, release branches and `ci:full` (D-580, #325); mutation run fixes and the pinned survivors (#244, #262); timing tests against a baseline and on CPU time (#274, #276, #294); the pasted-text browser test quarantined and fixed (#365, #369, this PR).
  The PR body has a table of all 51 commits since v1.0.0 with the changelog line that covers each.
- `README.md` line 5: "in English" becomes "in English or German". Nothing else.
- **#365 fix** (section 4, if chosen): `test_pasted_text_opens_and_is_analysed` waits for `#document[data-events]` to have count 0 before `check_axe`, the quarantine marker comes off, and the same wait goes into any other test that runs axe on a document page right after it opens. Proof: the browser job passes 5 runs in a row on one head (dispatch runs, ids in the PR body).
- `docs/learning/v1.1.md`: a one-page draft from the record in the template's headings, marked as a draft; "Hours spent" and "What I would tell a client" left for Colin (as D-489). Optional: drop it if the coordinator wants R1 smaller.
- Checks before opening: the full fast suite, browser suite, ruff, lint-imports, deptry, zizmor; locally the build job's three checks (tag/version, the date grep fails as intended on "unreleased", the release-notes awk extracts the 1.1.0 section) and `uv build` gives `sci2audio-1.1.0` wheel and sdist.

## 4. #365: ship with the quarantine, or fix first?

**What the quarantine skips.** The only browser test of the pasted-text path: paste text, give it a name, open it, see the document page with "My notes.txt" as its heading, and axe-core on the start page with pasted text and on that document page. The pasted-text path itself is still covered below the browser (the API and TestClient tests that keep pasted text as `<name>.txt` and read it as plain text, #74), and axe runs on the same document page template in other browser tests. So the gap is: no end-to-end check that the paste form works in a real browser, and no axe check of those two exact page states.

**Cause.** The test, not the product: the document page reloads itself when its analysis job ends, and if that lands while axe runs, the execution context is destroyed. The conftest helper already has the right wait (`tests/browser/conftest.py:221`).

**Risk of shipping with it.** Low for users: no known product fault behind it. But it breaks the standing rule (D-374: every quarantined test fixed before the release) and the release checklist item "No quarantined tests", and v1.1 changed the document page a lot (chapter order buttons, publisher hints, subtitles choice), so the pasted-text page is exactly what has had no browser check since 15 Nov.

**Recommendation: fix it first, inside R1.** It is about three lines plus five green browser runs, it keeps D-374 intact, and it costs less than writing the exception into the KB. #365 then comes out of Working Reader batch C (D-665), which needs one line in the plan file. Alternative: ship with the quarantine as a recorded exception to D-374, and #365 stays in batch C.

## 5. Checklist runs (this thread)

- **Nightly** on `release/1.1` by `workflow_dispatch` after R1 merges (slow tests, many-example properties, benchmarks, Firefox and WebKit browser tests). Must be green.
- **ZAP baseline scan** on `release/1.1` by `workflow_dispatch`; `zap-summary.md` goes into the R2 body. A red walk step is re-run once (D-602).
- **Mutation run** on `release/1.1` by `workflow_dispatch`. #246 (the run finishing on a hosted runner) is still open, so as for 1.0 (D-531) a partial result is accepted: whatever it reports in up to 3 hours goes into the R2 body, survivors that change what users hear get tests in R2 or a test-only PR, the rest go to #260. It does not hold the tag.
- **Quarantine list**: `uv run pytest -m quarantined --collect-only -q` collects none (after the #365 fix).
- **Dependabot**: the alerts API is closed to threads (403), so Colin looks at the Security tab (section 6).
- **Python version lines** (uv-managed 3.12.x) checked in the CI, nightly and release logs.

## 6. Colin's hand steps

His clone is `~/Documents/Projekte/sci2audio` on the MacBook Pro M4. Commands are written without comments; the explanation is beside each block.

**A. Get the release branch** (once R1 is merged):

```
cd ~/Documents/Projekte/sci2audio
git fetch origin
git switch -c release/1.1 --track origin/release/1.1
uv sync
uv run sci2audio --version
```
Switches the clone to the release branch and sets up its packages; the last line must print `1.1.0`. If the branch exists locally already, use `git switch release/1.1` and `git pull --ff-only` instead of the third line. If `uv run` says "No module named 'sci2audio'", run `chflags -R nohidden .venv` (the iCloud flag, #255).

**B. Listening test** (about 30 minutes): the same 10 English paragraphs as 1.0.0 (`docs/listening-tests/1.0.0.md`), this time with a score from 1 to 5 in each cell. New for 1.1, three German paragraphs from the corpus paper `arxiv2017-maass-privacyscore.pdf` (German voice Thorsten), which R2 adds to the template as rows 11 to 13 so later releases compare on them too. This thread picks the three paragraphs and posts them before Colin starts.

```
uv run sci2audio voices download --language de
uv run sci2audio convert tests/corpus/papers/arxiv2017-maass-privacyscore.pdf -o ~/Desktop/sci2audio-1.1
uv run sci2audio listen tests/corpus/papers/arxiv2017-maass-privacyscore.pdf -o ~/Desktop/sci2audio-1.1
```
Fetches the German voice (about 330 MB, it asks first), makes the German paper's audiobook on the Desktop, and opens it in the read-along player. The English papers work the same way with their file names, or through `uv run sci2audio ui`. He sends his scores and notes in the thread; this thread writes them into `1.1.0.md`.

**C. Screen-reader pass, short** (about 15 minutes): VoiceOver (Cmd-F5), keyboard only, on the controls new in 1.1: the Speed choice in the player, "Continue from …" and "Start from the beginning", "Move up" and "Move down" in the chapter list, and the subtitles checkbox. Known VoiceOver trouble is #314 (Working Reader batch D) and is not re-reported; anything new becomes an issue. NVDA on Windows is skipped, as for 1.0.0, since there is no Windows machine.

**D. Speed run on the M4** (about 10 minutes):

```
uv run python scripts/speed.py
```
Prints rows for `docs/baseline.md` and writes a JSON file; he pastes the printed rows into the thread. It checks that the separate PDF reader process (#345) has not slowed the job. No German-voice row: `scripts/speed.py` accepts English voices only (checked in R1), filed as #404.

**E. Dependabot**: open https://github.com/dubidu22/sci2audio/security/dependabot and say whether any alert is open.

**F. The tag** (after R2 is merged and the coordinator approves):

```
cd ~/Documents/Projekte/sci2audio
git fetch origin
git tag -a v1.1.0 -m "sci2audio 1.1.0" origin/release/1.1
git push origin v1.1.0
```
Fetches the final release branch, puts the annotated tag on its tip and pushes it, which starts the release workflow. This thread posts the exact commit the tag must land on before he runs it.

**G. Approve the publish**: when this thread says the release run waits, open the run link, click "Review deployments", tick `pypi`, and click "Approve and deploy".

Optional: the M4B check in Apple Books (chapter titles, jumping, cover and the AI-generated label), unticked for 1.0.0.

## 7. Choices for the decision log

- a. Version **1.1.0**, tag **v1.1.0**, on a branch **`release/1.1`** cut from a9e0e2d, as D-490 did for 1.0; PR branches named `release-prep/…` and `release-day/…` so the `release/*` ruleset does not block their pushes.
- b. **#365 is fixed in R1 before the release** (recommended), instead of a recorded exception to D-374.
- c. The listening test keeps the 10 English rows, now scored, and **adds three German rows** from the German corpus paper, since German reading is v1.1's theme.
- d. The screen-reader pass covers only the controls new in 1.1; VoiceOver only.
- e. A partial mutation result is accepted and does not hold the tag (as D-531).
- f. The CHANGELOG heading reads `## [1.1.0] - unreleased` until the release-day PR sets the date, so the build job's date check guards the order.
- g. The learning note for v1.1 is a short Claude draft finished by Colin (as D-489), and can be dropped.
- h. After the tag, `release/1.1` is merged forward into `main`, and `main` moves to **1.2.0.dev0** in the same PR (R3).

Not in this plan: the open v1.0.1 milestone (#3, 12 issues). 1.0.1 was never released; its issues stay open where they are, and moving them is the coordinator's call.

## 8. Size

R1: about 2 hours (most of it the changelog lines and the five browser runs). Checklist runs: hours of runner time, no thread time beyond starting and reading them. Colin: about an hour in all (B to G). R2 and R3: under an hour each.
