# Review of sci2audio PR #107, round 1 (issue #76: local server and job API)

Reviewed head: `ffbaef8` (branch `web/issue76-server`, on main `3ef8ac5`). Reviewer thread "Review local server PR", 13 Nov 2026.
Plan: `plans/issue76-server-plan.md`; decisions D-192 to D-209.

## Verdict

Not mergeable yet. M1 and M2 were found on `ffbaef8`; the author fixed both while this review ran (`5beba63`, `3d09866`, test-only). I checked them on `3d09866`: Windows CI is green, and the fast suite passed three times under `-n auto` (1345 passed each time). S1 to S4 are still open. The design matches D-192 to D-209 and none of them changes in substance. Every attack I tried against a running server was refused (list at the end).

## What I ran

- `ruff check`, `ruff format --check`, `lint-imports` (3 contracts kept), `deptry src`: all clean.
- Fast suite `pytest -m "not slow and not benchmark" -n auto`, twice: **1343 passed, 1 failed both times** (`test_the_download_with_consent_puts_the_files_in_place`, M2). It passes when run alone.
- `HYPOTHESIS_PROFILE=nightly pytest tests/unit/test_web_*.py -n auto`: 140 passed (Schemathesis included, 300 examples per operation).
- CI on `ffbaef8`: Linux and macOS green; **Windows red: 113 failed and 113 errors, all in `test_web_*.py`** (M1).
- A real server (`bind()` and `serve()` in a subprocess) attacked with curl and raw sockets; a script job end to end with SSE; an audio job without voice files; SIGINT shutdown (0.4 s, port closed afterwards).
- Licences: every new package in `uv.lock` checked against its PyPI metadata (fastapi MIT, starlette BSD-3, uvicorn BSD-3, python-multipart Apache-2.0, opentelemetry-api Apache-2.0, schemathesis MIT, werkzeug BSD-3, harfile, hypothesis-graphql, graphql-core, jsonschema-rs, pyrate-limiter MIT). All are in `THIRD_PARTY_LICENSES.md`; versions match the lock file.

## Must fix

**M1. Windows: every TestClient web test fails.** (Fixed in `5beba63`, verified: `tests (windows-latest)` green on `3d09866`.) `tests/unit/web_helpers.py:29` (`offline` fixture). On Windows, asyncio's `ProactorEventLoop` builds its self-pipe with `socket.socketpair()`, which on Windows is a TCP connect to 127.0.0.1. `no_network()` refuses that `socket.connect`, so each TestClient request fails with `NetworkUsedError: network access is not allowed here (socket.connect)` and the fixture's `assert attempts == []` errors at teardown. The launcher tests pass there, so the server itself is fine. Fix it in the test helpers without opening the network to real hosts. For example, let the web fixture allow the loopback `socketpair` the event loop makes (and still record and refuse every other connect), or start the TestClient's portal (`with TestClient(...)`) before entering `no_network()`. Either way the Windows job must run all 226 tests green.

**M2. A flaky test.** (Fixed in `3d09866`, verified: three parallel fast runs green.) `tests/unit/test_web_settings_voices.py:281` asserts `job["cancellable"] is True` on the 202 answer, but the fake download can finish before the answer's snapshot is taken (the snapshot then says `done`, `cancellable: false`). It failed in both of my parallel runs. `tests/unit/test_web_audio.py:53` has the same pattern, though the audio job usually runs long enough. Hold the fake fetch (and the fake voice) on an event until the 202 has been checked, as `test_download_progress_counts_bytes` already does, rather than loosening the assertion.

## Should fix

**S1. The D-205 contract misses `python_multipart`.** `pyproject.toml`, the "Only the web layer imports the web framework" contract. python-multipart's module has been `python_multipart` since 0.0.13, and `multipart` is only a compatibility shim (Starlette imports `python_multipart`). So `import python_multipart` in `app` or a stage passes `lint-imports` today. Add `python_multipart` to `forbidden_modules`.

**S2. A duplicate cookie locks the person out.** `web/security.py` `_cookie` returns the first `sci2audio-<port>` value only. Cookies ignore ports, so any page on 127.0.0.1 at another port can set a non-HttpOnly `sci2audio-<port>=x; Path=/api`. The browser sends the longer path first, and every API call from the real page then gets 401. I tested this: `Cookie: sci2audio-P=x; sci2audio-P=<token>` gets 401. It is a denial of service, not a leak. Accept the cookie when any value with that name matches (each one compared with `compare_digest`), and add a test.

**S3. Consent and overwrite must be exact booleans.** `web/models.py` `DownloadIn.consent` and `JobIn.overwrite` are plain `bool`, so pydantic's lax mode turns `"yes"`, `"on"`, `"1"` and `1` into `True`. I checked: `{"consent": "yes", "plan": "x"}` gets past the consent check to `stale-plan`. D-203 says `"consent": true`, and D-199 needs an explicit `"overwrite": true`. Use `StrictBool` (keep the 422 `no-consent` answer for `false`) and add the cases to the existing tests.

**S4. An output folder with a NUL byte is accepted.** `PUT /api/v1/settings` with `"output_folder": "/a\u0000b"` answers 200 and saves it, and `POST /jobs` with it answers 202. Path operations later raise `ValueError: embedded null byte`. Refuse it in `api._folder` with 422 `invalid`, and add the case to the settings tests (and to the Hypothesis property if it doesn't produce it).

## Nits: fix now or open an issue (say which)

**N1.** An `Upgrade: websocket` request makes uvicorn print `No supported WebSocket library detected. Please use "pip install 'uvicorn[standard]'"` in the person's terminal. `uvicorn.Config(ws="none", ...)` in `launch.py` refuses it quietly. A test can check `config.ws == "none"`.

**N2. The start token sits on the browser's command line.** On Linux and macOS, `webbrowser.open(start_url)` hands the token to `xdg-open` or `open`, and from there to the browser process's argv, where other users of the same computer can see it in `ps` while it runs. Jupyter avoids this by opening a small local redirect file instead. This is low risk on a one-person desktop, so **open an issue** (hardening, #12 or #77) rather than doing it in this PR.

**N3.** A `.part` file in `<work_root>/.incoming/` survives a kill during an upload (the `finally` only runs on an exception) and is never removed. Clear `.incoming` when the server starts, or open an issue.

## Checked and fine (no change needed)

Results from the running server (bearer token unless noted):

- Host `evil.com:<port>`, `127.0.0.1` without a port, `localhost.:<port>`, `0.0.0.0:<port>`, HTTP/1.0 without Host: 421. Two Host headers: 400 from h11.
- Origin `http://evil.com`, `http://127.0.0.1:1234` (another local port), `null`, and two Origin headers: 403. `Sec-Fetch-Site: cross-site` and `same-site` with the cookie: 403.
- Cookie POST without Origin (a cross-site form post) to `/voices/download`, cookie PUT without Origin, cookie POST with a foreign Origin: 403. Cookie POST with the right Origin: goes through. OPTIONS preflight: 403, and no response anywhere has Access-Control headers.
- `/start` with a wrong token, two tokens, or `/start/`: 401 and no cookie. With the right token: 303 to `/` with `HttpOnly; SameSite=Strict; Path=/`.
- No token: 401 on the API, `/openapi.json`, `/static/app.js` and `//api/...`. `/docs` and `/redoc`: 404.
- Path traversal: `documents/..%2F..%2Fetc`, `jobs/x/files/..%2F..%2Fetc%2Fpasswd`, `/static/../templates/base.html` and `/static/../api.py` (raw and encoded): 404. An upload named `../../../../tmp/evil.pdf` or `..\..\evil.pdf` is kept as `evil.pdf` inside its `source/` folder. `CON.pdf` becomes `_CON.pdf`, and `x.exe` gets 415.
- A file name with HTML in it is cleaned and escaped on the pages. `app.js` writes server data only through `textContent`.
- A WebSocket upgrade with a foreign Origin: 403. The middleware closes any websocket scope with 1008.
- Chunked body without a length: 411. `Content-Length: 999999999999`: 413 before anything is read.
- Telemetry: `TELEMETRY_OFF` matches FastAPI 0.162.5's `TelemetryConfig` keys (`operation_spans` included). The server runs with `lifespan="off"`, so the environment auto-configure path can't run there either. The tests catch a later change to the switch.
- SSE: a snapshot, then the end event for a finished job. An audio job without voice files fails with `job-failed` and the voices message ("run the voice download first"), not `internal`.
- Shutdown with SIGINT: 0.4 s, prints "sci2audio has stopped.", and the port is closed afterwards.
- D-192 to D-209 as implemented match the approved plan. No decision changed in substance.

## Process

M1 and M2 are done. Fix S1 to S4. For N1 and N3, fix or open an issue. For N2, open an issue. Answer item by item on the PR (fixed and how, or the issue link). Don't force-push; merge main if it moved (PR #108 for #72 also rewrites `cli.py`).
