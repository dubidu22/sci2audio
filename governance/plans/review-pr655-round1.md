# Review of PR #655, round 1 (speed in 0.01 steps, #651)

Head reviewed: 524fb94 (base fac140c; main is fb48c1c, no shared files, mergeable). Not critical, lane web, Opus medium, one round.
Reviewer: review thread cmsg_011gr2YyZJypGaV6NbzgSXQEWAKQSmBVXuRxCgw16XnnCA, 19 Nov 2026.

## Verdict

Changes requested: two test additions (M1, M2). The code itself is correct; both items were run locally against 524fb94 and pass, so they only lock in behaviour Colin asked for. No code change is asked.

## What was checked

| Focus | Result |
|---|---|
| `PUT /api/v1/player/speed` validation | `PlayerSpeed` is `Strict` (extra keys refused), `strict=True` (bool and "1.5" refused), `ge=0.5 le=3.0`, `allow_inf_nan=False`. NaN, Infinity, -Infinity, 1e999 give 400/422 and no cookie. Token required (401 anonymous). Value written is `f"{v:.2f}"` from a float, so no header injection is possible. Cookie HttpOnly, SameSite=Strict, Path=/, Max-Age one year. Unit tests cover each of these. |
| Cookie read | `known_player_speed`: length ≤16, `float()`, finite, clamp 0.5–3.0, round 0.01; anything else gives 1.0. Hypothesis test proves range and round-trip. The page renders it through `f"{:.2f}"`, so a hostile cookie (`<b>`) cannot reach the HTML (tested). |
| ZAP script | One `call("PUT", .../player/speed, 200, ...)` in `_every_api_route`: a visit, not a suppression. No rule ids or alert filters changed. |
| Formatting round-trip | JS `parseSpeed` accepts comma or point, optional ×/x, rejects sign, exponent, two separators, spaces inside, Infinity (table test). `roundSpeed` = `Math.round(v*100)/100` then clamp: 1.07+0.01 = 1.08, 1.1+0.05 = 1.15 (tested). Display `toFixed(2)` with the language decimal sign; server `Strings.fixed` the same. German page shows 1,07 and reads 1.5 too (tested). |
| Keyboard and screen reader | Disclosure button with `aria-expanded`/`aria-controls` and a visible+hidden name ("Speed 1.00×"); panel `role=group` labelled; presets `aria-pressed`; field is an ARIA spinbutton with valuenow/min/max/valuetext and the hint as description; −/+ use `aria-disabled` at limits so focus stays. Keyboard opening puts focus in the field (`event.detail === 0`), Esc closes and returns focus to the button, Tab out closes, a click outside closes. axe light and dark with the panel open and with an invalid value: pass. Global −/+ shortcuts ignore the field (`typing()`), and Page keys in the field do not count as scrolling (preventDefault). |
| Pipeline and goldens untouched | 26 files changed, all in `src/sci2audio/web`, tests, `scripts/zap_scan.py` and CHANGELOG. `JobSettings` already accepted any finite speed in 0.5–2.0; no server rounding. No golden, regression case or core file touched. |
| Tests weakened? | The old dropdown assertions were moved to the new control. Two old checks were dropped: "− at the slowest stays" in `test_every_key_on_the_listen_page` (the limit is now covered by Home + ArrowDown and Slower at 0.50 in `test_the_speed_field_by_keyboard`, and `+` at the fastest still has its own test), so accepted. |
| CI on 524fb94 | CI passed, Chromium 1/2 and 2/2, ZAP, CodeQL, lint, licences, web paths green. WebKit 1/2 and 2/2 green (reported only). Firefox 2/2 (reported only) failed one test, `test_flow.py::test_freeing_the_speech_cache_asks_first`: the `<details id="free-box">` stayed closed after the summary click. That card is not touched by this PR and the same leg is green on main fb48c1c; treated as an unrelated one-off, re-checked on the fix head (a second failure there means the flaky-test rule applies, not a fix in this PR). |

## Must fix (one commit)

**M1. Prove a voice speed off the old 0.05 grid reaches the voice and the settings.** The plan promised "1.07 saved in settings"; today every saved voice speed in the tests (1.25, 0.85) is also a 0.05 value, so a change that rounded the voice speed back to 0.05 anywhere between field and job would pass.
- `tests/browser/test_flow.py::test_the_main_flow`: type `"1.07"` instead of `"1.25"` in the Exact speed field; expect the slider value `"1.07"` and both `aria-valuetext` `"1.07 times"`; assert `live.voice.spoken[-1] == (PREVIEW_TEXT, "bm_george", 1.07)` and `settings["speed"] == 1.07`.
- `tests/browser/test_settings.py::test_the_defaults_are_saved_and_every_other_setting_is_kept`: fill `"0.87"` instead of `"0.85"`, expect `aria-valuetext` `"0.87 times"`, assert `saved.speed == 0.87`.
(Run locally on 524fb94 with these values: pass.)

**M2. Test that Esc in Focus listening closes the speed panel only.** `player.js` calls `preventDefault()` on Esc inside the speed menu so Focus stays on, and the comment says so, but no test fails if that line goes (review lesson #510: a focus change needs a test that fails without it). Add to `tests/browser/test_focus.py` a test: make the audiobook, press `f`, focus `#speed`, press Enter (focus in `#speed-exact`), press Escape: `#speed-panel` hidden, `#speed` focused, `focusing(page)` still true; press Escape again: `focusing(page)` false. (This probe passed locally on 524fb94.)

## Not asked (no issue needed)

- N1: the cookie is written 500 ms after the last change, so leaving the page within half a second keeps the earlier speed. It only affects the speed offered next time and the debounce avoids a request per arrow press; accepted as designed.
- N2: `SCRIPT_KEYS` now exposes all `speed.*` strings to the page script although only `listen.speed_value` and `voice.speed_value` are used by it. Harmless (no secrets in the table).

## Re-check on fix head 7171448 (19 Nov 11:37Z)

One commit, tests only (3 files, +29 −9). M1 (a) and (b) and M2 are done exactly as listed; the new test is `test_focus.py::test_esc_in_focus_closes_the_speed_panel_first` (the author also killed the no-preventDefault mutant with it). CI on 7171448: CI passed, tests (ubuntu-latest), Chromium 1/2 and 2/2, ZAP, CodeQL, lint, licences, web paths green; Firefox 1/2 and 2/2 green (so the 524fb94 `test_freeing_the_speech_cache_asks_first` failure was a one-off, no second failure, no quarantine); WebKit 1/2 green, 2/2 reported-only still running.

**Approved.** Squash-merge pinned to 7171448 (MRG-03; main fb48c1c touches no file of this PR, so no branch update).

## Merged

28d65ed on main (squash, pinned to 7171448), #651 closed. Main CI on 28d65ed: CI passed, tests on ubuntu, macOS and Windows, Chromium 1/2 and 2/2, CodeQL, lint, licences, security, web paths all green.
