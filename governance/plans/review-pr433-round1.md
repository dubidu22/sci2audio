# Review PR #433, round 1 (critical: Prepare with the job inline, #391, plus #427 #429 #430 #422 #365)

Head reviewed: **f7521e8**, base main f063454. Plan: working-reader-batch-c-plan.md (D-694 rulings, D-695 deviation).

**Verdict: changes needed, all small.** There is no blocker. The safety mechanism (Cancel deletes the speech cache only after the job stopped) is correct, and its test fails without it. The leftovers are test gaps in #427's own scope and in the failed card, plus three wording and behaviour points to fix or file.

## What held

**Runs, in a clean worktree at f7521e8:**
- Fast suite: 6,317 passed, 2 skipped.
- Browser suite (Chromium): 103 passed, 1 skipped (screens without their label).

Both match the PR body. PR checks are all green, including the browser job and CI passed.

**Cancel (D-694 ruling 2), the safety mechanism:**
- Cancel is a `<details>` confirm. It says what goes (the speech cache) and what stays (the file, its analysis, any audiobook). It names the cache size, read again when the confirm opens.
- Its button:
  - POSTs the job's cancel;
  - polls `GET /api/v1/jobs/{id}` every 250 ms until the state is no longer `running`. The board sets the state only when the job thread's work has returned (`JobBoard._run` → `_end`), so the voice has stopped writing by then;
  - only then sends the DELETE.
- The server's `_not_in_use` 409 stays as a second guard. Its own test is `test_web_audio.py::test_cancelling_while_speaking_keeps_the_chunks`: a DELETE while speaking gets 409. Each of the two guards has a test that fails without it (#345 lesson).
- Browser mutants (command below), all killed by `test_cancel_deletes_the_speech_cache_only_once_the_voice_stopped`:
  - `await stopped(jobUrl)` removed;
  - `stopped()` returning at once;
  - the confirm drawn open.
- Pause sends only the cancel. The author's mutant (Pause sends the DELETE) is killed.

**AudioProgress (D-695):**
- The two fields are additive and defaulted, and no existing field changes meaning.
- `chapter_number` follows the first-chunk order of `plan.chunks`: the dict comprehension keeps insertion order, so the chosen order (#119) counts.
- Every chunk, including reused ones, sends a progress, so a resumed job's last progress is right.
- `test_progress_numbers_the_chapter_and_says_when_it_is_done` pins the values across a chapter boundary, with chapters chosen as (2, 0).

**#427:**
- Drawn disabled and enabled once wired: `#make`, `#choose-all`, `#choose-none`, `#update`, `#analyse`, `#preview-listen` and the move buttons.
- The hold test checks each button disabled, then enabled.
- On the card, Replace and Free the speech cache keep their hold test.

**No internet and the CSP:**
- No `style=`, no `//`, no URL, no new EventSource. The card uses the existing `follow()`.
- The segments are spans with classes, no inline style.
- No hard-coded colour.
- Batch A's checks pass over the new templates.

**#365:** the quarantine is lifted, and `settled(page)` comes before axe (the release/1.1 fix, ported).

**#429:**
- A `saving()` helper waits for the `/appearance` or `/language` response, at both announce toggles, the theme toggles and the German switches.
- The author reports that dropping the change handler fails the test. I did not rerun that.

**#430:**
- Both tests exist.
- The author reports that each kills its mutant (the cache key → `(0, 0, 0)`, and `< last` → `<= last`). I did not rerun them.

**#422:**
- The walk's uploads are now fixed bytes: `steady()` replaces PDFium's random `/ID` with one made from the content, of the same length.
- The unit test checks two calls give the same bytes and that PDFium still reads them.
- I checked the two SHA-256 values today: neither holds a run of 16 digits, so the Luhn false positive cannot come from them.

**The author's mutation claims (D-676):**
- Rerun in my own clean worktree at f7521e8 with the PR body's command: `pytest tests/unit/test_web_prepare.py tests/unit/test_app_audio_job.py tests/unit/test_web_audio.py -q -p no:randomly -x`.
- Baseline: 52 passed.
- All 8 unit mutants named in the body are killed: pages.py `>=`→`>`, `number + 1`→`number`, both `if not cache`, `number > 1`→`>= 1`, `n=number - 1`→`n=number`, and audio.py `+ 1` and `== index`. The claim holds.

## My own mutants

| Mutant | Result |
|---|---|
| Unit: `phase in ("encoding","done")` → `("done",)` | killed |
| Unit: the paused title without the chapter | killed |
| Unit: the kept sentences dropped | killed |
| Unit: `n < current` → `<=` in `_segments` | killed |
| Unit: `/jobs/{id}` for an audio job renders `job.html` | killed |
| Unit: `phase != "speaking"` dropped in `_stopped_in` | survived. Equivalent: the fields are 0 outside the speaking phase. |
| Unit: `exists` → False | survived in unit tests, but `test_replace_waits_until_the_page_script_runs` covers "The audiobook files exist already." in the browser |
| **Unit: `elif where == "writing": kept_all` → never** | **survived (S2)** |
| **Unit: running card while writing: `current` → 0** | **survived (S2)** |
| Browser: no wait / `stopped()` returns at once / confirm drawn open | killed |
| **Browser: `#job-pause` drawn enabled** | **survived (S1)** |
| **Browser: `#job-cancel` drawn enabled** | **survived (S1)** |
| **Browser: `#job-again` drawn enabled** | **survived (S1)** |

Commands:
- Unit: `python m433.py <clean worktree at f7521e8> "tests/unit/test_web_prepare.py tests/unit/test_app_audio_job.py tests/unit/test_web_audio.py"`. Baseline: 52 passed.
- Browser: `python b433.py <worktree> "tests/browser/test_flow.py tests/browser/test_prepare.py" "pause or cancel or resume or wait or axe_on_prepare"` (Chromium). Baseline: 7 passed.

## Findings

**S1. #427's own scope is not complete.**
- **The card's buttons.** Pause, "Cancel and delete the speech cache" and "Make it again" / Resume are drawn disabled, but no hold test covers them. Drawing any of them enabled passes every test (three survivors).
- **The removal button.** `.remove-now` (#421's disclosure) is still drawn enabled on the document page and in the library rows, and only `removal()` in app.js wires it. #427 asks for every server-drawn `type="button"` on the document page that only app.js wires. An early press does nothing; it deletes nothing, but the click is lost silently.

**S2. Two card states are untested.**
- **A job that failed while writing the files** (phase `encoding`, cache present). The kept line must read "Every chapter is spoken and kept. Making it again only writes the files." With that branch removed, it falls through to "Nothing is spoken yet." and no test notices. That is the wrong promise in the direction that matters, because it tells the person nothing is kept when everything is.
- **The running card while writing the files.** Every segment should be done. With `current` → 0, all segments show as to come, and no test notices.

**N1. A Pause before the first sentence reads "Cancelled. The speech cache is empty."** A cancelled job with an empty cache always gets the Cancel title. A first run paused while the voice loads also has an empty cache, so the person who pressed Pause is told they cancelled. When `_stopped_in` gives "before", say "Paused. Nothing is spoken yet." (or similar); keep "Cancelled…" for a freed cache after speaking began. Fix it, or file an issue.

**N2. "Make it again" and Resume use the old run's settings while Prepare shows the current ones.** The card restarts with `data-settings` from the job. The steps below it may now show another voice, speed or chapter choice, if the person changed them after the failure or pause. Two buttons on one page then start different audiobooks, and only Make uses what is shown. Either have the card say that it continues with that run's settings, or make it use the page's current controls. The second changes what Resume means for the cache, so it needs a decision. Fix the wording, or file an issue.

**N3. `stopped()` has no upper bound.** If the job never leaves `running` (a voice stuck in native code ignoring cancel), the page polls every 250 ms forever and says "Stopping the voice…". Stop after about two minutes, say that the voice did not stop and nothing was deleted, and give the button back. Fix it, or file an issue.

Notes, no change asked:
- `zap_scan.uploads()` prepends to `sys.path` on every call, so the same entry is added again each time. It is harmless in a script.
- `/jobs/{id}` (Prepare with the card) does not write `opened.json`, unlike the document page. A person who only follows Make's redirect still updates it through the document page they came from.

## Fix list

1. **S1:**
   - Extend `test_the_document_pages_buttons_wait_for_the_script`, or add a card hold test with the voice held, so that `#job-pause` and `#job-cancel` (with the confirm open) are disabled while app.js is held and enabled after.
   - The same for `#job-again`, on a paused or failed card.
   - Draw `.remove-now` disabled, enable it in `removal()` as it is wired, and add it to the hold test, on the document page and on a library row.
   - Each test must fail with its button drawn enabled.
2. **S2:** unit tests for:
   - (a) a failed job whose last progress is the encoding phase, with a cache: the title "…stopped while writing the files", the kept line "Every chapter is spoken and kept…", and every segment done;
   - (b) a running job in the encoding phase: every segment done.

   Each must kill its mutant above.
3. **N1, N2, N3:** fix each, or file one issue each (milestone v1.3) and name them in the PR body.
4. **PR body:** add the new mutant results with their command and baseline.

## Final round

Critical, so the final round runs:
- `ui:screens`: I compare prepare, making, paused, failed and done against `prepare.png`, `making.png` and `failed.png`;
- `ci:full` on three systems;
- a nightly dispatch on the head.

Known nightly failures, not this PR's: the Firefox and WebKit-mac speed and position tests, and #410.
