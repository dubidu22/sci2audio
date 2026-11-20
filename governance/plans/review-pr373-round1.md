# Review PR #373, round 1 (v1.1 player wins, PR A: #152 speed, #153 position, #190 publisher pages)

Head reviewed: a604e77 (main 342a8f5 merged in). Plan: plans/v11-player-wins-plan.md (D-642, PR A). Non-critical, lane:app.

**Verdict: not approvable yet. No blocker, one should-fix (S1), one nit (N1). The deviation is accepted, with a follow-up issue (#376).**

## What I checked

- **Change against the plan and each issue's acceptance criteria.** Commit messages carry no closing keywords. The PR body closes #152, #153 and #190.
- **Fast suite:** 5589 passed, 1 skipped.
- **Browser suite (Chromium):** 64 passed, 1 skipped. The skip is the quarantined #365 test. These include the new speed and position tests, keyboard, axe light and dark, and the reflow test.
- **#152.** A native `<select>` with a visible label. Both `defaultPlaybackRate` and `playbackRate` are set, and set again on `loadedmetadata`, with `preservesPitch` and its prefixed forms. The strings are in en and de.
- **#153.**
  - The record is `<work>/position.json`, with a format name and version. It is stamped with the read-along file's SHA-256 and written atomically.
  - On reading, a record is ignored when it is a link, a non-file, over 4 KB, bad JSON, NaN or Infinity, has wrong types or a bool, or has the wrong document, stamp, chapter or time. A time before the first sentence ends, or after the last one ends, is not offered.
  - The POST runs under the normal token and origin checks, with a bounded model. It answers 404 when there is no audiobook, 422 for a place the book does not have, and 503 when the write fails.
  - The offer moves the position but never plays.
  - A web audio job removes the record.
- **#190.** `sci2audio script` on the Time Machine: Imprint, Colophon and Uncopyright are shown as `[ ] … not read (publisher's page)`. The title page, I–XII, Epilogue and Endnotes are selected. PDFs and Markdown are unchanged, and no golden file changes.

## The deviation: no "publisher's page" hint in the web chapter list

Accepted. #190's acceptance criteria do not ask for a hint. The web list is drawn from the report JSON (sci2audio-report v1), and a new per-chapter key would change the report goldens, which would make this PR critical (D-69). The report Markdown and the CLI say why. Without a hint, though, the web shows an unticked box with no reason, which is weaker than the reference-list hint, also for a screen-reader user. I filed **#376** (v1.1, lane:app): a `publisher` flag in the report JSON, the hint in the list, and a browser test. It fits PR B (#154, #119), which is critical anyway and already changes the chapter list.

## Fix list

### Should-fix

**S1. A listen page left open over a rerun of the audio job saves its old position into the new audiobook.**

The POST carries only `{chapter, time}`. The server stamps the record with the read-along file it finds at that moment (`located.stamp`), not with the one the page was drawn for.

Sequence:
1. A person listens.
2. They start "Make the audiobook" again in another tab.
3. The job finishes and removes `position.json`.
4. The old page then saves, on pause, on its 5 s tick or on `pagehide`. `fits` checks the time against the new book, which usually has the same chapters, so the save is written with the new book's stamp.

The next visit then offers "Continue from …" in an audiobook the person never heard. That breaks the criterion "A new audiobook for the same document drops the saved position" whenever the old page stays open.

Fix:
- Put the stamp the page was drawn with into the page data (`player-data`).
- Send it with each POST.
- Refuse a save whose stamp differs from the current read-along file's: 409 with a JSON reason, and write nothing. The player ignores the failure, as it already does.

Test (TestClient): write position, rerun or replace the read-along file, POST with the old stamp → 409, and no record. Also POST with the current stamp → 204.

### Nits

**N1. The two offer buttons do nothing when clicked before `player.js` has run.** They are drawn by the server and wired by the deferred script (the #350 lesson). The Play button already works this way on main, so this is a nit, not a new risk. Draw `resume-continue` and `resume-start` `disabled`, and enable them right after their listeners are added. The test trick is in the memory file sci2audio-app-review-checks: hold `player.js`, reload with `wait_until="commit"`, assert disabled.

### Deferred

- #376: the web chapter-list hint for a publisher's page.

## Next

Round 2 is the last round for this non-critical PR. It re-checks S1 and N1 with the fast and browser suites. `ci:full` (three systems) runs on the approving head.
