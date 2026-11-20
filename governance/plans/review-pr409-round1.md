# Review PR #409, round 1 (Working Reader batch A: #385 #386 #387 #388)

Head reviewed: 8982fcc (branch web/working-reader-a, from main a9e0e2d). Critical (risk:high), full depth, Opus high. Reviewer thread: "Review the Working Reader PRs".

**Verdict: changes needed. 2 blocking, 2 should-fix, 2 nits.** Fix all six in one push; round 2 then adds `ui:screens`, `ci:full` and the nightly browser dispatch.

## Blocking

**B1. The no-internet check misses protocol-relative addresses outside `src`/`href`/`action`, `url()` and `@import`.** Each of these one-line mutants passes both `tests/unit/test_web_design.py` and `test_web_pages.py::test_no_page_loads_anything_from_outside` (clean baseline: 50 passed; each mutant: 50 passed):
- `base.html`: `<img srcset="//192.168.1.9/x.png 1x" alt="">`
- `app.css`: `.x { background-image: image-set("//192.168.1.9/x.png" 1x); }`
- `base.html`: `<meta http-equiv="refresh" content="0;url=//192.168.1.9/">`
- `base.html`: `<video poster="//192.168.1.9/p.png"></video>`

The old `EXTERNAL` pattern needs a domain name (`.[a-z]{2,}`), and the new `PROTOCOL_RELATIVE` pattern only knows `src`, `href`, `action`, `url(` and `@import`, so an address given as an IP number in any other attribute or CSS function gets through. The browser fence would catch some of these at run time, but only on pages a test visits.
Fix:
1. In `outside_addresses`, for `.html`, `.css` and `.svg` files, report every `//` in the text. No such file contains `//` today (checked with `grep -rnP '(?<![:/])//'`), so the rule can be that strict.
2. For `.js` files, also report any quoted string that starts with `//` (the existing path rule in `test_web_pages.py` already covers this; say so in a comment, or move it next to the new check).
3. Add the four lines above to `test_the_check_finds_one_added_line`, each placed in the right kind of file. Today the self-check appends every case to `app.css`; give each case its own file name.

**B2. Every page with a job running now opens a second event stream, and three job tabs stop the whole interface.** `shelf()` opens its own `EventSource` on every page while a job runs. The job page and a document page whose analysis is running already follow the same URL, so they hold two streams each. Probe (init script counting `EventSource`, a gated voice job): `/jobs/voices-1` opened `['/api/v1/jobs/voices-1/events', '/api/v1/jobs/voices-1/events']`; `/` and `/settings` opened one each. A browser allows six HTTP/1.1 connections per host. With three job tabs open, a `fetch('/api/v1/settings')` from a fourth tab got no answer in 6 s (TimeoutError) on 8982fcc, and 200 in 0.01 s on main a9e0e2d (same probe, same test fixtures). Six library or Settings tabs during a job have the same effect, where main held no stream at all. The probe files are `tests/browser/test_zz_probe_streams.py` and `test_zz_probe_limit.py` in the reviewer's scratch worktree. Their code is in the appendix below.
Fix:
1. A page that already follows the running job (the job page, a document page with its analysis running) feeds the shelf from that same stream. Have `follow()` keep one `EventSource` per URL and hand each event to every caller.
2. On every other page, the shelf does not hold a stream. It asks `GET /api/v1/jobs/{id}` every 2 s (or a period you name), stops once the job is no longer running, and shows the end word as it does now. This is the "same poll" the plan named (§4). It also pauses while `document.hidden` is true and asks again on `visibilitychange`.
3. A browser test: with a gated job, the job page holds exactly one `EventSource` and the library and Settings hold none. Then, with three job tabs and three library tabs open, a `fetch` from another tab answers within 2 s. This test must fail on 8982fcc.
4. The same test, or a second one, checks the shelf from the script side: the words and the `<progress>` value change when progress arrives, and the end word shows when the job ends. Today no browser test runs `shelf()` (the unit test checks only the server-drawn item).

## Should fix

**S1. The licence metadata and the licence rule do not name OFL-1.1.** The wheel's `License-Expression` is `GPL-3.0-or-later`, but the wheel now carries twelve OFL-1.1 files. `.claude/rules/licences.md` does not list OFL-1.1 among the allowed licences (D-670 approved it for these fonts).
Fix:
1. In `pyproject.toml`, set `license = "GPL-3.0-or-later AND OFL-1.1"` and add `src/sci2audio/web/static/fonts/OFL-atkinson.txt` and `src/sci2audio/web/static/fonts/OFL-literata.txt` to `license-files`.
2. In `.claude/rules/licences.md` point 2, add "OFL-1.1 (fonts only, unmodified, licence text shipped beside them, D-670)".
3. `test_package_data.py`: the built wheel's METADATA has `License-Expression: GPL-3.0-or-later AND OFL-1.1` and both OFL files under `.dist-info/licenses/`.

**S2. The token test passes when a token is set again after the three blocks.** Mutants that pass all 49 tests of `test_web_design.py`: appending `:root { --cobalt: #000000; }`, and appending `:root[data-theme="dark"] .rail { --cobalt: #000000; }`. `LIGHT_BLOCK.search` reads only the first `:root {`, and no check looks at other selectors. No design token is declared outside the three blocks today (checked).
Fix: assert that there is exactly one `^:root \{` block, and that no `--<design token>:` declaration of the 22 `LIGHT` names appears anywhere outside the light block and the two dark blocks. Add both mutants to a self-check, as `test_the_check_finds_a_dark_block_that_drifted` does.

## Nits

**N1.** `test_the_appearance_route_is_guarded_and_its_cookies_grant_nothing`: add the wrong-Origin case (`headers={"Origin": "http://evil.example"}` gives 403). The middleware covers it, but the brief asks for the same guards as `/language`, and only `Sec-Fetch-Site` is tested.
**N2.** `test_the_screens_workflow_runs_no_value_into_a_script` checks only `run: |` blocks. Also check one-line `run:` steps for `${{` (zizmor covers it in CI; the test should too).

## Noted, no change asked

- Saving only the speed on Settings also writes the shown default folder (`~/Documents/sci2audio`) into `settings.json`. The command line then writes there instead of next to the source. Starting an audiobook from a document page already does the same (D-246), so this is consistent and not a new kind of change.
- Settings says "Speed of the voice" / "Tempo der Stimme" where the prototype says "Playback speed" / "Abspieltempo". The PR's wording is right, because the field is the synthesis speed (D-663: product facts win).
- The OFL texts differ from Fontsource's `LICENSE` files only in the first line. Fontsource lists one copyright per style, and the PR keeps one copyright line per family. The licence body is identical.

## Verified (no finding)

- **Fonts:** all 12 woff2 files are byte-identical to `@fontsource/atkinson-hyperlegible@5.3.0` and `@fontsource-variable/literata@5.3.0`, downloaded from registry.npmjs.org. Both tarball sha512 values match the `integrity` values in `THIRD_PARTY_LICENSES.md`. Every SHA-256 row matches its file. The name tables read Atkinson Hyperlegible Version 1.006 and Literata Version 3.103 (wght 200 to 900). All 12 `unicode-range` values equal Fontsource's own CSS. The wheel built from 8982fcc contains all 12 fonts, both OFL texts, `_icons.html` and `settings.html`. Adding a 13th font file fails two tests.
- **Mutants from the PR body:** the dark-block drift and the light-token change are killed by `test_the_tokens_are_the_designs_in_light_and_dark`. Changing either dark selector breaks the block count. The listed no-internet mutants are killed.
- **Cookie routes:** `/appearance` stores only values from `THEMES` and `ANNOUNCE`, with the cookie attributes as `/language` sets them. It redirects through `local_path`: `"/" + back[1:]` is the same path after the same refusals, control characters (tab) included. It is behind the token and Sec-Fetch-Site guards. The cookies grant nothing (401 without the token cookie).
- `security.py` is unchanged, so the CSP is unchanged. There is no `style=` and no inline handler in any template. There is no change to `core`, `app/`, `api.py` or the API schema (diff stat).
- **Strings:** both tables have the same keys. The German wording follows `prototype/app/i18n.js` and uses "Sie". The privacy text says "at most four cookies" in both languages.
- **Workflow `ui-screens.yml`:** label- and same-repo-gated, `permissions: {}` with `contents: read` on the job, head SHA checked out with `persist-credentials: false`. Its actions are pinned to the same SHAs as in `ci.yml` and `release.yml`. `zizmor --offline` reports no findings. The test uses only corpus documents (joss2021-waskom-seaborn.pdf, CC BY; the sample note, CC0).
- **D-288 amendment (D-673):** the tests check that Settings is linked from every page's rail and that the switch is on Settings. D-670 extras: neither Captures nor Keyboard shortcuts is in the rail.
- **Local runs on 8982fcc:** fast suite 5,932 passed, 1 skipped. Browser suite (Chromium) 82 passed, 2 skipped (the #365 quarantine and the screens test without its folder). That run covers axe light and dark at 1440 and 1280 px, keyboard order, reflow at 320 px in English and German, reduced motion, the Highlighter rule and the font loading. GitHub checks on 8982fcc are all green.

## Round 2 plan (reviewer)

Recheck B1, B2, S1, S2, N1 and N2 with their mutants (B2: the new test must fail on 8982fcc). Then add `ui:screens` and compare the artifact with `prototype/app/screens/`. Add `ci:full` and check three-green on the head. Dispatch `nightly.yml` on the branch for Firefox and WebKit.

## Appendix: probe code

```python
COUNT = """(() => { const E = window.EventSource; window.__streams = [];
  window.EventSource = function (url, o) { window.__streams.push(String(url)); return new E(url, o); };
  window.EventSource.prototype = E.prototype; })();"""
# test_zz_probe_limit: gated(live.state, JobKind.VOICES, None); open 3 new tabs at /jobs/<id>;
# page.evaluate("fetch('/api/v1/settings', {signal: AbortSignal.timeout(6000)}).then(r => r.status).catch(e => String(e))")
# 8982fcc: TimeoutError after 6.01 s; a9e0e2d: 200 in 0.01 s
```
