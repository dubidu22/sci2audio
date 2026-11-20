# Working Reader, batch C: Prepare with the job inline (#391), plus #427 #422 #429 #430

Web lane, one PR on top of main once #420 and #421 are merged. Binding: DESIGN.md and `prototype/app/` at sci2audio-design b4a7523 (`prepare.png`, `making.png`, `failed.png`), the plan `plans/working-reader-plan.md` (D-665, conflicts 4 and 5), and the batch A/B tokens, sprite, rail, records and CSP rules.

## Critical or not

**Not critical, in my reading.** Nothing changes these:

- a layer contract, `sci2audio.core`, the KB or a golden file;
- a record: no new file, and `opened.json`/`about.json` stay as they are;
- the app's job runner or the job API.

Pause, Resume and Cancel reuse three endpoints that exist today:

- `POST /api/v1/jobs/{id}/cancel`;
- `POST /api/v1/jobs` (a new audio job with the old one's settings, the "Make it again" path of the job page);
- `DELETE /api/v1/documents/{id}/chunks` (the job page's "Free the speech cache").

**The one judgement call is yours:** "Cancel" frees the speech cache, which deletes files in the working folder. It goes through the existing endpoint and its existing checks, after a confirm, the same disclosure pattern as removal (D-359). If you count a new path to an existing deletion as "deletes user files", the PR is `risk:high`.

## Commits, in order

1. **#427 first:** the document page's server-drawn buttons that only `app.js` wires are drawn `disabled`, and `documentPage()` enables each one as it wires it, as #350 did for Replace. The buttons are:
   - `#make`;
   - `#choose-all` and `#choose-none`;
   - `#update` and `#analyse`;
   - the preview's Listen button;
   - the chapter move buttons.

   `aria-disabled` and `data-blocked` keep their meaning for the blocked states. A browser test holds `app.js` and checks that each button is disabled, then enabled once the script runs. It must fail without the change. (Done before the restyle so it can be reviewed apart.)
2. **#391:** Prepare, described below.
3. **#429:** `test_the_announce_switch_saves_itself` waits for the `/appearance` response (`page.expect_response`), not for the URL the page is already on, at both toggles. I'll grep the Settings tests for the same pattern. A mutant that drops the change handler must fail the test.
4. **#430:**
   - A settled read-along file (mtime set back past `RACY_NS`) replaced by another version gives the new bounds. This kills the `(0, 0, 0)` key mutant.
   - A position exactly at the last sentence's end gives no Continue and `read_position` None. This kills the `<= last` mutant.
5. **#422:** the ZAP walk's uploads are deterministic: fixed bytes for `note.pdf` and the paper (a fixed creation date in the PDF maker the walk uses). A unit test checks that two calls give the same bytes.

## #391: the document page as Prepare

- **The paper header** (`_paper.html`, shared with Listen):
  - **h1:** the title from `about.json`, else the file name.
  - **Meta line:** authors, "N pages" (PDF), the language with where it came from, and the audiobook's length when there is one.
  - **Tabs:** a `<nav>` with "Prepare" and "Listen", `aria-current="page"` on the one shown. With no audiobook, Listen reads "Listen · No audio yet" as plain text, not a link.
  - Listen gets the header now. Its body stays for batch D.
- **Two columns from 1280 px:** the steps (up to 1240 px wide), and a 340 px sticky side column with two panels:
  - **"This document":** file, pages, sentences, changes to make, and the report as "read · JSON" links.
  - **"What stays where":** today's privacy sentence.

  Below 1280 px the side column follows the steps (no overlay: Prepare has no reading column to keep). At 320 px nothing scrolls sideways.
- **Step 1, "Check what will be read":**
  - The summary line: chapters, chosen, changes, how many change what you hear.
  - **Chapters:** the ordered list with checkbox, page and sentence count, the up/down buttons (the existing reorder), and Choose all / Choose none. References and publisher lines are struck, with their reason.
  - **Language:** the existing select.
  - **"Changes to make":** one row per category, with:
    - a switch (`<input type=checkbox role=switch>`, the existing `category` field);
    - its counts;
    - a disclosure of its examples as a three-column "printed → read as → why" table, keeping page, chapter and status. These are today's rows and limits.
  - "Update the analysis" stays the one submit.
  - Problems, warnings and "not run" become callouts.
- **Step 2, "Choose the voice":** voice, speed, letter pace and the preview, restyled only.
- **Step 3, "Make the audiobook":** folder, subtitles and the remembered-settings hint, then the Make button. The blocked notes are unchanged.
- **Removal:** #421's disclosure, at the end.
- **The job inline: "Making the audiobook"**, a card at the top of the steps. `/jobs/{id}` stays the route Make goes to (the tests and the API keep it). For an audio job with a document, it renders the Prepare page with this card. The document page shows the same card while an audio job for it runs or has just ended in this server run (`state.board` latest audio job). The card has four states:
  - **Running:**
    - "Speaking chapter 6 of 8";
    - "64 % · about 41 minutes left" (`seconds_left`, None while it measures);
    - the bar (`<progress>`);
    - one segment per chapter, done, current or to come (spans with classes, no inline style);
    - "2,499 of 3,880 sentences";
    - the note that closing the window is fine.

    It has two buttons:
    - **Pause** is today's cancel. Everything spoken is kept.
    - **Cancel** sits behind a confirm disclosure, its danger button naming the cache size. It cancels the job, then frees the speech cache once the job has stopped.
  - **Paused** (cancelled): "Paused at chapter N. M of T sentences are spoken and kept." Two actions:
    - **Resume** runs it again from the cache, through today's "Make it again" request.
    - **Free the speech cache (size)**.
  - **Failed:** "Making the audiobook stopped in chapter N", the reason, and what is really kept (conflict 5).
    - It reads "Chapters 1 to N−1 are finished and kept. Making it again speaks only what is missing", from the job's last progress (`chapter`, `chapters`, `chunks_done`), since the voice speaks chapters in order. Before I write that sentence I'll check that claim in `app/audio.py`; if the order does not hold, the wording falls back to sentences kept.
    - Two actions: **Make it again**, and **Free the speech cache (size)**.
    - "output exists" keeps today's Replace button.
  - **Done:** "The audiobook is ready" with:
    - the Listen link;
    - the files with sizes;
    - the folder;
    - reused sentences;
    - skipped sentences;
    - the cache line.

  The live updates use today's job stream (`follow()`, one EventSource per job, #409 B2), and the card is redrawn by the existing `app.js` job code with the new markup. The rail's shelf job item is unchanged.
- **Other job kinds** (voice download, preview) keep `job.html`, restyled as a panel in the app column.
- **#365:** the quarantine at `test_flow.py:249` lifts. The fix came with #403 on release/1.1. If R3 has not reached main when this PR is up, I port that one test fix: wait until `#document[data-events]` is gone before axe.
- **Strings:** en and de with the same keys. German follows `prototype/app/i18n.js` ("Vorbereiten", "Anhören", "Hörbuch wird erstellt", "Pausieren", "Fortsetzen").
- **Not in this PR:**
  - writing a partial audiobook on failure (#401, Later);
  - pausing inside the app's runner;
  - the Listen body (batch D).

## Tests

- **Unit** (TestClient):
  - the header in each state: title or file name, meta, the tabs, Listen as a link or "No audio yet";
  - the side panels;
  - the card in running, paused, failed (chapter and kept wording, with a progress before the first chapter as the edge) and done;
  - `/jobs/{id}` for an audio job renders Prepare, and for voices and preview renders `job.html`;
  - the Cancel confirm names the size;
  - every new string in both languages (the existing unused and same-key tests).
- **Browser:**
  - the main flow and keyboard flow updated: Make, then the card, then done, then Listen;
  - Pause, then Resume, then done, with the job held in-process so the test does not race a fast job;
  - Cancel's confirm frees the cache, and the folder's chunks are gone;
  - axe in light, dark and German at 1440, 1280 and 320 px;
  - reduced motion: no transition on the bar or the segments;
  - no highlighter colour on chips, buttons, tabs or segments;
  - the #427 hold test;
  - screens: `prepare`, `making`, `failed` and `paused` added to `test_screens` under the `ui:screens` label.
- **Run before the PR:**
  - the fast suite;
  - the Chromium browser suite;
  - one-line mutants on the card logic (chapter wording, kept count, Pause vs Cancel endpoint), with the command and a clean baseline in the PR body (the D-676 lesson).

## Size

About 1,200 to 1,600 lines:

| Part | Lines |
|---|---|
| templates and CSS | ~600 |
| `pages.py` and `app.js` | ~300 |
| strings | ~150 |
| tests | ~500 |
| the four small issues | ~150 |

## Fitness

This thread is on its second compression. I hold batch A and B's code facts in memory (CSP, records, shelf, streams, the conftest `download_plan` lambda, the worktree lesson) and the batch C scope above from the plan and the design screens read today.

## Rulings (D-694, coordinator, 16 Nov 03:41Z)

The plan is approved with these four rulings:

1. **Critical, `risk:high`.** Cancel is a new UI path to deleting user files, and the PR is 1,200+ lines. It gets the full process, and mutation and nightly runs on the final round.
2. **Cancel waits for the job to have stopped** before the DELETE is sent. A test must fail if the DELETE goes out while the job still runs. The confirm names the size.
3. **The "Chapters 1 to N−1 are kept" wording stays,** because `app/audio.py` speaks chapters in order (checked: `plan.chunks` follows the chosen chapters' order, line 121). Otherwise it would be sentences-kept wording.
4. **The commit order is as planned, #427 first.**

A fresh web-lane thread takes batch C from this file. Memory: `sci2audio-working-reader-web-lane`.

## Deviations

1. **D-695 (coordinator, 16 Nov 03:50Z): two additive fields on `AudioProgress`.** The plan read the card's chapter from the last progress, but `AudioProgress.chapter` is the document's chapter index, not the position among spoken chapters, and the last progress names the chapter of the last *finished* chunk. So when that chunk ended its chapter, the job really stopped in the next one. `_Speech.progress` now also sends:
   - `chapter_number`: the 1-based position among the chapters with something to say, in the order of `plan.chunks`;
   - `chapter_done`: true when this chunk was its chapter's last.

   The failed card says "stopped in chapter `chapter_number` (+1 if `chapter_done`)". A failure in the encoding phase says every chapter is spoken and kept. A failure before the first chunk says nothing is spoken yet. Existing fields keep their meaning. A test pins the values across a chapter boundary. The PR body's risk section names this change to the job progress shape.
