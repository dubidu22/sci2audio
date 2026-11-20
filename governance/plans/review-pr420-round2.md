# Review PR #420, round 2 (final round, critical)

Head reviewed: **4235d74**. Round 1 was on 980911d (see review-pr420-round1.md). The fixes are in 85006d7 and 4235d74.

**Verdict: approvable.** Every round 1 finding is fixed, and each fix has a test that fails without it. Two small test gaps are left, filed as #430. The nightly failures are not from this PR's code; I checked each one. I filed the announce-test bug as #429 (v1.3). I have not merged.

## Round 1 fix list, rechecked

1. **B1, done.** `RecursionError` is now caught in seven places (opened and about share `_read_record`):
   - `library._read_record`
   - `output/readalong.from_json`
   - `api._report`
   - `pages._report`
   - `player.recorded_folder`
   - `player.read_audio_record`
   - `player._recorded_source`
   - plus `ReadAlongError` in `heard()`.

   `test_a_record_nested_too_deep_fails_no_page` covers 6 records × 2 shapes: `"[" * 16000`, and the closed nest of 500,000 levels. In each case the library, Settings, Privacy, the document page and Listen answer 200, the report API answers 200 or 404, and a deep `audio.json` shows "can't be read" on Listen. `test_cli_listen` covers the CLI source check.

   The `output/readalong.py` change adds one exception type to an existing catch. It is not a contract change.
2. **S1, done.**
   - `privacy.work` (English and German) names opened.json, about.json and position.json.
   - Point 7 of `test_what_the_privacy_page_says_is_what_the_code_does` pins:
     - the three names;
     - that the two writers write only into the document's work folder;
     - the call counts: `write_opened` twice (the document page, and Listen when the document is not from the command line), `write_about` once (after an analysis);
     - that both strings name the records.
3. **The four test gaps, done.**
   - (a) A read that raises `PermissionError` reads as nothing.
   - (b) `test_opening_an_outside_job_writes_nothing_into_its_folders`: Listen and the library leave a command-line job's folders byte-for-byte as they were.
   - (c) `NaN`, `±Infinity` and `±1e400` are never offered.
   - (d) A relative folder is skipped. `in_folder` accepts relative folders, so the check stays, and a test covers it.
4. **N1, done.** `player.Bounds` holds Listen's condition (`fits` plus first ≤ time < last), and `read_position` and `heard()` share it.
5. **PR body:** the mutant command and baseline are there.

## The coordinator's checks

**No parse of every read-along file on every page.** `audiobook_bounds` keeps a few numbers per file version in an `lru_cache(256)`, keyed by (inode, mtime, size), the same way `_stamp` is kept. A read-along file is parsed in two cases only:
- the first time it is seen, or after it changes;
- on every call while it is younger than 2 s (the racy-file guard, #403 B1).

`test_the_bounds_of_a_fresh_read_along_file_are_read_again` proves that guard: a same-size rewrite in place with the same mtime is read again, and the racy-guard mutant fails it. Past 256 audiobooks the cache would thrash, which is far beyond a personal library.

**Every catch fails without itself.** Mutants, in a clean worktree at 4235d74:
- Command: `python m420r2.py <worktree> "tests/unit/test_web_library.py test_web_player.py test_web_pages.py test_cli_listen.py test_web_outside.py test_output_parts.py test_web_languages.py"`
- Baseline: 282 passed, 1 skipped.
- Result: 15 mutants, 13 killed.

| Mutant | Result |
|---|---|
| Each of the 7 `RecursionError` removals | killed, each by its own case (`opened.json-open`, `readalong-closed`, `report.json-closed` ×2, `audiobook.json-closed`, `audio.json-closed`, `test_cli_listen`) |
| `ReadAlongError` dropped in `heard()` | killed |
| Racy guard off | killed |
| `first <= time` → `first < time` | killed |
| `fits()` dropped in `continues` | killed |
| `got.resume` dropped on the shelf | killed |
| `continues()` → `True` | killed |
| `time < last` → `time <= last` | **survived** |
| Bounds cache key → `(0, 0, 0)` | **survived** |

The two survivors are test gaps with no known bug, because Listen checks again. They are filed as **#430** (v1.3).

**The focus-only WebKit test is a legitimate narrowing.**
- The skip covers only `webkit` on `darwin`. Chromium, Firefox and WebKit on Linux still press ArrowRight and check `scrollLeft > 0`, and every browser still checks that the region is reachable and focused, and runs axe.
- It failed on 85006d7 (nightly 43794356141, `wait_for_function … scrollLeft > 0` timed out) and passes on 4235d74.
- It follows D-678 (the speed select): Playwright's WebKit on macOS does not route arrow keys to a focused box. The release checklist's VoiceOver pass now covers scrolling the table by keyboard at 320 px.

## Runs

- **Local, clean worktree at 4235d74:**
  - Fast suite: 6,150 passed, 2 skipped.
  - Browser suite (Chromium): 92 passed, 2 skipped (the #365 quarantine; screens without their label).
- **PR checks on 4235d74** (CI run 43796082694, with `ci:full`): tests passed on ubuntu, macos and windows, plus the browser job, lint, licences, security, ZAP, CodeQL and CI passed. Labels: risk:high, ci:full, ui:screens.
  - The earlier dispatch on 85006d7 (43794357375) failed on Windows only, in `test_app_chunks::test_the_default_folders_come_from_platformdirs`. That is the `file_id` race fixed on release/1.1 (#403 B1), which reaches main with R3, and it is not this PR's code.
- **`ui:screens` (run 43794349499 on 85006d7):** 4235d74 changes no template and no CSS, so these screens hold for the head. I compared the library at 1440 light, empty at 1280 dark, and with a job running at 1440 in German against DESIGN.md. They match:
  - the opener card with its dashed slot, the file button and "Or paste text";
  - `table.papers` with chips (icon and word);
  - "—" for listened, and "Today, 02:49";
  - the shelf with the running job's meter and the recent items;
  - the empty panel with the specimen in Literata;
  - dark mode and German correct.

  Nits, no change asked:
  - The browser draws its own file button text ("Choose File") in the browser's language, so a German page shows it in English when the browser is English. It can't be translated from CSS.
  - The right-aligned "Opened" header looks a little heavier than the others.
- **Nightly dispatch on 4235d74, run 43796097796:**
  - Chromium: green. Benchmarks: green.
  - **WebKit macOS:** only `test_player_speed::test_the_speed_by_keyboard` (`'1' == '1.25'`), which is known and being fixed on the release branch. The table test passes.
  - **Firefox:** `test_player_speed::test_the_speed_select_…` (page crashed) and an error in `test_player_position::test_the_next_run_offers_…` (outside request). Both are known and being fixed on the release branch.
  - **WebKit Ubuntu**, 3 failures, none in this PR's code:
    - `test_flow::test_a_german_book_keeps_the_remembered_english_voice` and `test_player::test_text_from_the_file_cannot_change_how_the_page_parses` both time out in `wait_for_url(/jobs/…-audio-N)` right after "Make the audiobook" is clicked. The page stays on `/documents/…#step-check`. That is the lost early click of **#427** (`#make` is wired only by the deferred app.js). `listen_to()` already waits for `settled()`, so it is not the #413 race.
    - **The german-book test has now failed twice in WebKit** (runs 43787351861 and 43796097796). Its cause is known (#427), so it is not flaky without a cause. Still, the nightly stays red until #427 is fixed. Either quarantine it now with `issue=427, browser="webkit"`, or fix #427 before batch C. That's the coordinator's call.
    - `test_settings::test_the_announce_switch_saves_itself`: `assert None is not None` on the announce cookie. **This is a real test bug from batch A** (e517873; #420 touches neither the test nor Settings). After Space, the test waits with `wait_for_url(live.url + "/settings")`, but the page is already on that URL, so the wait returns at once and the cookie read races the GET /appearance save. Filed as **#429** (milestone v1.3), with the fix and the mutant its test must kill.
  - Slow tests and property-based tests were still running when this was written. On 85006d7, the slow tests failed only `test_convert_reads_an_epub_and_keeps_its_cover` on all three systems (#410, known). 4235d74 changes nothing they run.

## Before the merge

- **#420 first, #421 after it.** Squash-merge #420 with `Closes #389`, pinned to 4235d74, (the branch commit messages name no fixes/closes/resolves, checked). The branch may need main merged in first (update-branch), with the diff checked to be main only.
- Then merge main into #421, retarget it to main, and merge it on green (see review-pr421-round2.md).

## Leftovers

- #429: the announce test race (batch A's test, v1.3).
- #430: the bounds cache key test and the last-sentence edge test (v1.3).
- #427: the lost Make click. It is open, and the quarantine is the coordinator's call.

## Addendum (nightly 43796097796 finished)

- Property-based tests (many examples): green.
- Slow tests on all three systems: only `test_cli_end_to_end::test_convert_reads_an_epub_and_keeps_its_cover` failed (#410, known). Nothing new.
