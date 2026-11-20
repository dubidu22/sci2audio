# Plan: Working Reader batch A (foundation, screenshots, rail, Settings)

Issues: #385 (WR-1 tokens, fonts, sprite, no-internet test), #386 (WR-2 `ui:screens` workflow), #387 (WR-3 cobalt rail), #388 (WR-4 Settings). One PR, branch `web/working-reader-a` from main a9e0e2d (main stays open; v1.1 is cut on `release/1.1`). Critical (risk:high): third-party fonts, a new CI workflow, the interface contract. Waits for the coordinator's approval before code or tests.

Read before planning: `plans/working-reader-plan.md` incl. D-663 to D-666; sci2audio-design b4a7523 `DESIGN.md`, `IMPLEMENTATION-PROMPT.md`, `prototype/app/` (app.css, index.html sprite, i18n.js, fonts, `screens/settings.png`); sci2audio a9e0e2d `CLAUDE.md`, `.claude/rules/*`, `web/` (base.html, pages.py, i18n.py, security.py, static/), `app/config.py`, `app/settings.py`, `.github/workflows/ci.yml` and `ci-full-label.yml`, `tests/browser/` (conftest, axe, keyboard, reflow), `tests/unit/test_package_data.py`, `test_web_languages.py`; KB D-45, D-193, D-194, D-256, D-257, D-259, D-288, D-321.

## 1. Files touched

| File | Change |
|---|---|
| `src/sci2audio/web/static/app.css` | Rewritten: `@font-face` (5 faces), tokens light / dark, base type, shell (rail), the design's controls (button, primary, quiet, danger, small, input, select, switch, segmented, kbd, field, hint), state chips, notices, tables, reduced-motion block, breakpoints. Existing page markup keeps working on the new base (see 4). |
| `src/sci2audio/web/static/fonts/` (new) | `atkinson-400-normal.woff2`, `atkinson-400-italic.woff2`, `atkinson-700-normal.woff2`, `literata-normal.woff2`, `literata-italic.woff2` (byte-identical to the prototype), `OFL-atkinson.txt`, `OFL-literata.txt`. Choice 2 may add subset files. |
| `src/sci2audio/web/templates/_icons.html` (new) | The 34-symbol sprite from `prototype/app/index.html`, as an inline `<svg hidden>` included once by `base.html`, without the `xmlns` attribute (not needed inline; keeps the no-http test strict). `i-proto` dropped (prototype-only), so 33 symbols. |
| `src/sci2audio/web/templates/base.html` | New shell: skip link, `<nav>` rail (wordmark, Library, Open a document, Voices; Captures not rendered until #397), shelf slot `{% block shelf %}` with the running job, foot (Settings, Privacy; Keyboard shortcuts per choice 3), `<main id="main">`. Header, language buttons and footer removed. `<html data-theme>` from the appearance cookie. |
| `src/sci2audio/web/templates/settings.html` (new) | Appearance, interface language, defaults (folder, speed), announce sentences. |
| `src/sci2audio/web/templates/*.html` | Only what the new base needs (block names, removing the footer/privacy line where the rail now carries it, `icon()` macro use where a state already has a word). No page redesign (that is B to D). |
| `src/sci2audio/web/pages.py` | `_page` context: `current` nav item, theme, library count, running-job shelf item (title, phase word, progress 0 to 1). New routes `GET /settings`, `GET /appearance` (choice 1). |
| `src/sci2audio/web/i18n.py` | Cookie constants for appearance and announce, `known_theme()`; SCRIPT_KEYS gets `settings.` saved/failed words. |
| `src/sci2audio/web/server.py` | `mimetypes.add_type("font/woff2", ".woff2")` before the static mount (Python's table lacks it on some systems). |
| `src/sci2audio/web/static/app.js` | Settings: save folder and speed (read fresh `GET /api/settings`, change two fields, `PUT /api/settings`, status line). Shelf: refresh the running job's progress from the job API while a job runs (same poll the job page uses), stop when it ends. |
| `src/sci2audio/web/strings/en.toml`, `de.toml` | `nav.*`, `settings.*`, `shelf.*` keys; German wording from `prototype/app/i18n.js`. `common.footer`, `common.language_switch` and the header's running line go if no longer used (the "every string is used" test enforces it). |
| `THIRD_PARTY_LICENSES.md` | New section "Bundled fonts": both families, version (Atkinson Hyperlegible 1.006, Literata 3.103), source, OFL-1.1, file names and SHA-256. |
| `.github/workflows/ui-screens.yml` (new) | See 3. |
| `tests/browser/test_screens.py` (new) | The screenshot run, skipped unless `SCI2AUDIO_SCREENS` names an output folder. |
| `tests/unit/test_web_design.py` (new), `test_package_data.py`, `test_web_languages.py`, `test_web_pages.py` | See 6. |
| `tests/browser/test_axe.py`, `test_keyboard.py`, `test_reflow.py`, `test_german.py`, new `test_shell.py`, `test_settings.py` | See 6. |

No change to `sci2audio.core`, the pipeline stages, `app/` or the API schema (with choice 1 as recommended). `lint-imports` unchanged.

## 2. Tokens, fonts and the sprite (#385)

**Token mapping.** The custom properties are ported from `prototype/app/app.css` unchanged in name and value, one property per `DESIGN.md` colour token (`--cobalt`, `--cobalt-deep`, `--cobalt-line`, `--on-cobalt`, `--on-cobalt-2`, `--ink`, `--ink-2`, `--pencil`, `--paper`, `--desk`, `--desk-2`, `--rule`, `--rule-strong`, `--hl-read`, `--hl-note`, `--hl-quote`, `--hl-card`, `--hl-mark`, `--error`, `--error-wash`, `--wait`, `--wait-wash`) plus the prototype's derived ones (`--on-hl`, `--sweep-c`, `--on-sweep`, `--held`, `--sheet-shadow`, `--pop-shadow`, `--ui`, `--read`, `--r`, `--rail`, `--panel`, `--dock`, `--ease`). Dark values exactly once in source as two identical blocks: `@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {…} }` and `:root[data-theme="dark"] {…}`; a test checks both blocks are identical so they cannot drift. Radii, spacing and type sizes are written as in DESIGN.md (no extra token layer; the prototype does not have one either). `.num` / every number: `font-variant-numeric: tabular-nums lining-nums`, applied to `body` for figures in tables, meters, counts and times (tabular figures do not change letters).

**Theme.** `<html>` gets `data-theme="light"` or `"dark"` only when the person chose one; "As the system" renders no attribute and the media query decides. Server-side, so no flash and no script needed.

**Fonts.** Five woff2 files copied byte for byte from sci2audio-design b4a7523 `prototype/app/fonts/` (Atkinson Hyperlegible 1.006, © 2020 Braille Institute of America; Literata 3.103 variable 200 to 900, © 2017 The Literata Project Authors; both SIL OFL 1.1, no Reserved Font Name in either notice, checked). Shipped inside the package at `web/static/fonts/` with both licence texts beside them, so the wheel carries font and licence together (OFL condition 2). `font-display: swap`; no preload (local server). CSP needs no change: `font-src` falls back to `default-src 'self'`. Licence gate: row in `THIRD_PARTY_LICENSES.md` with SHA-256 per file; PR body names OFL-1.1.

**Sprite.** Inline `<svg hidden aria-hidden="true">` with `<symbol>`s, used as `<svg class="i" aria-hidden="true"><use href="#i-library"></use></svg>` through a Jinja macro `icon(name, size)`. Every icon is decorative next to its word (Form-Not-Colour rule); icon-only buttons get an `aria-label`. No icon font, no external file.

**CSP consequence.** `style-src 'self'` forbids `style=""` attributes, so meters use `<progress>` (styled with `::-webkit-progress-value` / `::-moz-progress-bar`), never an inline width.

## 3. The screenshot workflow (#386)

- `.github/workflows/ui-screens.yml`: `on: pull_request: types: [labeled]`; job `if: github.event.label.name == 'ui:screens' && github.event.pull_request.head.repo.full_name == github.repository` (as `ci-full-label.yml`); `permissions: contents: read`; checkout of `github.event.pull_request.head.sha` with `persist-credentials: false`; setup-uv and the Playwright cache pinned to the same SHAs as `ci.yml`; `uv sync --locked`; `playwright install --with-deps chromium`; `uv run pytest tests/browser/test_screens.py --browser chromium -p no:randomly` with `SCI2AUDIO_SCREENS=$RUNNER_TEMP/screens`; `actions/upload-artifact` (pinned SHA as in `release.yml`) with the name `screens-<head sha>` (sha passed through `env`, never interpolated into `run`); a summary step lists the files. `timeout-minutes: 20`. Passes `zizmor --offline`. No network beyond what the browser job already does (uv, Playwright browser download).
- `tests/browser/test_screens.py`: uses the browser conftest (fake voice, fake download, external requests aborted), so the pages show **corpus documents only**: `tests/corpus/papers/joss2021-waskom-seaborn.pdf` (CC BY, already in `tests/corpus/LICENSES.md`) and the corpus sample note. Page states: library first run, library with documents, document page, running job, failed job, listen page (fake-voice audiobook), voice page, privacy, settings, not found. Each at 1440 × 900 and 1280 × 800, in light English, dark English and light German = 60 PNGs named `<page>-<width>-<variant>.png`. Waits for `document.fonts.ready` and turns off the caret. Skipped (one skip line) when `SCI2AUDIO_SCREENS` is unset, so the normal browser job stays as fast as now and `ci.yml` is unchanged.
- The label `ui:screens` is created on the repository when the PR opens (REST call, colour and description "Render every page as screenshots (#386)").
- Images are not golden files and are not compared (no pixel diff across systems). Closes #14 as replaced.

## 4. The rail and the new base (#387)

**Layout choice (deviation from the prototype, same look).** The prototype makes the body `overflow: hidden` and scrolls inside `.main`. Here the **document itself scrolls** and the rail is `position: sticky; top: 0; height: 100vh` in a two-column grid. Reasons: keyboard scrolling (Space, Page Down) works without focus in the main column, the listen page's "follow the reading" (D-301) listens to window `wheel` and scroll keys today, find-in-page and the skip link behave, and the dock of batch D can be `position: sticky; bottom: 0`. Shelf scrolls inside the rail when long.

**Widths.** 264 px rail; at 1399 px and below 232 px. Below 760 px (not designed; WCAG reflow D-257 at 320 px must hold, en and de) the rail becomes a top band: wordmark and nav items wrap in a row, the shelf collapses into a `<details>` "Reading and recent", the foot items join the row, and the page scrolls normally. The existing reflow test stays green.

**Content.** Wordmark "sci2audio" as text with the "2" in a reading-yellow tab (allowed by the Highlighter rule; D-663 calls the wordmark a proposal, so it is one template line to change). Nav: Library (`/`, with the document count in tabular figures), Open a document (`/#open`, the library's open form), Voices (`/voice`). Captures is not rendered until #397. The current item is a paper tab with ink 700 text and `aria-current="page"`; the document, job and listen pages mark no nav item (their paper shows on the shelf from batch B). Focus ring inside the rail reading yellow, 2 px at 2 px offset; on paper cobalt (quote blue in dark).

**Shelf (slot).** "Reading and recent" heading only when the shelf has an item. In batch A its only item is the running job: title, phase word ("Making the audiobook", "Reading the PDF", …, from the existing job strings), a white `<progress>` meter, linking to `/jobs/{id}`. Refreshed by `app.js` from the job API while running (no live region: the job page already announces at most every 30 s). Batch B fills the slot with papers and "Continue listening" (D-664).

**Foot.** Settings, Privacy, (Keyboard shortcuts, choice 3).

**Landmarks.** Skip link first; `<nav aria-label>` for the rail; `<main id="main" tabindex="-1">`; one `<h1>` per page. The privacy link that every page carried in the footer is now the rail's Privacy item on every page (the test that checks it moves to the rail).

**Existing pages in the new shell.** Base element styles map to the design's components (`button` → button, `.primary` → primary, inputs → input, `fieldset`/`legend` → field labels, tables → ruled rows, the existing notices → error-wash / wait-wash notices with an icon and a word). Their layout is not redesigned in batch A; screenshots of the in-between state are expected to look plain, not broken. axe light and dark must pass on all of them.

**Reduced motion.** One block: under `prefers-reduced-motion: reduce` every transition and animation is 0 s (switch knob, hover washes; the sweep comes in D).

## 5. Settings (#388)

Page `/settings` like `screens/settings.png`, without the dock and without the sounds switch (waits for #397), three paper sections:

1. **Appearance** (As the system, Light, Dark) and **Language of the interface** (English, Deutsch): segmented controls, each a GET form of submit buttons with `aria-pressed`, working without the script, as the language switch does today (D-288, D-321: a form POST arrives with `Origin: null` and is refused).
2. **Defaults for new audiobooks**: Audiobook folder (text input, the saved `output_folder` or the server's default) and Playback speed (select 0.5× to 2.0× in the steps the document page offers). Saved into the existing `settings.json` through the existing `PUT /api/settings`: the script reads the current settings fresh, changes only these two fields and writes, so switches, voice and letter pace are kept; a `role="status"` line says "Saved" or the reason it failed (e.g. a relative folder, 422). These two fields are already in the file, so the command line already reads them (`sci2audio` with saved settings) and never writes them (test).
3. **Announce the sentence being read to screen readers**, off by default, with its hint; a switch in a GET form (submit on change by script, a "Save" button without script). Batch D reads it.

**Choice 1, where appearance and announce are kept** (the open point of this batch):
- **(a) Recommended: cookies, like the language (D-288).** `sci2audio-theme` (`system`, `light`, `dark`) and `sci2audio-announce` (`on`, `off`), each one year, `SameSite=Strict`, `HttpOnly`, not named after the port, granting nothing; set by `GET /appearance?theme=…&back=…` and `GET /appearance?announce=…&back=…`, with the same guards and `local_path` redirect as `/language`. No change to `app/`, the settings file or the API schema; the theme is known before the page renders. D-288 already rejected the settings file for an interface-only choice.
- (b) An `interface` section in `settings.json`: survives a browser change, but `save_settings` would have to preserve it, `load_settings` stop warning about it, the API schema grows, and older versions warn "unknown setting". More risk for no visible gain on a one-person local app.
With (a), #388's "saved settings / command line reads them and never writes them" applies to folder and speed, which are the only ones the command line uses.

**D-288 amended:** the language switch leaves the header of every page and lives on the Settings page, reachable from every page's rail (IMPLEMENTATION-PROMPT, #388). Same cookie, same route, same guards. The test "the switch is on every page" becomes "Settings is linked from every page and the switch is on Settings". The KB thread records it (draft for D-number below).

## 6. Tests

Fast (unit, no browser):
- `test_web_design.py`: every DESIGN.md colour token is defined in `app.css` with its literal light value, and its literal dark value in both dark blocks; the two dark blocks are identical (values pinned as literals from b4a7523, not read from the design repo).
- No-internet: no `http://` or `https://` (any case) in any text file under `web/templates/` and `web/static/`, nor `//` protocol-relative `src`/`href`/`url()`/`@import`; every `url()` in `app.css` points to an existing file under `static/`.
- Fonts: the five woff2 and two OFL files exist, are in the wheel (`test_package_data.py`), each woff2 SHA-256 matches its row in `THIRD_PARTY_LICENSES.md`, and `/static/fonts/*.woff2` is served as `font/woff2` with the security headers.
- Sprite: every `icon('x')` used in a template has a `<symbol id="i-x">`; no unused symbol.
- Rail: on every page the rail has Library, Open a document, Voices, Settings, Privacy, no Captures; `aria-current="page"` on the right item for `/`, `/voice`, `/settings`, `/privacy` and on none for document, job, listen and not-found pages; a running job shows as the shelf item with its title and a `<progress>`.
- Appearance and announce routes: only known values reach the cookie, cookie attributes as above, redirect only to a local path (the `/language` cases reused), guarded like every page, grants nothing; `data-theme` rendered for light/dark and absent for system and for a forged cookie value.
- Settings page: shows the saved folder and speed (and the server default when none); GET never writes `settings.json`; the command line never writes it (run `sci2audio script` with a settings file, file byte-identical after).
- Strings: both tables same keys and placeholders, every key used (existing tests), German typography and "Sie" (existing).

Browser (`uv run pytest -m browser`, Chromium; Firefox and WebKit nightly):
- axe-core on every page state in light, in dark by system (`emulate_media(color_scheme="dark")`) and in dark by choice (`data-theme="dark"` with system light), at 1440 × 900 and 1280 × 800: library empty and with documents, document, running and failed job, listen, voice, privacy, settings, not found.
- Keyboard: skip link → rail → main order; the focus ring is ≥ 2 px and reading yellow inside the rail, cobalt on paper (quote blue in dark); the existing whole-flow and "Tab never gets stuck" tests updated for the rail and extended to Settings; segmented buttons and the switch work with Enter and Space; saving folder and speed by keyboard announces "Saved" in the status line.
- Settings flow: choosing Dark sets `data-theme` on this and the next page and after a server restart (cookie not tied to the port); choosing Deutsch switches the language from Settings; a bad folder shows the server's reason; switches and voice in `settings.json` survive a save.
- Reduced motion: with `reduced_motion="reduce"` emulated, toggling the switch starts no animation (`document.getAnimations()` empty) and every computed transition duration is 0 s.
- Widths: rail 264 px at 1440, 232 px at 1280, no sideways scroll at 1440, 1280 and 320 (existing reflow test, en and de, plus Settings).
- Highlighter rule: on every page, in light and dark, no button, chip, nav or shelf item has a computed background or border colour equal to a highlighter token (the wordmark's "2" is the one allowed exception, by selector).
- Fonts load: after `document.fonts.ready`, `document.fonts.check('15px "Atkinson Hyperlegible"')` and Literata are true; no request leaves the test server (the conftest already fails the test on any).
- German: Settings and the rail in German use the i18n.js wording.

Before the PR: `ruff check`, `ruff format --check`, `lint-imports`, `deptry src`, fast suite, `pytest -m browser`, `zizmor --offline .github/workflows`. Final round (critical): `ci:full` three systems, `ui:screens` run, nightly browsers on the branch by `workflow_dispatch` if the review asks.

## 7. Choices for the coordinator

1. **Appearance and announce in cookies (a), not in `settings.json` (b).** Recommend (a). See 5.
2. **Font coverage.** The prototype's files are the Latin subset (221 and 231 glyphs: no ł, ř, č, ő, no Greek). Interface strings and English/German text are fully covered (checked with fontTools: all of äöüß „“ ‚‘ – — × … present; arrows ← → ⇧ ⌘ fall back to the system font). Paper titles and authors from batch B and the sheet in batch D will contain Greek letters (α, β, μ) and Central European names; those glyphs would fall back to Georgia / system-ui letter by letter. Options: (a) bundle only the five files now and decide in batch D; (b) add the `latin-ext` subsets of both families and the `greek` subset of Literata from the same upstream releases (Google Fonts builds as packaged by Fontsource, pinned versions and SHA-256, OFL-1.1) with `unicode-range`, so they load only when a page needs them (about +150 KB in the wheel, nothing loaded for English/German pages). **Recommend (b)**: it keeps the font licence work in this one critical PR instead of a second one in batch D, and the files are the same fonts and licence. If (a), batch D gets an issue.
3. **Keyboard shortcuts in the rail foot.** The `?` dialog and the keys come with #394 (batch D); today the app has no shortcuts to list. Recommend: leave the foot item out until #394 adds the dialog (as Captures waits for #397), and note it on #387. Alternative: an item that opens a dialog saying shortcuts come with Listen (an empty promise in the interface).

## 8. KB drafts (for the KB thread; D-numbers from the coordinator)

- **The interface's appearance and announce choices are cookies** (if choice 1a): `sci2audio-theme`, `sci2audio-announce`, same rules as D-288 and D-321; settings file and API unchanged. Decided (Claude).
- **D-288 amended: the language switch moves to the Settings page**, reachable from every page's rail (#388, D-663). Decided (Claude).
- **The document scrolls, the rail is sticky** (deviation from the prototype's inner scroll, same look; reasons in 4). Decided (Claude).
- **Below 760 px the rail becomes a top band** (not designed; keeps D-257 reflow). Decided (Claude).
- Font coverage (choice 2) as decided.

## 9. Size and order

About 1,800 to 2,500 changed lines (CSS ~600, templates ~300, Python ~200, JS ~120, tests ~900, workflow ~70, licences/strings ~150). Order of work: fonts + tokens + no-internet and design tests → base/rail + rail tests → Settings + cookie routes + tests → existing pages fitted, axe light/dark → screenshot test + workflow → full checks → PR (draft until green), label `risk:high`, `lane:web`, `lane:infra`; attribution lines; ledger line.
