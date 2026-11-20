# Review of PR #183 (app: Markdown, text and pasted text, #74 part 3), round 1

Head reviewed: 4cc636f. Plan: plans/issue74-text-input-plan.md, D-337 to D-352 (PR 3 test list).

## What I checked

- **Diff against the plan.** The diff has 16 files against main, with no core, contract, golden or licence change, so the PR is not critical. `EXTRACTORS` gains `.md`, `.markdown` and `.txt` (D-350), and suffixes are matched in lower case in both the job and the web upload. `encoding_warning` (D-346) is the first report warning and is also printed by `script` and `convert` as `sci2audio: warning: …`. The paste form needed no change.
- **CLI, run by hand:**
  - a Windows-1252 `win.TXT` (upper-case ending): the script was written, stderr has the warning line and report.md lists it;
  - an empty `.txt`: "the file is empty";
  - a `%PDF-` file named `.txt`: "this is a PDF, not a text file; open it with the .pdf ending";
  - a blank `.md`: "the file holds no text";
  - the corpus sample copied as `.markdown`: the script was written;
  - every failure exits without a traceback.
- **Browser, with throwaway tests that are not committed:**
  - In English, an uploaded Windows-1252 `notes.txt` shows the warning under Notes as `<li lang="en">`, and axe is clean.
  - In German (de-DE), the page is `lang="de"` and the same warning shows in English inside `lang="en"`, as other app words are (D-291). Axe is clean.
  - `Notes.MD` with an upper-case ending opens and is analysed.
- **Paste cap.** It is the existing 5 MB `TEXT_LIMIT` (D-198), unchanged and already tested in test_web_documents. Pasted text is UTF-8, so it is never guessed and never gets the warning.
- **Local runs (CPython 3.12):**
  - ruff, format, lint-imports (3 kept) and deptry pass;
  - fast suite: 2930 passed, 1 skipped;
  - browser suite: 44 passed, 2 skipped (one of them quarantined as #138).
- **CI on 4cc636f:** all green on Linux, macOS and Windows, plus browser and ZAP.

## Must-fix

None.

## Should-fix

None.

## Notes (no action needed)

- A paste that is only white space opens a document whose analysis then fails with "The job could not finish. Details from sci2audio: pasted text.txt: the file holds no text". The message is clear enough. Refusing a blank paste in the form would be nicer UX but is out of scope.
- No browser test pins the encoding warning on the document page; the template shows any report warning generically and the unit tests pin the text. Fine for now.

## Outcome

Merge after updating with main (the branch is 1 behind) and green CI on the new head.

- ZAP baseline scan failed once on a022a07 ("files exist already" at the Replace step of zap_scan.py, a path this PR does not touch). One re-run passed; filed as #184, later closed as a duplicate of #177.
- CI on a022a07 green on all three systems. Squash-merged 13 Nov 2026 19:14 UTC as b8e1e3f; #74 closed.
