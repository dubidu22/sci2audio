# PR #675 review, round 1 (head c691608)

Reviewer: B-W1 web/app review thread, Opus. 20 Nov 2026. Plan: plans/web-b-w1-plan.md (D-837).
Critical: **yes** (CRIT-01: the first network call outside the voice download; `risk:high` set; plan approved as D-837).
Verdict: **changes requested** (2 must-fix, 4 should-fix, 4 notes).

## Checked and fine

- **(a) Privacy and hard rules.** `app/updates.py`: one `GET RELEASES_URL` (constant, no query, no body); `session.headers.clear()` then exactly `User-Agent: sci2audio` and `Accept: application/vnd.github+json` (no version, system or ID); `trust_env = False`; `allow_redirects=False` and any non-200 fails; streamed body cut at 1 MiB (checked on decoded chunks, so a compressed answer cannot grow past it); only `tag_name` is read, strict `v<int>.<int>.<int>` with ASCII digits; the link is `RELEASE_PAGE.format(...)`, `html_url` ignored. Off is the default (`UpdateState()`), a missing, damaged, folder-in-place or unknown-version file reads as off. `test_a_server_as_shipped_makes_no_request` runs every page, the API and a job with the real fetch under `offline`. Transport-level tests pin method, URL, two headers, timeout, no proxy, `verify=True` against `~/.netrc`, `HTTPS_PROXY` and `REQUESTS_CA_BUNDLE`.
- **(b) Layers.** The check lives in `app`; `web` only calls `UpdateCheck` and renders; no pipeline stage or `cli.py` imports `app.updates`; `.importlinter`/`pyproject.toml` untouched; `lint-imports` 3 kept.
- **(c) Failure behaviour.** Timeout `(5, 10)`, daemon thread, one at a time (lock plus alive check), no retry; every exception becomes `failed`, logged once by `sci2audio.app.updates`, which propagates into the app's `sci2audio.app` file handler (`web/window.py:71-86`), so the privacy page's app-log sentence is true. Fault-injection tests present: no network, timeout, any exception, disk full (result kept for the run), killed mid-write (old file intact), file removed before the request, turned off during a request.
- **(d) Once a day.** `due()` re-read under the lock in `check()` right before the request; failed counts as checked; clock set back is due once; restart within the day does not check; tests present with an injected clock.
- **(e) Headers.** Both in `SECURITY_HEADERS`, so on the middleware's 401, 403, 405, 421 too; unit test covers 10 answer kinds incl. a 206 and the 405 from `/start`; `autoplay=(self)` is the only non-`()` feature (pinned by a test); `web-share` dropped from the plan's list for a Chromium console message, as the PR says. Browser test: `crossOriginIsolated` true, no Permissions-Policy/COEP console message.
- **(f) Docs.** Privacy page (`local`, new `updates` section with the host from `urlsplit(RELEASES_URL)`, `app_log`), README privacy list and CHANGELOG Unreleased say what the code does; truth test extended.
- **(g) Strings.** All new keys in both `en.toml` and `de.toml` (`js.updates_*`, `privacy.updates*`, `nav.update`, `settings.updates*`); German page tested.
- **(h) Browser.** `tests/browser/test_updates.py`: switch on/off, rail link is the built one, axe clean off and on; the fence sees no outside request.
- **(i) Tests fail without the change**, by reading: new module and endpoints, header assertions on `main`'s `SECURITY_HEADERS` fail.
- **(j) Licence and scope.** No new dependency (`requests`, Apache-2.0, D-122); licence note present. `scripts/zap_scan.py` gains the two new routes with a fake fetch, which keeps the ZAP walk complete and offline; in scope. CLAUDE.md §4 line deliberately held back for the owner (not a finding).
- **Local run** (temporary worktree at c691608, macOS): RESULTS_PLACEHOLDER

## Must fix

**M1. Turning the check off on a disk that will not take the write leaves it running.** `src/sci2audio/app/updates.py:203-211` builds the "off" state and saves it first; when `save_update_state` raises, `self._unsaved` is not touched, so `_read()` (line 200) still returns the old "on" state (from the file, or from an earlier unsaved result) and `poll()` keeps starting requests. Probe: on, then a day later a result that cannot be saved, then `set_enabled(False)` on the full disk → 507, `state().enabled` is still True, and one more day later a third request goes out. The person asked for no more requests and gets them; for the one opt-in network call this must fail closed. Fix at the root: an "off" always takes effect in memory for this run whether or not it can be saved (e.g. keep it in `_unsaved` before or after the failed save, and let `check()` refuse when either the memory or the file says off); the API may still answer 507 so the person knows it will not survive a restart, and the settings page/JS should then show it off for this run. Add a fault-injection test: on, disk full, turn off → no further request on later days within the run.

**M2. `sci2audio listen` runs the update check, which D-837 and plan §1 rule out.** D-837: "runs only in the server, never in the CLI commands"; plan §1: "The CLI's `convert`, `listen` and `voices` never run the check." `cli.py:1057` `run_listen_command` calls `sci2audio.web.run(..., outside=(job,))` → `launch.serve` → `create_app(config)` (`web/launch.py:150`) → `ServerState.updates` with the real fetch and `create_app`'s `poll()` (`web/server.py:294`). So with the check on, `sci2audio listen paper.pdf` makes the request. Either pass a disabled/never-fetching `UpdateCheck` when `outside` is given (matching the approved plan), or get the coordinator to record that `listen` counts as "the server" and change the plan text; in both cases pin the chosen behaviour with a test (no `fetch` call when the server is started for `listen`). The PR body's "runs only inside the server ... never in the CLI commands" currently does not match the code.

## Should fix

**S1. The network guard is the old regex, not the AST scan plan §3.7 promised.** `tests/unit/test_web_languages.py:613-627` matches `^\s*(import|from)\s+(requests|socket|...)\b`; it misses `from urllib import request`, `import json, requests`, `importlib.import_module("requests")` and modules such as `ssl`, `ftplib`, `smtplib`, `asyncio` streams. Replace it with an `ast` walk over `src/sci2audio` (every `Import`/`ImportFrom`, top-level module name against a deny set, plus `import_module`/`__import__` calls with a literal), allow-listing `voices/download.py`, `app/updates.py`, `web/launch.py`, `testing/text_steps.py` by name (META-03).

**S2. No test proves the failed-check line reaches the app log.** The privacy page now says the start-up log notes a failed update check (`app_log` string), which holds only because `sci2audio.app.updates` is a child of the `sci2audio.app` logger that `window.open_log` sets. A rename of the module or logger would break the claim silently. Add a test (D-293 pattern) that after `open_log(tmp)` a failed check writes one line to that file, and that the line carries no body.

**S3. The audio 206 answer is not checked for the new headers.** Plan §3.8 and the brief ask for a `Range` audio answer; `tests/unit/test_web_security.py:265` uses `/static/app.js`, and the browser header test visits only `/`, `/settings`, `/voice`, `/privacy`. Add an audio `Range` request (the player's chapter route) to the unit list, or a Listen page to the browser test, so COEP/Permissions-Policy on media answers are pinned.

**S4. The `PRODUCT.md` follow-up has no issue.** The PR body says `docs/design/PRODUCT.md:40` still says "no update check" and leaves it to the docs lane, but names no issue (GH-01). Open one (lane:docs, v1.4 or next milestone) and link it in the PR body.

## Notes

- **N1.** PR title names only `(#217)` though it closes #172 too; consider `(#217, #172)` as in the plan.
- **N2.** `TIMEOUT` read value bounds the gap between chunks, not the total; a trickling server can keep the daemon thread alive for long (bounded by the 1 MiB cap). Harmless since nothing waits and no second check starts meanwhile; mentioned only.
- **N3.** Two server processes at once (`sci2audio ui` and the app) each have their own lock and could both check on the same day. Edge case, not a plan requirement.
- **N4.** `api.py` `put_updates`: `error.strerror` can be `None` for an `OSError` without errno, giving "could not save the choice: None"; `str(error)` as fallback.

## Handoff (THR-07)

- Goal: PR #675 (B-W1) to merge.
- Done: round 1 at c691608, changes requested (M1, M2, S1 to S4).
- Next: round 2 on the author's fix commit; check the fail-closed "off" test, the `listen` decision and test, the AST guard; then the three-system run on the final head (CRIT-02).
