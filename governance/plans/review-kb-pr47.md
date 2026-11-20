# Review: KB PR #47 (dubidu22/sci2audio-design), second batch of 13 Nov 2026

Head reviewed: dbda349 (branch kb/2026-11-13-daily-2, base main c8494bf, main unchanged since). Reviewer thread: "Review second KB decision batch". Result: approved, no required fixes.

## Checks

| Check | Result |
|---|---|
| Numbering | 52 new rows D-384 to D-435, no gaps or duplicates; continuous with D-383 on main. Whole D-table strictly descending (D-01 to D-09 are zero-padded, unchanged). No row removed. |
| Table shape | Every D-row has 6 cells. |
| Status markers | All 52 new rows are **Decided (Claude)** under D-80. None is a rule Colin approved himself, so none should be plain Decided. |
| Colin informed times | All 11 post times checked against the posts' created_at: 17:56:02 (D-384), 17:58:38 (D-385–391), 18:08:31 (D-392), 19:33:34 (D-393–404), 20:00:23 (D-405–418), 20:22:28 (D-420–428), 20:26:00 (D-419), 20:32:50 (D-429–430), 20:46:13 (D-431), 20:51:29 (D-432–433), 21:01:01 (D-434–435). All match. |
| Merge hashes | Checked against sci2audio main: #167 d79eb25, #169 5d8fd2f, #179 3a55407, #180 5aad4ae, #182 b83418f, #183 b8e1e3f, #188 255ce4a, #192 f5ec33f, #197 14513b2. All match. |
| "fixes:" before a PR link | None in the PR body or the added rows. "Closes #75" in D-418 is quoted file text in code format, not a keyword in a PR body. |
| D-419 | Wording matches the amended cut-short rule as relayed (20:26:08): rule (a) object data after the last %%EOF, rule (b) no %%EOF and xref rebuilt or unreadable, the check order, the trade-off. D-395 carries "amended by D-419". |
| D-429 | Says "Refines D-411"; D-411 carries "refined by D-429". |
| D-433 / D-431 | D-433 amends D-431; D-431 carries "amended by D-433". |
| Status notes on older rows | D-84, D-143, D-144, D-148, D-374, D-377 notes are accurate. Record cells of D-337–352, D-378, D-380–383 cite the right merged PRs. |
| Scope | No merge records for #194, #198 or #196 (they go to tomorrow's batch). D-434/435 rightly name no PR yet. |

## Nit (not required)

- The PR body's "Status notes on existing rows" line does not list the back-notes on D-395, D-411 and D-431 (the log itself has them). The squash commit message is written by the reviewer, so this does not reach main.
