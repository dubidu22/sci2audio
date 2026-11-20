# Plan: batch B-W1, opt-in update check and two more security headers (#217, #172)

Thread: web/app lane implementation, Opus 5.5 high. Status: **proposal, waits for the coordinator's approval**. Critical (CRIT-01: a network call), so `risk:high`; no code or tests before approval (PLAN-01).

Sources read: main f98d446: `CLAUDE.md`, `governance/rules/implementation.yaml`, `.claude/rules/tests.md`, `src/sci2audio/web/security.py`, `web/pages.py` (settings and privacy pages), `web/api.py` (settings API), `web/window.py`, `app/settings.py`, `app/config.py`, `voices/download.py` (the one network client today), `testing/text_steps.py` (`no_network`), `tests/browser/conftest.py` (the request fence), `tests/unit/test_web_security.py`; issues #217 (AQ-07) and #172; decision log D-47, D-104, D-122, D-192 to D-196, D-203, D-293, D-458, D-460, D-666.

One PR into `main`, title `app, web: opt-in update check and Permissions-Policy and COEP headers (#217, #172)`, labels `lane:app`, `lane:web`, `risk:high`. Files: `src/sci2audio/app/**`, `src/sci2audio/web/**`, tests, `README.md`, `CHANGELOG.md`. No `pyproject.toml`, `uv.lock` or `.github/**` change, no new dependency (`requests` is already one, D-122), so no `lane:infra` lock.

## 1. Where the check lives

- **`app/updates.py`** (new, lane:app) owns everything that touches the network or the file: the choice, the request, parsing the answer, the "once a day" rule and the result. No pipeline stage touches it, and the stages never import it (layers unchanged; `lint-imports` stays as is).
- **`web`** only shows it and passes the person's switch through: a settings section, a JSON endpoint, and a notice on every page. It never opens a connection itself.
- The CLI's `convert`, `listen` and `voices` never run the check. It runs only inside the server (`sci2audio ui` and the app window), because that is where its result can be shown.
- No global state: the server's `ServerState` holds one `UpdateCheck` object built from `ServerConfig` (the state file path and an injected `fetch` callable, default the real one), so each test passes its own.

### 1.1 The remembered choice

A separate small file **`update-check.json`** next to `settings.json` in the user's configuration folder (`default_config_file().parent`), not a field of `JobSettings`: it is not a job setting, and adding it to `settings.json` would make 1.4.0 warn "unknown setting" on a downgrade. Contents: `{"version": 1, "enabled": bool, "checked_at": ISO-8601 UTC or null, "outcome": "newer" | "current" | "failed" | null, "latest": "X.Y.Z" or null}`. Written with `app.files.write_text_atomically`. **A missing, unreadable, damaged or unknown-version file means off**, never on.

### 1.2 What is sent and received

- **One `GET https://api.github.com/repos/dubidu22/sci2audio/releases/latest`**, the constant `RELEASES_URL` in `app/updates.py`. This endpoint never returns drafts or pre-releases.
- Sent: the request line, `Host`, `User-Agent: sci2audio` (GitHub's API refuses requests without one; **no version number, no system name, no ID**), `Accept: application/vnd.github+json`, and what `http.client` adds by itself (`Accept-Encoding: identity`). No cookie, no query string, no body, no authorisation. A `requests.Session` with **`trust_env = False`** and cleared default headers, so a `~/.netrc` entry or environment can never add credentials. The IP address is unavoidably seen by GitHub; the privacy page says so.
- `allow_redirects=False`: any answer other than 200 is a failed check. The body is read streamed and cut at 1 MiB (a release answer is about 30 KB).
- Received and used: only `tag_name`, which must match `v<int>.<int>.<int>`. The link shown is **built by us** as `https://github.com/dubidu22/sci2audio/releases/tag/v<X.Y.Z>`; the answer's own `html_url` and everything else in it is ignored, so a tampered answer can show at most a wrong version number, never a foreign link or text.
- Compared as integer tuples against `sci2audio.__version__`; "newer" only when strictly greater.

### 1.3 When it runs ("at most once a day", "started by the user")

- Off by default. The person turns it on in Settings (a checkbox with one sentence saying what is sent, and a link to the privacy page); turning it off stops it. Turning it on is the start the person gives (the same idea as the voice-download consent, D-203).
- It runs only when `enabled` is true **and** `checked_at` is missing or 24 hours or more ago, at three moments: when the person turns it on, when the server starts, and when a page is rendered while the server has run past the 24 hours. It never runs twice at once (a lock), and a failed check counts as a check, so a failure is retried the next day, not on the next page.
- The file is read again right before each request, so a file turned off or removed in between means no request.
- No retry (REV-06), no "check now" button (it would break "at most once a day"); a follow-up issue if wanted.

### 1.4 Timeouts and failure behaviour

- Timeout `(5, 10)` seconds (connect, read). The check runs in a daemon thread; pages, the API and jobs never wait for it, and the server's shutdown does not wait either.
- Every failure (no network, DNS, TLS, timeout, non-200, a redirect, too long, not JSON, wrong tag) is caught, stored as `"outcome": "failed"` with the time, and logged once with `logging.getLogger("sci2audio.updates").warning` naming the kind of failure only (no answer body). Nothing is shown in a dialog; Settings shows "The last check on <date> did not work".
- A failed write of the state file (disk full, removed folder) keeps the result in memory for this run and logs a warning; it never raises into the server.

### 1.5 What the interface shows

- **Settings**: a section "New versions" with the checkbox (`PUT /api/v1/updates {"enabled": bool}` from `app.js`, like `PUT /api/v1/settings`), and the last result: off; on, not checked yet; up to date as of <date>; "sci2audio X.Y.Z is out" with the link; or the failure line.
- **Every page**: when the stored outcome is "newer" and the check is on, one quiet line in the rail: "sci2audio X.Y.Z is out: release page" (a plain link; the app window already opens other sites in the system browser, `OPEN_EXTERNAL_LINKS_IN_BROWSER`). Nothing downloads or installs.
- **`GET /api/v1/updates`** returns `{enabled, checked_at, outcome, latest, release_url}`; `PUT` takes `{enabled}`. Both behind the token and origin check like every route; Schemathesis covers them through the OpenAPI schema.
- Strings in `en.toml` and `de.toml`. CSP is unchanged: the page never contacts GitHub, so the browser tests' fence (no request outside the server) still holds.
- **Privacy page** (#79, D-293): the "nothing leaves" point loses "no update check" and gains "no update check unless you turn it on"; a new point "The update check you turn on" names the host (from `RELEASES_URL`, not typed), what is sent (above), that GitHub sees the IP address, and that it is off by default. The app-log line says the log may also note a failed update check. README "no update check" line and CHANGELOG known limit "No update check" change to match.

## 2. The two headers (#172)

Added to `SECURITY_HEADERS` in `web/security.py`, so they are on every answer including the middleware's own 401, 403, 405 and 421 (they already pass through `_with_headers`):

- **`Permissions-Policy`**: `accelerometer=(), autoplay=(self), camera=(), clipboard-read=(), clipboard-write=(), display-capture=(), encrypted-media=(), fullscreen=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), midi=(), payment=(), picture-in-picture=(), publickey-credentials-get=(), screen-wake-lock=(), serial=(), sync-xhr=(), usb=(), web-share=(), xr-spatial-tracking=()`. Checked against `static/*.js` and the templates: the interface uses none of these except audio playback, which keeps `autoplay=(self)` because the player starts the next chapter by itself after one ends. Only feature names Chromium knows, so no "Unrecognized feature" console error.
- **`Cross-Origin-Embedder-Policy: require-corp`**. Every resource is same-origin (pages, `/static`, fonts, audio with `Range`, figure crops) or a `data:` image; none needs CORP. With the COOP `same-origin` already sent, the page becomes cross-origin isolated, which changes nothing it uses.

What must not break, and the tests that prove it: the main flow, axe pages, the player (play, seek with `Range`/206, next chapter, speed, figures), fonts, the download links, the app window. The browser suite runs whole; one new browser test asserts both headers on the page and its audio answer and that Chromium logs no Permissions-Policy or COEP console message. The ZAP workflow stays as it is; I run `zap-baseline.py -a` once by hand only if Docker is available and report the result in the PR body (not a CI change).

## 3. Tests (written first, all with the network blocked)

Unit (`tests/unit/test_app_updates.py`, `test_web_updates.py`, additions to `test_web_security.py`, `test_web_pages.py`):

1. **Off by default proves no request**: a fresh server (no state file) under `no_network()`, every page and API route requested, a job run → `attempts == []` and the fake `fetch` never called. Same with `enabled: false`, with a damaged file, with an unknown version and with the file removed.
2. **On means exactly one request**: enabled and due → the fake `fetch` is called once with `RELEASES_URL`; a second page render within 24 h → still once; time moved 24 h on (injected clock) → twice.
3. **What is sent**: the real `fetch` with `requests.Session.send` replaced by a recorder (under `no_network()`, so a leak fails the test): the prepared request has method GET, exactly `RELEASES_URL` with no query, no body, headers exactly `User-Agent: sci2audio` and the `Accept` line, no `Cookie`/`Authorization`, `trust_env` false, `allow_redirects` false, the timeout `(5, 10)`. A `~/.netrc` with a password for `api.github.com` in a temporary `HOME` adds nothing.
4. **What is used**: the shown link is ours even when `html_url` points elsewhere; `latest` older, equal, newer; tags `1.5.0`, `v1.5`, `v1.5.0-rc1`, a 2 MiB body, non-JSON, a list, a 301, a 404 → "failed" or "current", never an exception. A Hypothesis property: any JSON value as the answer → a valid outcome, never an exception.
5. **Never blocks**: a fake `fetch` that waits on an event; pages and `GET /api/v1/updates` answer at once and a job finishes while it waits.
6. **Settings and the notice**: `PUT /api/v1/updates` on and off, kept across a server restart; the rail notice only when on and newer; the privacy page names the host taken from `RELEASES_URL` and no longer says "no update check" unqualified (D-293 check-against-code pattern); the strings exist in both languages.
7. **A static guard (META-03)**: an AST scan of `src/sci2audio` asserts that only `voices/download.py` and `app/updates.py` import `requests`, `urllib.request`, `http.client` or `socket` (the launcher's own 127.0.0.1 socket is listed by name). This turns the CLAUDE.md network rule into a failing test for any third place.
8. **Headers**: `test_security_headers_on_every_kind_of_answer` extended with both headers on all eight answers plus a `Range` audio answer (206) and the 405 from `/start`.

**Fault injection** (tests.md: first network code and new file writing):

- no network: `no_network()` with the real `fetch` → "failed", one warning logged, server fine;
- timeout: a `fetch` raising `requests.Timeout` → "failed", and the next attempt only after 24 h;
- disk full: `write_text_atomically` raising `OSError(ENOSPC)` → result shown from memory, warning logged, no 500;
- killed mid-run: a write that fails after the temporary file is made → the old file is intact and parses, the next start checks again;
- file removed during the run: removed between "turn on" and the request → no request.

Browser (`tests/browser/test_updates.py`, Chromium on PRs): turn the check on in Settings with a fake `fetch` returning a newer version → the notice shows on the next page, the link is the built one, axe clean on Settings with the section, and the fence sees no outside request. The existing browser suite runs whole for the headers.

No `slow`, `benchmark` or nightly additions: one bounded request, nothing long-running.

## 4. Proposed CLAUDE.md wording

Current: "**No network calls** except a voice or model download the user started. No telemetry, no analytics, no crash upload, no paid APIs."

Proposed: "**No network calls** except a voice or model download the user started, and the update check the user turned on (at most one request a day to the GitHub releases API, sending nothing but the request itself; off by default). No telemetry, no analytics, no crash upload, no paid APIs."

The same widening applies to INV-03 in `governance/claude-project-rules.yaml` ("unrequested network calls"), which already reads correctly (the check is requested by turning it on); META-01 means any change there is the owner's. Recommendation: land the CLAUDE.md line in this PR, so the rule and the behaviour never disagree on `main`; the coordinator decides.

## 5. Rough size

- `app/updates.py` about 160 lines; `app/__init__.py` exports.
- `web`: `security.py` +3, `api.py` +45, `pages.py` +25, `models.py` +15, `state.py` +15, templates +35, `app.js` +30, strings +25 lines each language.
- Tests about 550 lines unit, 80 lines browser. Docs: privacy strings, README, CHANGELOG, CLAUDE.md (if approved here).

## 6. Choices made (no open question)

- Separate state file rather than a `settings.json` key (1.1).
- GitHub REST `releases/latest` rather than the `releases.atom` feed: JSON needs no XML parser (no new dependency, no XML-attack surface); the unauthenticated limit of 60 requests an hour per address is far above one a day.
- `trust_env = False`: system proxy variables are not honoured in this version; behind a proxy the check fails silently. Follow-up issue only if someone asks.
- `requests` (already a dependency) over `urllib.request`, matching the voice download.

Follow-ups (issues only if the coordinator wants them): a "check now" button; proxy support; the update check in the CLI.
