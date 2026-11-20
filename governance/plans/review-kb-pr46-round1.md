# Review of KB PR #46 (daily decision log, 13 Nov 2026), round 1

Head reviewed: `62e353a`. One file, `docs/kb/00-index/decision-log.md`, +42 / −2.

## Checked and correct

- **D-337 to D-352** match `issue74-text-input-plan.md` §2–§6 and the §8/§9 tables, q1 to q16 in order, every recommendation, alternative and measured fact (maxNesting 20/100/1000, 0.77 s, 64 MB, the q11 table).
- **D-353 to D-363** match `issue120-remove-document-plan.md` §3 questions 1 to 11 and the §7 table.
- **D-364 to D-372** match `issue12-zap-plan.md` §3 Q1 to Q9, with the §2 docs lines (release checklist, `THIRD_PARTY_LICENSES.md`, "run it yourself" note) placed in D-370 and D-371.
- **Colin-informed times** match the chat posts: 14:48:34 (D-337–352), 14:50:18 (D-353–363), 14:52:37 (D-364–372), 14:53:28 (D-373–375). Colin's approval "all 3 suggestions approved" is at 14:53:09, quoted exactly.
- **Numbers and order:** no duplicate IDs in the file, D-rows strictly newest first, F-25 placed above F-24 as the F-11+ block is ordered. No D- or F-number clashes with queued KB PRs #38, #39, #40, #42, #43, #44, #45 (they add D-176–191, D-281–336 and status notes; none touch D-21, D-260 or F-25).
- **Table form:** every new D-row has 6 cells, F-25 has 4; no raw `|` inside a cell.
- **Status notes** on D-260 ("carried out by D-353 to D-363") and D-21 ("the concurrency limit revised by D-375") are correct and reciprocal with D-375's "Revises the max 4 concurrent of D-21".
- **PR body:** attribution lines present; no "fixes:" or other closing keyword before any link.

## Must fix

**M1. D-373, D-374, D-375: wrong status value.** They read "**Decided (Claude), approved by Colin**". The log's own legend says **Decided** = "Colin stated or approved it", and **Decided (Claude)** = "a decision Claude made itself". Colin approved these three, so they are **Decided**. The same case has a precedent: D-78 (a coordinator proposal Colin answered "yes") reads "**Decided** (Colin, 12 Nov: "yes" to the coordinator's proposal in the project chat)". Suggested status cell:
`**Decided** (Colin, 13 Nov 14:53 UTC: "all 3 suggestions approved", answering the coordinator's three proposals in the project chat at 14:52 UTC; Colin informed in the project chat at 2026-11-13 14:53:28 UTC)`. Change the PR body's D-373–375 bullet to match.

**M2. D-373, D-374, D-375 and F-25: wrong proposal time.** They say the coordinator proposed the rules "at 14:51 UTC". In the project chat, 14:51:15 is Colin's question ("do you suggest any workflow change that neey my approval?"); the coordinator's three proposals were posted at **14:52:31 UTC**. Change "14:51 UTC" to "14:52 UTC" in all four rows. (The 14:51 came from the coordinator's handoff note, not from the chat.)

**M3. D-373 contradicts itself and D-68.** It says the day's PR is "written, reviewed and merged by **one KB thread**", and two sentences later "a separate review thread (D-68) merges it". What Colin approved (coordinator, 14:52:31) was "one KB PR per day that collects all decisions since the last one, reviewed and merged in one thread", and D-68 keeps author and reviewer apart. Suggested wording: "**All decision-log entries of a day go into one KB PR, written by one KB thread and reviewed and merged in one review thread** (D-68); implementation threads do not open their own KB PRs." Keep the rest of the row. Update the PR body's wording to match if it repeats the phrase.

## Not changed (noted only)

- D-375 names the lanes "extraction, layout, app/release"; the proposal said "extraction, layout, release". The row follows the project instructions' wording, which is clearer. No change needed.
