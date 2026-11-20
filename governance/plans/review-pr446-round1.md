# Review PR #446, round 1 (D2: library search and drop, voice cards, download links, CLI chapter number; #416 #417 #419 #435 #432)

Head reviewed: **b14ed09**, on main 7a3b3ec. Main is now 71ca0aa (#444). Non-critical (D-704 Q1).

**Verdict: changes needed, all small.** Nothing blocks. Three behaviours have no test, and there is one note about drops. The #432 deviation is accepted.

## What held

**Runs, in a clean worktree at b14ed09:**
- Fast suite: 6,337 passed, 2 skipped.
- Browser suite (Chromium): 115 passed, 1 skipped.
- Both match the PR body. PR checks on Linux are green.

**#432 (the deviation, ruled).**
- D-695 defines `chapter_number` as the chapter of the chunk just spoken, and `chapter_done` as "that chunk was its chapter's last".
- The CLI line names that chapter with its own title and "of {chapters}" (the chapters with something to say). That is exactly D-695's reading.
- The web card steps ahead on `chapter_done` because it shows the chapter "now" and has every title. The CLI has only the finished chapter's title, so stepping would pair the next number with the old title.
- Both count among the chapters spoken, which is #432's point. **Accepted.**
- `test_the_progress_numbers_a_chapter_among_the_chapters_spoken` (chapters 1 and 3 → "1 of 2", "2 of 2", never "chapter 3") kills U10.

**#435.**
- `download` is on all four `?download=true` links: the report (read and JSON), the script, and the job card's files.
- `test_every_download_link_saves_without_leaving_the_page` reads the served package's templates. It kills U11, and my R5 (the job card's link).
- The browser test holds app.js, clicks the report download and releases it, and `#update` and `#make` become enabled.

**#416.**
- `library.folded` (Python) and `folded` (app.js) fold the same way: lower case, NFKD, `M` categories dropped, ß → ss. The rows' `data-find` is folded on the server, and the script folds only the query.
- Every word must match, and the counts stay those of every document.
- Without the script, the GET form filters on the server (the test aborts app.js).

**#417.**
- The drop goes through the same `open()` as the form, so it gets the same request, errors and size limit.
- One file only. The hint shows only once the drop is wired.

**#419.**
- Cards are listed default first, with the sample sentence of the voice's language.
- A missing pack names its own size and has no button. Nothing is fetched.
- The Play buttons are drawn disabled and enabled as they are wired, with a hold test.
- One `<audio>` plays at a time.

## Mutants (D-676)

Command: `python m446.py <clean worktree at b14ed09> unit|js`. It applies the author's list from `plans/working-reader-d2-mutants.py` plus mine, in place, with `PYTHONPATH=src`.
- Unit set: `test_web_library.py`, `test_web_pages.py`, `test_web_design.py`, `test_cli_convert.py`. Baseline: 221 passed, 1 skipped.
- Browser set (Chromium): `test_library.py`, `test_voice_cards.py` and the #435 flow test. Baseline: 13 passed.

**The author's 20 claims hold:** U1 to U11 and B1 to B9 are all killed.

Mine:

| Mutant | Result |
|---|---|
| R1 JS search keeps case | killed |
| R5 the job card's download without `download` | killed |
| R7 the query never kept in the address | killed |
| R8 the server query not folded | killed |
| **R2 a stopped sample still plays** (`if (mine !== asked) return;` removed) | **survived (S1a)** |
| **R4 command-line rows can't be found** (`find` → "" in `_outside_row`) | **survived (S1b)** |
| **R3 a sample that ended keeps "Stop"** (the `ended` listener removed) | **survived (S1c)** |
| R6 dragleave ignores the depth count | survived: the synthetic drag never passes over a child (note) |

## Findings

**S1. Three behaviours have no test.**
- **(a) Stop, or a second Play, while a sample is still being made.**
  - `asked` and `mine` make sure a sample that was stopped, or replaced while its preview job was still running, never starts playing when the job ends.
  - Without that check, Stop during "Listening…" is ignored: the voice still plays a few seconds later. No test catches it, because the B7 test only stops a sample that is already playing.
- **(b) Command-line audiobooks in the search.**
  - `_outside_row` gives those rows a `find` text. With it emptied, nothing fails.
  - #416 asks that every row be found by its title or file name.
- **(c) A sample that plays to its end.**
  - The `ended` listener gives the button back as "Play a sample". Without it, the button keeps saying "Stop the sample" after the sample is over, and no test notices.

**N1. A file dropped beside the opener leaves the app.**
- The drop is handled only on the opener form. A file dropped anywhere else on the library page gets the browser's default action: it opens the file in the tab, and the person is out of the app.
- Calling `preventDefault` on `dragover` and `drop` at the document, for drags that carry files, would stop that.
- Fix it, or file an issue (milestone v1.3, lane:web).

**N2, no change asked.** R6: every synthetic drag in the tests enters and leaves the form itself, so the depth count is never exercised. A test with a drag over a child element would cover it. That is optional.

## Fix list (one fix commit, then round 2, the final round)

1. **S1a:** a browser test that clicks Play, then Stop (or another voice's Play) before the first preview job has finished. Hold or slow the job, for example with the fake voice's delay, or by holding the job's events. Check that the first sample never plays: the `<audio>` gets no `src` from it and stays paused. It must fail without `if (mine !== asked) return;`.
2. **S1b:** a unit test that a command-line (outside) row is found by its name with `?q=` and hidden by a query that doesn't match. It must fail with `find` emptied in `_outside_row`.
3. **S1c:** a browser test that a sample which plays to its end gives the button back: its label and text read "Play a sample…" again. It must fail without the `ended` listener.
4. **N1:** fix it with a test (a synthetic drop beside the opener stays on the page, if one can be made meaningful), or file an issue and name it in the PR body.
5. **Main:** main moved to 71ca0aa (#444), which touches the same `app.css`, `pages.py` and strings files. Take it in with a merge commit in the fix round, never a rebase or force-push. Check that the PR's own diff is unchanged apart from any conflict resolution, and say in the PR body what the resolution touched.
6. **PR body:** the round 1 answer, and each new mutant with its command and clean baseline.
