# Review of KB PR #46, round 4 (D-377)

Head reviewed: `dfa131e`. It adds one commit on top of `ab28a15`, which was checked after main was merged in. The commit adds one row and changes nothing else.

- **D-377 matches its sources.** sci2audio Issue #174 is open with milestone v1.1, and #158 is open with milestone v1.1. The measured figures are copied correctly from the #174 body: about 2 KB per Markdown paragraph; 400,000 paragraphs in 1.2 MB, 28 s, 0.82 GB; about 440 bytes per text line; about 14 GB for text and 45 GB for Markdown; 1 MB read in under a second. The 0.03 s for the corpus EPUB is copied correctly from #158.
- **The byte caps match the code on main.** In `extraction/epub.py`, `MAX_MEMBER` is 64 MB and `MAX_TOTAL` is 512 MB (D-315). In `web/config.py`, `UPLOAD_LIMIT` is 200 MB and `TEXT_LIMIT` is 5 MB (D-198). The text and Markdown limit is 64 MB (D-351). The author was right to leave out the handoff's "20 MB": that is `MAX_COVER`, which caps cover images, not input files. The coordinator's chat post has since been corrected to the same caps.
- **Status:** "Decided (Claude)" is correct, because this is the coordinator's own decision. The time Colin was told is 2026-11-13 15:31:59 UTC, the creation time of the chat post.
- **Form:** the row sits above D-376, has 6 cells and no raw `|`, and D-377 was the next free number. The PR title and body cover D-377, and there is still no closing keyword before a link.

**Approved at dfa131e.** It merges after KB PR #45 has merged, main has been merged into this branch, and a final check passes.
