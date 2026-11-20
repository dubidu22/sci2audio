# Review: sci2audio-design PR #35 (D-244 to D-261, #77 browser main flow)

Reviewer thread: "Review KB PR 35 main flow decisions", 13 Nov 2026. PR head 7215439; code PR #121 head 5ab8246.

## Round 1 (13 Nov 2026, ~07:25 UTC)

### Format: all pass
- 18 rows D-261 down to D-244, directly above D-226; the whole log is strictly descending, no duplicate IDs, 228 rows (gaps only D-176–191 and D-227–243, both in other open PRs).
- Every row has exactly six columns (no unescaped pipe).
- All 18 rows are **Decided (Claude)** (coordinator, 13 Nov 06:46 UTC, under D-80; plan approved as written; Colin informed 2026-11-13T06:46:15Z). The chat post cmsg_…PKkG1Ypn7996eF3RFFHpHN has created_at 2026-11-13T06:46:15Z (checked with read_messages_by_id).
- main d87cede is the parent of the PR head; mergeable_state clean. No closing keyword anywhere in the PR body; code PR #121 is a plain link.
- The four status cross-references (D-133, D-166, D-204, D-209) only append to the status cell; the rest of each row is byte-identical.

### Against plan section 9 (q1–q18) and the chat post: all match
q1 = D-244 … q18 = D-261 in order; each row gives the decision, question, alternative and reason as the plan and the chat line say. Where a row goes beyond or differs from the plan's wording, I checked it against PR #121:
- D-249 sentence default is #18's `voices.PREVIEW_TEXT`, limit 300 (`PREVIEW_LIMIT = 300`, models.py:12), file `<work_root>/preview/preview.wav` (tasks.py:58–59), 409 `voice-missing` (api.py:572). Matches.
- D-250 failure drops the engine, cancel and OutputExists keep it (tasks.py:134–147). Matches.
- D-253 "measuring the speed" (en.toml:182), 30 s throttle (app.js:5). Matches.
- D-255 `?download=true` (the plan said `download=1`; the code takes a bool and the templates send `true`), `voice-failed`, `disk-full`. Matches the code.
- D-256 test for missing and unused keys exists (test_web_pages.py:258). Matches.
- D-257 axe tags wcag2a/2aa/21a/21aa/22aa with every impact, best-practice only serious/critical, light and dark (conftest.py:169–192); keyboard test asserts outline ≥ 2 px and no stuck Tab (test_keyboard.py:45–50). Matches.
- D-258 has an alternative ("axe-core from a CDN") the plan's q15 did not list; it is a fair statement of what was rejected and fits the no-network rule. No change needed.
- D-259 nightly Chromium/Firefox/WebKit on Linux plus WebKit on macOS, nightly property job and mutmut skip `browser` (nightly.yml:57–70, pyproject.toml:126). Matches.
- D-246 settings PUT when the audiobook starts (app.js:228–239), page text in en.toml:122. Matches.
- D-261 paste box shown only when `.txt` is readable (pages.py:124). Matches.

### Findings

- **F1 (must fix): D-252 says "the plan has 30 rows".** `download_plan()` on PR #121 has **31** files (config.json, the weights, 28 English voices, the spaCy model), counted by running the code. The plan's own "60+" was wrong too; the row should say 31 (or "about 30", which stays true if voices change). Fix: change "the plan has 30 rows" to "the plan has 31 rows".
- **S1 (should fix): D-204's added status "replaced by D-244"** covers only the pages half of D-204. Its other half (Playwright and axe-core arrive with #77) is fulfilled by D-258 and D-259, not replaced. Suggested status: "**pages replaced by D-244; Playwright and axe-core: D-258, D-259** (13 Nov, #77)".

Note for the code review of PR #121, not the KB: none.

KB PR #35 merges once F1 is fixed (and S1 fixed or answered), and after merging main if KB PR #34 lands first (numeric order D-261…D-244, D-243…D-227, D-226).

## Round 2 (13 Nov 2026, ~07:17 UTC)

Author's fix b6ef820 changes exactly two status/decision cells:
- F1 fixed: D-252 now reads "the plan has 31 files: the model's configuration and weights, 28 voices and the spaCy model" (31 matches `download_plan()`).
- S1 fixed: D-204's status now reads "pages replaced by D-244; Playwright and axe-core: D-258, D-259 (13 Nov, #77)".
Log still strictly descending, 228 rows, six columns each; mergeable_state clean; KB PR #34 still open, so #35 merges first. Approved and merged (squash).
