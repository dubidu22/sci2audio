# Nightly-green batch: hand-off after PR 1

Written 17 Nov 2026 by the thread "Port the release 1.1 fixes to main" (2 compressions, stops here).
Goal: main's nightly green on Firefox, WebKit Ubuntu and WebKit macOS (D-731). Lane:web, non-critical.
At most three PRs, grouped by cause, one at a time, same review thread
(cmsg_011gr2YyZJypGaV6NbzgSXQEMAdYua6GyR8gbNH6QvLfdP), max 2 rounds each.

## PR 1 = #510 (branch tests/webkit-focus-tab, from main 1e461a7)

Closes #496, #497, #498, #502. #508 was closed as a duplicate of #506.

- **#502, the real cause** (the issue's guess "Tab starts from the last focused control" was wrong).
  A press on the narrow panel's text focuses `<main tabindex=-1>`. Chromium and Firefox Tab from
  main to `#tab-prepare`, outside the panel, so the panel closes. WebKit Tabs from the pressed
  text, the panel's last item. The focus leaves the page for the browser bar: focusout on main
  with relatedTarget null, then `document.activeElement === body`. No page element is focused,
  so the panel's focusout/focusin listeners do not close it. The next Tab comes back in and
  closes it. The test now checks that WebKit path explicitly. The app is right.
- **#498 ruling:** tests follow Safari's click-focus rule (a click gives a button no focus in
  WebKit macOS), except the narrow panel Close button. `player.js` Close now calls
  `toggle.focus()` after `set(false)` in every browser. A new test in
  `test_the_panel_beside_the_desk_and_over_it` (blur, dispatch the click) fails without it.
- **`conftest.click_focuses(page)`**: False only in WebKit on macOS. Wrap only a check of the
  focus that a click itself gives: `if click_focuses(page): expect(btn).to_be_focused()`.
  Never skip a whole test, and never skip a focus the app sets itself.
- **`conftest.tab_key(page)`**: "Alt+Tab" in WebKit, "Tab" elsewhere. WebKit, like Safari's
  default, leaves links and buttons out of plain Tab. Any test that Tabs onto a button uses
  `page.keyboard.press(tab_key(page))` or `f"Shift+{tab_key(page)}"`. #496 and #497 were this.

Verification: the 9 changed/affected tests pass locally in Chromium, Firefox and WebKit (Linux).
WebKit macOS can only be checked by a nightly dispatched on the branch (run 44065741504).

## What remains: PR 2 (#499 #500 #501), key chords, transition, pixels

- **#499** (WebKit macOS): `test_focus.py::test_the_keys_stay_out_of_the_way` presses
  `Meta+ArrowLeft`, which is Back on macOS; drop it on darwin or swap for a chord the system
  ignores, and assert the page is still the Listen page. `test_library.py::test_the_search_filters_
  as_the_person_types_and_works_without_the_script`: `Control+a` → `ControlOrMeta+a`.
- **#500** (Firefox Ubuntu, WebKit macOS): `test_listen.py::test_the_sentence_being_read_is_marked_
  plainly_and_a_heard_one_has_no_tint` fails in `marked_plainly()` with `all: 1` right after
  `page.emulate_media(color_scheme="dark")`. Likely the switches' `.2s` transition (`app.css`
  `input.switch`/`::after`). Confirm first with `document.getAnimations().map(a => a.effect.target)`
  in Firefox (reproducible on Linux). Fix: await `Promise.all(document.getAnimations().map(a =>
  a.finished))` after a theme change only; keep `all == 0` everywhere else (D-709).
- **#501** (Firefox Ubuntu): `test_player.py::test_the_dock_never_hides_the_page` asserts
  `bar["bottom"] == height`; Firefox gives 799.99998. Use `abs(...) < 0.5`.

## What remains: PR 3 (#506 #509), timing

- **#506**: `test_markers.py::test_the_note_box_pauses_esc_leaves_it_and_a_note_survives_a_reload`
  clicks Save and reloads at once. Wrap the Save click in `page.expect_response(...)` for the
  marker write, then reload; same for the second reload. #507's branch nightlies hit it in WebKit
  Linux and in Firefox.
- **#509**: `test_flow.py::reload_holding_back_app_js` reloads with `wait_until="commit"` and the
  tests act at once. Do NOT use `domcontentloaded`: app.js is `defer`, so DOMContentLoaded waits
  for the held-back script. Wait for `document.readyState !== "loading"` on the new document
  (make sure it is the new one, e.g. a marker set before reload is gone). Then 40 runs each in
  Firefox and WebKit (D-682).

## Local browser setup (Linux container)

- `export UV_PYTHON=/usr/bin/python3.12`
- Chromium: `SCI2AUDIO_CHROMIUM=/opt/pw-browsers/chromium PLAYWRIGHT_BROWSERS_PATH= uv run pytest -q -m browser --browser chromium -p no:cacheprovider <file> -k <name>`
- Firefox/WebKit: `PLAYWRIGHT_BROWSERS_PATH=<dir> uv run playwright install firefox webkit`, then
  `apt-get update && apt-get install` the libs Playwright names, plus `gstreamer1.0-plugins-base
  gstreamer1.0-plugins-good gstreamer1.0-plugins-bad gstreamer1.0-libav` (without them the WebKit
  page crashes). Run with `--browser firefox|webkit` and the same `PLAYWRIGHT_BROWSERS_PATH`.
- Nightly on a branch: `gh api -X POST repos/dubidu22/sci2audio/actions/workflows/nightly.yml/dispatches -f ref=<branch>`.
  Failures: `gh api repos/dubidu22/sci2audio/actions/jobs/<id>/logs | grep -E "^.{29}(FAILED|ERROR) tests"`.
  Compare job by job with main's nightly (D-731); a job re-runs only after the whole run ends.

## Update 17 Nov 12:30Z (thread "Finish the nightly-green PRs 2 and 3")

- **PR 2 = #511** (branch tests/nightly-keys-motion-pixels, from main 68f322d, head b1cb33a), closes #499 #500 #501. Linux CI green.
  Branch nightly 44079398176: all four browser jobs green (before, run 44065741504: Firefox 2, WebKit Ubuntu 0, WebKit macOS 3).
  - #499: **Ctrl+Left is Back too in WebKit macOS** (nightly 44073597837 named it), not only Cmd+Left. The test uses only
    right-arrow chords (Alt/Meta/Control+ArrowRight; no forward page) and checks the Listen URL after every chord.
  - #500 confirmed in Firefox: the only animation after `emulate_media(dark)` is a CSSTransition on `background-color` of
    `input#follow.switch`. `change_theme()` in test_listen.py awaits CSS transitions only; `all == 0` unchanged (D-709).
  - #501: `abs(bottom - height) < 0.5`.
- **PR 3 stopped by D-736 (Colin's token budget)**. Fix committed, NOT opened as a PR: branch **tests/nightly-reload-timing**
  8813e19 (from 68f322d). #506: expect the row's `.mk-note` text before `page.reload()` (also after Ctrl+Enter in the
  markers axe test). #509: `reload_holding_back_app_js` sets `window.beforeReload` before the reload and then
  `wait_for_function("!window.beforeReload && document.readyState !== 'loading'")`. 7 affected tests pass in all three
  browsers; the D-682 40-run loops were stopped at 4/40 in Firefox and WebKit (all passed). To finish: merge main, rerun
  40 × each, open the PR, branch nightly.
- **Untracked new failure** (no issue filed, D-736): `test_voice_cards.py::test_a_sample_stopped_while_it_is_made_never_plays[firefox]`,
  once in nightly 44071380866: `hold.reached.wait(30)` False (the sample's first sentence never reached the voice).
- Local note: one unexplained WebKit-Linux failure of `test_the_dock_never_hides_the_page` seen once locally, then 0/50.
