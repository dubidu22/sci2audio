# Review of KB PR #46, round 5 (D-378)

Head reviewed: `245a161`. It adds one commit on top of `dfa131e`, which was approved in round 4. The commit adds one row and changes nothing else.

- **D-378 matches the coordinator's decision post** (project chat, 2026-11-13 15:34:45 UTC). For v1.0, CI and the release are pinned to a uv-managed current CPython patch level, and that minimum is stated in the install docs and the release checklist. The reader handling these cases itself goes to v1.1 under #175. The row names no exact version, and neither does the post.
- **The facts match the body of #175.** The issue is open with milestone v1.1. The `HTMLParser` under `extraction/markup.py` is used by EPUB since #148 and by Markdown from #169. The parser changed in security releases from 3.12.11 on, with backports in distribution builds. macOS CI runs 3.12.10 and Linux CI 3.12.16, and macOS CI failed on the unclosed-comment test. The issue lists eight cases, and well-formed files (every corpus sample and golden file) read the same.
- **Status:** "Decided (Claude)" is correct, because this is the coordinator's own decision. The time Colin was told matches the post's creation time. The record links D-304 and D-340, which are the right related rows.
- **Form:** the row sits above D-377, has 6 cells and no raw `|`, and D-378 was the next free number. The PR title and body cover D-378, and there is still no closing keyword before a link.

**Noted only (no change needed):** the bracket after "eight such cases" lists them in short and leaves out two: `<a href` at the end of a file (an unclosed tag) and `<!--->`. It doesn't claim to be complete, and the issue linked in the same row has the full table.

**Approved at 245a161.** It merges after KB PR #45 has merged, main has been merged into this branch, and a final check passes.
