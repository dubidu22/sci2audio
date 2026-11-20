# Review of sci2audio PR #142 (#79, German interface and privacy page), round 1

Reviewed head: 5d1da7e (branch web/languages-79). KB PR: sci2audio-design #42 at 20485ed.
Reviewer thread: "Review German interface PR 142", 13 Nov 2026.

## What was checked

- Whole diff (18 files) against plan `issue79-languages-plan.md` and D-288 to D-293, D-321.
- Fast suite (`ci` profile): 2154 passed. `test_web_launch.py::test_nothing_listens_after_the_server_stopped`
  timed out once under load and passed on its own rerun (known SIGINT timing flake in this
  container; `web/launch.py` is not touched by this PR).
- ruff, ruff format, lint-imports (3 contracts kept), deptry: clean.
- Browser suite (Chromium 1243): 26 passed, including the 17 German axe states.
- Nightly Hypothesis profile on `tests/unit/test_web_*.py`: 237 passed, 1 failure = the same launch flake.
- Own Hypothesis probes (20 000 examples each, not committed): `local_path` on any text always gives a
  Location with no scheme and no host after Starlette's quoting; `from_accept_language` never fails and
  returns only None/en/de; `Strings.number`/`size` never fail.
- Security by hand: `/language` with `//evil.test`, `/\evil`, `https://evil`, `/%2F%2Fevil.test`,
  fullwidth solidus, U+2028, DEL, `/.//evil.test`: all stay on this server. Unknown or upper-case language
  sets no cookie. `Sec-Fetch-Site: same-site` (another port on 127.0.0.1) is refused 403. Cookie:
  `sci2audio-language=de; HttpOnly; Max-Age=31536000; Path=/; SameSite=strict`, separate from the
  port-named start cookie, value always from `LANGUAGES`. Templates: all text through `t()` and Jinja
  autoescape; error details set with `textContent`; the report's language validated by `_TAG`.
- Privacy page points checked against code: HF_HUB_OFFLINE, network imports, TELEMETRY_OFF,
  HOST, access_log=False, folders (work root, output, settings file, models dir incl. the spaCy model),
  cookies. All true.
- Reflow at 390 px (WCAG 1.4.10), which axe does not test: start, document, voice, privacy in German;
  document in English.
- CI on 5d1da7e: all green on Linux, macOS, Windows, browser job, CodeQL.

## Findings

### M1 (must fix): the German document page scrolls sideways at 390 px

The voice `<select id="voice">` is as wide as its longest option. In German that is
"Heart, amerikanisches Englisch, weiblich (Standard)", 445 px wide, so at a 390 px viewport the page
scrolls horizontally (`document.documentElement.scrollWidth` = 445; the select, its label, the licence
hint and the speed row stick out). English stays at 390 px. This fails WCAG 2.2 SC 1.4.10 Reflow (AA,
D-257's bar), which axe doesn't check. Start, voice and privacy pages are fine at 390 px.

Fix: let form controls shrink, e.g. `select, input, textarea { max-width: 100%; }` in `app.css`, and a
browser test that every German and English page state has `scrollWidth <= 320` at a 320 px viewport
(the change-list tables don't widen the page today: English measures 390 with them on it).

### S1 (should fix): the "open the link" page is English only and outside the tables

`security._unauthorised` builds the 401 page a browser sees without the start cookie (for example a
tab left open after sci2audio restarted) with a hard-coded English sentence. A German browser gets
English there, and #79's first criterion asks for all interface strings in the tables. Fix: choose the
language with `i18n.language_of`-style logic from the request headers (cookie, then Accept-Language)
and take the sentence and title from the table (`common.no_token` or reuse `error.no-token`), with
`lang` set accordingly; a unit test in both languages. If it is deferred, open a v1.0 issue.

### N1 (nit, optional): a missing key gives `KeyError: 'n'`

`Strings.t` falls through to the plural lookup when a key is missing and no `n` is given, so a typo
reports `KeyError: 'n'` instead of the key. The table tests make this unlikely; a clearer
`KeyError(key)` would help whoever adds strings later.

## KB PR #42

Content matches the plan, the code and the coordinator's decisions; rows sit above D-280 newest first;
back-references on D-256 and D-195 change only the Record column. One finding:

### K1 (must fix): D-321's "Colin informed" time

D-321 says "Colin informed in the project chat at 2026-11-13T13:06Z". The chat post's created_at is
2026-11-13T13:06:20Z; the other rows give the full time, so D-321 should too.

Order: KB #38, #39, #40, #41 merge first; then merge main into kb/decisions-79 and keep numeric order
(D-321 above D-320/D-319; D-293 to D-288 between D-304 and D-287).

## Verdict

Not yet. Fix M1 and K1; fix S1 or open an issue for it; N1 optional. Then round 2.
