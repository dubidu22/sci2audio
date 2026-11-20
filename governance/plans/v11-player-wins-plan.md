# Plan: v1.1 player wins in one PR (#152, #153, #154, #119, #190)

App-lane thread "Finish v1.1 player wins", 15 Nov 2026, on main 82d9e0d.
Read: CLAUDE.md, `.claude/rules/tests.md`, `.claude/rules/licences.md`, project-instruction rules 1-6 (D-626, D-627), KB D-600 to D-627 plus the pending batches up to D-637 (D-635 names this batch), D-133, D-165, D-194, D-247, D-295, D-300, D-409; `plans/issue78-player-plan.md`; memory files sci2audio-issue78-player and sci2audio-app-review-checks; the five issues; code on main: `app/settings.py`, `app/chapters.py`, `app/script.py`, `app/job.py`, `app/audio.py`, `web/player.py`, `web/api.py`, `web/pages.py`, `web/static/player.js`, `web/templates/listen.html`, `web/templates/document.html`, `cli.py`, `tests/unit/__snapshots__/test_cli_golden.ambr`.

## Approval (D-642, coordinator 15 Nov 15:55 UTC)

Approved with a split: **PR A, non-critical**: #152, #153, #190. **PR B, critical**: #154 and #119, branched from main (not stacked on A). Title page stays selected; #154 is a command. Kept requirements: the resume POST keeps the token and origin checks and never autoplays; `listen` serves only from the two named folders and takes no path from a file; the chapter order line appears only when the order differs from printed order; deselected publisher pages stay selectable.

## 0. Criticality: the PR is critical (risk:high)

Two of the five change a golden file: the CLI help snapshot (`tests/unit/__snapshots__/test_cli_golden.ambr`).
- #119: `--chapters` now keeps the order given, so its help line says so ("... in the order given").
- #154: a new command `sci2audio listen` appears in the top-level help and gets its own help snapshot.

#154 also widens what the local server serves from disk (a second working folder and its output folder), which is a safety mechanism (the D-295 path checks). No layer contract, no `sci2audio.core` dataclass, no corpus truth, no regression case and no other golden file changes: the report, script, `job.json` and `audio.json` snapshots all use the default chapter choice (`None`) or sorted choices, which serialise as before (checked below). So: one PR, labels `risk:high`, `lane:web`, `lane:app`, one commit per issue so the reviewer can read it issue by issue. (If the coordinator prefers, #152, #153 and #190 split off cleanly as a non-critical PR; I recommend one PR, as asked.)

## 1. #152 Speed control in the player bar

- `listen.html`: a native `<select id="speed">` with a visible `<label>` "Speed", options 0.75×, 1×, 1.25×, 1.5×, 1.75×, 2× (1× selected). Native select: keyboard and screen reader announce the value for free.
- `player.js`: on change set `audio.defaultPlaybackRate` and `audio.playbackRate`, and `preservesPitch = true` (plus `webkitPreservesPitch`/`mozPreservesPitch` where present). Loading a new `src` resets `playbackRate` to `defaultPlaybackRate`, so setting both keeps the speed across chapter MP3s, jumps and the M4B fallback; `loadedmetadata` re-applies it as a guard.
- The highlight already reads `audio.currentTime` per animation frame, so it follows any rate.
- The speed is not remembered across server runs (not asked; it could join the #153 record later).
- Strings `player.speed`, `player.speed_value` in `en.toml` and `de.toml`.
- Tests (browser): the select sets `playbackRate` 2 and `preservesPitch`; the rate stays 2 after the next chapter's file starts, after a sentence jump, after a chapter jump and in M4B mode; at 2× the highlight is on the sentence whose time span holds `currentTime` at three sample points; keyboard-only change of the select; axe light and dark; the reflow test of #144 at 390×844 and 320×256 still passes with the select in the bar.

## 2. #153 Remember the listening position across server runs

- **Record** `<work>/position.json`, web-owned, next to `audiobook.json` (D-295): `{"format": "sci2audio-web-position", "version": 1, "document": "<id>", "audiobook": "<stamp>", "chapter": <n>, "time": <seconds>}`.
  - `chapter`: index into the audiobook's chapters (read-along order, so it also works for a chosen order, #119); `time`: seconds on the book's timeline.
  - `audiobook` stamp: SHA-256 (first 16 hex digits) of the read-along file's bytes. A rerun of the audio job writes a new read-along file, so a stale position no longer matches and is dropped; this also covers an audiobook remade by the command line. The web's audio task also deletes `position.json` after a successful audio job.
  - Written atomically with `app.files.write_text_atomically`.
- **Reading** (`web/player.py`, `read_position`): ignored (None, never an error) unless format and version match, the document id matches, the stamp matches the read-along file the player found, `chapter` exists and `0 <= time < duration`, and `time` lies inside that chapter's span. A broken file (bad JSON, wrong types, too large: over 4 KB) is ignored.
- **Saving**: `POST /api/v1/documents/{id}/position` with `{"chapter": n, "time": s}` (pydantic model, bounds checked), under the existing token and origin checks (D-194; no new exemption). 204 on success; 404 for an unknown document or no audiobook; 422 for a position the audiobook doesn't have; 503 with a JSON reason when the disk refuses the write (the old record stays, by the atomic write). The player ignores a failed save (no message while listening, D-300).
- **player.js**: saves at most every 5 s while playing, and on pause, on a jump (sentence, chapter, click), when the last chapter ends (the end is saved, and no "continue" offer is shown for a time in the book's last 5 s), and on `pagehide`/`visibilitychange` hidden with `fetch(..., {keepalive: true})` so the session header goes along (sendBeacon can't send it).
- **Offer**: when a valid position exists, the page shows above the text: "You stopped in chapter 2, Methods, at 3:12." with two buttons, **[Continue from 3:12]** and **[Start from the beginning]**. Neither starts playback by itself: "Continue" moves the position and highlight there (as a paused jump does today) and focuses Play; the person presses Play (D-300: status only after the person's own action). The status region announces the move.
- Strings `listen.resume_*` in `en.toml` and `de.toml`.
- **Tests**: unit tests for `read_position`/`write_position` (each refusal rule; stamp mismatch; time at the end; chapter/time disagreement); fault injection: disk full (`OSError(ENOSPC)` from the atomic write → 503, old record unchanged), working folder removed between page load and save (404, nothing created), record replaced by a folder or a link (ignored on read, refused on write), the read-along file changed (dropped). TestClient: token and origin checks apply (403 without the own Origin, 421 with a foreign Host); a successful web audio job removes the record. Browser: play, pause at a known time, stop the server, start a new server on a new port with the same work root, open the listen page: the offer names the chapter and time; "Continue" puts the highlight there without playing; Play continues from there; "Start from the beginning" goes to 0. Keyboard-only run and axe light and dark on the page with the offer.

## 3. #154 Open an audiobook the command line made

- **New command** `sci2audio listen FILE [-o FOLDER] [--work-folder FOLDER] [--no-browser]`: the same options, defaults and settings file as `convert`, so the person names the folders exactly as they did for `convert` and nothing is read from a path written in a file the web did not write.
  - It resolves the working folder (`--work-folder`, else `default_work_folder(FILE)`) and the output folder (`-o`, else the settings file's output folder, else next to FILE), as `convert` does.
  - Checks before the server starts, with plain messages and exit code 2 on failure: `audio.json` and `document.json` exist in the working folder; FILE's SHA-256 first 16 hex digits equal `audio.json`'s `source.sha256[:16]` (D-198 id rule); the read-along file listed in `audio.json` is found in the output folder with the D-295 checks (bare names, regular file, resolved parent is the folder, agrees with `audio.json`).
  - Then it starts the same server as `ui` (127.0.0.1 only, same token) with this one job registered read-only, and opens `/documents/<id>/listen`.
- **Server side** (`web/state.py`, `web/player.py`): a small read-only map `outside: {document id: (working folder, output folder)}` passed in at start (no global state). The listen page, the audiobook file route and the position route look a document id up in the work root first, then in this map. For an outside job the candidate folders are only the named output folder (no saved or default fallback); every file goes through `in_folder` as today. Nothing else of the outside folder is served: no document page, no jobs, no removal; the listen page leaves out the links to the document page for it. The position record (#153) is written in that working folder, which is the app's own cache folder for that file.
- KB question: how the player finds a command-line job. Recommended: the person names the folders on the command line, as for `convert`. Alternative not chosen: an "Open a finished job" entry in the interface with a typed folder (a browser form can't pick a folder, typing a cache path is hard, and the command line already knows both folders); the command line writing `audiobook.json` (a path written in a file, which the issue asks not to trust alone).
- **Tests**: CLI: help snapshot (new); `listen` on a job `convert` made in the test (FakeVoice, real ffmpeg, a few seconds) starts the server with the job registered (server start mocked) and prints the link; each refusal: no `audio.json`, FILE changed since (hash differs), read-along missing, output folder wrong. TestClient with an outside job: the listen page renders and highlights data are complete; the audiobook route serves only names in `audio.json`; a name with `..`, a link pointing outside the folder, a file renamed after the job, and a request for another outside id are 404; the document page of an outside id is 404. Browser: the outside job plays and highlights; keyboard and axe on its listen page. The server still binds to 127.0.0.1 only (existing binding test runs for `listen` too).

## 4. #119 Choose the order of the chapters

- **`JobSettings.chapters`** becomes `tuple[int, ...] | None` (D-133 amended): the person's order, duplicates dropped (first kept). A set or frozenset passed in (old callers, tests) is sorted, so its meaning is unchanged; a list or tuple keeps its order.
- **`app.chapters.selected`** returns the chosen chapters as an ordered tuple; **`prepare_script`** builds the chosen `ChapterScript`s in that order, followed by the not-chosen ones in printed order (so the report still lists every chapter). Everything downstream follows `ScriptResult.chapters`' order: the script file, `audio.json`'s chapter list, output's chapter list, so the MP3 numbering, the M4B chapter marks and the read-along file follow the chosen order. The player (`build_view`) already walks the read-along's chapters, so it shows them in the listened order and finds every sentence.
  - A block moved into another chapter (a footnote read at its mark, #213) still belongs to the chapter it is read in (`_pieces_in` unchanged).
- **Records**: `job.json` and `audio.json` `settings.chapters` list the indices in the chosen order (today `sorted`); the report JSON's per-chapter list stays in printed order with `selected` (no new key, so no golden change), and its `settings.chapters` shows the order.
- **What the report and the script show** (the KB question): when the chosen order differs from printed order, the report's Markdown and the listening script get one line before the chapters: "Read in the chosen order, not as printed: 3 Results, 1 Introduction, 2 Methods." Printed order shows nothing new, so every existing golden stays.
- **Command line**: `--chapters 3,1-2` keeps the order given; "all" stays printed order. Help line changes (golden). An unknown index is still a warning (D-133).
- **Web**: the chapter list on the document page (step 3) gets **Move up** and **Move down** buttons per chapter (native buttons named "Move up: Methods"; the first chapter's Move up and the last's Move down are disabled). `app.js` moves the list item, keeps focus on the pressed button (or its sibling when it becomes disabled) and announces "Methods is now chapter 2 of 5" in the polite status region. The form posts the checked chapters in list order; `api.py` keeps the order (no `sorted`, no `frozenset`), and the job page shows the order. Without JavaScript the buttons are hidden and printed order is used.
- **Tests**: unit: `JobSettings` keeps order and dedups, sorts sets; `selected` keeps order and still ignores unknown indices; `prepare_script` order; Hypothesis: for any permutation of any subset, the script's utterances are the same multiset as in printed order and every chapter's utterances stay together; audio job with FakeVoice and chapters (2, 0): MP3 file 01 is chapter 2, the M4B's chapter marks and the read-along's chapter list follow, `audio.json` settings show [2, 0]; the report line appears only out of order; CLI `--chapters 3,1` order in `job.json`. Browser: reorder by keyboard alone (Tab to Move down, Enter, focus stays, status announces), start the job, the job page shows the order; the listen page plays chapter 2 first and highlights; axe light and dark on the reordered list.

## 5. #190 Leave publishers' pages out by default (EPUB)

- **`app.chapters`**: a chapter whose heading line carries a publisher page tag is deselected by default, as the reference list is (TP-06). New field `Chapter.publisher: bool`; `default_selection` leaves out `references` and `publisher` chapters. The tags are read from the runs of the heading block's first item (`TextRun.tags`, which already holds the ancestors' `epub:` and `role:` tokens).
- **The list** (fixed in the PR): `epub:imprint`, `epub:colophon`, `epub:copyright-page`, `epub:seriespage`, `epub:other-credits`, `epub:errata`, `epub:toc`, `epub:landmarks`, `epub:loi`, `epub:lot`, `epub:page-list`, `epub:index`, `role:doc-colophon`, `role:doc-credits`, `role:doc-errata`, `role:doc-toc`, `role:doc-index`, `role:doc-pagelist`.
- **Stays selected**: the title page (`epub:titlepage`: the book's title and author, a natural start, and not in the issue's list), half-title, dedication, epigraph, preface, foreword, introduction, the story's chapters, epilogue, endnotes.
- The Time Machine (corpus, read today): Imprint (`epub:imprint`), Colophon (`epub:colophon`, `role:doc-colophon`), Uncopyright (`epub:copyright-page`) deselected; title page, I to XII and Epilogue (the 13 story chapters) and Endnotes selected.
- The web chapter list shows "(publisher's page, not chosen by default)" like the reference-list hint; the report JSON gets no new key (the `selected` flag carries it), so the paper goldens don't change. PDFs and Markdown have no such tags and are unchanged.
- **Tests**: unit on hand-built documents for each tag in the list and for the kept ones; the Time Machine corpus test above; the person can choose them again (`chapters` given explicitly); CLI `script` on the EPUB lists them as not chosen.

## 6. Checks before the PR

`uv run ruff check && uv run ruff format --check && uv run lint-imports && uv run deptry src && uv run pytest -m "not slow and not benchmark and not browser"`, `uv run pytest -m browser`, the nightly Hypothesis profile on the touched tests, CHANGELOG entry (Unreleased: Added speed control, listening position, `sci2audio listen`, chapter order; Changed publisher pages deselected). No new dependency, so no licence row.

Rough size: ~1,100 lines of code, template, script and strings; ~1,300 lines of tests.

## 7. KB decisions to record (the coordinator assigns the numbers)

1. The PR is critical (CLI help golden, served folders).
2. #152: speed by a native select, not remembered across runs.
3. #153: where the position lives (`<work>/position.json`, stamped by the read-along file's hash) and that the page offers, never plays.
4. #154: `sci2audio listen` with the person naming the folders as for `convert`; outside jobs are read-only and served only from the named folders.
5. #119: `JobSettings.chapters` keeps the person's order (amends D-133, follows D-247); the report and script add one line when out of printed order.
6. #190: the tag list above; the title page stays selected.

## 8. Out of scope

Remembering the speed; a folder picker in the interface for outside jobs; drag-and-drop reordering (buttons only, as the issue asks).
