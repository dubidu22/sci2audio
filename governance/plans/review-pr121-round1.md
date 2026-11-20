# Review of PR #121 (issue #77 browser main flow, closes #8), round 1

Reviewed head `5ab8246` (base `b82eb66`), 13 Nov 2026, against the approved plan `plans/issue77-main-flow-plan.md` and D-244 to D-261.

## What I ran (all on the PR head, Linux)

- `ruff check`, `ruff format --check`, `lint-imports` (3 contracts kept, D-205 web-only framework import kept), `deptry src`: all clean.
- Fast suite `-m "not slow and not benchmark and not browser"`: **1761 passed** (159 s).
- Nightly Hypothesis profile on `tests/unit/test_web_*.py`: **184 passed**.
- `pytest -m browser` with Chromium 1243: **13 passed, twice in a row** (about 34 s each).
- CI on the head: all checks green on Linux, macOS and Windows, including the new required job "browser (Linux, Chromium)" and CodeQL (Python and Actions).
- Test merge of `main` (a0d363a, PRs #98 and #108 since the base): merges cleanly.
- Lock diff: the only new packages are axe-playwright-python 0.1.8, playwright 1.65.1, greenlet 3.5.6, pytest-playwright 0.10.0, python-slugify 9.1.3, text-unidecode 1.3. Each has a row in `THIRD_PARTY_LICENSES.md` (test-only section). pyee and pytest-base-url are not in the lock, so they need no row.
- Probes with throwaway tests (deleted again): preview speed `NaN`, `Infinity` and `1e999` get 422; text of 300 characters plus white space gets 422; `/documents/{id}/files/` serves only the three analysis files (`source.pdf` and `..%2Fsource.pdf` get 404), with `nosniff` and the CSP on every answer and `text/markdown` / `text/plain` / `application/json` types; saved settings with every category on (`switched_off: []`) reach the next document's analysis and its `data-shown`; an audio job with `chapters: []` fails with "there is nothing to read in the chosen chapters"; the job page when the server goes away (see M2).

## Plan and decisions, point by point

| Decision | Verdict |
|---|---|
| D-244 page structure (home, document with 3 numbered steps, job, voice) | kept |
| D-245 analysis on open; Make uses exactly the report on screen; "Update the analysis first" while controls differ | kept (the Make start sends `shown.switched_off` and `shown.chapters` from the report). There is no browser test that pressing Make while the controls differ starts nothing (see S4) |
| D-246 switches, voice, speed, folder saved on start; chapters stay with the document | kept (see N8) |
| D-247 printed chapter order; order to #119 | kept |
| D-248 every change, 500 per category, then `report.md` | kept, unit-tested |
| D-249 preview job kind, #18 sentence, 300 characters, `<audio controls>`, `<work_root>/preview/` | kept |
| D-250 one engine kept; dropped after a failure; disposed at stop | kept (see N6, N7) |
| D-251 slider 0.5 to 2.0, step 0.05, `aria-valuetext` | kept |
| D-252 full plan table, hosts with redirects, consent checkbox, digest | kept; server still needs `consent: true` (StrictBool) and the digest |
| D-253 announcements at most every 30 s and on a phase change | kept, tested under Playwright's clock |
| D-254 Replace is its own button, no `confirm()` | kept; `overwrite: true` is sent only by that button |
| D-255 preview route, document files route, `download` flag | kept |
| D-256 one TOML table, `t()`, JSON data block, API messages in English | kept (see S3, N1, N2) |
| D-257 WCAG 2.2 AA; axe fails any A/AA plus serious/critical best practice; every state, light and dark | rule kept; two states not checked (S2); one live-region problem axe can't see (S1) |
| D-258 dev dependencies and licence rows | kept |
| D-259 marker, `tests/browser/`, required Linux Chromium job, nightly 3 engines plus WebKit on macOS | kept |
| D-260 remove a document is #120 | kept |
| D-261 paste box only once a text extractor exists | kept (`paste = ".txt" in supported_suffixes()`) |

Security (as in the #107 review): server still binds to 127.0.0.1 only; the cookie, Host, Origin and Sec-Fetch-Site checks are unchanged and cover the new routes (the routes sit under the same router); CSP `script-src 'self'` holds, because the strings block is `type="application/json"` and a test makes sure `</` can't end it; no inline script, style or handler (tested); the browser tests abort and fail on any request outside the server; the file routes can't leave the analysis folder or the job's file list; nothing is overwritten without the Replace button; consent comes before any download.

## Must-fix

- **M1 Merge `main` into the branch.** The PR is behind `main` (PRs #108 and #98 landed since its base), and the ruleset refuses to merge a PR that is behind. It merges cleanly. Run the fast suite and `pytest -m browser` again on the merged head, because #98 changes the text steps that the report on the page shows.
- **M2 The job page says nothing when the server goes away.** The plan (section 6) promised "a lost server shows 'can't reach sci2audio'". `follow()` only says so when `EventSource.readyState === CLOSED`. When the stream drops on a network error, the browser keeps reconnecting and stays in `CONNECTING`, so that branch never runs. Probe: a job page with a running job, then every `/api/**` request aborted (`connectionrefused`) and the stream ended (`state.stopping`); after 8 s `#message` was still empty and the page went on showing the last progress. The job page is where a person waits for minutes. Fix: when an `error` arrives before `end`, treat a stream that has not reopened within a few seconds as lost: say `js.lost`, move the focus to the message, and close the EventSource. Add a browser test for the job page and one for the document page while it analyses (that page also follows a stream).

## Should-fix

- **S1 The status message is `display: none` until it has text** (`.message:empty { display: none; }` in `app.css`). The `role="status"` region on the start, document and voice pages is then outside the accessibility tree when its first text arrives, and NVDA and JAWS often don't announce a live region that only just appeared. Messages that are not also focused ("Opening…", "Listening…", "Starting…", "The preview is ready") can go unspoken. Keep the region in the tree, for example by collapsing its padding and background while it is empty, as `#job-status` already does with `visually-hidden`.
- **S2 Two page states have no axe check, although D-257 says every state:** the document page while it analyses (`analysing`: no report, the message, no Analyse button), and a job page that failed with a real error (not `output-exists`, for example a `job-failed` audio job, which also shows "Start again"). Add both, in light and dark.
- **S3 The strings test lists job kinds and states by hand** (`used_keys`: `("running", "done", "failed", "cancelled")` and `("script", "audio", "voices", "preview")`). Build them from `JobState` and `JobKind`, so that a new kind without a `job.title_*` key fails the test. As it stands, it would be a 500 on the page (`t()` raises `KeyError`).
- **S4 Make is enabled when the report has no chapter chosen** ("Choose none", then Update). The job starts and then fails with "there is nothing to read in the chosen chapters". Block it like the other cases, with a `make.needs_chapters` note ("Choose at least one chapter and update the analysis"). In the same browser test, check D-245 itself: after a change to a switch, pressing Make starts no job (the board stays empty) and moves the focus to the note.

## Nits

- **N1** Voice names show language codes: "Heart, en-US, female". A table entry per accent (`accent.en-US = "American English"`, `accent.en-GB = "British English"`) reads better and is ready for #79.
- **N2** `app.js` preview end: `say(ended.error ? ended.error.message : ended.state, true)` shows the raw state id ("cancelled"). Use `job.state_*` from the table (add those keys to `SCRIPT_KEYS`).
- **N3** `<output for="speed">` has the implicit role `status`, so a screen reader may say each value twice, once from the output and once from `aria-valuetext`. Consider `aria-hidden="true"` on the output, since the slider already says its value.
- **N4** The plan (section 1) listed the size of each document on the start page; the list has name, analysed and audiobook only.
- **N5** Every preview writes to the same `preview/preview.wav`, so the file link of an earlier preview job plays the newest preview. That is harmless in the page flow. Either say so in the `preview_work` docstring, or make the route return 404 for a preview job that is not the latest.
- **N6** `audio_work` drops the kept engine on any failure, including app errors that have nothing to do with the voice ("nothing to read in the chosen chapters", an unreadable document). The next preview then loads the model again. That is allowed by D-250 as written; dropping it only on `EngineError` or an unexpected exception would keep it loaded. Your choice; if you keep it, a one-line comment helps.
- **N7** `serve()` disposes the engine after `board.shutdown(5)` even if a preview (not cancellable) is still speaking. The process is exiting, so this is cosmetic, but `dispose` could wait for the job (`job.join`) or skip disposing while one runs.
- **N8** `app.js` saves the settings (`PUT /settings`) before `POST /jobs`, so a start refused as busy still changes the remembered settings. D-246 says they are saved "when the person starts an audiobook". Either order them the other way round, or accept this and say so in a comment.
- **N9** `Closes #8`: #8's first criterion also names "play, read-along highlight", which #78 tests (its own criterion "Playwright test of the highlight and the jump"). This is fine; I will note it on #8 when it closes.
- **N10** `test_flow.py`: `assert names[0] == "Introduction.m4b" or names[0].endswith(".m4b")`. The first half adds nothing. Assert the exact name, which is known from the paper's title.

## Verdict

The PR is well built and matches the plan and D-244 to D-261 closely. It is not ready to merge yet: M1 and M2 must be fixed. Please answer each item as fixed (and how), deferred (with an issue link) or declined (with the reason), never "most".
