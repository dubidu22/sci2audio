# PR #719 review, round 1 (head c12427b)

Reviewer: review-web-b-w2, Opus. 21 Nov 2026. PR: "web: the speed panel keeps its clicks in WebKit and the browser tests wait for a page at rest (#699)", closes #697, #699, #714; `lane:web`, `testing`, `risk:low`. Plan: plans/web-tests-b-t1-plan.md, approved as D-862.
Head: the brief named dd21cd1; the author lifted the Firefox quarantine in c12427b before the round began, so c12427b is the round-1 head (coordinator's word). `git diff dd21cd1 c12427b` is only the removal of the five-line `@pytest.mark.quarantined(issue=697, …)` marker in `tests/browser/test_flow.py`; `pytest -m quarantined --collect-only` now collects nothing.
Critical: **no** (one interface behaviour change in `player.js` and test changes; no golden, contract, workflow, safety mechanism, file writing or network; D-862 sets risk:low).
Verdict: **approved** (0 must-fix, 0 should-fix, 5 notes).

## Checked and fine

- **(1) Scope.** 6 files against base b00002d: `web/static/player.js` (+12/-2), `tests/browser/conftest.py`, `test_flow.py`, `test_player.py`, `test_player_speed.py`, `test_updates.py`. No other page, template or Python source file.
  - `player.js:422-443`: `pressedInside` set on `pointerdown` (target inside the menu), cleared on `pointerup`; `focusout` returns early while it is set; the Esc handler moved from the menu to `document`. It is registered before the Focus-listening `keydown` handler (`player.js:920`), and its `preventDefault` makes that one return (`defaultPrevented`), so the first Esc in Focus still closes only the panel; `test_focus.py::test_esc_in_focus_closes_the_speed_panel_first` pins that and passes.
  - `conftest.py`: session `browser_context_args` adds `locale="en-US"` in WebKit only. That differs from D-862's wording ("pins locale en-US"), and the PR body gives the reason (in Chromium a `locale` outranks a test's `Accept-Language` header; a context-wide header broke audio there); accepted (N2).
  - `signed_in`: a context init script sets `volume = 0` on every `HTMLMediaElement` at `loadstart` (capture listener on `document`).
  - `listen_to`: `at_rest` before "Make the audiobook" and before "Listen with the text"; `test_updates.py`: `at_rest` before `uncheck`; the new guard test `test_a_second_step_while_the_file_loads_stays_on_its_sentence`; #697: `at_rest` before Replace, `expect_request(…/api/v1/jobs$)` around the click with `overwrite` asserted true, `wait_for_url` for an address other than the refused run's.
- **(2) The conditional assertion.** `test_player_speed.py:42-43`: "the click leaves the focus on the button" only where `click_focuses(page)`. The reason (#498: Safari gives a clicked button no focus, as `test_focus.py` already follows) is in the PR body. Every other assertion of the test is unconditional, and the panel's own checks (expanded, visible, presets, `aria-pressed`) still run in every browser.
- **(3) Promised tests.** All 13 node IDs of the PR body exist (12 unchanged names plus the new guard test).
- **(4) Volume 0.** The page code never reads or sets `volume` and creates no detached `Audio()` (every media element is in the templates, so the capture listener reaches it), and `volume = 0` neither stops playback nor changes the autoplay rules (unlike `muted`). The tests assert on `currentTime`, rate and the highlight, never on audibility, so a real playback failure (time not advancing, wrong rate, no highlight) still fails them. The script runs in all three browsers: it is plain DOM, and every CI shard on dd21cd1 and c12427b passes with it, the playback-heavy WebKit and Firefox shards included.
- **(5) Local run** (fresh worktree /tmp/review-719, macOS): ruff, ruff format (388 files), lint-imports (3 kept, 0 broken), deptry green; fast suite `-k "not espeak"`: 8669 passed, 6 skipped, 6 xfailed, 0 failed; `pytest -m browser --browser chromium`: 199 passed, 5 skipped, 0 failed.
  - **WebKit, the seven #714 tests:** with the PR's `player.js` 5 passed, 2 failed (`test_at_2x_the_highlight_stays_with_the_voice`, `test_listen.py::test_the_sentence_being_read_is_marked_plainly…`); with main's `player.js` 1 passed, 6 failed. The two left fail on a playback wait (highlight empty, `wait_for_function` timeout). This Mac's WebKit does not advance playback right now: the untouched `test_player.py::test_the_highlight_follows_the_voice_into_the_next_chapter[webkit]` fails the same way with main's `conftest.py` too, as the PR body reports. So locally the fix turns the five panel tests that do not need playback from red to green, and CI's Linux WebKit shards (green) are the evidence for the other two.
- **(6) Issues.** #714 states the two Safari focus causes and the criteria the fix meets; #720 holds the markers failure (cause not found, guard test named, quarantine on a second failure); #697's comments give the cause (no request after the click, `hold.calls == 0`), the fix, the local counts and `isolate.yml` 44843888954 on 999a78c with 40 of 40 Firefox, all as the PR body says. The isolation rerun on dd21cd1 (44852282922) has finished with success; the coordinator checks its counts.
- **CI on c12427b (Linux)**: `CI passed`, governance pr checks, `tests (ubuntu-latest)`, lint and layers, licences, security, both Chromium shards, and all four report-only Firefox and WebKit shards green.

## Notes

- **N1.** The #697 wait matches the URL only (`re.compile(r"/api/v1/jobs$")`); the plan and the body say POST. `GET /api/v1/jobs` exists (`web/api.py:873`); the page does not call it today, but if it ever did around that click the test would fail on `post_data_json["overwrite"]` with a `TypeError` instead of its clear message. `lambda r: r.method == "POST" and r.url.endswith("/api/v1/jobs")` says what is meant. Optional.
- **N2.** The locale is pinned in WebKit only, not for all browsers as D-862 words it; the PR body's reason holds; recorded so the decision log can say WebKit.
- **N3.** The Esc ordering (panel first, then Focus) rests on the two `document` listeners' registration order in `readAlong()`; `test_esc_in_focus_closes_the_speed_panel_first` guards it, so a reorder fails a test.
- **N4.** The new comments in `player.js` cite "#699"; the speed-panel cause is filed as #714. Optional when the file is touched next.
- **N5.** `test_updates.py`'s `at_rest` is, as the PR says, the probable and not the proven cause; if that test fails again in WebKit without a code cause, D-374 applies.

## Handoff (THR-07)

- Goal: PR #719 (B-T1) merged.
- Done: round 1 at c12427b, approved.
- Next: on the coordinator's go (after checking isolate run 44852282922 on dd21cd1), gate, squash-merge pinned to the reviewed head.
