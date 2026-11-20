# Answer to the PR #409 round 1 review (Working Reader batch A)

The review was of 8982fcc. The new head is **6c367e1** on branch web/working-reader-a. Four commits fix all six findings, plus one test race found while running the suite.

| Commit | Answers |
|---|---|
| `web: one event stream per job on a page; the shelf asks elsewhere` | B2 |
| `tests: stricter no-internet and token checks, the wrong Origin, one-line run steps` | B1, S2, N1, N2 |
| `packaging: the wheel names OFL-1.1 for its fonts and carries both texts` | S1 |
| `tests: measure the finished job page at 320 px once it has reloaded and styled` | race found on the way (see the end) |

## B1. Protocol-relative addresses: fixed

In `tests/unit/test_web_design.py::outside_addresses`:
- For `.html`, `.css` and `.svg`, every `//` in the text is now reported, with its line number. No such file contains one today; CSS comments are `/* */`.
- For `.js`, any quoted string (`"`, `'` or `` ` ``) starting with `//` is reported. A comment points to the existing path rule in `test_web_pages.py::test_no_page_loads_anything_from_outside`, which checks the same thing for app.js and player.js.
- Other file kinds keep the old `PROTOCOL_RELATIVE` pattern.

`test_the_check_finds_one_added_line` is now parametrised by file and line. Each case first checks the real file is clean, then adds the line to it. There are ten cases, including the review's four, each in its own kind of file:
- `templates/base.html`: srcset
- `static/app.css`: `image-set()`
- `templates/base.html`: meta refresh
- `templates/_icons.html`: video poster
- `static/app.js`: `fetch("//192.168.1.9/x")`

I applied each of the four, plus the JS line, to the real file and ran `test_no_page_refers_to_an_address_outside_this_server`. Every one failed (1 failed each), and the files were restored afterwards.

## B2. One stream per job: fixed

**`follow()` in `static/app.js`.** A module-level `STREAMS` map keeps one `EventSource` per address.
- A second caller for the same address joins the existing stream and gets the latest progress at once.
- Each event goes to every part. The stream leaves the map when it ends or is lost.
- "Lost" is said once, if any part that joined is not quiet.

**`shelf()`.**
- If the page already follows the running job's address, the shelf joins that stream (quiet). That is the job page, or a document page whose analysis is running.
- Otherwise the shelf holds no stream. It asks `GET /api/v1/jobs/{id}` every `SHELF_EVERY = 2000` ms; the address comes from the new `data-job` attribute on `#shelf-job`.
- It never asks while `document.hidden` is true, and asks at once on `visibilitychange` back to visible.
- It never has two questions in flight.
- It shows the end word and stops once the job is no longer running, or after any error (it keeps its last words).

**New `tests/browser/test_streams.py`**, run on both heads:

| Test | 8982fcc | 6c367e1 |
|---|---|---|
| `test_a_page_holds_one_stream_per_job_and_the_shelf_none`: job page exactly `[events]`; /, /settings, /voice and /privacy `[]` (EventSource counted by an init script) | **fails** (two streams on the job page) | passes |
| `test_six_tabs_during_a_job_leave_the_interface_answering`: three job tabs and three library tabs open, then a `fetch('/api/v1/settings')` with a 2 s timeout must answer 200 | **fails** (a library tab could not even load: goto timed out after 30 s) | passes |
| `test_the_shelf_follows_the_job_by_asking_and_shows_its_end`: on /, `job.report()` moves the words to "downloading, 25 % done" and the `<progress>` to 25. While hidden: no question for 4.5 s and the words stay. Shown again: 75 % within 1.5 s. After the job ends: "done", value 100, and no more questions | **fails** | passes |
| `test_the_shelf_on_the_jobs_own_page_moves_with_its_stream`: the shelf on the job page moves to 50 % from the shared stream, and `#job-progress` moves too | passes (it covers the shared feed and was not meant to fail) | passes |

The four tests take about 20 s.

## S1. OFL-1.1 in the metadata and the rule: fixed

- `pyproject.toml` now has `license = "GPL-3.0-or-later AND OFL-1.1"`. `license-files` adds both `src/sci2audio/web/static/fonts/OFL-*.txt`. `uv lock --check` is clean.
- In `.claude/rules/licences.md`, point 2 adds "OFL-1.1 (fonts only, unmodified, licence text shipped beside them, D-670)".
- New test `test_package_data.py::test_the_wheel_names_the_font_licence_and_carries_its_texts`. It builds the wheel with hatchling into `tmp_path` (about 0.1 s) and checks three things:
  - METADATA `License-Expression: GPL-3.0-or-later AND OFL-1.1`
  - both files appear as `License-File`
  - both files sit under `.dist-info/licenses/`

## S2. Tokens set again after their blocks: fixed

`check_tokens` now asserts two more things:
- There is exactly one `^:root \{` block.
- After the light block and the two dark blocks are cut out, none of the 22 `LIGHT` token names is declared anywhere (`--<name>\s*:`).

New self-check `test_the_check_finds_a_token_set_again_after_its_blocks` has the review's two mutants (`:root { --cobalt: #000000; }` and `:root[data-theme="dark"] .rail { --cobalt: #000000; }`) plus `.rail { --paper: #000000; }`. I appended both review mutants to the real app.css and ran `test_the_tokens_are_the_designs_in_light_and_dark`: both failed, and the file was restored.

## N1. Wrong Origin: fixed

`test_the_appearance_route_is_guarded_and_its_cookies_grant_nothing` now covers a foreign Origin:
- `Origin: http://evil.example` gives 403.
- Neither refused answer carries a `set-cookie` header.

## N2. One-line run steps: fixed

`test_the_screens_workflow_runs_no_value_into_a_script` now also reads every `run: <command>` line that is not `|` or `>`. It asserts at least one is found (`- run: uv sync --locked`) and that none contains `${{`. Mutant check: with `&& echo ${{ github.event.pull_request.title }}` added to that step, the test fails.

## Found on the way: a reflow race in the test, not the page

The whole browser suite failed once in `test_reflow.py::test_no_page_scrolls_sideways_at_320_pixels`, at "audiobook done": 348 px, with links and SVG icons sticking out. A rerun on 8982fcc failed too (1 of 2), so this is not from these fixes.

The cause is that the job page drawn while the audiobook is made reloads itself at `#result` when the job ends. The check could measure the new page before app.css applied, when the icons have their default size. This is the same race `settled()` waits out for the document page (#166).

The test now waits for three things before measuring:
- `#job[data-state="done"]`
- the load event
- app.css applying (`.skip` has `position: absolute`)

What it measures is unchanged: it still measures the page a person sees, whose stylesheet blocks rendering. Three reruns passed.

## Checks run locally on 6c367e1

- ruff check, ruff format --check, lint-imports, deptry src and zizmor --offline: all clean.
- Fast suite: 5,941 passed, 1 skipped.
- Browser suite (Chromium): 86 passed, 2 skipped (the #365 quarantine and the screens test without its folder).

## Round 2 runs on 6c367e1: one fix, at ffd4a57

The reviewer's nightly dispatch failed `test_shell.py::test_the_bundled_fonts_load` in Firefox and WebKit. Both write the computed font-family without quotes (`Atkinson Hyperlegible, system-ui, sans-serif`). The fonts did load: all three `document.fonts.check` asserts before that line passed. The test now compares the first family's name without quotes. The fix is in the tests only; ffd4a57 is the new head.

These failures in the same run are not from this PR. The nightly of `release/1.1` (run 43770960312, built from main a9e0e2d) fails the same way:
- Firefox: `test_player_speed.py::test_the_speed_select_sets_the_rate_and_keeps_the_pitch` (page crashed).
- Firefox: the teardown error of `test_player_position.py::test_the_next_run_offers_to_continue_where_the_person_stopped` (`/position` requests to the previous test's server port, counted as outside).
- WebKit on macOS: `test_player_speed.py::test_the_speed_by_keyboard` (`'1' == '1.25'`) failed there.

The release thread's branch `release-fix/1.1.0-nightly` is working on these.
- Slow tests (ubuntu): `tests/integration/test_cli_end_to_end.py::test_convert_reads_an_epub_and_keeps_its_cover` (`assert 0 == 1`). This PR touches no CLI, EPUB or output code, and the release/1.1 nightly (job 132986546047) fails the same test the same way.

### The nightly on ffd4a57 (run 43776619822)

- WebKit (macOS): only `test_the_speed_by_keyboard`, as on release/1.1. The font test now passes in WebKit and Firefox.
- WebKit (Linux) failed three document-page tests:
  - `test_flow.py::test_make_starts_nothing_until_the_report_matches_and_has_a_chapter`: the message stayed empty.
  - `test_keyboard.py::test_the_main_flow_by_keyboard`: focus was on h2#step-check with no ring.
  - `test_player.py::test_a_skipped_code_block_shows_its_notice_and_its_code`: no job page within 15 s.

  All three passed in WebKit (Linux) on 6c367e1, and ffd4a57 changed only the font-name assertion in `test_shell.py`, so the code under test is the same. `test_make_starts_nothing…` also failed in WebKit on main's nightly of 14 Nov (run 43578799837, "Element is outside of the viewport"). I read this as WebKit timing around the document page's reload after an analysis, not this PR.

  I could not settle it locally. WebKit installed here crashes the page in the keyboard and code-block tests on main a9e0e2d too (`Navigation failed because page crashed`), while the flow test passes on both heads. A rerun of that one job would show whether it is flaky.
