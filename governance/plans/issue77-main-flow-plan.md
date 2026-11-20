# Plan: Issue #77, the browser interface's main flow (web layer; closes #8)

Status: **waiting for the coordinator's approval of the questions in section 9** (risk:high because it adds dev dependencies with licences and changes the CI workflows; no change to core, a layer contract, the KB or a golden file). Written 13 Nov 2026 on `main` at 7767174 (PR #107, issue #76 merged). Thread "Build the browser main flow". Feature IDs: UC-01, UC-02, UC-03, VA-03, VA-05, WI-04 (shown), AQ-01.

Sources read: Issues #77, #8, #78, #79; `CLAUDE.md`, `.claude/rules/tests.md`, `.claude/rules/licences.md`, `.github/lanes.yml`, `ci.yml`, `nightly.yml`; `plans/v1-remaining-plan.md` (row 24, Q6, Q7, Q12); `plans/issue76-server-plan.md` (D-192 to D-209); KB D-100, D-130 to D-133, D-142, D-154 to D-166; the feature list (UC-03 is "Chapter selection and **order**"); code on `main`: `web/*` (api, pages, jobs, tasks, state, templates, app.js), `app/report.py`, `app/settings.py`, `app/voice.py`, `voices` (types, kokoro engine), `tests/unit/web_helpers.py`, `audio_fakes.py`. Reports measured on the 7 corpus papers today: 54 to 547 proposed edits per paper (arsiwalla: 547, 278 of them citations; report JSON up to 281 KB), 1 to 14 chapters.

Checked today on PyPI (wheels downloaded and their licence files read): playwright 1.65.1 (Apache-2.0; needs greenlet 3.5.6, MIT AND PSF-2.0, and pyee 16.0.2, MIT), pytest-playwright 0.10.0 (Apache-2.0; needs python-slugify 9.1.3, MIT, text-unidecode 1.3, Artistic-1.0 **or** GPL-2.0-or-later, we take GPL-2.0-or-later; pytest-base-url 2.1.0, MPL-2.0), axe-playwright-python 0.1.8 (MIT; bundles `axe.min.js`, axe-core 4.12.1, MPL-2.0, copyright notice kept in the file). All dev only: nothing is shipped in the wheel. pytest-playwright allows our pytest 9.2.

## 1. The flow (what the person sees)

```
/  Open a document ──upload──► /documents/{id}   (analysis starts by itself, progress inline)
                                 1 Check:  report summary, one switch per category,
                                           every proposed change, chapter list
                                           [Update the analysis]
                                 2 Voice:  voice list with licence, preview sentence, speed
                                           (not installed → link to /voice)
                                 3 Make:   output folder, [Make the audiobook]
                                         ──► /jobs/{id}  progress, time left, cancel
                                                         ──► results: files, folder, skipped
/voice  Voice setup: the whole download (files, sizes, licences, hosts), consent, progress
```

- **`/` Open**: one file field (types from `supported_suffixes()`), the documents opened before (name, size, analysed or not, audiobook made or not) as links, and a voice status line linking to `/voice`. The paste box appears only once a text extractor exists (#74; until then the server answers 415, so showing it would only produce an error).
- **`/documents/{id}`** is one page with three numbered sections (headings, so a screen reader can jump between them): **1 Check**, **2 Voice**, **3 Make**. Opening a file starts the pre-analysis at once (a script job, seconds); the page shows its progress in a status line and reloads itself with the report.
- **1 Check** (UC-01, UC-02, UC-03):
  - Summary line: chapters, how many changes, how many will change what is heard.
  - **One switch per category** (a checkbox in a fieldset "Read these with sci2audio's changes"), with the counts per category (applied, not spoken because the chapter is not chosen, set aside, switched off) and the category's label.
  - **Every proposed change**, one collapsed `<details>` per category holding a table: page as printed, chapter, the text as printed, what is said instead ("not read" for a removal, "a pause" for a pause), the reason, and what became of it (applied; not spoken, chapter not chosen; set aside for the step that won; switched off).
  - **Chapter list**: a checkbox per chapter with its title as printed, first page, number of sentences, and "reference list, off by default" where it applies; "Choose all" and "Choose none" buttons.
  - Problems (steps that failed) and warnings from the report, in a note above the switches.
  - **[Update the analysis]** runs the script job again with the switches and chapters on screen.
  - Downloads of the latest listening script, `report.md` and `report.json` (sci2audio's own files in the work folder, D-199).
- **2 Voice** (VA-03, VA-05): a voice list (name, accent, gender; the default first), the voices' licence (from the download plan), a preview sentence box with **[Listen]**, and the speed (0.5 to 2.0). If the voice files are missing, the section says so and links to `/voice`, and the Make button explains it.
- **3 Make**: the output folder (from the settings, else `~/Documents/sci2audio`; a text field, because a browser cannot pick a folder), the files that will be written, **[Make the audiobook]**.
- **`/jobs/{id}`** (WI-04): phase, a progress bar by sentences done of all, "about N minutes left" once the job has measured its speed (D-159), sentences reused from an earlier run, **[Cancel]**. When it ends: the files with sizes and download links, the folder they are in, sentences the voice could not say (D-162), and **[Free the speech cache (N MB)]** (D-158, `DELETE …/chunks`). If the audiobook exists already: the files that are in the way and **[Replace these files]**, which starts the same job with `"overwrite": true` (D-163, D-199).
- **`/voice`** (VA-03, Q12): a table of every file of the download plan (file, size, licence), the total, the hosts it talks to with their redirect hosts (D-141), a checkbox "I agree to download these files from these hosts" and **[Download]**, then progress and cancel on the job page. The consent sends the plan's digest (D-203).
- **Every page**: a skip link, a header with "A job is running: … (open it)" while one runs (the server runs one at a time, D-200), and the footer line that nothing leaves the computer (the privacy page itself is #79).

## 2. Server additions (web only; the app and the stages are unchanged)

| Route | Does |
|---|---|
| `POST /api/v1/voices/preview` (`{"voice", "speed", "text"}`) | a **preview job** (new job kind `preview`, one at a time like the rest): speaks the text with the voice at that speed into `<work_root>/preview/preview.wav` (replaced each time) and lists it as the job's file; 409 `voice-missing` when the voice files are not installed; text 1 to 300 characters (the cutter's limit, Q4) |
| `GET /api/v1/documents/{id}/files/{name}` | the latest analysis' files (script, `report.md`, `report.json`) from `<work>/script/`, by name as written; 404 for any other name |
| `?download=1` on both file routes | `Content-Disposition: attachment` instead of `inline` |
| `JobOut.kind` | gains `preview` |
| pages | `/`, `/documents/{id}`, `/jobs/{id}`, `/voice` rebuilt; the JSON API stays as #76 made it |

The preview uses `VoiceSource.make()` → `createSession()` → `voices.speak_to_wav` (the same call the audio job uses; `voices.preview` is that call with `PREVIEW_TEXT`, from #18), in `web/tasks.py`.

## 3. Templates ready for translation (#79)

Every string a person reads goes through `{{ t("key") }}` from **one table, `web/strings/en.toml`** (read with `tomllib`, standard library), with `{name}` placeholders filled before autoescaping. The script gets its strings from a `<script type="application/json" id="strings">` block (data, not code, so the CSP's `script-src 'self'` still holds). Category labels are keyed by category id (`category.citations`), with the report's English label as the fallback. The `lang` attribute comes from the table. #79 then adds `de.toml`, the language choice and the test that every key exists in both. **API error messages stay the app's English words** (they come from `JobError` and friends); #79 decides whether to key them.

## 4. Accessibility (AQ-01)

- Native controls only (buttons, checkboxes, `<input type="range">`, `<details>`, `<progress>`, `<audio controls>`); every control labelled; groups in `fieldset`/`legend`; tables with `<th scope>`; one `<h1>` per page and numbered `<h2>` steps.
- **Focus**: visible focus ring (3 px, contrast ≥ 3:1) on everything; after an action the focus moves to its result (the new report's heading after an analysis, the status line after an error) instead of being lost on a reload.
- **Live regions**: one polite status region per page. **Progress is announced at most every 30 seconds and on each phase change**, not on every sentence, so a screen reader is not flooded; the progress bar carries `aria-valuetext` ("120 of 480 sentences, about 6 minutes left").
- **Contrast**: WCAG AA in light and dark (`prefers-color-scheme`); `prefers-reduced-motion` respected.
- **Keyboard**: everything reachable and usable by Tab, Shift+Tab, Space, Enter and arrow keys, in reading order; no keyboard traps; no `tabindex` above 0.

## 5. Modules (lane web; plus infra and docs as named)

| File | Holds | Size |
|---|---|---|
| `web/pages.py` | the four pages, the `t()` table, view helpers for the report | ~250 |
| `web/strings/en.toml` | every interface string | ~200 |
| `web/templates/*.html` | base, index, document (with three step partials), job, voice, missing | ~450 |
| `web/static/app.js` | open, analysis, switches/chapters, preview, start, job progress with throttled announcements, cancel, replace, free cache, voice consent | ~450 |
| `web/static/app.css` | layout, focus, light and dark tokens, reduced motion | ~200 |
| `web/api.py`, `web/models.py`, `web/tasks.py`, `web/jobs.py` | preview route and job, document files route, `download` flag, `preview` kind | ~150 |
| `pyproject.toml`, `uv.lock` (infra) | dev deps, marker `browser`, package data for `strings/` | ~15 |
| `.github/workflows/ci.yml`, `nightly.yml` (infra) | browser job on every PR, three browsers nightly | ~50 |
| `THIRD_PARTY_LICENSES.md`, `CLAUDE.md`, `.claude/rules/tests.md` (docs) | licence rows; the commands with the new marker | ~20 |

## 6. Tests

- **`tests/browser/`** (pytest-playwright, marker `browser`): a live server per test module, uvicorn in a thread on a socket bound to `127.0.0.1:0` (the launcher's own binding), folders in `tmp_path`, the fake voice from `audio_fakes.py`, a fake download fetch, a small generated PDF (`pdf_maker`), **real ffmpeg for a few seconds of audio** (allowed in the fast tier, tests.md). The browser logs in through `/start?token=…` like a person. **Every request the page makes to anything but this server is aborted and fails the test** (`page.route`), so no page can reach the network.
  - `test_flow.py`: the main flow end to end: open the PDF → the analysis runs by itself → report shown with counts → switch a category off → update → its count moves to "switched off" → deselect a chapter → update → the report marks its edits "not spoken" → voice missing → `/voice`: plan shown, Download refused without the checkbox, with it the fake download completes → preview plays a WAV (the `<audio>` element loads it) → speed 1.25 → make the audiobook → progress with sentences done and the time estimate → results list the M4B, the MP3s and the read-along file, downloads answer 200 → making it again shows "files exist" → Replace → done → free the speech cache → size 0. Also: cancel during speech ends as cancelled; a second start while busy shows the busy message with a link; a damaged PDF shows the app's message; a lost server shows "can't reach sci2audio".
  - `test_keyboard.py`: the same main flow with the keyboard only (`keyboard.press`/`type`; the file chooser is the one OS dialog), checking focus order, a visible focus ring on every stop, and where focus lands after each action.
  - `test_axe.py`: axe-core (axe-playwright-python) on **every page in every state** (empty home, analysing, report, voice missing, voice page, download running, job running, job done, job failed, output exists, not found), in light and dark colour schemes; fails on any violation of the WCAG 2.0/2.1/2.2 A and AA rules, whatever its impact, and on serious or critical best-practice findings (question 14).
  - Live-region throttling with Playwright's clock: a stream of 200 progress events in 60 s produces at most 3 announcements.
- **TestClient tests** (fast, all three systems): preview job (missing voice 409, text limits 422, WAV written and served as `audio/wav`, disk full leaves no `.part`, busy 409); document files route (each name, any other name 404, `..` 404); `download=1` header; every page renders and escapes a file name like `<script>.pdf`; templates and static files contain no external URL (already a test, extended to the new files); every `t()` key used in templates and the script exists in `en.toml` and every key in the table is used.
- **Schemathesis** keeps running over the whole OpenAPI document, so the new routes are covered.
- **CI**: a new job "browser (Linux, Chromium)" on every PR (`playwright install --with-deps chromium`, then `pytest -m browser`), required by "CI passed"; the matrix job runs `-m "not slow and not benchmark and not browser"`. **Nightly**: Chromium, Firefox and WebKit on Linux, and WebKit on macOS (the pywebview window of D-47 uses it, #8).
- Before the PR: the CLAUDE.md check list, `pytest -m browser`, the nightly Hypothesis profile on the web tests, the layer check.

Rough size: about 1,700 lines of templates, script, styles and Python; about 1,100 lines of tests.

## 7. Out of scope

- The read-along player (#78); German, the language switch and the privacy page (#79); OWASP ZAP (#12).
- Deleting a whole document's work folder from the home page (D-209 left it to #77 to show where; I propose a small follow-up issue, question 17).
- Chapter reordering, if question 4 is decided as recommended (a new issue).
- Settings the interface does not show in v1.0: the language (English only, D-50).

## 8. Sequencing

One PR (lanes web, infra, docs). I start now on the parts that no open question changes (pages, strings table, styles, the preview and file routes, the TestClient tests) and leave the dependencies, the CI wiring and anything a decision below would change until the coordinator answers. The KB entries go in a separate KB PR after approval, with the D-numbers the coordinator assigns.

## 9. Design questions (my recommendation first; the coordinator decides and assigns D-numbers)

1. **Page structure**: home, one page per document with three numbered steps (check, voice, make), a voice setup page and a job page for progress and results. Alternative: a multi-page wizard (more back-and-forth, and a screen reader loses the overview the headings give).
2. **When the analysis runs, and what the audiobook uses**: the pre-analysis starts by itself when a file is opened; changing a switch or chapter needs **[Update the analysis]**; **the audiobook is always made with exactly the switches and chapters of the report on screen**: while the controls differ from it, the Make button says "Update the analysis first to see what your changes do". Alternatives: re-analyse on every click (several seconds per click on a long paper, focus jumps); start the audiobook with unseen choices (the person would hear changes the report never showed, against UC-01).
3. **What is remembered**: the switches, the voice, the speed and the output folder are saved as the settings (`PUT /settings`, D-139) when the person starts an audiobook, and the page says so ("sci2audio remembers these for the next document"); the chapter choice belongs to the document and lives in its latest report (`report.settings.chapters`), so reopening a document shows its last choice. Alternative: a separate settings page (one more page for four values the flow already shows).
4. **Chapter order (UC-03 says "selection and order")**: **v1.0 reads the chosen chapters in printed order**; the list shows that order. Reordering becomes a new issue after v1.0 and UC-03's "order" part moves there. Reason: `JobSettings.chapters` is a set by D-133, so reordering would change the app (an ordered tuple), the script job, the report, `job.json`, `audio.json` and the command line's `--chapters`, and a book out of printed order fights the faithful-text goal and the read-along (#78) for little gain on papers. Alternative: make the order part of v1.0 in an app PR before this one (about 150 lines plus tests across app and cli, and a change to D-133).
5. **Showing every proposed change**: all edits, server-rendered, one collapsed section per category; above 500 edits in one category the page shows the first 500 and links the full `report.md`. Alternatives: client-side paging (more script, harder for screen readers); counts only (fails "every proposed change", UC-01).
6. **Voice preview (VA-05)**: a new job kind `preview` through the same one-at-a-time board, `POST /api/v1/voices/preview`, an editable sentence whose default is #18's `voices.PREVIEW_TEXT` ("This is how this voice reads your text. The results in the second table were measured over three years."), at most 300 characters, played in an `<audio controls>` element; the WAV lives in `<work_root>/preview/` and is replaced each time. Alternatives: the document's first sentence as the default (often the title or an author list, as the corpus shows); a synchronous route returning the WAV (blocks a request for the model load, no progress, races an audio job).
7. **Keeping the voice loaded**: after the first preview the server keeps one Kokoro engine loaded until it stops and hands it to audio jobs through `VoiceSource.make`/`release` (D-166 left this open for a server), so a second preview takes about a second instead of the model load. Alternative: load and dispose per preview (simplest; a few seconds per click on a CPU; memory freed at once). I lean to keeping it, but would accept per-preview if the coordinator prefers less state.
8. **Speed control**: a range slider from 0.5 to 2.0 in steps of 0.05 with the value shown next to it and `aria-valuetext` ("1.25 times"); the preview uses it. Alternative: a few fixed choices (coarser than the voice allows).
9. **Voice download consent**: the full plan as a table on its own page, a checkbox naming the hosts, and a Download button; the request carries the plan's digest (D-203). The voice section shows the voices' licence and links to that page when files are missing. Alternative: a dialog on the document page (dialogs are harder to make accessible; the plan has 60+ rows).
10. **Progress and estimate**: progress bar by sentences, the phase in words, "about N minutes left" from `seconds_left` once measured (D-159), "measuring speed" before; the status region speaks at most every 30 seconds and on each phase change. Alternative: announcing every event (floods a screen reader).
11. **Results and replacing files**: files with sizes and links (`download=1`), the folder path, the skipped sentences, a button to free the speech cache with its size; "output exists" lists the files and offers an explicit **[Replace these files]** button (the button press is the confirmation; no browser `confirm()`). Alternative: a `confirm()` dialog (blocks the page, poor with screen readers and automation).
12. **New API routes (web only)**: the preview route and job kind, `GET /documents/{id}/files/{name}` for the latest analysis files, `download=1` on both file routes. Alternative: read the analysis files through the script job's file list (gone after a server restart).
13. **Translation readiness**: one string table per language as TOML (`web/strings/en.toml`) behind a `t()` function in templates and a JSON data block for the script; API messages stay English for now. Alternative: gettext with Babel (a new dependency and a compile step for about 200 strings).
14. **Accessibility bar**: WCAG 2.2 AA; axe fails on **any** WCAG A/AA violation (stricter than #8's "no serious or critical", cheap on new code) plus serious or critical best-practice findings; checked on every page state in light and dark; a keyboard-only run of the whole flow. Alternative: exactly #8's bar (serious and critical only).
15. **Test dependencies** (dev only): `playwright>=1.65.1`, `pytest-playwright>=0.10.0`, `axe-playwright-python>=0.1.8`, and their trees as listed above; licence rows for each, with text-unidecode taken under GPL-2.0-or-later and axe-core's MPL-2.0 named. Browsers come from Playwright's CDN in CI only (a CI download, not the program's).
16. **Test wiring**: marker `browser`, tests in `tests/browser/`, a live uvicorn server on `127.0.0.1:0`, every off-server request aborted and failing the test; a required CI job on Linux with Chromium on every PR; nightly Chromium, Firefox and WebKit on Linux plus WebKit on macOS; the matrix job and the CLAUDE.md command gain `and not browser`, and `uv run pytest -m browser` is added to the commands. Alternative: browser tests in the three-system matrix (installs three browsers per system on every PR, minutes each).
17. **Deleting documents**: not in #77; a small v1.0 issue for "Remove this document" (its work folder: source copy, analysis, speech cache, records; never the audiobook in the person's folder). Alternative: add it here (it deletes files, so it is risk:high on its own and better reviewed alone).
18. **Pasted text**: the paste box shows only once a text extractor is registered (#74); until then it is hidden. Alternative: show it and let the server's 415 explain (an error the person can't avoid).
