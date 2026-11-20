# Plan: Issue #76, the local server and job API (web layer; closes #7)

Status: **waiting for the coordinator's approval** (critical: new run-time dependencies and a network-facing process, a new layer-contract rule, writes user files; risk:high). Written 13 Nov 2026 on `main` at 395e4c9 (after #94). Thread "Build the local server and job API". Feature IDs: AQ-03 (no telemetry, nothing leaves the computer), PE-05 (layers: the server is a thin layer over `app`), plus the server side of UC-01, UC-03, VA-03, WI-04.

Sources read: Issues #76, #7, #72, #77, #78, #79; `CLAUDE.md`, `.claude/rules/tests.md`, `.claude/rules/licences.md`, `.github/lanes.yml`, `pyproject.toml` (layer contracts); KB D-45, D-46, D-101 (Q7), D-103, D-104 (Q12), D-114, D-122, D-137 to D-141; `plans/v1-remaining-plan.md` §2 to §4; `plans/issue70-script-job-plan.md`; `plans/issue71-audio-job-plan.md` with D-154 to D-166; code on `main`: `app` (job, report, chapters, config, settings, files), `voices` (download, kokoro_engine, wav), `sci2audio.testing.no_network`, `tests/unit/pdf_maker.py`, `voice_fakes.py`.

Checked today on PyPI: FastAPI 0.162.5 (MIT), Starlette 1.10.0 (BSD-3-Clause), uvicorn 0.54.0 (BSD-3-Clause), Jinja2 3.1.6 (BSD-3-Clause), python-multipart 0.0.33 (Apache-2.0), pydantic 2.14.3 (MIT), Schemathesis 4.33.4 (MIT, dev only), httpx 0.28.1 (BSD-3-Clause, dev only, for `TestClient`).

**One finding that needs a decision (question 4):** since 0.143 (8 Oct 2026) FastAPI depends on `opentelemetry-api` (Apache-2.0) and instruments every request with OpenTelemetry spans, metrics and logs. Without an SDK and exporter that is a no-op, and its automatic export only switches on with `FASTAPI_OTEL_AUTO_CONFIGURE=true` plus OTLP endpoint variables plus the `fastapi[opentelemetry]` extra (none of which we install). I read the code in `fastapi/telemetry/_runtime.py` and `applications.py`. It is still telemetry machinery inside a program that promises none, so the plan switches it off in code and tests that.

## 1. What the server is

```
sci2audio ui → web.serve(config) → uvicorn on 127.0.0.1:<random> → FastAPI app (create_app)
                                                     ↓
                                    JobBoard (one job at a time) → app.JobRunner → stages
```

- `create_app(config, *, runner=None, fetch=None, clock=None) -> FastAPI`: no global state; everything (folders, token, runner, download fetch for tests) is passed in and kept on the app object. Tests build their own apps.
- `ServerConfig(token, work_root, models_dir, config_file, default_output_folder, upload_limit)`. The command line fills it from the app defaults (`app.config`: the settings file from D-139, models and work folders from #71, D-164) and a fresh token.
- The server adds no pipeline logic: it stores what the person opens, starts the app's jobs, relays their progress and serves their files.

## 2. Local-only security (AQ-03, #7)

The realistic attacks are another web page in the same browser (cross-site requests, DNS rebinding) and another program's page on 127.0.0.1 at a different port (same *site*, different *origin*, so `SameSite` cookies alone do not stop it).

1. **Binding**: the launcher opens the socket itself on `127.0.0.1`, port 0 (the OS picks a free ephemeral port), and hands it to `uvicorn.Server.serve(sockets=[sock])`, so the port is known before the browser opens and there is no race. No `--host` option exists; IPv6 `::1` is not bound; the browser is sent to `http://127.0.0.1:<port>/…`, never `localhost`.
2. **Start-up token**: `secrets.token_urlsafe(32)` per run. The browser is opened at `/start?token=…`; the server checks it (`secrets.compare_digest`), sets a cookie `sci2audio-<port>` (HttpOnly, `SameSite=Strict`, `Path=/`, session cookie) and redirects (303) to `/` so the token leaves the address bar. The terminal prints the same link, so the person can open it again; the token is valid until the server stops. Programs (tests, a later cli client) send `Authorization: Bearer <token>` instead. **Every route except `/start` needs the token**, including static files and `/openapi.json`. Without it: 401 with a page saying to open the link shown in the terminal.
3. **Host check (DNS rebinding)**: `Host` must be exactly `127.0.0.1:<port>` or `localhost:<port>`; anything else gets 421 before routing or token checks.
4. **Origin check (cross-site and other local ports)**: if `Origin` is present it must equal `http://127.0.0.1:<port>` or `http://localhost:<port>`; if `Sec-Fetch-Site` is present it must be `same-origin` or `none` (a typed link or the launcher). A **cookie-authenticated** `POST`/`PUT`/`DELETE` must carry a matching `Origin` (browsers always send one on such requests); bearer requests need not, since a page cannot set that header cross-origin without a CORS preflight, and there is **no CORS** at all (preflights get 405). Refusals are 403 with a JSON reason.
5. **Response headers**: `Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; media-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `Cache-Control: no-store` on the API, `X-Frame-Options: DENY`.
6. **No outbound network**: FastAPI's `/docs` and `/redoc` are switched off (they load Swagger and ReDoc from a CDN); FastAPI's telemetry is switched off in code (question 4); uvicorn's access log is off (it would print the token from `/start` and file names); templates and static files contain no external URL (a test scans them). The voice download (section 6) is the only code path that opens a connection.

The checks are one pure ASGI middleware (`web/security.py`, about 120 lines), outermost, so it also covers static files, 404s and the OpenAPI document.

## 3. API (JSON under `/api/v1`)

| Method and path | Does | Answers |
|---|---|---|
| `POST /api/v1/documents` (multipart `file`) | stores an opened file (section 4) | 201 `Document`; 413 too large; 415 type sci2audio can't read; 507 disk full |
| `POST /api/v1/documents/text` (`{"text", "name"}`) | stores pasted text as `<name>.txt` (readable once #74 lands; until then 415 like any unknown type) | as above |
| `GET /api/v1/documents`, `GET /api/v1/documents/{id}` | documents in the work folders: id, file name as opened, size, sha256, whether a report and audio records exist | 200; 404 |
| `GET /api/v1/documents/{id}/report` | the latest pre-analysis report (`<name>.report.json`, `sci2audio-report` v1, unchanged) | 200; 404 none yet |
| `GET /api/v1/documents/{id}/chapters` | the report's chapter list (index, title as printed, first page, references, selected, utterances) | 200; 404 |
| `DELETE /api/v1/documents/{id}/chunks` | `app.clean_work_folder` (#71): frees the kept speech chunks | 204; 409 while a job uses the document |
| `GET /api/v1/settings`, `PUT /api/v1/settings` | the saved settings (D-139) with load warnings, plus the choices: categories with label and default, speed range, voices | 200; 422 with JobSettings' message |
| `POST /api/v1/jobs` (`{"kind": "script" or "audio", "document", "settings", "overwrite"}`) | starts a job (section 5) | 202 `Job`; 404 document; 409 busy; 422 |
| `GET /api/v1/jobs`, `GET /api/v1/jobs/{id}` | jobs of this server run: state, last progress, error, files written | 200; 404 |
| `GET /api/v1/jobs/{id}/events` | progress as server-sent events (section 5) | `text/event-stream` |
| `POST /api/v1/jobs/{id}/cancel` | asks the job to stop | 202; 409 finished or not cancellable |
| `GET /api/v1/jobs/{id}/files/{name}` | one file the job wrote, by its name as written (Range requests for the player, #78) | 200/206; 404 for any name not in the job's list |
| `GET /api/v1/voices` | voices (`ENGLISH_VOICES`), installed or not (`missing_files`), the download plan (files, sizes, licences, hosts incl. the redirect hosts) and the plan's digest | 200 |
| `POST /api/v1/voices/download` (`{"consent": true, "plan": "<digest>"}`) | starts the voice download as a job (section 6) | 202 `Job`; 409 busy or stale plan; 422 no consent |

- Pydantic models for every request and response, so the OpenAPI document is exact and Schemathesis can check responses against it. The report keeps its own versioned JSON (an object in the schema, described as `sci2audio-report` v1).
- Errors: `{"error": "<kind>", "message": "<words a person can act on>"}` everywhere, with kinds such as `busy`, `output-exists`, `unsupported-file`, `too-large`, `disk-full`, `not-found`, `no-consent`.
- Pages (section 7) are at `/`, `/documents/{id}` and `/jobs/{id}`; static files at `/static/…`.

## 4. Documents and folders

- A browser can only send a file's bytes, not its path, so **an opened file is copied** into its work folder: `<work_root>/<sha256[:16]>/source/<name as opened, cleaned with output.names.clean>`. The **document id is the first 16 hex digits of the sha256**, the same as #71's default work folder (D-164), so the script records, the speech chunks and the source live together, and **opening the same file again, even after a restart, finds its folder and reuses every chunk** (resume across server runs, WI-02). Opened again under another name: the new name replaces the old.
- The upload streams to `<name>.part` while hashing, then is renamed; disk full → 507, no `.part` left. Limit: **200 MB per file** (`Content-Length` checked first, bytes counted while copying), pasted text **5 MB**. The type is checked against `app.EXTRACTORS` before storing (415 names the types sci2audio reads).
- **Pre-analysis files stay in the work folder**: the server's script job writes `<name>.script.txt`, `.report.json`, `.report.md` into `<work>/script/` with `overwrite=True`. These are sci2audio's own files, rewritten each time the person changes a switch or chapter choice, and downloadable from the job. The person's folders are never touched by a pre-analysis.
- **The audiobook goes to the person's output folder**: `settings.output_folder` if set (an absolute path, checked), else **`platformdirs.user_documents_path()/"sci2audio"`** (`~/Documents/sci2audio`). The audio job refuses to overwrite (D-163); the server reports that as job error `output-exists` with the file names as written, and the interface can start the job again with `"overwrite": true` after asking (#77).

## 5. Jobs, progress and cancel

- **One job at a time per server**, for all three kinds (script, audio, voice download), on top of the runner's lock (D-138) and #71's work-folder file lock (D-161). A second start gets 409 `busy` at once; a `JobBusyError` from another process holding `job.lock` ends the job with error `busy`.
- Each job runs in its own thread. `JobRecord`: id, kind, document, state (`running`, `done`, `failed`, `cancelled`), settings as sent, events, error, files. **Job ids** are `<document id>-<kind>-<n>` (n counts jobs of this server run, e.g. `3f2a9c0d1e2b4a5c-audio-2`), so a job always names its document. The job list lives in memory for one server run; what lasts is on disk (`job.json`, report, `audio.json`, the files).
- Settings in `POST /jobs`: the request carries the person's choices for this job (chapters included); fields left out come from the saved settings. The server never saves settings as a side effect of a job (`PUT /settings` does that).
- **Progress (SSE)**: `GET /jobs/{id}/events` sends first a `snapshot` event (the job as `GET /jobs/{id}` shows it), then `progress` events as they come (script: each `Phase`; audio: each `AudioProgress` from #71 with chunks, characters, measured speed and `seconds_left`; download: bytes done of total and the file), then one `end` event with the final state, and closes. A comment line every 15 s keeps proxies and the browser from timing out. On reconnect the browser just gets a fresh snapshot (no `Last-Event-ID` replay: the snapshot carries everything a page shows). Implemented with `StreamingResponse` over a thread-safe event list (Q7).
- **Cancel**: audio jobs through #71's cancel event (D-160); the voice download by raising from its progress callback, which `download_voice_files` lets through after removing the `.part` file (no change to voices; tested). Script jobs take seconds and have no cancel point, so cancelling one answers 409 `not-cancellable`.
- **Shutdown** (Ctrl-C in the terminal): the running job is cancelled, the server waits up to 5 s for it, open event streams end.

## 6. Voice list and download with consent (VA-03, Q12)

- `GET /voices` shows the whole download before anything happens: every file with size and licence, the total (about 355 MB), the two hosts and their redirect hosts (D-141), whether each file is already in place, and a **digest of the plan** (sha256 of its file list).
- `POST /voices/download` needs `"consent": true` and that digest. Without consent 422 and nothing is fetched; with a digest of another plan 409 (the person agreed to something else). It then calls **`voices.download_voice_files(models_dir, progress=…)`, the one download function** (D-104, D-122), as a job with progress events. Tests inject a fake `fetch` through `create_app(fetch=…)`; no test touches the network.
- The voice preview sentence (VA-05) belongs to #77 with the voice page; it needs a loaded engine and fits there.

## 7. Minimal pages

Enough to exercise the API by hand, server-rendered with Jinja2 (autoescape on), a little plain JavaScript, no build step (D-101):

- `/`: open a file or paste text; list of opened documents; whether the voice is installed.
- `/documents/{id}`: chapters and the report's counts, buttons to analyse again and to make the audiobook.
- `/jobs/{id}`: progress through `EventSource`, the error if any, links to the files.

They are tested with TestClient (status, content, escaping of a file name like `<script>.pdf`, no external URLs). **Playwright and axe-core come with #77**, which builds the real accessible interface on these routes and closes #8 (question 13).

## 8. Command line

`sci2audio ui [--no-browser]`: makes the config from the app defaults, binds the socket, prints `sci2audio is running at http://127.0.0.1:<port>/start?token=…` and opens the browser (`webbrowser.open`) unless `--no-browser`; Ctrl-C stops it. `cli.py` imports `sci2audio.web` only inside the `ui` command, so `sci2audio --version` and the #72 commands do not load FastAPI. **`cli.py` is lane cli and #72 rewrites it too**: I add the `ui` subcommand in about 15 lines and merge main in if #72 lands first (or #72 merges mine).

## 9. Sequencing with #71

The script part does not need #71; the audio part needs `JobRunner.run_audio`, `AudioProgress`, the cancel event, `VoiceSource`/`kokoro_voice`, `clean_work_folder` and the default folders.

1. Build everything except the audio wiring against `main`: security, launcher, documents, settings, voices and download, script jobs, SSE, pages, and the job board with the audio job kind behind one small adapter written against the approved #71 interfaces (section 6 of that plan).
2. When #71's PR merges, merge `main` into my branch, wire the adapter and add the audio tests (fake Kokoro adapter from `voice_fakes.py`, a tiny generated PDF, real ffmpeg for a few seconds of audio, as #71's tests do). **One PR** if #71 has merged by the time the rest is tested, which I expect (it was approved first).
3. If #71 is still open when everything else is ready, I open the PR without the audio kind (`POST /jobs` with `"kind": "audio"` answers 501 `not-available`) and add audio in a second small PR right after #71 merges, with its own review. I'll say in the PR which case applies.

## 10. Modules (lane web, plus cli, infra and docs as named)

| File | Holds | Size |
|---|---|---|
| `web/__init__.py` | `create_app`, `serve`, `ServerConfig` | ~20 |
| `web/server.py` | app factory (`FastAPI(docs_url=None, redoc_url=None, telemetry=off)`), exception handlers, routes wiring | ~120 |
| `web/security.py` | token, cookie exchange, Host/Origin/Sec-Fetch-Site middleware, headers | ~140 |
| `web/launch.py` | socket on 127.0.0.1:0, uvicorn, browser, shutdown | ~80 |
| `web/documents.py` | storing uploads and pasted text, listing work folders | ~140 |
| `web/jobs.py` | `JobBoard`, `JobRecord`, events, the three job kinds, cancel | ~250 |
| `web/api.py` | routes and pydantic models | ~300 |
| `web/pages.py`, `templates/*.html`, `static/app.js`, `static/app.css` | minimal pages | ~100 + ~200 |
| `cli.py` | `ui` subcommand | ~15 |
| `pyproject.toml`, `uv.lock` | dependencies, the new import contract, package data for templates | ~20 |
| `THIRD_PARTY_LICENSES.md` | rows for each new package | ~15 |

No change to core, the pipeline stages or app (the app defaults come from #71).

## 11. Tests (per tests.md "the FastAPI server in web/" and "any file writing")

- `test_web_security.py`: wrong `Host` (including a rebinding name with the right port) → 421; foreign `Origin`, other local port, `null` origin → 403; `Sec-Fetch-Site: cross-site` and `same-site` → 403; cookie `POST` without `Origin` → 403; missing or wrong token → 401 on every route (parametrised over the app's own route list, so a new route cannot skip it); `/start` with the right token sets the cookie with HttpOnly, SameSite=Strict, Path=/ and redirects without the token; with a wrong token no cookie; bearer works; security headers on API, pages, static files and errors; `/docs` and `/redoc` 404; no CORS headers; FastAPI telemetry off (config checked, and no `opentelemetry` span or exporter module touched during a request).
- `test_web_launch.py`: the socket is bound to `127.0.0.1` with a port > 0 and two binds get different ports; **subprocess** `sci2audio ui --no-browser` (folders in `tmp_path` through environment variables): prints the link, answers on 127.0.0.1, is **not reachable on the machine's other addresses** (skipped where the machine has none), stops on SIGINT / CTRL_BREAK; killed with SIGKILL during a script job and started again on the same folders, the document opens and a job runs (no stale lock).
- `test_web_api_*.py` (TestClient, one test or more per endpoint and answer): documents (upload, paste, list, same content → same id, new name replaces old, 413 by header and by counted bytes, 415, 507 by injected ENOSPC with no `.part` left); settings (get with warnings from a broken file, put valid and invalid, saved file content); script jobs (start → events snapshot, phases, end → report and chapters endpoints and file downloads; busy 409; source file removed before the run → job `failed` with a clear message; cancel → 409); file names outside the job's list, `..`, encoded slashes → 404; voices (list, consent missing 422, stale digest 409, fake fetch: progress events, files in place, cancel mid-download leaves no `.part`, network error → job `failed` with the voices message); audio jobs once #71 lands (fake voice: progress with `seconds_left`, files listed and downloadable with Range, `output-exists` then `overwrite`, cancel while speaking, chunk clean-up 204 and 409 while running).
- **No network**: an autouse fixture runs every web test inside `sci2audio.testing.no_network()`, except the launcher tests, which only connect to 127.0.0.1 (they check the attempts list holds nothing else).
- `test_web_schemathesis.py`: Schemathesis against the app's OpenAPI document in process (ASGI, with the bearer token): no 5xx and responses match the schema, for every operation; examples per operation follow the Hypothesis profile (ci deterministic, nightly many more). The event stream is run against finished jobs only, so it ends.
- Hypothesis property tests: any opened file name is stored inside its document's `source/` folder and is a valid file name on all three systems; the Host/Origin check accepts exactly the four allowed values for any header text; any JSON body to `PUT /settings` either saves settings that load back equal or answers 422 (never 500).
- `test_web_pages.py`: the three pages render, escape names, carry no external URL (templates and static scanned), and the SSE script uses only relative URLs.
- The import contract test is `lint-imports` itself.

Before the PR: the full CLAUDE.md check list, the nightly Hypothesis profile on the new tests (`HYPOTHESIS_PROFILE=nightly`), and the launcher tests on Linux here (CI runs them on macOS and Windows).

Rough size: about 1,300 lines of code and templates, 1,400 lines of tests.

## 12. Design questions (my recommendation first; the coordinator decides and assigns D-numbers)

1. **Binding and port**: 127.0.0.1 only, no host option, IPv6 not bound; port 0 chosen by the OS on a socket the launcher binds itself and passes to uvicorn. Alternative: a fixed default port (bookmarkable, but clashes and a predictable target).
2. **Start-up token**: 256-bit per run; the browser trades it at `/start` for an HttpOnly, SameSite=Strict cookie named after the port and is redirected to a clean URL; programs use `Authorization: Bearer`; every route but `/start` needs it; valid until the server stops. Alternative: token in every URL (leaks into history and logs); a one-time token (the person couldn't reopen the tab from the terminal link).
3. **Request checks**: Host must be `127.0.0.1:<port>` or `localhost:<port>` (421); Origin, when present, must be the server's own; `Sec-Fetch-Site` must be `same-origin` or `none`; cookie-authenticated unsafe requests must carry a matching Origin; no CORS; the security headers of section 2.5. Alternative: a CSRF form token (more moving parts; the Origin rule covers the same attacks in every browser sci2audio supports).
4. **FastAPI's built-in OpenTelemetry**: accept the current FastAPI (0.162.x) with its `opentelemetry-api` dependency, **switch telemetry off in code** (`telemetry={"tracing": False, "metrics": False, "logs": False, "auto_configure": False}`) and test it; name it in the licence notes and the privacy page (#79). Alternatives: pin `fastapi<0.143` (no security fixes after July 2026); Starlette alone without FastAPI (no OpenAPI document, so Schemathesis and typed requests need a hand-written schema).
5. **No docs pages, no access log**: `/docs` and `/redoc` off (CDN scripts), `/openapi.json` behind the token, uvicorn access log off.
6. **API shape**: JSON under `/api/v1` with two resources, documents and jobs, plus settings and voices; pydantic models for everything; one error shape `{error, message}`. Alternative: unversioned `/api` (a later web version, ADR-002, would have to rename).
7. **Documents**: opened files are copied into `<work_root>/<sha256[:16]>/source/`, the id is that hash prefix (the #71 work folder, D-164), the same content finds the same folder after a restart; limits 200 MB per file and 5 MB of pasted text; type checked on opening. Alternative: open a typed local path instead of uploading (no copy, but the server would read any path it is given and the browser cannot browse folders).
8. **Where files go**: the pre-analysis (script job) writes into the work folder (`<work>/script/`, always replaced, downloadable); the audiobook goes to the person's output folder, default `~/Documents/sci2audio` (`platformdirs.user_documents_path()`), never overwritten without `"overwrite": true`, reported as job error `output-exists` with the names. Alternative: script and report next to the audiobook in the person's folder on every analysis (each switch change would need an overwrite question).
9. **Jobs**: one job at a time per server across script, audio and voice download (409 `busy`); a thread per job; ids `<document id>-<kind>-<n>`; the job list kept for one server run, results on disk. Alternative: a queue (not needed for one person; the interface can disable the start button).
10. **Progress events**: SSE with a `snapshot` first, then `progress`, then one `end`, a keep-alive every 15 s, no replay on reconnect (fresh snapshot). Alternative: `Last-Event-ID` replay (state the snapshot already carries).
11. **Cancel**: audio through #71's event, voice download by raising from its progress callback (no voices change), script jobs not cancellable (409). Alternative: add a cancel event to the script job and to `download_voice_files` (changes to app and voices for jobs of seconds, and a download that already resumes).
12. **Voice consent**: the download starts only on `POST` with `"consent": true` and the digest of the plan the person was shown; else 422 or 409. Alternative: `consent: true` alone (the person could have agreed to an older, smaller plan).
13. **Minimal pages now, Playwright with #77**: three plain pages tested with TestClient; Playwright and axe-core arrive with #77, which owns #8 and replaces these pages. Alternative: wire Playwright now for pages that #77 rewrites in its first PR.
14. **New import rule (layer contract)**: a `forbidden` import-linter contract with `include_external_packages`: only `sci2audio.web` may import `fastapi`, `starlette`, `uvicorn`, `jinja2`, `multipart` and `pydantic`, so app and the stages stay free of the web framework (PE-05, a later web version). Alternative: no rule (relies on review).
15. **Dependencies**: run time `fastapi>=0.162.5,<1` (the telemetry test fails if a later release changes the switch), `uvicorn>=0.54` **without the `[standard]` extra** (no uvloop, httptools, watchfiles or websockets; h11 is enough on 127.0.0.1), `jinja2>=3.1.6`, `python-multipart>=0.0.33`, `pydantic>=2.14` (imported directly); dev `schemathesis>=4.33`, `httpx>=0.28.1`. Every package and the new transitive ones (Starlette, anyio, h11, click, MarkupSafe, pydantic-core, annotated-types, typing-inspection, annotated-doc, opentelemetry-api; Schemathesis' dev tree) get a row in `THIRD_PARTY_LICENSES.md`; all MIT, BSD or Apache-2.0 as far as checked; anything else stops the PR.
16. **`sci2audio ui`** in `cli.py` (lane cli, overlaps #72): a small subcommand with `--no-browser`, web imported lazily; whichever of #72 and #76 merges second merges main in.
17. **Sequencing with #71**: section 9 (one PR if #71 has merged when the rest is ready, else audio in a second PR right after).
18. **Clearing speech chunks** from the API (`DELETE /documents/{id}/chunks`, #71's `clean_work_folder`) now; deleting whole documents waits for #77 to show where (an issue if wanted).

## 13. Out of scope

- The accessible interface, voice preview, speed control, chapter ordering UI (#77); the player (#78); German and the privacy page (#79); OWASP ZAP (#12); a window shell (D-45, later).
- Keeping a voice engine loaded between jobs (D-166 leaves it possible; a later issue if speed needs it).
- Several people or remote access: never; the server is for the person at this computer.
