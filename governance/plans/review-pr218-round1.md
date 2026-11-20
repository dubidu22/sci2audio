# Review of PR #218, round 1 (closes #205, nightly Firefox/WebKit browser tests)

Reviewed head: 368e1f5 (8133f47 plus main 31b6d16 merged in). Non-critical: tests and one nightly-only workflow step. Decisions in force: D-451, D-452, D-466.

## Scope

Four files: `.github/workflows/nightly.yml` (+8), `tests/browser/conftest.py` (+9 −1), `tests/browser/test_flow.py` (+28 −1), `tests/browser/test_keyboard.py` (+8 −1). No `src/` change, no golden, contract, KB or release-workflow change.

## Checks

1. **Fence (D-451).** `inside(url, origin)` is `url.startswith((origin + "/", "blob:" + origin + "/"))`. `live.url` is `config.origin` with no trailing slash (the fixture asserts `page.url == live.url + "/"`). The trailing `/` is what stops `http://127.0.0.1:5000@evil/…`, `…:50000/…` and other-port prefixes. Still caught: `blob:` of another origin, `data:`, plain http to other hosts, another port, an origin embedded in another host's path. The unit test lists each of those; `test_a_request_elsewhere_is_caught_and_refused` drives a real navigation to TEST-NET-1 through the fence and checks it is recorded and aborted. Both pass locally (Chromium).
2. **Tab round (D-452).** A press that leaves focus on the same stop is skipped, not counted. A genuine trap never reaches the body, so the bounded loop (`MAX_TABS * 2`) ends in `Tab never left …`. Checked by mutation, locally in Chromium: unchanged test passes; a one-element trap (keydown Tab preventDefault) fails with `Tab never left`; a two-element cycle (Tab on b refocuses a) fails with `Tab never left`. Note, accepted under D-452 and not a finding: an element that swallows exactly one Tab mid-page would now pass on every engine. That is an extra keystroke, not a trap (WCAG 2.1.2 is not broken), so no issue.
3. **PulseAudio (D-466).** The step is in `nightly.yml` only, guarded by `matrix.browser == 'firefox'`; the only Firefox row is `ubuntu-latest`, so `sudo apt-get` never runs on macOS. `apt-get update` already ran inside `playwright install --with-deps` just before. `ci.yml` is untouched; its browser job runs Chromium only. `--exit-idle-time=-1` keeps the server alive for the whole test step.
4. **No app code.** Diff against main 31b6d16 touches only the four files above.
5. **Local runs.** `ruff check`, `ruff format --check`, `zizmor --offline .github/workflows` clean. Chromium browser keyboard and fence tests pass.

## Nightly run on the branch

Run 43517768285 (workflow_dispatch, head 368e1f5): see result below.

- browser (chromium, ubuntu-latest): success, 48 passed
- browser (firefox, ubuntu-latest): success, 48 passed (PulseAudio step works)
- browser (webkit, ubuntu-latest): success, 48 passed
- **browser (webkit, macos-latest): failure, 2 failed, 46 passed**
  - `test_player.py::test_the_player_by_keyboard_only[webkit]`: `no focus ring on BODY`. The test presses plain `Tab`; macOS WebKit skips buttons and links on plain Tab, which is why `test_keyboard.py` uses `tab_key` (`Alt+Tab` for WebKit). Lines 174, 191, 331 use plain Tab.
  - `test_flow.py::test_the_document_page_says_when_the_server_is_gone_while_it_analyses[webkit]`: `Page.reload: Navigation canceled by policy check` (line 315). Guess, not verified: `open_paper` returns on `#summary` visible while the page's own `reloadAt("step-check")` (app.js 77-80) may still be running; the two reloads collide.
  - Both tests did not exist at the 13 Nov nightly (17 browser tests then, 48 now), so they are new failures on this row, not caused by this PR, but inside #205 (acceptance: all four rows green).

Fast CI on 368e1f5: all checks green (tests on three OSes, Chromium browser, lint, licences, security, CodeQL, ZAP).

## Findings

Must fix (posted as PR review https://github.com/dubidu22/sci2audio/pull/218#pullrequestreview-5898856855, a COMMENT review because GitHub refuses "request changes" on the account's own PR):

1. Make the macOS WebKit row green: use `tab_key` in `test_player.py` (share it via `conftest.py`); find the cause of the reload cancel in the server-gone-while-analysing test and fix it (likely wait for the page to settle before reloading), or show it does not reproduce (D-374 quarantine only after a second failure without a code cause).
2. Dispatch the nightly on the branch again and post the four browser rows.

No should-fix. The three fixes in the PR are correct as they stand.
