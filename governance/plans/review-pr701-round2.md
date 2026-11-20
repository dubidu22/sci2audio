# Review PR #701, round 2 (batch B-D1, #395)

Thread: review-docs-b-d1 (Opus 5.5). Head reviewed: 92c2894 (fix commit on b6905d2; `ci:full` still set). Date: 2026-11-20.
**Critical: yes** (unchanged; KB architecture document). Answer: `plans/answer-pr701-round1.md` (governance 2b3e9e0). The coordinator ruled S2 and S3.

**Verdict: approved** (0 must-fix, 0 should-fix, 2 notes).

## Verified

- Fix commit `git diff b6905d2 92c2894`: one file, the ADR, +10/−10, and only the round-1 answers. Against `main` 9066c3d the PR still touches the same three files (+120/−4).
- **S1 (issue-scope-drift): fixed.**
  - `adr-008:99-100` say that the file part is in `app` (2.3) and that the issue also carries `lane:app`.
  - On GitHub, #396 and #475 now carry `lane:core` and `lane:app`. The edit history (20 Nov 21:01 UTC) shows each body gained only a "Scope per ADR-008 2.3 (20 Nov 2026)" paragraph at the top, and no other line changed.
  - #396's paragraph names the second criterion as `app` work. #475's states the carry-over rule of 2.1 item 5.
- **S2 (underspecified-contract): fixed.**
  - 2.1 item 7 defines `document` as the title as the Library shows it, and `page` as the number of the PDF page on which the sentence starts, empty for EPUB, Markdown and text. This matches `core.content.Page`, where a page is a PDF page, an EPUB spine document or a whole text file.
  - 2.2 C refers to item 7.
  - #399 gained this as a criterion.
- **S3 (self-contradiction): fixed as the coordinator ruled.**
  - (a) The Why row now says "No capture the user removed stays on disk". It states that a v1.3 `markers.json` stays as it was until the document is removed, so the promise is true as written.
  - (b) 2.1 item 4 says that, once written, `captures.json` stays even when it holds no capture. That removes the "last capture deleted, file removed, markers come back" path.
  - 2.1 item 5 names the remaining path: if the user removes `captures.json` by hand, the v1.3 markers come back as the recovery path, deliberately. With that, "never read again" is no longer claimed.
  - The carry-over records `migrated_from: markers.json`.
  - This stays within D-854: `markers.json` is migrated once and left untouched.
- Round-1 notes:
  - N1: `TY  - GEN` unless extraction records an explicit type.
  - N2: the line break in RIS is left to #399 with a test, and #399 has the criterion.
  - N3: Related now says "(both on branch `governance`)".
  - N4: the "Scope per" paragraphs of #397, #398 and #399 now say 20 Nov; the edit history shows only the date changed, plus a trailing newline.
- I checked the other sections against round 1 again: Colin's labels and time, 2.2 B, the layering and the hard rules are unchanged. The ADR still matches D-850 and D-854.
- Merge with #700 at 5465f8f: `git merge-tree` is clean.
- Local run in a fresh `/tmp/review-701` at 92c2894: `uv run ruff check` clean; fast suite `-m "not slow and not benchmark and not browser" -k "not espeak" -n auto`: 8638 passed, 6 skipped, 6 xfailed.
- CI on 92c2894: `governance pr checks`, `label critical paths` and CodeQL are green; `CI` was running at review time.
  - For this critical PR the coordinator checks `CI passed`, and `tests (ubuntu-latest)`, `tests (macos-latest)` and `tests (windows-latest)` on this head, before the merge go (MRG-01, CLAUDE.md step 8).

## Findings

### Notes
- N1: `migrated_from` is a key of the file, not of a record. #396 writes the format checks of `captures.json`'s JSON form. If those checks take a fixed key set, as `markers.py:51` `_FILE_KEYS` does, and leave `migrated_from` out, #475 has to change `core` a second time. Only #475's paragraph names the key. #396 can list it among the file's keys when it is planned, at no cost.
- N2: by 2.1 item 5, the text of a removed migrated note stays in `markers.json` until the document is removed. The ADR now says so. When #398 and the privacy page describe removal, they should not promise more than that.

Verdict: approved. Merge on the coordinator's go, pinned to 92c2894, once the three-system run on that head is green.
