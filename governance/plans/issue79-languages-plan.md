# Plan: English and German interface and the privacy page (#79)

Issue: dubidu22/sci2audio #79 (AQ-02, AQ-03; v1.0 plan row 26, Q10; lane web). Builds on #77 (PR #121, 8f0aee6).
Sources read: Issue #79; `CLAUDE.md`, `.claude/rules/tests.md`, `.claude/rules/licences.md`; KB D-45, D-50, D-101, D-192 to D-209 (server, privacy facts), D-244 to D-261 (#77, above all D-256 strings table and D-257 axe bar); `plans/issue77-main-flow-plan.md` §3 and §9 (13); `plans/issue76-server-plan.md` §12 (4); code on `main`: `web/pages.py`, `web/strings/en.toml`, all templates, `static/app.js`, `web/config.py`, `web/security.py`, `web/api.py` error kinds, `tests/unit/test_web_pages.py`, `tests/browser/*`.

Status: **non-critical** (web layer only; no layer contract, no `core`, no KB, no golden file). The questions in §9 are numbered for the coordinator to assign D-numbers.

## 1. What changes

| Part | Change |
|---|---|
| `web/strings/de.toml` | New: every key of `en.toml`, in German. |
| `web/strings/en.toml` | New keys for the language switch, the privacy page, error kinds and plural forms. |
| `web/i18n.py` (new, web only) | `LANGUAGES = ("en", "de")`, `Strings` (one language's table: `t`, `size`, `number`, `script_json`), `language_of(request)`, the plural rule. Loaded once at import, no global "current language". |
| `web/pages.py` | Every page gets the `Strings` of the request's language in its context (instead of the module-wide `t`); helpers (`_said`, `_status`, `_categories`, `_voice_options`, `_job_view`, `size_text`) take it as a parameter. New routes `POST /language` and `GET /privacy`. |
| Templates | `base.html`: `lang` from the table, the language switch in the header, a footer link to the privacy page. New `privacy.html`. App-written English (edit reasons, problems, warnings, error details, the preview sentence) marked `lang="en"`; document text (as printed, read as, chapter titles) marked with the document's language. No other template text changes. |
| `static/app.js` | `tr()` learns plural forms; numbers formatted with the page language (`Intl.NumberFormat`, built into the browser); error messages chosen by error kind from the table, the app's own words kept as details. |
| Tests | Unit (TestClient) and browser (Playwright + axe) in both languages, §8. |

No new dependency. No API change (the JSON API and its OpenAPI document stay as they are; `/language` and `/privacy` are interface routes, `include_in_schema=False` like the pages).

## 2. Language choice and detection (Q1)

- **Order: the switch's cookie, else the browser's `Accept-Language`, else English.** `Accept-Language` is parsed with its q-values; the first range whose primary subtag is `de` or `en` wins (`de-AT` → German, `fr, de;q=0.5` → German, `fr` → English, `*` → English).
- **The switch**: in the header of every page, a small form `POST /language` with two buttons, each language named in its own language and marked with its `lang` ("English", "Deutsch"); the current one has `aria-pressed="true"`. Works without the script (a plain form; CSP `form-action 'self'` allows it). The form carries the current path in a hidden field; the server sends the browser back there with 303, **only to a local path** (must start with one `/`, no `//`, no backslash, no scheme; anything else goes to `/`), so the route can't be used as an open redirect.
- **Remembered in a cookie `sci2audio-language`** (value `en` or `de`, `Path=/`, `SameSite=Strict`, `HttpOnly`, one year). Unlike the start-up cookie it is *not* named after the port on purpose: cookies ignore ports, so the choice survives the next server run on a new port. Holds nothing but the language; an unknown value is ignored.
- The route sits behind the existing middleware (token cookie, own `Origin`, `Sec-Fetch-Site`), so another page can't switch it.

Alternatives not chosen: (a) a field in the app's settings file via `PUT /settings` (survives a browser change, but changes `app.Settings`, the settings file and the API schema for an interface matter, and collides with #78's lane); (b) `?lang=de` in every URL (lost on every link the server writes, and in bookmarks); (c) browser language only, no switch (#79 asks for a switch, and many Germans run English browsers).

## 3. How strings are keyed (Q2)

- **Keep D-256 as it is**: one TOML table per language, `section.key`, `{name}` placeholders filled before Jinja escapes. `de.toml` has **exactly the keys of `en.toml`**; a test fails on a key or plural form missing in either table, on a key nothing uses, and on any key whose placeholders differ between the two languages.
- **German typed into its own table, no fallback to English at run time**: a missing German key is a test failure, never a silent English word on a German page.
- A test also fails on a German value that is identical to the English one, except a short allowlist (`common.app` = "sci2audio", `common.language`, "OK"-like words such as the units MB/KB), so a pasted English line can't hide.
- Category labels (`category.<id>`) and accents (`accent.<code>`) are already keyed by id; the report's English label stays only as the fallback for a category added later (a test proves every `Category` has a key in both tables).

## 4. Plurals, numbers and dates (Q3)

- **Plurals**: a string that depends on a count is a small table with `one` and `other` in the TOML (`[check.category_changes] one = "…1 change" other = "…{n} changes"`); `t(key, count=n, …)` picks `one` for exactly 1, else `other`. English and German share this rule (CLDR "one/other" for whole numbers), so no library is needed; the script gets the same two forms and the same rule. Strings with several numbers (the summary line) are split so each number has its own plural-aware part. This also fixes today's English "1 changes" / "1 chapters".
- **Numbers**: decimal sign from the table (`common.decimal`: "." / ","), used for sizes (1,5 MB) and the speed (1,25-fach); no digit grouping in either language, as today. In the script, `Intl.NumberFormat(document.documentElement.lang)` (the browser's own, offline) with grouping off.
- **Units**: a no-break space between number and unit in both tables ("1,5 MB", "50 %"), so they never wrap apart.
- **Dates**: the interface shows no dates in v1.0. If one appears later it is written as ISO 8601 (`2026-11-13`), the same in both languages and referenceable; noted in the table's header comment.

Alternative not chosen: Babel / ICU MessageFormat (a new dependency and a compile step for two languages that share one plural rule; D-256 already declined gettext with Babel).

## 5. What is not translated (Q4)

- **Spoken words stay English in v1.0 (D-50, #79's acceptance)**: notices, the preview sentence (`voices.PREVIEW_TEXT`), the voices' names. The interface's labels for them are translated ("Formeln: mit einem kurzen Hinweis übersprungen"), the notices themselves are not.
- **What the app writes stays as written**: edit reasons, step problems and warnings in the report, and the app's error messages. They are the same words as in `report.md`, the CLI and the terminal, so a person can find them in both places (referenceable, as printed). On a German page they are marked `lang="en"` (WCAG 2.2 SC 3.1.2 Language of Parts, AA), so a screen reader reads them with English pronunciation.
- **Error messages (D-256 left this to #79)**: the API keeps `{"error": kind, "message": words}` unchanged. The interface shows **the table's sentence for the error kind** (`error.<kind>`, both languages, e.g. `error.busy` "Ein anderer Auftrag läuft; warten Sie, bis er endet.") **followed by the app's words as details**, marked `lang="en"`; an unknown kind shows the app's words alone. The job page does the same for a failed job.
  Alternative not chosen: localising the API's messages by `Accept-Language` (changes the API contract the CLI, the player and Schemathesis use, and the app's own exceptions would need keys: a change across layers for words the person can read next to a translated sentence).
- **Document text** (as printed, read as, chapter titles) is marked with the document's language from the report (`en` in v1.0).

## 6. German style and typography (Q5)

- **Formal "Sie"** in sentences; buttons and headings in the infinitive or as nouns ("Dokument öffnen", "Hörbuch erstellen"), which avoids the address altogether. Reason: the convention of German desktop and open-source software (Firefox, LibreOffice, GNOME) and of academic settings; the earlier hosted app's "du" belonged to its consumer shop pages, which are being retired. Easy to change later: it is one table.
- **Quotation marks „…“** (U+201E, U+201C), never `"`; a test fails on a straight double quote or an English curly quote “ ” used as an opening mark in a German value. Apostrophes ’. The ellipsis character … (as in English). Spaced en dash " – " for a dash. 
- A short glossary as the table's header comment, so later strings stay consistent: audiobook Hörbuch; listening script Hörskript; analysis Analyse; pre-analysis Voranalyse; change (edit) Änderung; voice Stimme; job Auftrag; speech cache Sprachzwischenspeicher; page furniture Seitenrahmen (Kopf- und Fußzeilen, Seitenzahlen); set aside zurückgestellt; switched off ausgeschaltet; chapter Kapitel; reference list Literaturverzeichnis; folder Ordner; download Download (noun) / herunterladen (verb).
- Language names in the switch in their own language ("English", "Deutsch"), as is usual for language pickers.

## 7. The privacy page (Q6)

**`GET /privacy`**, title "Privacy: what stays on this computer" / "Datenschutz: Was auf diesem Computer bleibt". Linked from **the footer of every page** (the footer's existing sentence becomes the link's lead-in) and from **the voice setup page next to the consent box**. It is a plain statement of how the program behaves, not a legal privacy policy (no one but the person processes anything). Where it can, the page **shows live values instead of repeating them**, so it can't go stale:

1. **Nothing leaves this computer.** No telemetry, no analytics, no crash reports, no update check, no accounts, no online services. The texts, the analysis and the speech are made on this computer by the Kokoro voice running here.
2. **The one exception: the voice download you start.** Only on the voice page, only after you tick the consent box and press "Download". The page lists the files, sizes, licences and **the hosts it talks to (taken live from the download plan, the same list as the voice page)**. After that sci2audio needs no network.
3. **The framework's telemetry is switched off.** FastAPI, the web framework, comes with OpenTelemetry built in; sci2audio switches it off in code and its tests check that nothing is recorded (D-195).
4. **The interface is for you only.** The server listens on 127.0.0.1 (this computer) only, on a port the system picks for each run; other computers can't reach it. The start link's key is new for each run; the browser trades it for a cookie. Requests from other web pages are refused. The pages load nothing from the internet (no fonts, scripts or images from outside). sci2audio keeps no access log, so neither the key nor your file names end up in one (D-192 to D-196).
5. **Where your files are** (paths shown live from the server's configuration): opened files are **copied** into the working folder (one folder per document, with its analysis files and the speech cache, which the job page can free); audiobooks go to **the folder you choose** (default shown) and are never replaced without your "Replace" (D-199); the settings file; the voice files. To remove everything sci2audio keeps, delete these folders (the voice files and the settings file included).
6. **Cookies**: two, both stay in your browser and are only sent to this program: the start cookie (until the server stops) and the language cookie (one year, holds "en" or "de").
7. **What sci2audio can't control**: your browser's own features (extensions, sync, online spelling services) and the operating system.
8. A line with the licence (GPL-3.0-or-later) and that the source is open for anyone to check.

No outside links on the page (the axe and network tests already fail on any request elsewhere; a plain-text repository name is fine).

Alternatives not chosen: (a) a section on the start page (long text on the page people use most; no address to link to); (b) a static text with paths and hosts typed in (goes stale when the download plan or folders change).

## 8. Tests

Unit (TestClient, fast suite):
- Tables: same keys and plural forms in both; same placeholders per key; every key used (templates, `pages.py`, `i18n.py`, `app.js`) exists, every key is used; every `Category` and every voice accent has a key; German values differ from English except the allowlist; German typography (no `"`, no “ as an opening mark).
- `language_of`: cookie wins; unknown cookie ignored; `Accept-Language` with q-values, regions, `*`, garbage; default English.
- `POST /language`: sets the cookie with the expected attributes and redirects to the given local path; `//evil.test`, `http://…`, `/\evil`, empty → `/`; refused without the own `Origin` / without the start cookie (existing middleware).
- Every page (start, document before and after analysis, job pages of every kind and state, voice, privacy, not found) renders in German with `lang="de"`, no English sentence from the table on it, and the script data block in German.
- Privacy page: lists exactly `plan_hosts` of the download plan and the configured folders; linked from every page's footer and from the voice page; says what D-195 says.
- Plurals and numbers: `one`/`other` chosen right in both languages; "1,5 MB", "1,25-fach".
- Error kinds: every kind the API and the job runner can send has `error.<kind>` in both tables (collected from the code by the test, like today's key check).

Browser (Playwright + axe, `browser` marker, both in Chromium in CI):
- **Every axe state of #77 runs in German too** (the existing state tests parametrised by language through the browser's locale, `de-DE`), with D-257's bar (A/AA, light and dark).
- The main flow once in German end to end (open, analyse, switch a category, preview, make, results).
- The switch: by keyboard, from a document page; the page comes back in German at the same address; the choice survives a new tab; then back to English.
- `lang="en"` parts on a German document page (reasons) are present.
- The privacy page in both languages, axe-clean, reachable from the footer by keyboard.

## 9. Questions and recommendations (D-288 to D-293)

D-numbers as assigned by the coordinator in this thread (13 Nov 2026, 08:00 UTC), in its wording: 1 header switch sets a cookie, Accept-Language without it, English default, local redirect only = **D-288**; 2 de.toml mirrors the keys with no runtime fallback and the four table tests = **D-289**; 3 one/other plurals, decimal sign and no-break space from the table, ISO dates = **D-290**; 4 spoken words and the app's own words stay English with lang="en", API errors translated by kind = **D-291**; 5 "Sie", infinitives on buttons, „…" quotes, glossary = **D-292**; 6 /privacy with the eight points, linked from every footer and the voice consent = **D-293**. **D-321** (coordinator, 13 Nov 13:06 UTC): the switch is a GET form, not a POST, because under the no-referrer policy (D-194) a form POST carries `Origin: null` and the origin check refuses it; found by the browser tests. The coordinator's two checks: the language cookie stays separate from the session cookie of D-192 to D-209 (SameSite=Strict, no secrets), and each point of the privacy page is verified against the server's code.

1. **Language detection and switch**: cookie from a header switch, else `Accept-Language`, else English; the switch is a plain POST form with a local-path-only redirect; the cookie is not port-named so it survives server runs (§2). Alternatives: app settings field; `?lang=`; no switch.
2. **String keys**: keep D-256's tables; `de.toml` with exactly the same keys and placeholders; no run-time fallback to English; tests for parity, use, identical-to-English and typography (§3).
3. **Plurals, numbers, dates**: `one`/`other` sub-keys with the shared rule, decimal sign from the table, no digit grouping, no-break space before units, ISO dates if any appear; no Babel (§4).
4. **What stays English**: spoken words (D-50), and the app's own words (reasons, problems, warnings, error details) as written and marked `lang="en"`; error messages translated in the interface by error kind with the app's words as details; the API unchanged (§5).
5. **German style**: "Sie", infinitive buttons, „…“, glossary in the table (§6). Alternative: "du".
6. **Privacy page**: `/privacy`, linked from every footer and the voice consent, eight plain points with live hosts and paths, no outside links, not a legal policy (§7).

## 10. Out of scope

- Translating edit reasons and the report's words (they come from textprep and the app; would need message keys across layers): follow-up issue for v1.1 if wanted.
- German text processing and a German voice (D-50; later).
- The README's privacy statement (the docs lane can point to the page's wording later).

## 11. Size and order

About 1 day. Order: `i18n.py` with tests → plurals and English key changes (English pages unchanged except plural fixes) → `de.toml` → switch and cookie → privacy page → `lang` marks and error kinds → browser tests in German. One PR, branch `web/languages-79`; main merged whenever #78 or the browser CI fix lands.
