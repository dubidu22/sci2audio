# Review: sci2audio-design PR #40 (D-304 to D-319, #73 EPUB extraction and covers)

Reviewer thread: "Review EPUB core fields PR 140", 13 Nov 2026. PR head fe4f64f, base main b6836fd; code PR sci2audio #140 head 34b3ae0.

## Round 1 (13 Nov 2026, ~13:30 UTC)

### Format: pass, one fix
- 16 rows D-319 down to D-304, directly above D-280; the whole log is strictly descending, no duplicate IDs, 280 rows. Every new row has exactly six columns. No existing row edited.
- All 16 rows are **Decided (Claude)** (coordinator, 13 Nov 08:10 UTC, under D-80; plan approved as recommended). Plan section 9 says "all sixteen as recommended", so the wording is right.
- No closing keyword in the PR body; code PR #140 is a plain "see" link. Issues #134 and #135 are named as v1.1 follow-ups.
- mergeable_state clean today; KB PRs #38 and #39 are still open and merge first, so #40 must merge main afterwards and keep D-319…D-304 above D-287.

### Against plan sections 2 to 8 and the decision post
q1 = D-304 … q16 = D-319 in order; each row gives decision, question, alternative(s) and reason as the plan does. Checked in detail:
- D-305: lxml / BeautifulSoup4 / EbookLib (AGPL) / xml.etree for XHTML, as section 3.
- D-306: block elements, `br` tag, CSS white-space folding, `head/script/style/template` not recorded, ids `p{n}-l{i}`/`p{n}-i{k}`: as q3.
- D-307: tag table and the 100-element cap: as q4.
- D-309 to D-311: match the code in PR #140 (`Page` refuses a wrong order; `Content` checks an outline item is on the entry's page; empty defaults).
- D-313: `extract_cover`, JPEG/PNG sniffed, 20 MB, PDF page 1 at 1400 px PNG with a stdlib writer, app writes to the working folder, failure means no cover: as q10.
- D-315: every row of the q12 table, 64 MB / 512 MB / 10,000 spine items, U+FFFD for bad encodings: as q12.
- D-312, D-314, D-316 to D-319: as q9, q11, q13 to q16.

### Findings

- **K1 (fix): "Colin informed" time.** All 16 rows say "Colin informed in the project chat at 2026-11-13 08:10 UTC". The log records this as the chat post's exact created_at since 12 Nov evening (D-280: "2026-11-13T07:27:05Z"). The decision post cmsg_…DdoUg8e3d2VvNgurGWWYJk has created_at **2026-11-13T08:10:59Z** (checked with read_messages_by_id). Fix: write "Colin informed in the project chat at 2026-11-13T08:10:59Z" in all 16 rows.

No other findings. KB PR #40 merges once K1 is fixed and #38 and #39 have landed and #40 has merged main in numeric order.

## Round 2 (13 Nov 2026, ~13:25 UTC)

Author's fix 34435da (new commit, no force-push): K1 fixed. All 16 rows and the PR body now say "Colin informed in the project chat at 2026-11-13T08:10:59Z"; with that phrase normalised, the log is byte-identical to fe4f64f. Approved. Waiting for KB #38 and #39 to merge; then #40 merges main keeping D-319…D-304 above D-287, and merges after a format re-check.

## Round 3 (13 Nov 2026, ~13:45 UTC)

New head 9a5e3bc adds one sentence at the end of the D-316 decision cell, nothing else (diff against 34435da: one line, one added sentence): "Note (coordinator, 13 Nov 13:38 UTC): the nightly command-line test (#73 PR 3, D-224) converts the corpus EPUB cut inside the test to three spine documents (title page, imprint, epilogue) ... accepted because the cut book still has an outline, pictures and the cover, which the test asserts." Matches the coordinator's instruction to the author thread at 13:38:27Z word for word in substance. Row still has six columns; log still strictly descending. Approved at 9a5e3bc.
Observation (no change asked): the note carries no "Colin informed" time; if the coordinator counts this as a decision for Colin, a chat line is still owed.

## Round 4 (13 Nov 2026, ~13:55 UTC)

New head 7d9fbf4 adds one sentence at the end of the D-315 decision cell, nothing else (diff against 9a5e3bc: one line): "Note (coordinator, 13 Nov 13:52 UTC): review of sci2audio PR #148 (finding M4) added one more limit, `MAX_TAGS = 200` tags per element with its ancestors' tags included (more are left out), because many `epub:type` or `role` tokens copied into every descendant used 1.56 GB for a 230 KB chapter; it sits beside the 100 nested elements that add tags." Matches the coordinator's instruction to the author thread at 13:52:57Z; consistent with D-307's 100-element cap, which it does not replace. Row has six columns. Approved at 7d9fbf4. Merge after KB #38 and #39 land and #40 has merged main.

## Merge (13 Nov 2026, ~15:12 UTC)

After KB #38 (bc25d60), #41 (D-320, 8d647f8) and #39 (da0ce8d) landed, I merged main into the branch (merge commit 78bed64, no force-push): D-320, then D-319…D-304, then D-287…D-281, D-280… Checked: 304 rows, strictly descending, no duplicates, six columns in every row, every line of main and of 7d9fbf4 kept, diff against main exactly the 16 new rows. Squash-merged pinned to 78bed64: main dc505cf. No closing keyword in the KB PR. (sci2audio PR #148 had already merged at 14:11:55Z as 586094f, and Issue #73 closed with it at 14:11:56Z, before this KB merge.)
