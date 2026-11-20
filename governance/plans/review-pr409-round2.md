# Review PR #409, round 2 (final round, critical)

Head reviewed: **ffd4a57** (6c367e1 plus one test assertion). Round 1: 8982fcc, see review-pr409-round1.md. Author's answer: answer-pr409-round1.md.

**Verdict: approvable.** All six round 1 findings are fixed, and each fix kills its mutants. Three-system CI is green on ffd4a57. The screenshots match the design for what batch A changes. The nightly failures on ffd4a57 are either already on release/1.1 or were a WebKit flake that passed on rerun; that flake is filed as #411, with one test due for quarantine. I have not merged.

## Round 1 findings, rechecked on 6c367e1 in a clean worktree

Baseline before the mutants: the four test files passed (69 tests).

| Finding | Check | Result |
|---|---|---|
| B1 no-internet gaps | `test_no_page_refers_to_an_address_outside_this_server` with each mutant applied to the real file: `srcset="//192.168.1.9/…"` (base.html), `image-set("//192.168.1.9/…")` (app.css), meta refresh `url=//192.168.1.9/` (base.html), `<video poster="//192.168.1.9/…">` (settings.html), `` fetch(`//192.168.1.9/x`) `` (app.js), `new EventSource('//10.0.0.1/e')` (player.js) | every mutant fails the test |
| B2 one stream per job | The author's `tests/browser/test_streams.py` run against 8982fcc's src | 3 of 4 fail for the right reasons: two streams on the job page; a library tab could not load with 6 tabs open; the shelf did not ask. The fourth is a shared-feed check, not meant to fail. |
| B2, JS mutants (6c367e1) | No join in `follow()` | 2 tests fail |
| | The shelf always follows the stream | 3 tests fail |
| | No stop when the job ends | 1 test fails |
| | All three `document.hidden` guards removed together | the asking test fails |
| | Only the guard inside `ask()` removed | passes: the `visibilitychange` handler clears the timer, so that guard is defence in depth, not a gap |
| S1 OFL-1.1 | `license` back to GPL only; one OFL file dropped from `license-files` | each fails `test_the_wheel_names_the_font_licence_and_carries_its_texts`. `.claude/rules/licences.md` lists OFL-1.1 (fonts only, D-670). |
| S2 tokens set again | `:root { --cobalt: #000000; }`, `:root[data-theme="dark"] .rail { --cobalt: … }` and `main{--hl-read:#000}` appended | each fails `test_the_tokens_are_the_designs_in_light_and_dark` |
| N1 Origin | Origin check in `security.py` disabled | `test_the_appearance_route_is_guarded_…` fails |
| N2 one-line run | `&& echo ${{ github.event.pull_request.title }}` added to `- run: uv sync --locked` | the workflow test fails |

The B2 code reads correctly:
- `STREAMS` keeps one EventSource per address, and a later caller gets the last progress at once.
- "Lost" is said only if a part that is not quiet joined.
- The shelf's poll never has two questions in flight. It pauses while the tab is hidden, asks again when the tab is shown, and stops at the job's end or at an error, keeping its last words.
- The shelf joins only when the page already follows that job. Pages call `follow()` synchronously before `shelf()` in DOMContentLoaded, and `board.current` is the running job only.

The reflow-test change (wait for `#job[data-state="done"]`, the load event and app.css before measuring at 320 px) measures the same page and removes a race. ffd4a57 changes only the font-family check, so it accepts the name without quotes, as Firefox and WebKit write it.

## Runs

- **Local on 6c367e1:** the fast suite had 5,941 passed and 1 skipped. The browser suite (Chromium) had 86 passed and 2 skipped (#365 quarantine; screens without their folder).
- **`ci:full` dispatch on ffd4a57, run 43776617487:** tests passed on ubuntu, macos and windows. Lint, security, licences, the browser job and CI passed are all green. The PR checks on ffd4a57 (CodeQL, ZAP) are green, and mergeable_state is clean.
- **`ui:screens` (run 43775950174 on 6c367e1; the UI is unchanged since):** 78 PNGs. Shell and Settings compared with `prototype/app/screens/settings.png` and `library.png`:
  - The rail matches: width, wordmark, the current-page tab, Settings and Privacy at the foot, "Reading and recent" with the running job and its meter. Captures and Keyboard shortcuts are absent (D-670).
  - The Settings panels, segmented controls and switch match. Dark mode and German render correctly.
  - The deviations are the decided ones. Speed uses the same range control as the document page, labelled "Speed of the voice" (the synthesis speed). The sounds switch waits for #397. The v1 pages keep their own layout until batches B to D.
- **Nightly dispatch on ffd4a57, run 43776619822:**
  - Chromium: green. Property-based tests and benchmarks: green.
  - **WebKit on Linux, attempt 1:** 3 failures, all racing the reload after an analysis (`test_flow::test_make_starts_nothing_…`, `test_keyboard::test_the_main_flow_by_keyboard`, `test_player::test_a_skipped_code_block_…`). **Rerun (attempt 2): 86 passed.** WebKit had also passed these tests on 6c367e1. Filed as **#411**. `test_make_starts_nothing_…` has now failed twice without a code cause in WebKit (main 3b9ac6d, 14 Nov, run 43578799837; and here), so **the flaky-test rule asks for its quarantine today**, linked to #411.
  - **Pre-existing, not from this PR:** the same failures show on release/1.1 08d5965 (run 43770960312, main a9e0e2d plus #403):
    - Firefox: `test_player_position::test_the_next_run_offers_…` (outside request to `/position`) and `test_player_speed::test_the_speed_select_…` (page crashed).
    - WebKit on macOS: `test_player_speed::test_the_speed_by_keyboard` (`'1' == '1.25'`).
    - Slow tests on all three systems: `test_cli_end_to_end::test_convert_reads_an_epub_and_keeps_its_cover`.

    Per the coordinator, these are being fixed on release-fix/1.1.0-nightly.
  - The font test fails on Firefox and WebKit only on 6c367e1; ffd4a57 fixed it, and the test passed there in Firefox, WebKit Linux (rerun) and WebKit macOS.

## Before the merge

- Squash-merge with the PR body's `Closes #385 #386 #387 #388`. No branch commit message names fixes, closes or resolves for any issue (checked).
- #14 can be closed as replaced by #386, by hand.
- After the merge: KB entry (D-670 to D-673 already drafted), tell the other lanes to merge main, and quarantine `test_make_starts_nothing_…` in WebKit with #411. Which thread does the quarantine is the coordinator's call. A one-line marker on main is enough.

## Leftovers

#411 (WebKit reload race, three tests; quarantine one now). Nothing else is deferred.
