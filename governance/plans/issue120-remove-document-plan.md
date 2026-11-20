# Issue #120: remove an opened document from the web app (plan)

Thread "Add removing a document from the web app", 13 Nov 2026. Base: main 47c86fb (after #78 PR #144 and #79 PR #142). Lane web. risk:high (it deletes files), so the plan waits for the coordinator's approval. Feature IDs AQ-03, WI-02. Follow-up of #77, D-260.

## 1. What exists today

- An opened file lives in its working folder `<work_root>/<id>/` (D-198): `source/<name>`, `script/` (the latest pre-analysis: script, report.json, report.md), `chunks/` (speech cache, D-158), `job.json`, `audio.json`, `document.json` (D-165), `audiobook.json` (the web's record of the output folder, D-295) and `job.lock` (D-161).
- `DELETE /api/v1/documents/{id}/chunks` frees the speech cache through `app.clean_work_folder`, which holds the work-folder lock (D-226) and answers 409 while this server's job uses the document (`api._not_in_use`).
- Only the audio job takes the work-folder lock (`app/audio.py`); the script job does not. The board runs one job at a time (D-200).
- Buttons that change things call the API with `fetch` from `app.js`. A form POST would carry `Origin: null` because of `Referrer-Policy: no-referrer` and be refused (D-194, D-321); `fetch` sends the page's own origin.
- The privacy page says: "To remove everything sci2audio keeps, stop it and delete the working folder..." (D-293).

## 2. The change in short

- `DocumentStore.remove(id)` in `web/documents.py` (about 80 lines) removes the whole working folder under the work-folder lock, in an order that keeps the document listed until the end, and never touches anything outside `<work_root>/<id>/`.
- `DELETE /api/v1/documents/{id}` in `web/api.py` answers 200 with what was removed and where the audiobook stays; 404, 409, 500 as below.
- `JobBoard.forget(document_id)` drops this run's finished jobs of the document.
- Templates: a "Remove this document" disclosure on the document page and per document on the start page; `app.js` handles the press; new `[remove]` strings in `en.toml` and `de.toml`; the privacy page names the new way.
- Rough size: 200 lines of code and templates, 350 lines of tests.

## 3. Design questions (recommendation first; the coordinator decides and assigns D-numbers)

1. **What removing deletes.** The whole working folder `<work_root>/<id>/`: the copied source, the pre-analysis files, the speech cache, `job.json`, `audio.json`, `document.json`, `audiobook.json`, `job.lock`, and the folder itself. **Never** anything in an output folder (the MP3s, the M4B, the read-along file stay byte for byte), the settings file, the voice folder, the voice preview folder or another document's folder. After removing, the listen page for that document is gone too (its record was in the working folder); the audiobook itself stays playable in any player. Alternative: keep the pre-analysis or the speech cache (then "remove" would not remove what the person opened by mistake, AQ-03).

2. **Where the code lives.** In the web layer, `DocumentStore.remove`, using `app.lock.work_folder_lock`; `source/` is the web's own idea (D-198), and the command line has no list of opened documents. Alternative: an app function `remove_work_folder` next to `clean_work_folder` (the app would have to learn about `source/` and the web's records; nothing else would call it in v1.0).

3. **Order and a removal that fails part-way.** Under the work-folder lock: first every entry except `source/` and `job.lock`, then `source/`, then `job.lock` and the folder (on Windows the lock file is closed first, so it is removed just after the lock is released; if that fails, an empty `job.lock` in an otherwise empty folder stays, which holds nothing and the start page doesn't list). A file that is already gone counts as removed. A read-only file gets its write bit set and is tried once more (Windows refuses to remove read-only files). If anything else can't be removed (a file another program holds open on Windows, a permission problem), the answer is 500 `remove-failed` naming the first path left, and because the source goes last the document **stays listed**, so the person sees it and can press again. Alternative: rename the folder to a trash name first and delete that (atomic on POSIX, but Windows can't rename a folder with the open lock file inside, and leftovers would hide in a trash folder the person never sees).

4. **Busy and races.** 409 `busy` when this server's running job (script or audio) is on the document, and 409 `busy` when another process holds the work-folder lock (a command-line audio job, D-161). Jobs on other documents, a voice preview and the voice download don't block a removal. While a removal runs, the store treats the id as gone (`get` answers None, so starting a job answers 404) and opening the same bytes waits for the removal and then makes a fresh folder (one `threading.Lock` in the store around the removal and around putting a new file in place). Alternative: hold the board's lock during the removal (pages read the board on every request and would hang while a large speech cache is deleted).

5. **This run's job records.** The finished jobs of the removed document are dropped from the board (`JobBoard.forget`), so their job pages answer "no such job" instead of half a page with buttons for a document that is gone; their files are gone or are in the output folder, which the person keeps. Alternative: keep them and show "a removed document" (the "Free the speech cache" and "Try again" buttons would then fail with 404).

6. **The API answer.** `DELETE /api/v1/documents/{id}` answers 200 with `{"id", "name", "freed_bytes", "audiobook_folder"}` (`models.RemovedOut`; `audiobook_folder` is the recorded folder from `audiobook.json` or null), so the page can say in one step what went and where the audiobook stays. 404 `not-found` for an unknown or malformed id (also after removal), 409 `busy`, 500 `remove-failed`. Same token and origin rules as every route; no change to the D-194 checks. Alternative: 204 like the chunks route (the page would need the folder from somewhere else, and it is gone after the removal).

7. **Confirmation.** A native disclosure (`<details>` with a `<summary>` "Remove this document…") holding what goes ("the copy of the file, its analysis and the speech cache, N MB in all"), what stays ("your audiobook in <folder>" when one was made, and "the file you opened, wherever it is on your computer") and one button **"Remove <name> now"**. Opening the disclosure is the deliberate step and **the press of the button is the confirmation**; no browser `confirm()` (as D-254). Alternative: the button straight on the page as the issue words it (one stray press loses the speech cache, which can be an hour of speaking for a book) or a modal dialog (harder to make accessible, against D-254's reasoning). This refines the issue's acceptance criterion, hence a decision.

8. **Where it is offered.** On the document page as its own section after step 3, heading "Remove this document"; on the start page inside each document's list item, its summary's accessible name naming the document ("Remove report.pdf…", the name in a span with the text's language), so a screen reader's list of buttons tells them apart. Not on the job page or the listen page. Alternative: the document page only (the issue asks for both, and the start page is where someone looks after opening the wrong file).

9. **Keyboard and screen reader after the press.** Start page: the list item goes, the status region `#message` says "report.pdf was removed. Your audiobook stays in /Users/…" (or without the second sentence when there was none) and takes focus; when the list is empty, "No document opened yet." shows. Document page: no navigation; the page's steps are replaced in place by a "report.pdf was removed" heading, which takes focus, with the same sentence and a link back to the start page; the document's name never travels in a URL and nothing is kept in browser storage. A failure: the reason in the status region in the page's language with the app's words as details (D-291), focus on it, the button stays. The button is disabled while the request runs, so a double press sends one request. Alternative: navigate to the start page with `?removed=<name>` (puts the person's file name in the history and lets any link show a made-up message).

10. **While a job works on this document.** The page shows, instead of the button, "sci2audio is working on this document; you can remove it when the job has ended." (server-rendered from the board, as the running-job banner is); a job that starts between page load and press gets the 409's message. Alternative: show the button and let the 409 explain (an error the person can't avoid).

11. **German and the privacy page.** New table `[remove]` in `en.toml` and the same keys in `de.toml` ("Dokument entfernen…", "Sie", „…“, D-292), `error.remove-failed` in both, table tests as today. The privacy page's `work` line adds "a document's page can remove it with all of this", and `remove` says that the start page or the document page removes one document, and that the folders are for removing everything. Alternative: leave the privacy page as is (it would then send people to delete folders by hand, which this issue makes unnecessary; D-293 asks that every statement match the code).

## 4. Tests

- **TestClient** (`tests/unit/test_web_remove.py`): removal deletes the whole folder and only it (an output folder with an audiobook, the preview folder, a second document and the settings file are compared byte for byte before and after); the answer's fields; 404 after, 404 for a malformed id and for `..`-style ids; 409 while a board job runs on the document (script and audio), 200 while a job on another document or a preview runs; 409 while the test holds `work_folder_lock` itself (another process); cookie request without `Origin` 403, wrong `Origin` 403, bearer without `Origin` 200 (D-194), the folder untouched after each refusal; `forget` drops only that document's finished jobs; the start page and document page render the disclosure, and the sentence instead of it while a job runs.
- **Fault injection**: a file removed during the removal (a hook removes the next file just before `rmtree` reaches it) still ends in 200 and an empty work root; a file that can't be removed (an injected `PermissionError`) answers 500 `remove-failed`, keeps the document listed and lets a second press finish; a read-only file is removed; opening the same bytes while a removal runs makes a fresh, complete folder; starting a job during a removal answers 404.
- **Schemathesis** picks up the new route from the schema (its 200, 404, 409, 500 answers are declared).
- **Browser** (`tests/browser/`): by keyboard only, open the start page's disclosure for one of two documents, press Remove, focus lands on the message and the other document stays; the document page's removal ends on the focused heading and the link works; axe-core on the opened disclosure, after removal and after a failure, light and dark, English and German; reflow at 320 px for the opened disclosure on both pages in both languages; the request leaves the page as `fetch` with the page's origin (not refused by the D-194 check).
- Before the PR: `ruff check`, `ruff format --check`, `lint-imports`, `deptry src`, the fast suite, the browser suite, and the nightly Hypothesis profile for the web tests.

## 5. Not in this issue

- Removing every document at once, or removing the audiobook files from the output folder (a person's own files; v1.1 at most, new issue only if wanted).
- Working folders without a source file (left by an old crash or a failed removal's empty lock file) are not listed and not cleaned; a "clean the working root" action would be its own issue.

## 6. Sequencing

One code PR (web lane). No KB PR from this thread: under D-373 the daily KB thread records D-353 to D-363.

## 7. Decisions (coordinator, 13 Nov 2026 14:50 UTC, approved as recommended)

| Question | Decision | Short |
|---|---|---|
| 1 | D-353 | Removing deletes the whole working folder; never the output folder, settings, voices or other documents |
| 2 | D-354 | `DocumentStore.remove` in the web layer under the work-folder lock |
| 3 | D-355 | Order: everything else, then `source/`, then lock and folder; read-only retried once; part-way failure answers 500 `remove-failed` naming the first path, the document stays listed |
| 4 | D-356 | 409 `busy` for this server's job or another process's lock; during removal the id is gone; opening the same bytes waits, then gets a fresh folder |
| 5 | D-357 | This run's finished jobs of the document are forgotten |
| 6 | D-358 | `DELETE /api/v1/documents/{id}` answers 200 with id, name, freed_bytes, audiobook_folder; 404/409/500; D-194 unchanged; `fetch`, not a form POST |
| 7 | D-359 | Native `<details>` disclosure stating what goes and stays; one "Remove <name> now" button is the confirmation; no `confirm()` |
| 8 | D-360 | Offered on the document page after step 3 and in each start-page item, the name in the accessible name |
| 9 | D-361 | In-place replacement with focused status or heading; no name in a URL; nothing in browser storage; button disabled while the request runs |
| 10 | D-362 | While a job works on the document a sentence replaces the button; a race gets the 409 message |
| 11 | D-363 | `[remove]` tables in en.toml and de.toml, `error.remove-failed`, privacy page lines updated |

Status in the KB: Decided (Claude); Colin informed in the project chat at 2026-11-13 14:50:18 UTC.
